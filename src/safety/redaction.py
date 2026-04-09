from __future__ import annotations

import re

from src.observability.metrics import metrics_registry


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_RE = re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[-_][A-Za-z0-9]{10,}\b")

# Matches formatted phone numbers only: +7..., +1-800-..., (999) 123-4567, etc.
# Deliberately excludes bare numeric sequences like "3200 rpm" or "1250 ms".
PHONE_RE = re.compile(
    r"\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{2,4}"  # E.164 / intl
    r"|\(\d{3}\)\s?\d{3}[\s\-]\d{4}"  # (NXX) NXX-XXXX
)


def redact_text(value: str) -> str:
    redacted, email_count = EMAIL_RE.subn("[REDACTED_EMAIL]", value)
    redacted, token_count = TOKEN_RE.subn("[REDACTED_TOKEN]", redacted)
    redacted, phone_count = PHONE_RE.subn("[REDACTED_PHONE]", redacted)
    redactions = email_count + token_count + phone_count
    if redactions > 0:
        metrics_registry.increment("pii_redactions_total", redactions)
    return redacted


def redact_list(values: list[str]) -> list[str]:
    return [redact_text(value) for value in values]
