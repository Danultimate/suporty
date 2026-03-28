import pytest
from app.middleware.pii_scrubber import scrub, is_sensitive


@pytest.mark.parametrize("raw,pii_value,expected_token", [
    ("Contact me at john@example.com",   "john@example.com",   "[EMAIL_REDACTED]"),
    ("Call 555-867-5309 for support",    "555-867-5309",       "[PHONE_REDACTED]"),
    ("My SSN is 123-45-6789",            "123-45-6789",        "[SSN_REDACTED]"),
    ("Card number: 4111 1111 1111 1111", "4111",               "[CARD_REDACTED]"),
    ("Server IP is 192.168.1.100",       "192.168.1.100",      "[IP_REDACTED]"),
    ("Born on 01/15/1990",               "01/15/1990",         "[DOB_REDACTED]"),
])
def test_scrub_replaces_pii(raw, pii_value, expected_token):
    result = scrub(raw)
    assert expected_token in result
    assert pii_value not in result


def test_scrub_clean_text_unchanged():
    text = "I cannot log in to the dashboard after the latest update."
    assert scrub(text) == text


def test_is_sensitive_with_pii():
    assert is_sensitive("Email me at user@corp.com") is True


def test_is_sensitive_without_pii():
    assert is_sensitive("My account keeps timing out on the API.") is False


def test_scrub_multiple_pii_in_one_string():
    text = "Name: Alice, email: alice@example.com, SSN: 987-65-4321"
    result = scrub(text)
    assert "[EMAIL_REDACTED]" in result
    assert "[SSN_REDACTED]" in result
    assert "alice@example.com" not in result
    assert "987-65-4321" not in result
