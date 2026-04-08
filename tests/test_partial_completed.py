from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app


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

    data = response.json()
    assert data["status"] == "partial_completed"
    assert data["final_report"] is not None
    assert "Partial triage result generated." == data["final_report"]["summary"]
    assert len(data["tool_calls"]) == 0
