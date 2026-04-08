from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from src.domain.enums import ApprovalDecision, SessionStatus, Severity
from src.domain.schemas import (
    ApprovalInput,
    ApprovalRequest,
    IncidentInput,
    Observation,
    ToolCallRecord,
)
from src.domain.enums import ToolCallStatus
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


def build_approval_id(session_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"approval:{session_id}"))


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


def test_sqlite_repository_updates_session_state_metadata(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    updated = sqlite_repository.update_session_state(
        session.session_id,
        budget_remaining=4,
        failure_reason="Budget exhausted before tool execution.",
    )

    assert updated.budget_remaining == 4
    assert updated.failure_reason == "Budget exhausted before tool execution."


def test_sqlite_repository_applies_approval(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    sqlite_repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    sqlite_repository.update_status(session.session_id, SessionStatus.PLANNING)
    sqlite_repository.update_status(session.session_id, SessionStatus.ANALYZING)
    sqlite_repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)
    approval_id = build_approval_id(session.session_id)
    sqlite_repository.set_approval_request(
        session.session_id,
        ApprovalRequest(
            approval_id=approval_id,
            action_type="rollback_deployment",
            reason="Rollback requires approval.",
            risk_level="high",
            status="pending",
            recommended_action="Rollback the latest production deploy.",
        ),
    )

    updated = sqlite_repository.apply_approval(
        session.session_id,
        ApprovalInput(
            approval_id=approval_id,
            decision=ApprovalDecision.APPROVED,
            comment="Approved by reviewer.",
        ),
    )

    assert updated.status == SessionStatus.COMPLETED


def test_sqlite_repository_rejects_mismatched_approval_id(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    sqlite_repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    sqlite_repository.update_status(session.session_id, SessionStatus.PLANNING)
    sqlite_repository.update_status(session.session_id, SessionStatus.ANALYZING)
    sqlite_repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)
    sqlite_repository.set_approval_request(
        session.session_id,
        ApprovalRequest(
            approval_id=build_approval_id(session.session_id),
            action_type="rollback_deployment",
            reason="Rollback requires approval.",
            risk_level="high",
            status="pending",
            recommended_action="Rollback the latest production deploy.",
        ),
    )

    try:
        sqlite_repository.apply_approval(
            session.session_id,
            ApprovalInput(
                approval_id="wrong-approval-id",
                decision=ApprovalDecision.APPROVED,
                comment="Approved by reviewer.",
            ),
        )
    except ValueError as exc:
        assert "Approval ID does not match" in str(exc)
    else:
        raise AssertionError("Expected approval ID mismatch to raise ValueError.")


def test_sqlite_repository_persists_enriched_tool_call_metadata(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    tool_call = ToolCallRecord(
        tool_call_id="tool-call-1",
        tool_name="metrics_tool",
        input_payload={"service": "payments-api"},
        status=ToolCallStatus.SUCCESS,
        normalized_status="completed",
        latency_ms=123,
        normalized_output={"metric": "5xx"},
        summary="Collected metrics successfully.",
    )

    updated = sqlite_repository.add_tool_call(session.session_id, tool_call)

    assert updated.tool_calls[0].tool_call_id == "tool-call-1"
    assert updated.tool_calls[0].input_payload["service"] == "payments-api"
    assert updated.tool_calls[0].normalized_output["metric"] == "5xx"
    assert updated.tool_calls[0].normalized_status == "completed"
    trace = sqlite_repository.get_trace(session.session_id)
    assert trace is not None
    assert trace[-1].metadata["tool_call_id"] == "tool-call-1"
    assert trace[-1].metadata["has_normalized_output"] == "true"
    assert trace[-1].metadata["normalized_status"] == "completed"


def test_sqlite_repository_persists_enriched_observation_metadata(
    sqlite_repository: SQLiteSessionRepository,
) -> None:
    session = sqlite_repository.create_session(build_incident())
    observation = Observation(
        observation_id="obs-1",
        source="metrics_tool",
        source_type="tool",
        source_ref="tool-call-1",
        title="payments-api 5xx error rate",
        summary="5xx increased from 0.8% to 12.4%.",
        confidence=0.9,
        observed_at=datetime.now(UTC),
        refs=["runbooks/payments-api.md"],
    )

    updated = sqlite_repository.add_observation(session.session_id, observation)
    trace = sqlite_repository.get_trace(session.session_id)

    assert updated.observations[0].observation_id == "obs-1"
    assert updated.observations[0].source_type == "tool"
    assert updated.observations[0].source_ref == "tool-call-1"
    assert updated.observations[0].title == "payments-api 5xx error rate"
    assert updated.observations[0].confidence == 0.9
    assert trace is not None
    assert trace[-1].metadata["source_type"] == "tool"
    assert trace[-1].metadata["source_ref"] == "tool-call-1"
