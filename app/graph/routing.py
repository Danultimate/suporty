"""
Conditional edge routing functions for the LangGraph StateGraph.
"""

from app.state import SupportState
from app.config import settings


def route_after_verify(state: SupportState) -> str:
    """
    After the verify node:
      - not verified  →  escalate immediately (security boundary)
      - verified       →  fetch_context to enrich ticket
    """
    if not state.get("identity_verified", False):
        return "escalate"
    return "fetch_context"


def route_after_resolution(state: SupportState) -> str:
    """
    After the resolve node:
      - confidence < threshold OR escalation flag set  →  escalate
      - otherwise                                       →  END
    """
    confidence = state.get("confidence", 0.0)
    escalation_reason = state.get("escalation_reason")

    if escalation_reason or confidence < settings.ESCALATION_THRESHOLD:
        return "escalate"
    return "__end__"
