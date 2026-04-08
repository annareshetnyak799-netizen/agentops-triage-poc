from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app


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

    data = response.json()
    assert "session_id" in data
    assert data["status"] == "completed"
    assert data["incident"]["service"] == "payments-api"
    assert len(data["tool_calls"]) == 3
    assert len(data["observations"]) == 3
    assert data["final_report"] is not None
    assert len(data["final_report"]["hypotheses"]) >= 1
    assert len(data["final_report"]["next_steps"]) >= 1

    trace_response = client.get(f"/sessions/{data['session_id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert len(trace) >= 5

