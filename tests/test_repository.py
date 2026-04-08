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


def build_approval_id(session_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"approval:{session_id}"))


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


def test_repository_updates_session_state_metadata() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    updated = repository.update_session_state(
        session.session_id,
        budget_remaining=4,
        failure_reason="Budget exhausted before tool execution.",
    )

    assert updated.budget_remaining == 4
    assert updated.failure_reason == "Budget exhausted before tool execution."


def test_repository_applies_approval_decision() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    repository.update_status(session.session_id, SessionStatus.PLANNING)
    repository.update_status(session.session_id, SessionStatus.ANALYZING)
    repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)
    approval_id = build_approval_id(session.session_id)
    repository.set_approval_request(
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

    updated = repository.apply_approval(
        session.session_id,
        ApprovalInput(
            approval_id=approval_id,
            decision=ApprovalDecision.APPROVED,
            comment="Approved by human reviewer.",
        ),
    )

    assert updated.status == SessionStatus.COMPLETED


def test_repository_rejects_mismatched_approval_id() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
    repository.update_status(session.session_id, SessionStatus.VALIDATING_INPUT)
    repository.update_status(session.session_id, SessionStatus.PLANNING)
    repository.update_status(session.session_id, SessionStatus.ANALYZING)
    repository.update_status(session.session_id, SessionStatus.WAITING_APPROVAL)
    repository.set_approval_request(
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
        repository.apply_approval(
            session.session_id,
            ApprovalInput(
                approval_id="wrong-approval-id",
                decision=ApprovalDecision.APPROVED,
                comment="Approved by human reviewer.",
            ),
        )
    except ValueError as exc:
        assert "Approval ID does not match" in str(exc)
    else:
        raise AssertionError("Expected approval ID mismatch to raise ValueError.")


def test_repository_persists_enriched_tool_call_metadata() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
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

    updated = repository.add_tool_call(session.session_id, tool_call)

    assert updated.tool_calls[0].tool_call_id == "tool-call-1"
    assert updated.tool_calls[0].input_payload["service"] == "payments-api"
    assert updated.tool_calls[0].normalized_output["metric"] == "5xx"
    assert updated.tool_calls[0].normalized_status == "completed"
    trace = repository.get_trace(session.session_id)
    assert trace is not None
    assert trace[-1].metadata["tool_call_id"] == "tool-call-1"
    assert trace[-1].metadata["has_normalized_output"] == "true"
    assert trace[-1].metadata["normalized_status"] == "completed"


def test_repository_persists_enriched_observation_metadata() -> None:
    repository = InMemorySessionRepository()

    session = repository.create_session(build_incident())
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

    updated = repository.add_observation(session.session_id, observation)
    trace = repository.get_trace(session.session_id)

    assert updated.observations[0].observation_id == "obs-1"
    assert updated.observations[0].source_type == "tool"
    assert updated.observations[0].source_ref == "tool-call-1"
    assert updated.observations[0].title == "payments-api 5xx error rate"
    assert updated.observations[0].confidence == 0.9
    assert trace is not None
    assert trace[-1].metadata["source_type"] == "tool"
    assert trace[-1].metadata["source_ref"] == "tool-call-1"
