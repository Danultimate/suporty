"""
Async background ticket processor.

Used for fire-and-forget ingestion: caller provides a callback_url,
we process the graph and POST the result back when done.
"""

import logging
import httpx
from app.state import SupportState
from app.graph.graph import support_graph

logger = logging.getLogger(__name__)


async def process_ticket_async(initial_state: SupportState, callback_url: str | None) -> None:
    """
    Runs the support graph and optionally POSTs the result to callback_url.
    Designed to be called via FastAPI BackgroundTasks.
    """
    ticket_id = initial_state.get("ticket_id", "unknown")
    try:
        final_state = await support_graph.ainvoke(initial_state)
        escalated = bool(final_state.get("escalation_reason"))
        result = {
            "ticket_id": ticket_id,
            "status": "escalated" if escalated else "resolved",
            "intent": final_state.get("intent"),
            "urgency": final_state.get("urgency"),
            "confidence": final_state.get("confidence", 0.0),
            "resolution": final_state.get("resolution"),
            "escalation_reason": final_state.get("escalation_reason"),
        }
    except Exception as exc:
        logger.exception("Background processing failed for ticket %s", ticket_id)
        result = {
            "ticket_id": ticket_id,
            "status": "error",
            "error": str(exc),
        }

    if callback_url:
        await _post_callback(callback_url, result)


async def _post_callback(url: str, payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Callback delivered to %s — status %s", url, resp.status_code)
    except Exception as exc:
        logger.error("Callback delivery failed to %s: %s", url, exc)
