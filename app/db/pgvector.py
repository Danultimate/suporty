"""
Async PostgreSQL + pgvector client.
Handles connection pool, embedding storage, and similarity search.
"""

from typing import List, Optional
import asyncpg
from langchain_openai import OpenAIEmbeddings
from app.config import settings

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = settings.DATABASE_URL.replace("+asyncpg", "")
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=settings.DATABASE_POOL_SIZE)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def ensure_schema() -> None:
    """Create the pgvector extension and docs table on first run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_chunks (
                id          BIGSERIAL PRIMARY KEY,
                source      TEXT NOT NULL,
                chunk_text  TEXT NOT NULL,
                embedding   vector(1536),
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS doc_chunks_embedding_idx
            ON doc_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
            """
        )


async def similarity_search(query: str, top_k: int = None) -> List[str]:
    """
    Embed the query and return the top-k most similar chunk texts.
    Uses cosine distance (<=>).
    """
    k = top_k or settings.RAG_TOP_K
    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    vector = await embedder.aembed_query(query)
    vector_literal = "[" + ",".join(str(v) for v in vector) + "]"

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_text
            FROM   doc_chunks
            ORDER  BY embedding <=> $1::vector
            LIMIT  $2;
            """,
            vector_literal,
            k,
        )
    return [row["chunk_text"] for row in rows]


async def insert_chunk(source: str, text: str, embedding: List[float]) -> None:
    """Ingest a single pre-embedded chunk (used by the indexing pipeline)."""
    vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO doc_chunks (source, chunk_text, embedding) VALUES ($1, $2, $3::vector);",
            source,
            text,
            vector_literal,
        )
