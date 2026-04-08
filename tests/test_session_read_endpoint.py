from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app
from tests.http_helpers import unwrap_success


client = TestClient(app)


def test_get_session_returns_completed_session_state() -> None:
    payload = {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": "Error rate increased after deploy",
        "signals": ["5xx > 12%"],
        "environment": "prod",
        "reporter": "oncall-engineer",
        "alert_payload": {},
        "links": [],
    }

    create_response = client.post("/incident", json=payload)
    assert create_response.status_code == 201

    session_id = unwrap_success(create_response)["session_id"]

    session_response = client.get(f"/sessions/{session_id}")
    assert session_response.status_code == 200

    session = unwrap_success(session_response)
    assert session["session_id"] == session_id
    assert session["lifecycle_state"] == "completed"
    assert session["session_state"]["lifecycle_state"] == "completed"
    assert session["session_state"]["waiting_for_approval"] is False
    assert session["session_state"]["partial_result"] is False
    assert session["iteration_count"] == 1
    assert session["llm_provider"] is not None
    assert session["policy_mode"] == "strict"
    assert session["investigation_plan"] is not None
    assert session["investigation_plan"]["session_id"] == session_id
    assert session["investigation_plan"]["status"] == "active"
    assert len(session["tool_calls"]) == 3
    assert all(item["status"] == "completed" for item in session["tool_calls"])
    assert all("input_payload" in item for item in session["tool_calls"])
    assert all("normalized_output" in item for item in session["tool_calls"])
    assert session["report"] is not None
    assert len(session["report"]["hypotheses"]) >= 1
    assert len(session["report"]["next_steps"]) >= 1


def test_get_session_returns_partial_completed_after_rejected_approval() -> None:
    payload = {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": "Rollback may be needed after deploy",
        "signals": ["5xx > 12%"],
        "environment": "prod",
        "reporter": "oncall-engineer",
        "alert_payload": {},
        "links": [],
    }

    create_response = client.post("/incident", json=payload)
    assert create_response.status_code == 201

    session = unwrap_success(create_response)
    session_id = session["session_id"]
    approval_id = session["report"]["approval_requests"][0]["approval_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "approval_id": approval_id,
            "decision": "rejected",
            "comment": "Do not rollback yet.",
        },
    )
    assert approval_response.status_code == 200

    session_response = client.get(f"/sessions/{session_id}")
    assert session_response.status_code == 200

    session = unwrap_success(session_response)
    assert session["session_id"] == session_id
    assert session["lifecycle_state"] == "partial_completed"
    assert session["session_state"]["lifecycle_state"] == "partial_completed"
    assert session["session_state"]["partial_result"] is True
    assert session["session_state"]["waiting_for_approval"] is False
    assert session["iteration_count"] == 2
    assert session["completed_at"] is not None
    assert session["investigation_plan"] is not None
    assert len(session["tool_calls"]) == 3
    assert session["report"]["approval_requests"] == []
