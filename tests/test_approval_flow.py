from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import ensure_app_services
from src.llm.base import LLMAnalysisOutput
from tests.http_helpers import unwrap_success


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

    session_id = unwrap_success(create_response)["session_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "approval_id": "approval-not-applicable",
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

    session = unwrap_success(create_response)
    assert session["report"]["status"] == "waiting_approval"

    session_id = session["session_id"]
    approval_id = session["report"]["approval_requests"][0]["approval_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "approval_id": approval_id,
            "decision": "approved",
            "comment": "Rollback approved by on-call.",
        },
    )

    assert approval_response.status_code == 200
    data = unwrap_success(approval_response)
    assert data["session_id"] == session_id
    assert data["approval_id"] == approval_id
    assert data["lifecycle_state"] == "completed"
    assert data["report"]["status"] == "completed"
    assert data["decision"] == "approved"
    assert data["report"]["approval_requests"] == []
    assert any(
        note["message"] == "Action was human-approved before continuation."
        for note in data["report"]["safety_notes"]
    )
    assert all("safety_event_id" in note for note in data["report"]["safety_notes"])

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = unwrap_success(trace_response)["trace"]
    approval_step = next(step for step in trace if step["step_type"] == "approval_decision")
    assert approval_step["type"] == "approval"
    assert approval_step["metadata"]["approval_id"] == approval_id
    assert approval_step["metadata"]["decision"] == "approved"
    assert approval_step["metadata"]["resulting_status"] == "completed"
    assert approval_step["metadata"]["comment_present"] == "true"


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

    session = unwrap_success(create_response)
    assert session["report"]["status"] == "waiting_approval"

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
    data = unwrap_success(approval_response)
    assert data["session_id"] == session_id
    assert data["approval_id"] == approval_id
    assert data["lifecycle_state"] == "partial_completed"
    assert data["report"]["status"] == "partial_completed"
    assert data["decision"] == "rejected"
    assert data["report"]["approval_requests"] == []
    assert any(
        "human-rejected" in note["message"]
        for note in data["report"]["safety_notes"]
    )
    assert all(note["session_id"] == session_id for note in data["report"]["safety_notes"])

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = unwrap_success(trace_response)["trace"]
    approval_step = next(step for step in trace if step["step_type"] == "approval_decision")
    assert approval_step["type"] == "approval"
    assert approval_step["metadata"]["approval_id"] == approval_id
    assert approval_step["metadata"]["decision"] == "rejected"
    assert approval_step["metadata"]["resulting_status"] == "partial_completed"
    assert approval_step["metadata"]["comment_present"] == "true"


@pytest.mark.anyio
async def test_natural_language_risky_recommendation_requires_approval(
    monkeypatch,
) -> None:
    ensure_app_services(app)
    original_adapter = app.state.orchestrator._llm_adapter
    original_collect_refs = app.state.orchestrator._collect_refs

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
        app.state.orchestrator,
        "_llm_adapter",
        RiskyLanguageAdapter(),
    )
    monkeypatch.setattr(
        app.state.orchestrator,
        "_collect_refs",
        lambda session: [],
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

    session = unwrap_success(create_response)
    assert session["report"]["status"] == "waiting_approval"
    assert session["report"]["approval_requests"] != []
    approval_request = session["report"]["approval_requests"][0]
    assert any(note["type"] == "policy" for note in session["report"]["safety_notes"])
    assert any(note["type"] == "groundedness" for note in session["report"]["safety_notes"])
    assert all(item["status"] == "weakened" for item in session["report"]["hypotheses"])
    assert all(item["confidence"] <= 0.7 for item in session["report"]["hypotheses"])
    assert "rollback" in approval_request["action_type"]
    assert approval_request["risk_level"] == "high"
    assert "evidence is limited" in approval_request["reason"].lower()
    assert (
        "rolling back the deployment"
        in session["report"]["next_steps"][1]["action"].lower()
        or "rolling back the deployment"
        in session["report"]["next_steps"][0]["action"].lower()
    )

    trace_response = client.get(f"/sessions/{session['session_id']}/trace")
    assert trace_response.status_code == 200
    trace = unwrap_success(trace_response)["trace"]
    policy_step = next(step for step in trace if step["step_type"] == "policy_check")
    assert policy_step["metadata"]["weakly_grounded"] == "true"

    monkeypatch.setattr(app.state.orchestrator, "_llm_adapter", original_adapter)
    monkeypatch.setattr(app.state.orchestrator, "_collect_refs", original_collect_refs)


def test_approval_endpoint_rejects_mismatched_approval_id() -> None:
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
    assert session["report"]["status"] == "waiting_approval"

    session_id = session["session_id"]

    approval_response = client.post(
        f"/sessions/{session_id}/approval",
        json={
            "approval_id": "wrong-approval-id",
            "decision": "approved",
            "comment": "This should fail.",
        },
    )

    assert approval_response.status_code == 409
