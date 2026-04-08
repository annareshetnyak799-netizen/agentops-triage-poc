from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.app import app


client = TestClient(app)


def test_trace_endpoint_returns_meaningful_steps() -> None:
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

    create_response = client.post("/incident", json=payload)
    assert create_response.status_code == 201

    session_id = create_response.json()["session_id"]

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = trace_response.json()
    assert len(trace) >= 9

    step_types = [step["step_type"] for step in trace]

    assert "session_created" in step_types
    assert "status_transition" in step_types
    assert "tool_call" in step_types
    assert "observation" in step_types
    assert "context_assembly" in step_types
    assert "prompt_build" in step_types
    assert "llm_analysis" in step_types
    assert "report" in step_types

    session_created = next(step for step in trace if step["step_type"] == "session_created")
    assert session_created["metadata"]["service"] == "payments-api"
    assert session_created["metadata"]["severity"] == "P1"

    context_step = next(step for step in trace if step["step_type"] == "context_assembly")
    assert int(context_step["metadata"]["observations_count"]) >= 1
    assert int(context_step["metadata"]["known_facts_count"]) >= 1

    prompt_step = next(step for step in trace if step["step_type"] == "prompt_build")
    assert prompt_step["metadata"]["prompt_template"] == "analysis.txt"
    assert int(prompt_step["metadata"]["prompt_length"]) > 0

    llm_step = next(step for step in trace if step["step_type"] == "llm_analysis")
    assert "backend" in llm_step["metadata"]
    assert "provider" in llm_step["metadata"]
    assert "model" in llm_step["metadata"]
    assert llm_step["metadata"]["structured_output"] == "true"
    assert int(llm_step["metadata"]["next_steps_count"]) >= 1


def test_trace_endpoint_includes_policy_check_for_risky_recommendation() -> None:
    payload = {
        "title": "Severe 5xx spike after deploy",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": "Rollback may be needed after deploy",
        "signals": ["5xx > 20%", "timeouts on /charge"],
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

    trace_response = client.get(f"/sessions/{session_id}/trace")
    assert trace_response.status_code == 200

    trace = trace_response.json()
    step_types = [step["step_type"] for step in trace]

    assert "policy_check" in step_types
    assert "approval_request" in step_types

    policy_step = next(step for step in trace if step["step_type"] == "policy_check")
    assert policy_step["status"] == "approval_required"
    assert policy_step["metadata"]["policy_trigger"] == "rollback"
    assert "rollback" in policy_step["details"].lower()
