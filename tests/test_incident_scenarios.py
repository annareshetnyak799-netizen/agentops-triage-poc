import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from tests.incident_scenarios import SCENARIOS, IncidentScenario
from tests.http_helpers import unwrap_success


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

    data = unwrap_success(response)
    report = data["report"]
    assert report["status"] == scenario.expected_status
    assert report["incident_summary"]["service"] == scenario.payload["service"]
    assert len(report["hypotheses"]) >= 1
    assert len(report["next_steps"]) >= 1
    assert any(ref["snippet"] == scenario.expected_ref for ref in report["refs"])

    if scenario.expected_status == "waiting_approval":
        assert report["approval_requests"] != []
    else:
        assert report["approval_requests"] == []


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

    session_id = unwrap_success(response)["session_id"]

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = unwrap_success(trace_response)["trace"]
    step_types = [step["step_type"] for step in trace]

    assert "context_assembly" in step_types
    assert "prompt_build" in step_types
    assert "llm_analysis" in step_types

    if scenario.expected_status == "waiting_approval":
        assert "policy_check" in step_types
        assert "approval_request" in step_types
