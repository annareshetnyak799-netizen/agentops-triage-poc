from datetime import UTC, datetime

from src.domain.enums import ApprovalDecision, SessionStatus, Severity
from src.domain.schemas import ApprovalInput, IncidentInput
from src.persistence.sqlite_repository import SQLiteSessionRepository


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


def test_sqlite_repository_creates_and_reads_session(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    loaded = sqlite_repository.get_session(session.session_id)

    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.status == SessionStatus.NEW


def test_sqlite_repository_updates_status_and_trace(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    updated = sqlite_repository.update_status(
        session.session_id,
        SessionStatus.VALIDATING_INPUT,
    )
    trace = sqlite_repository.get_trace(session.session_id)

    assert updated.status == SessionStatus.VALIDATING_INPUT
    assert trace is not None
    assert len(trace) >= 2
    assert trace[-1].step_type == "status_transition"
    assert trace[-1].metadata["from_status"] == "new"
    assert trace[-1].metadata["to_status"] == "validating_input"


def test_sqlite_repository_applies_approval(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    sqlite_repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    sqlite_repository.update_status(session.session_id, SessionStatus.PLANNING)
    sqlite_repository.update_status(session.session_id, SessionStatus.ANALYZING)
    sqlite_repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)

    updated = sqlite_repository.apply_approval(
        session.session_id,
        ApprovalInput(
            decision=ApprovalDecision.APPROVED,
            comment="Approved by reviewer.",
        ),
    )

    assert updated.status == SessionStatus.COMPLETED


