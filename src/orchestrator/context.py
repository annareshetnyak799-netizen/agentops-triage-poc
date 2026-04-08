from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.schemas import SessionView
from src.safety.redaction import redact_text
from src.safety.sanitization import sanitize_untrusted_text


class KnownFact(BaseModel):
    value: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class SessionContext(BaseModel):
    incident_title: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    observations: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    known_facts: list[KnownFact] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def build_session_context(session: SessionView) -> SessionContext:
    refs: list[str] = []
    observations: list[str] = []

    for observation in session.observations:
        observations.append(redact_text(sanitize_untrusted_text(observation.summary)))
        refs.extend(observation.refs)

    known_facts = [KnownFact(value=summary) for summary in observations[:5]]

    return SessionContext(
        incident_title=session.incident.title,
        service=session.incident.service,
        summary=redact_text(sanitize_untrusted_text(session.incident.summary)),
        observations=observations,
        refs=sorted(set(refs)),
        known_facts=known_facts,
    )
