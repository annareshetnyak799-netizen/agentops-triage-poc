from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app


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

    session_id = create_response.json()["session_id"]

    session_response = client.get(f"/sessions/{session_id}")
    assert session_response.status_code == 200

    session = session_response.json()
    assert session["session_id"] == session_id
    assert session["status"] == "completed"
    assert session["final_report"] is not None
    assert len(session["tool_calls"]) == 3
    assert len(session["observations"]) == 3


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

    session_id = create_response.json()["session_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "decision": "rejected",
            "comment": "Do not rollback yet.",
        },
    )
    assert approval_response.status_code == 200

    session_response = client.get(f"/sessions/{session_id}")
    assert session_response.status_code == 200

    session = session_response.json()
    assert session["session_id"] == session_id
    assert session["status"] == "partial_completed"
    assert session["approval_request"] is not None
