import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from tests.incident_scenarios import SCENARIOS, IncidentScenario


client = TestClient(app)


@pytest.mark.parametrize(
    ("scenario",),
    [(scenario,) for scenario in SCENARIOS],
    ids=[scenario.name for scenario in SCENARIOS],
)
def test_incident_scenarios_return_expected_session_shapes(
    scenario: IncidentScenario,
) -> None:
    response = client.post("/incident", json=scenario.payload)

    assert response.status_code == 201

    data = response.json()
    assert data["status"] == scenario.expected_status
    assert data["incident"]["service"] == scenario.payload["service"]
    assert len(data["tool_calls"]) == 3
    assert len(data["observations"]) == 3
    assert data["final_report"] is not None
    assert len(data["final_report"]["hypotheses"]) >= 1
    assert len(data["final_report"]["next_steps"]) >= 1
    assert scenario.expected_ref in data["final_report"]["refs"]

    if scenario.expected_status == "waiting_approval":
        assert data["approval_request"] is not None
    else:
        assert data["approval_request"] is None


@pytest.mark.parametrize(
    ("scenario",),
    [(scenario,) for scenario in SCENARIOS],
    ids=[scenario.name for scenario in SCENARIOS],
)
def test_incident_scenarios_emit_trace_for_llm_stage(
    scenario: IncidentScenario,
) -> None:
    response = client.post("/incident", json=scenario.payload)
    assert response.status_code == 201

    session_id = response.json()["session_id"]

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = trace_response.json()
    step_types = [step["step_type"] for step in trace]

    assert "context_assembly" in step_types
    assert "prompt_build" in step_types
    assert "llm_analysis" in step_types

    if scenario.expected_status == "waiting_approval":
        assert "policy_check" in step_types
        assert "approval_request" in step_types
