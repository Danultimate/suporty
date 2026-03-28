"""
resolve node — generates a resolution or a draft reply.

Routing:
  sensitive == True  →  local Ollama
  sensitive == False →  GPT-4o
"""

import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.state import SupportState
from app.llm.router import get_llm
from app.tools.freshdesk import post_resolution
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior enterprise support engineer. Given a support ticket, account context, and relevant documentation chunks, produce a resolution.

Return ONLY a JSON object:
{
  "resolution": "<full reply text to send to the customer>",
  "confidence": <float 0.0-1.0>,
  "needs_escalation": <bool>,
  "escalation_reason": "<reason if needs_escalation is true, else null>"
}

Guidelines:
- Be concise, professional, and empathetic.
- If you cannot resolve with high confidence (< 0.75), set needs_escalation=true.
- Reference specific documentation sections when available.
- Never expose internal system details or other customers' data."""


def _build_user_message(state: SupportState) -> str:
    parts = [
        f"**Ticket ID:** {state.get('ticket_id')}",
        f"**Intent:** {state.get('intent')}",
        f"**Urgency:** {state.get('urgency')}",
        "",
        "**Customer Message:**",
        state.get("sanitized_text") or state.get("raw_text", ""),
    ]

    ctx = state.get("context") or {}
    if ctx:
        account = ctx.get("account", {})
        parts += [
            "",
            "**Account Context:**",
            f"- Plan: {account.get('plan', 'unknown')}",
            f"- Billing status: {account.get('billing_status', 'unknown')}",
            f"- Open tickets: {account.get('open_tickets', 0)}",
        ]

    chunks = state.get("rag_chunks") or []
    if chunks:
        parts += ["", "**Relevant Documentation:**"]
        for i, chunk in enumerate(chunks[:3], 1):  # cap at 3 to stay within context
            parts.append(f"[Doc {i}]: {chunk[:500]}")

    return "\n".join(parts)


async def resolve(state: SupportState) -> SupportState:
    ticket_id = state.get("ticket_id", "unknown")
    sensitive = state.get("sensitive", False)

    llm = get_llm(sensitive=sensitive)
    user_msg = _build_user_message(state)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    try:
        response = await llm.ainvoke(messages)
        payload = json.loads(response.content.strip())
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("resolve: LLM error for ticket %s: %s", ticket_id, exc)
        payload = {
            "resolution": "We were unable to generate an automated response. A support engineer will follow up shortly.",
            "confidence": 0.0,
            "needs_escalation": True,
            "escalation_reason": f"LLM error: {exc}",
        }

    confidence = float(payload.get("confidence", 0.0))
    needs_escalation = payload.get("needs_escalation", False) or confidence < settings.ESCALATION_THRESHOLD

    logger.info(
        "resolve: ticket=%s confidence=%.2f needs_escalation=%s",
        ticket_id,
        confidence,
        needs_escalation,
    )

    resolution_text = payload.get("resolution", "")

    update: SupportState = {
        **state,
        "resolution": resolution_text,
        "confidence": confidence,
    }

    if needs_escalation:
        update["escalation_reason"] = payload.get("escalation_reason") or "Confidence below threshold"
    else:
        # Post resolution back to Freshdesk if this ticket came from there
        fd_id = state.get("freshdesk_ticket_id")
        if fd_id:
            try:
                await post_resolution(
                    ticket_id=fd_id,
                    resolution=resolution_text,
                    confidence=confidence,
                )
            except Exception as exc:
                logger.error("freshdesk: resolution post failed for ticket %s: %s", fd_id, exc)

    return update
