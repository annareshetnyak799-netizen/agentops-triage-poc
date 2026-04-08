from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest

from src.api.app import app
from src.domain.enums import Severity
from src.domain.schemas import IncidentInput
from src.orchestrator.service import OrchestratorService
from src.persistence.repository import InMemorySessionRepository
from tests.http_helpers import unwrap_success


client = TestClient(app)


def test_forced_tool_failure_returns_partial_completed() -> None:
    payload = {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": "force_tool_failure during triage",
        "signals": ["5xx > 12%"],
        "environment": "prod",
        "reporter": "oncall-engineer",
        "alert_payload": {},
        "links": [],
    }

    response = client.post("/incident", json=payload)

    assert response.status_code == 201

    data = unwrap_success(response)
    assert data["report"]["status"] == "partial_completed"
    assert data["session_state"]["partial_result"] is True
    assert "Forced tool failure" in data["session_state"]["failure_reason"]
    assert data["report"] is not None
    assert data["report"]["hypotheses"][0]["statement"] == (
        "Insufficient evidence for a confident conclusion."
    )
    assert data["report"]["next_steps"][0]["action"] == "Collect more telemetry and rerun triage."
    assert data["report"]["unknowns"] != []
    assert "Forced tool failure" in data["report"]["unknowns"][0]
    assert any(note["type"] == "degradation" for note in data["report"]["safety_notes"])
    assert any(note["type"] == "groundedness" for note in data["report"]["safety_notes"])

    trace_response = client.get(f"/sessions/{data['session_id']}/trace")
    assert trace_response.status_code == 200

    trace = unwrap_success(trace_response)["trace"]
    degradation_step = next(step for step in trace if step["step_type"] == "degradation")
    assert degradation_step["status"] == "degraded"
    assert degradation_step["type"] == "report"
    assert "Forced tool failure" in degradation_step["metadata"]["reason"]
    assert degradation_step["metadata"]["degradation_type"] == "tool_failure"


@pytest.mark.anyio
async def test_budget_exhaustion_partial_trace_includes_budget_snapshot(monkeypatch) -> None:
    repository = InMemorySessionRepository()
    orchestrator = OrchestratorService(repository=repository)

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
    session = repository.create_session(incident)

    class ExhaustedBudget:
        def __init__(self) -> None:
            self.exhausted = True

        def snapshot(self):
            class Snapshot:
                tool_calls_used = 0
                tool_calls_remaining = 0
                elapsed_seconds = 30.0
                time_remaining_seconds = 0.0

            return Snapshot()

    monkeypatch.setattr("src.orchestrator.service.SessionBudget", ExhaustedBudget)

    updated = await orchestrator.run_initial_triage(session.session_id)

    assert updated.status.value == "partial_completed"
    assert updated.partial_result is True
    assert updated.budget_remaining == 0
    assert "Budget exhausted" in (updated.failure_reason or "")

    trace = repository.get_trace(session.session_id)
    assert trace is not None
    degradation_step = next(step for step in trace if step.step_type == "degradation")
    assert degradation_step.metadata["degradation_type"] == "budget_exhausted"
    assert degradation_step.metadata["tool_calls_used"] == "0"
    assert degradation_step.metadata["tool_calls_remaining"] == "0"
    assert degradation_step.metadata["elapsed_ms"] == "30000"
    assert degradation_step.metadata["time_remaining_ms"] == "0"
