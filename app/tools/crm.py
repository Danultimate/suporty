"""
CRM Tool — async stub.

In production replace the HTTP call with your actual CRM SDK or API.
The stub simulates a 200ms round-trip and returns a mock account record.
"""

import asyncio
from typing import Optional
import httpx
from app.config import settings


async def verify_identity(user_id: str, ticket_id: str) -> dict:
    """
    Verify a user against the CRM.

    Returns:
        {
            "verified": bool,
            "account_id": str | None,
            "plan": str | None,       # e.g. "enterprise" | "pro" | "free"
            "account_status": str,    # "active" | "suspended" | "churned"
            "reason": str             # human-readable result
        }
    """
    if settings.CRM_API_URL and settings.CRM_API_KEY:
        return await _real_crm_call(user_id, ticket_id)
    return await _stub_crm_call(user_id)


async def fetch_account_context(user_id: str) -> dict:
    """
    Pull billing history and recent interactions for context injection.

    Returns a dict that will be stored in SupportState.context.
    """
    if settings.CRM_API_URL and settings.CRM_API_KEY:
        return await _real_context_call(user_id)
    return await _stub_context(user_id)


# ---------------------------------------------------------------------------
# Stub implementations (used when CRM_API_KEY is not set)
# ---------------------------------------------------------------------------

async def _stub_crm_call(user_id: str) -> dict:
    await asyncio.sleep(0.05)  # simulate latency
    # Simulate: user IDs ending in "0" are unverified
    verified = not user_id.endswith("0")
    return {
        "verified": verified,
        "account_id": f"ACC-{user_id.upper()}",
        "plan": "enterprise",
        "account_status": "active",
        "reason": "stub verification — replace with real CRM",
    }


async def _stub_context(user_id: str) -> dict:
    await asyncio.sleep(0.05)
    return {
        "account_id": f"ACC-{user_id.upper()}",
        "plan": "enterprise",
        "open_tickets": 2,
        "last_invoice": "2026-02-28",
        "billing_status": "current",
        "recent_interactions": [
            {"date": "2026-03-15", "channel": "email", "topic": "API latency"},
            {"date": "2026-03-20", "channel": "chat", "topic": "rate limits"},
        ],
    }


# ---------------------------------------------------------------------------
# Real CRM call (skeleton — implement when credentials are provided)
# ---------------------------------------------------------------------------

async def _real_crm_call(user_id: str, ticket_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.CRM_API_URL}/v1/verify",
            json={"user_id": user_id, "ticket_id": ticket_id},
            headers={"Authorization": f"Bearer {settings.CRM_API_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "verified": data.get("verified", False),
            "account_id": data.get("account_id"),
            "plan": data.get("plan"),
            "account_status": data.get("status", "unknown"),
            "reason": data.get("reason", ""),
        }


async def _real_context_call(user_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.CRM_API_URL}/v1/accounts/{user_id}/context",
            headers={"Authorization": f"Bearer {settings.CRM_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()
