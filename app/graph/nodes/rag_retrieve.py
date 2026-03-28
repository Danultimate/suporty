"""
rag_retrieve node — semantic search over technical docs via pgvector.
Uses the sanitized text so PII never enters the embedding pipeline.
"""

import logging
from app.state import SupportState
from app.db.pgvector import similarity_search
from app.config import settings

logger = logging.getLogger(__name__)


async def rag_retrieve(state: SupportState) -> SupportState:
    query = state.get("sanitized_text") or state.get("raw_text", "")
    ticket_id = state.get("ticket_id", "unknown")

    if not query:
        logger.warning("rag_retrieve: empty query for ticket %s", ticket_id)
        return {**state, "rag_chunks": []}

    chunks = await similarity_search(query=query, top_k=settings.RAG_TOP_K)

    logger.info(
        "rag_retrieve: ticket=%s retrieved %d chunks",
        ticket_id,
        len(chunks),
    )

    return {**state, "rag_chunks": chunks}
