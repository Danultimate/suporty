import pytest
import pytest_asyncio
from app.tools.crm import verify_identity, fetch_account_context


@pytest.mark.asyncio
async def test_verify_returns_verified_for_normal_user():
    result = await verify_identity(user_id="usr123", ticket_id="tkt-001")
    assert result["verified"] is True
    assert "account_id" in result
    assert result["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_verify_returns_unverified_for_id_ending_zero():
    result = await verify_identity(user_id="usr120", ticket_id="tkt-002")
    assert result["verified"] is False


@pytest.mark.asyncio
async def test_fetch_account_context_returns_expected_keys():
    ctx = await fetch_account_context(user_id="usr123")
    for key in ("account_id", "plan", "billing_status", "open_tickets", "recent_interactions"):
        assert key in ctx
