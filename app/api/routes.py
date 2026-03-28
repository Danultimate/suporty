"""
FastAPI route layer.

POST /webhook/ticket        — synchronous ingestion (response when done)
POST /webhook/ticket/async  — fire-and-forget with optional callback_url
GET  /health                — liveness probe
GET  /readiness             — readiness probe (checks DB)
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, AnyHttpUrl
from typing import Optional
from app.graph.graph import support_graph
from app.api.background import process_ticket_async
from app.db.pgvector import get_pool
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TicketPayload(BaseModel):
    ticket_id: Optional[str] = Field(default=None, description="Idempotency key; generated if omitted")
    user_id: str = Field(..., description="CRM user identifier")
    raw_text: str = Field(..., min_length=1, max_length=10_000)
    metadata: Optional[dict] = None


class AsyncTicketPayload(TicketPayload):
    callback_url: Optional[AnyHttpUrl] = Field(
        default=None,
        description="If set, result is POSTed here when processing completes",
    )


class TicketResponse(BaseModel):
    ticket_id: str
    status: str            # "resolved" | "escalated" | "accepted"
    intent: Optional[str]
    urgency: Optional[str]
    confidence: float
    resolution: Optional[str]
    escalation_reason: Optional[str]


def _build_initial_state(payload: TicketPayload) -> dict:
    return {
        "ticket_id": payload.ticket_id or str(uuid.uuid4()),
        "user_id": payload.user_id,
        "raw_text": payload.raw_text,
        "metadata": payload.metadata or {},
        "identity_verified": False,
        "sensitive": False,
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# Synchronous webhook (waits for graph completion)
# ---------------------------------------------------------------------------

@router.post("/webhook/ticket", response_model=TicketResponse, status_code=200)
async def ingest_ticket(payload: TicketPayload):
    """Runs the full LangGraph pipeline and returns the result inline."""
    initial_state = _build_initial_state(payload)
    ticket_id = initial_state["ticket_id"]

    try:
        final_state = await support_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Graph execution failed for ticket %s", ticket_id)
        raise HTTPException(status_code=500, detail="Internal processing error")

    escalated = bool(final_state.get("escalation_reason"))
    return TicketResponse(
        ticket_id=ticket_id,
        status="escalated" if escalated else "resolved",
        intent=final_state.get("intent"),
        urgency=final_state.get("urgency"),
        confidence=final_state.get("confidence", 0.0),
        resolution=final_state.get("resolution"),
        escalation_reason=final_state.get("escalation_reason"),
    )


# ---------------------------------------------------------------------------
# Async / fire-and-forget webhook
# ---------------------------------------------------------------------------

@router.post("/webhook/ticket/async", response_model=TicketResponse, status_code=202)
async def ingest_ticket_async(payload: AsyncTicketPayload, background_tasks: BackgroundTasks):
    """
    Accepts the ticket immediately (202) and processes it in the background.
    If callback_url is provided, POSTs the result there when done.
    """
    initial_state = _build_initial_state(payload)
    ticket_id = initial_state["ticket_id"]

    callback = str(payload.callback_url) if payload.callback_url else None
    background_tasks.add_task(process_ticket_async, initial_state, callback)

    return TicketResponse(
        ticket_id=ticket_id,
        status="accepted",
        intent=None,
        urgency=None,
        confidence=0.0,
        resolution=None,
        escalation_reason=None,
    )


# ---------------------------------------------------------------------------
# Health probes
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/readiness")
async def readiness():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database not ready")
