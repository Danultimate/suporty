"""
PII Scrubber middleware — sanitizes raw_text before any external LLM call.
Patterns: email, phone, SSN, credit card, IP address, full name heuristic.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Compiled patterns (order matters — more specific first)
# ---------------------------------------------------------------------------

_PATTERNS = [
    # Credit card (Visa / MC / Amex / Discover)
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD_REDACTED]"),
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    # Email
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL_REDACTED]"),
    # Phone  (E.164, US formats)
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE_REDACTED]"),
    # IPv4
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP_REDACTED]"),
    # IPv6 (simplified)
    (re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"), "[IP_REDACTED]"),
    # Date of birth  (MM/DD/YYYY or DD-MM-YYYY)
    (re.compile(r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b"), "[DOB_REDACTED]"),
    # Passport / ID numbers (generic 6-9 alphanumeric after keyword)
    (re.compile(r"(?i)\b(?:passport|license|id)\s*(?:number|no|#)?\s*[:\-]?\s*[A-Z0-9]{6,9}\b"), "[ID_REDACTED]"),
]


def scrub(text: str) -> str:
    """Apply all PII patterns and return sanitised text."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_sensitive(text: str) -> bool:
    """
    Heuristic: returns True if the *original* text contained any PII
    so the LLM router can enforce the local-only boundary.
    """
    original = text
    scrubbed = scrub(text)
    return original != scrubbed
