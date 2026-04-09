from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.config import settings
from src.domain.schemas import SessionView
from src.safety.redaction import redact_text
from src.safety.sanitization import sanitize_untrusted_text


class RollingSummary(BaseModel):
    """Compact memory of what the session has established so far (STATE_MEMORY.md §3)."""

    what_we_know: list[str] = Field(default_factory=list)
    what_we_tried: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SessionContext(BaseModel):
    incident_title: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    observations: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    rolling_summary: RollingSummary = Field(default_factory=RollingSummary)

    model_config = ConfigDict(extra="forbid")


def build_session_context(session: SessionView) -> SessionContext:
    """Assemble context for LLM analysis.

    Applies G9 (context truncation) and G15 (rolling summary) from CLAUDE.md.
    All text is sanitized and PII-redacted before inclusion.
    G20: observations are the single source of truth — known_facts duplication removed.
    """
    refs: list[str] = []
    observations: list[str] = []

    max_obs = settings.max_observations_in_context
    max_chars = settings.max_observation_chars

    for observation in session.observations[:max_obs]:
        sanitized = redact_text(sanitize_untrusted_text(observation.summary))
        truncated = sanitized[:max_chars]
        observations.append(truncated)
        refs.extend(observation.refs)

    # G15: build rolling summary from session state (STATE_MEMORY.md §3).
    high_confidence_obs = [
        obs.summary
        for obs in session.observations
        if obs.confidence is not None and obs.confidence >= 0.7
    ]
    what_we_know = [
        redact_text(sanitize_untrusted_text(s))[:max_chars]
        for s in high_confidence_obs[:max_obs]
    ]

    # G21: include tool call status so LLM knows what was tried and what happened.
    what_we_tried = [
        f"{tc.tool_name}: {tc.normalized_status or tc.status.value}"
        for tc in session.tool_calls
    ]

    open_questions: list[str] = []
    if not session.observations:
        open_questions.append("No telemetry available yet — live data is needed.")
    if not refs:
        open_questions.append("No runbook references found — KB search may need broadening.")

    rolling_summary = RollingSummary(
        what_we_know=what_we_know,
        what_we_tried=what_we_tried,
        open_questions=open_questions,
    )

    return SessionContext(
        incident_title=session.incident.title,
        service=session.incident.service,
        summary=redact_text(sanitize_untrusted_text(session.incident.summary)),
        observations=observations,
        refs=sorted(set(refs)),
        rolling_summary=rolling_summary,
    )
