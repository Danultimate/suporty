"""
Freshdesk inbound webhook.

Setup in Freshdesk:
  Admin → Workflows → Automations → New Rule → Webhook action
  Method: POST
  URL:    https://yourdomain.com/api/v1/webhook/freshdesk
  Content-Type: application/json
  Body (custom JSON):
  {
    "freshdesk_ticket_id": "{{ticket.id}}",
    "subject":             "{{ticket.subject}}",
    "description":         "{{ticket.description}}",
    "requester_email":     "{{ticket.contact.email}}",
    "requester_name":      "{{ticket.contact.name}}",
    "priority":            "{{ticket.priority}}",
    "status":              "{{ticket.status}}"
  }
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import uuid
from app.graph.graph import support_graph
from app.db.tickets import save_ticket
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Freshdesk priority int → our urgency string
_PRIORITY_TO_URGENCY = {1: "low", 2: "medium", 3: "high", 4: "critical"}


class FreshdeskPayload(BaseModel):
    freshdesk_ticket_id: int
    subject: Optional[str] = None
    description: Optional[str] = None
    requester_email: Optional[str] = None
    requester_name: Optional[str] = None
    priority: Optional[int] = 2
    status: Optional[int] = 2


@router.post("/webhook/freshdesk", status_code=200)
async def freshdesk_webhook(payload: FreshdeskPayload):
    """
    Receives a ticket event from Freshdesk, runs it through the support graph,
    and posts the result back as a private note on the originating ticket.
    """
    fd_id = payload.freshdesk_ticket_id

    # Compose the ticket text from subject + description
    raw_text = "\n\n".join(filter(None, [payload.subject, payload.description])).strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Ticket has no subject or description")

    ticket_id = f"fd-{fd_id}"
    user_id = payload.requester_email or f"fd-user-{fd_id}"
    urgency = _PRIORITY_TO_URGENCY.get(payload.priority or 2, "medium")

    logger.info(
        "freshdesk: received ticket fd_id=%s subject=%r user=%s",
        fd_id, payload.subject, user_id,
    )

    initial_state = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "raw_text": raw_text,
        "identity_verified": True,   # Freshdesk already authenticated the user
        "sensitive": False,
        "confidence": 0.0,
        "source": "freshdesk",
        "freshdesk_ticket_id": fd_id,
        "metadata": {
            "freshdesk_priority": payload.priority,
            "freshdesk_status": payload.status,
            "requester_name": payload.requester_name,
        },
        # Pre-fill urgency from Freshdesk priority so classify can refine it
        "urgency": urgency,
    }

    try:
        final_state = await support_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("freshdesk: graph failed for fd ticket %s", fd_id)
        raise HTTPException(status_code=500, detail="Processing error")

    escalated = bool(final_state.get("escalation_reason"))
    status = "escalated" if escalated else "resolved"

    try:
        await save_ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            raw_text=raw_text,
            intent=final_state.get("intent"),
            urgency=final_state.get("urgency"),
            confidence=final_state.get("confidence", 0.0),
            status=status,
            resolution=final_state.get("resolution"),
            escalation_reason=final_state.get("escalation_reason"),
            sensitive=final_state.get("sensitive", False),
        )
    except Exception as exc:
        logger.error("freshdesk: failed to persist ticket %s: %s", ticket_id, exc)

    return {
        "ticket_id": ticket_id,
        "freshdesk_ticket_id": fd_id,
        "status": status,
        "intent": final_state.get("intent"),
        "confidence": final_state.get("confidence", 0.0),
    }
