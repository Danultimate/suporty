"""
Integration-style tests for the API layer using httpx + TestClient.
LLM calls are mocked so no real OpenAI / Ollama is needed.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Patch LLM before importing the app
_mock_classify_response = '{"intent": "technical", "urgency": "high", "confidence": 0.88, "summary": "API latency issue"}'
_mock_resolve_response = '{"resolution": "Please try clearing your cache.", "confidence": 0.88, "needs_escalation": false, "escalation_reason": null}'


@pytest.fixture()
def client():
    with (
        patch("app.graph.nodes.classify.get_llm") as mock_classify_llm,
        patch("app.graph.nodes.resolve.get_llm") as mock_resolve_llm,
        patch("app.db.pgvector.get_pool", new_callable=AsyncMock),
        patch("app.db.pgvector.ensure_schema", new_callable=AsyncMock),
        patch("app.db.pgvector.similarity_search", new_callable=AsyncMock, return_value=["Doc chunk 1", "Doc chunk 2"]),
    ):
        mock_classify_llm.return_value.ainvoke = AsyncMock(
            return_value=type("R", (), {"content": _mock_classify_response})()
        )
        mock_resolve_llm.return_value.ainvoke = AsyncMock(
            return_value=type("R", (), {"content": _mock_resolve_response})()
        )

        from app.main import app
        with TestClient(app) as c:
            yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingest_ticket_resolved(client):
    r = client.post("/api/v1/webhook/ticket", json={
        "user_id": "usr123",
        "raw_text": "The API keeps returning 504 errors after your latest deploy.",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert body["intent"] == "technical"
    assert body["confidence"] == pytest.approx(0.88)
    assert body["ticket_id"] is not None


def test_ingest_ticket_escalated_unverified_user(client):
    # user_id ending in "0" → CRM stub returns verified=False → escalate
    r = client.post("/api/v1/webhook/ticket", json={
        "user_id": "usr120",
        "raw_text": "I need to reset my enterprise license key.",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "escalated"
    assert body["escalation_reason"] is not None


def test_async_endpoint_returns_202(client):
    r = client.post("/api/v1/webhook/ticket/async", json={
        "user_id": "usr123",
        "raw_text": "Billing discrepancy on invoice #INV-2026-042.",
        "callback_url": "https://example.com/callback",
    })
    assert r.status_code == 202
    assert r.json()["status"] == "accepted"


def test_missing_user_id_returns_422(client):
    r = client.post("/api/v1/webhook/ticket", json={"raw_text": "Help!"})
    assert r.status_code == 422


def test_empty_raw_text_returns_422(client):
    r = client.post("/api/v1/webhook/ticket", json={"user_id": "usr1", "raw_text": ""})
    assert r.status_code == 422
