"""
escalate node — routes ticket to the human support queue.
In production this would push to a queue (SQS, Redis, etc.) or call a ticketing API.
"""

import logging
from datetime import datetime, timezone
from app.state import SupportState
from app.tools.freshdesk import post_escalation

logger = logging.getLogger(__name__)


async def escalate(state: SupportState) -> SupportState:
    ticket_id = state.get("ticket_id", "unknown")
    reason = state.get("escalation_reason", "Automatic escalation")
    urgency = state.get("urgency", "medium")

    payload = {
        "ticket_id": ticket_id,
        "user_id": state.get("user_id"),
        "intent": state.get("intent"),
        "urgency": urgency,
        "reason": reason,
        "confidence": state.get("confidence", 0.0),
        "resolution_draft": state.get("resolution"),
        "escalated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.warning("ESCALATE: ticket=%s urgency=%s reason=%s", ticket_id, urgency, reason)

    # Post back to Freshdesk if this ticket originated there
    fd_id = state.get("freshdesk_ticket_id")
    if fd_id:
        try:
            await post_escalation(
                ticket_id=fd_id,
                reason=reason,
                urgency=urgency,
                draft=state.get("resolution"),
            )
        except Exception as exc:
            logger.error("freshdesk: escalation post failed for ticket %s: %s", fd_id, exc)

    return {
        **state,
        "metadata": {
            **(state.get("metadata") or {}),
            "escalation": payload,
        },
    }
