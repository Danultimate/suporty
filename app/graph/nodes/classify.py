"""
classify node — extracts intent, urgency, and sensitive flag from raw_text.

Security boundary: scrubs PII BEFORE any LLM call.
Sensitive tickets are routed to the local Ollama instance.
"""

import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.state import SupportState
from app.middleware.pii_scrubber import scrub, is_sensitive
from app.llm.router import get_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a support ticket classifier. Analyze the support message and return ONLY a JSON object with:
{
  "intent": "<one of: billing | technical | account | onboarding | feature_request | complaint | other>",
  "urgency": "<one of: low | medium | high | critical>",
  "confidence": <float 0.0-1.0>,
  "summary": "<one sentence summary of the request>"
}

Rules:
- critical: service is completely down or data loss
- high: severe degradation, unable to complete core tasks
- medium: degraded experience, workaround exists
- low: question, feature request, or cosmetic issue
Return ONLY valid JSON. No markdown, no extra text."""


async def classify(state: SupportState) -> SupportState:
    raw = state.get("raw_text", "")
    if not raw:
        logger.warning("classify: empty raw_text for ticket %s", state.get("ticket_id"))
        return {
            **state,
            "intent": "other",
            "urgency": "low",
            "confidence": 0.0,
            "sanitized_text": "",
            "sensitive": False,
        }

    # --- Security boundary: scrub PII before any LLM call ---
    sanitized = scrub(raw)
    sensitive = is_sensitive(raw)

    llm = get_llm(sensitive=sensitive)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=sanitized),
    ]

    try:
        response = await llm.ainvoke(messages)
        payload = json.loads(response.content.strip())
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("classify: LLM parse error for ticket %s: %s", state.get("ticket_id"), exc)
        payload = {"intent": "other", "urgency": "medium", "confidence": 0.5, "summary": ""}

    logger.info(
        "classify: ticket=%s intent=%s urgency=%s confidence=%.2f sensitive=%s",
        state.get("ticket_id"),
        payload.get("intent"),
        payload.get("urgency"),
        payload.get("confidence", 0.0),
        sensitive,
    )

    return {
        **state,
        "sanitized_text": sanitized,
        "sensitive": sensitive,
        "intent": payload.get("intent", "other"),
        "urgency": payload.get("urgency", "medium"),
        "confidence": float(payload.get("confidence", 0.5)),
        "metadata": {
            **(state.get("metadata") or {}),
            "classify_summary": payload.get("summary", ""),
        },
    }
