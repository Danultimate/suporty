"""
escalate node — routes ticket to the human support queue.
In production this would push to a queue (SQS, Redis, etc.) or call a ticketing API.
"""

import logging
from datetime import datetime, timezone
from app.state import SupportState

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
        "resolution_draft": state.get("resolution"),  # attach draft if any
        "escalated_at": datetime.now(timezone.utc).isoformat(),
    }

    # TODO: replace with real queue / ticketing integration
    # e.g.: await sqs_client.send_message(QueueUrl=..., MessageBody=json.dumps(payload))
    logger.warning("ESCALATE: ticket=%s urgency=%s reason=%s", ticket_id, urgency, reason)

    return {
        **state,
        "metadata": {
            **(state.get("metadata") or {}),
            "escalation": payload,
        },
    }
