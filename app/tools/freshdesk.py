"""
Freshdesk API client.

Auth: Basic auth — API key as username, "X" as password.
Docs: https://developers.freshdesk.com/api/
"""

import base64
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Freshdesk status codes
STATUS_OPEN      = 2
STATUS_PENDING   = 3
STATUS_RESOLVED  = 4
STATUS_CLOSED    = 5

# Freshdesk priority codes
PRIORITY_MAP = {
    "low":      1,
    "medium":   2,
    "high":     3,
    "critical": 4,
}


def _headers() -> dict:
    token = base64.b64encode(f"{settings.FRESHDESK_API_KEY}:X".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _base() -> str:
    domain = settings.FRESHDESK_DOMAIN.rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/api/v2"


def _enabled() -> bool:
    return bool(settings.FRESHDESK_DOMAIN and settings.FRESHDESK_API_KEY)


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_ticket(ticket_id: int) -> dict:
    if not _enabled():
        return {}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_base()}/tickets/{ticket_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ── Write ─────────────────────────────────────────────────────────────────────

async def post_note(ticket_id: int, body: str, private: bool = True) -> None:
    """Add a note to a Freshdesk ticket."""
    if not _enabled():
        logger.debug("Freshdesk not configured — skipping note for ticket %s", ticket_id)
        return
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_base()}/tickets/{ticket_id}/notes",
            headers=_headers(),
            json={"body": body, "private": private},
        )
        resp.raise_for_status()
        logger.info("freshdesk: posted note on ticket %s (private=%s)", ticket_id, private)


async def update_ticket(ticket_id: int, **fields) -> None:
    """Update arbitrary fields on a Freshdesk ticket (status, priority, tags…)."""
    if not _enabled():
        return
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.put(
            f"{_base()}/tickets/{ticket_id}",
            headers=_headers(),
            json=fields,
        )
        resp.raise_for_status()
        logger.info("freshdesk: updated ticket %s — %s", ticket_id, fields)


# ── High-level helpers ────────────────────────────────────────────────────────

async def post_resolution(ticket_id: int, resolution: str, confidence: float) -> None:
    """Post the AI-generated resolution as a private note and mark ticket resolved."""
    note = (
        f"<b>AI Resolution</b> (confidence: {confidence:.0%})<br><br>"
        f"{resolution.replace(chr(10), '<br>')}"
    )
    await post_note(ticket_id, note, private=True)
    await update_ticket(ticket_id, status=STATUS_RESOLVED)


async def post_escalation(ticket_id: int, reason: str, urgency: str, draft: str = None) -> None:
    """Post escalation note and bump priority; leave ticket open for a human."""
    body = f"<b>AI Escalation</b><br><br><b>Reason:</b> {reason}"
    if draft:
        body += f"<br><br><b>Draft response:</b><br>{draft.replace(chr(10), '<br>')}"
    await post_note(ticket_id, body, private=True)
    priority = PRIORITY_MAP.get(urgency, 2)
    await update_ticket(ticket_id, priority=priority, status=STATUS_OPEN)
