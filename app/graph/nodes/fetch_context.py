"""
fetch_context node — injects account and billing history from CRM into state.
"""

import logging
from app.state import SupportState
from app.tools.crm import fetch_account_context

logger = logging.getLogger(__name__)


async def fetch_context(state: SupportState) -> SupportState:
    user_id = state.get("user_id") or ""
    ticket_id = state.get("ticket_id", "unknown")

    if not user_id:
        logger.warning("fetch_context: no user_id for ticket %s", ticket_id)
        return state

    account_ctx = await fetch_account_context(user_id=user_id)

    logger.info(
        "fetch_context: ticket=%s plan=%s billing=%s open_tickets=%s",
        ticket_id,
        account_ctx.get("plan"),
        account_ctx.get("billing_status"),
        account_ctx.get("open_tickets"),
    )

    return {
        **state,
        "context": {
            **(state.get("context") or {}),
            "account": account_ctx,
        },
    }
