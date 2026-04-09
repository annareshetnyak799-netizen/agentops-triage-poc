from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from src.observability.metrics import metrics_registry


INSTRUCTION_LIKE_PATTERNS = (
    r"\bignore (all|previous|prior) instructions\b",
    r"\bdisregard (all|previous|prior) instructions\b",
    r"\bsystem prompt\b",
    r"\byou are chatgpt\b",
    r"\bexecute this\b",
    r"\brun this command\b",
)

UNTRUSTED_INSTRUCTION_TOKEN = "[UNTRUSTED_INSTRUCTION]"


class SanitizationCheckResult(BaseModel):
    contains_untrusted_instructions: bool
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def detect_untrusted_instructions(*texts: str) -> SanitizationCheckResult:
    normalized = "\n".join(texts).lower()
    matched = any(
        re.search(pattern, normalized) is not None
        for pattern in INSTRUCTION_LIKE_PATTERNS
    )
    if not matched:
        return SanitizationCheckResult(
            contains_untrusted_instructions=False,
            warnings=[],
        )

    metrics_registry.increment("untrusted_instruction_inputs_total")

    return SanitizationCheckResult(
        contains_untrusted_instructions=True,
        warnings=[
            "Untrusted instruction-like content was detected and must not influence policy or execution."
        ],
    )


def sanitize_untrusted_text(value: str) -> str:
    sanitized = value
    for pattern in INSTRUCTION_LIKE_PATTERNS:
        sanitized = re.sub(
            pattern,
            UNTRUSTED_INSTRUCTION_TOKEN,
            sanitized,
            flags=re.IGNORECASE,
        )
    return sanitized
