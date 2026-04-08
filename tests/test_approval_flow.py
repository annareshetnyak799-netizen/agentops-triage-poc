from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.routes import incident as incident_routes
from src.api.app import app
from src.llm.base import LLMAnalysisOutput


client = TestClient(app)


def test_approval_endpoint_returns_conflict_for_completed_session() -> None:
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

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "decision": "approved",
            "comment": "Reviewed by human.",
        },
    )

    assert approval_response.status_code == 409


def test_approval_endpoint_completes_waiting_approval_session() -> None:
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

    session = create_response.json()
    assert session["status"] == "waiting_approval"

    session_id = session["session_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "decision": "approved",
            "comment": "Rollback approved by on-call.",
        },
    )

    assert approval_response.status_code == 200
    data = approval_response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "completed"
    assert data["decision"] == "approved"


def test_approval_rejection_transitions_to_partial_completed() -> None:
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

    session = create_response.json()
    assert session["status"] == "waiting_approval"

    session_id = session["session_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "decision": "rejected",
            "comment": "Do not rollback yet.",
        },
    )

    assert approval_response.status_code == 200
    data = approval_response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "partial_completed"
    assert data["decision"] == "rejected"


@pytest.mark.anyio
async def test_natural_language_risky_recommendation_requires_approval(
    monkeypatch,
) -> None:
    original_adapter = incident_routes.orchestrator._llm_adapter

    class RiskyLanguageAdapter:
        async def analyze(self, payload):
            del payload
            return LLMAnalysisOutput(
                summary="The service likely regressed after the latest deploy.",
                hypotheses=[
                    "Recent deployment introduced a regression affecting request handling.",
                ],
                next_steps=[
                    "Inspect the latest deployment diff for risky configuration changes.",
                    "Consider rolling back the deployment if the service continues to degrade.",
                ],
            )

    monkeypatch.setattr(
        incident_routes.orchestrator,
        "_llm_adapter",
        RiskyLanguageAdapter(),
    )

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

    session = create_response.json()
    assert session["status"] == "waiting_approval"
    assert session["approval_request"] is not None
    assert "deployment rollback" in session["approval_request"]["reason"].lower()
    assert (
        "rolling back the deployment"
        in session["approval_request"]["recommended_action"].lower()
    )

    monkeypatch.setattr(incident_routes.orchestrator, "_llm_adapter", original_adapter)
