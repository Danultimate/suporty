from typing import TypedDict, Optional, List, Any


class SupportState(TypedDict, total=False):
    ticket_id: str
    raw_text: str
    sanitized_text: str
    intent: Optional[str]
    urgency: Optional[str]           # low | medium | high | critical
    identity_verified: bool
    confidence: float
    context: Optional[dict]          # account/billing history from CRM
    rag_chunks: Optional[List[str]]  # top-k docs from pgvector
    resolution: Optional[str]
    escalation_reason: Optional[str]
    sensitive: bool                  # controls local vs cloud LLM routing
    user_id: Optional[str]
    metadata: Optional[dict]
