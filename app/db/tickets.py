"""
Ticket persistence — stores every processed ticket for the dashboard.
"""

from datetime import datetime, timezone
from typing import Optional
from app.db.pgvector import get_pool


async def ensure_tickets_schema() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id              BIGSERIAL PRIMARY KEY,
                ticket_id       TEXT UNIQUE NOT NULL,
                user_id         TEXT,
                raw_text        TEXT,
                intent          TEXT,
                urgency         TEXT,
                confidence      FLOAT,
                status          TEXT,
                resolution      TEXT,
                escalation_reason TEXT,
                sensitive       BOOLEAN DEFAULT FALSE,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                processed_at    TIMESTAMPTZ
            );
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets (status);"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS tickets_created_at_idx ON tickets (created_at DESC);"
        )


async def save_ticket(
    ticket_id: str,
    user_id: str,
    raw_text: str,
    intent: Optional[str],
    urgency: Optional[str],
    confidence: float,
    status: str,
    resolution: Optional[str],
    escalation_reason: Optional[str],
    sensitive: bool,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tickets (
                ticket_id, user_id, raw_text, intent, urgency,
                confidence, status, resolution, escalation_reason,
                sensitive, processed_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (ticket_id) DO UPDATE SET
                intent            = EXCLUDED.intent,
                urgency           = EXCLUDED.urgency,
                confidence        = EXCLUDED.confidence,
                status            = EXCLUDED.status,
                resolution        = EXCLUDED.resolution,
                escalation_reason = EXCLUDED.escalation_reason,
                sensitive         = EXCLUDED.sensitive,
                processed_at      = EXCLUDED.processed_at;
            """,
            ticket_id, user_id, raw_text, intent, urgency,
            confidence, status, resolution, escalation_reason,
            sensitive, datetime.now(timezone.utc),
        )
