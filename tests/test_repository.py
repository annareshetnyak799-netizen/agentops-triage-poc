from datetime import UTC, datetime

from src.domain.enums import ApprovalDecision, SessionStatus, Severity
from src.domain.schemas import ApprovalInput, IncidentInput
from src.persistence.repository import InMemorySessionRepository


def build_incident() -> IncidentInput:
    return IncidentInput(
        title="High 5xx rate",
        service="payments-api",
        severity=Severity.P1,
        timestamp=datetime.now(UTC),
        summary="Error rate increased after deploy",
        signals=["5xx > 12%"],
        environment="prod",
        reporter="oncall-engineer",
        alert_payload={},
        links=[],
    )


def test_repository_creates_session_and_trace() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    trace = repository.get_trace(session.session_id)

    assert session.status == SessionStatus.NEW
    assert trace is not None
    assert len(trace) == 1
    assert trace[0].step_type == "session_created"


def test_repository_updates_status_and_appends_trace() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    updated = repository.update_status(
        session.session_id,
        SessionStatus.VALIDATING_INPUT,
    )
    trace = repository.get_trace(session.session_id)

    assert updated.status == SessionStatus.VALIDATING_INPUT
    assert trace is not None
    assert len(trace) == 2
    assert trace[-1].step_type == "status_transition"


def test_repository_applies_approval_decision() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    repository.update_status(session.session_id, SessionStatus.PLANNING)
    repository.update_status(session.session_id, SessionStatus.ANALYZING)
    repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)

    updated = repository.apply_approval(
        session.session_id,
        ApprovalInput(
            decision=ApprovalDecision.APPROVED,
            comment="Approved by human reviewer.",
        ),
    )

    assert updated.status == SessionStatus.COMPLETED
