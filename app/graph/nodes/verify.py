"""
verify node — checks user identity against the CRM.
Sets identity_verified and populates context stub.
"""

import logging
from app.state import SupportState
from app.tools.crm import verify_identity

logger = logging.getLogger(__name__)


async def verify(state: SupportState) -> SupportState:
    user_id = state.get("user_id") or ""
    ticket_id = state.get("ticket_id", "unknown")

    if not user_id:
        logger.warning("verify: no user_id for ticket %s — escalating", ticket_id)
        return {
            **state,
            "identity_verified": False,
            "escalation_reason": "Missing user_id — cannot verify identity",
        }

    result = await verify_identity(user_id=user_id, ticket_id=ticket_id)
    verified = result.get("verified", False)

    logger.info(
        "verify: ticket=%s user=%s verified=%s plan=%s status=%s",
        ticket_id,
        user_id,
        verified,
        result.get("plan"),
        result.get("account_status"),
    )

    update: SupportState = {
        **state,
        "identity_verified": verified,
        "context": {
            **(state.get("context") or {}),
            "crm": result,
        },
    }

    if not verified:
        update["escalation_reason"] = result.get("reason", "Identity verification failed")

    return update
