from __future__ import annotations

import re


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_RE = re.compile(r"\b(?:sk|pk|ghp)_[A-Za-z0-9]{10,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    redacted = TOKEN_RE.sub("[REDACTED_TOKEN]", redacted)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    return redacted


def redact_list(values: list[str]) -> list[str]:
    return [redact_text(value) for value in values]
