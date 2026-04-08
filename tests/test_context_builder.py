from datetime import UTC, datetime

from src.domain.enums import SessionStatus, Severity
from src.domain.schemas import IncidentInput, Observation, SessionView
from src.orchestrator.context import build_session_context


def test_build_session_context_collects_observations_and_refs() -> None:
    incident = IncidentInput(
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

    session = SessionView(
        session_id="session-1",
        status=SessionStatus.ANALYZING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        incident=incident,
        observations=[
            Observation(
                source="metrics_tool",
                summary="Error rate elevated to 12.4%.",
                refs=[],
            ),
            Observation(
                source="runbook_retrieval_tool",
                summary="Relevant runbooks retrieved.",
                refs=["runbooks/payments-api.md"],
            ),
        ],
        tool_calls=[],
    )

    context = build_session_context(session)

    assert context.incident_title == "High 5xx rate"
    assert context.service == "payments-api"
    assert len(context.observations) == 2
    assert "runbooks/payments-api.md" in context.refs
    assert len(context.known_facts) >= 1
