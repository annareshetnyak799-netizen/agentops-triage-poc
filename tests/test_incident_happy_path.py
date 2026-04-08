from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app
from tests.http_helpers import unwrap_success


client = TestClient(app)


def test_create_incident_session_returns_structured_result() -> None:
    payload = {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": "Error rate increased after deploy",
        "signals": ["5xx > 12%", "latency p95 up 3x"],
        "environment": "prod",
        "reporter": "oncall-engineer",
        "alert_payload": {},
        "links": [],
    }

    response = client.post("/incident", json=payload)

    assert response.status_code == 201

    data = unwrap_success(response)
    assert "session_id" in data
    assert data["incident_id"] is not None
    assert data["incident"]["incident_id"] == data["incident_id"]
    assert data["incident"]["service"] == "payments-api"
    assert data["lifecycle_state"] == "completed"
    assert data["session_state"]["lifecycle_state"] == "completed"
    assert data["session_state"]["waiting_for_approval"] is False
    assert data["session_state"]["partial_result"] is False
    assert data["investigation_plan"] is not None
    assert data["investigation_plan"]["status"] == "active"
    assert len(data["investigation_plan"]["steps"]) >= 1
    assert len(data["tool_calls"]) == 3
    assert all(item["status"] == "completed" for item in data["tool_calls"])
    assert all(item["latency_ms"] is not None for item in data["tool_calls"])
    assert all("has_normalized_output" in item for item in data["tool_calls"])
    assert all("input_payload" in item for item in data["tool_calls"])
    assert all("normalized_output" in item for item in data["tool_calls"])
    report = data["report"]
    assert report["status"] == "completed"
    assert report["incident_summary"]["service"] == "payments-api"
    assert report["summary"] != ""
    assert len(report["hypotheses"]) >= 1
    assert all(item["source"] == "llm_analysis" for item in report["hypotheses"])
    assert all(0.0 <= item["confidence"] <= 1.0 for item in report["hypotheses"])
    assert all(item["status"] in {"active", "weakened"} for item in report["hypotheses"])
    assert len(report["next_steps"]) >= 1
    assert all(step["source"] == "llm_analysis" for step in report["next_steps"])
    assert all(step["rationale"] is not None for step in report["next_steps"])
    assert any(ref["type"] == "observation" for ref in report["refs"])
    assert any(ref["type"] == "tool_result" for ref in report["refs"])
    assert any(ref["type"] == "kb_doc" for ref in report["refs"])
    assert all("target_ref" in ref for ref in report["refs"])
    assert report["safety_notes"] != []
    assert any(note["type"] == "uncertainty" for note in report["safety_notes"])
    assert all("safety_event_id" in note for note in report["safety_notes"])
    assert all(note["session_id"] == data["session_id"] for note in report["safety_notes"])
    assert all("created_at" in note for note in report["safety_notes"])

    trace_response = client.get(f"/sessions/{data['session_id']}/trace")
    assert trace_response.status_code == 200
    trace = unwrap_success(trace_response)["trace"]
    assert len(trace) >= 5
