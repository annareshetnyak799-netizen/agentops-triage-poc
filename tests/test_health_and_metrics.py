from fastapi.testclient import TestClient

from src.api.app import app
from src.config import settings


client = TestClient(app)


def test_root_endpoint_returns_service_metadata() -> None:
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "agentops-triage-poc"
    assert data["environment"] == settings.environment
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/health"
    assert data["metrics_url"] == "/metrics"


def test_health_endpoint_returns_ok_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "agentops-triage-poc"


def test_metrics_endpoint_returns_request_counters() -> None:
    client.get("/health")
    client.get("/metrics")

    response = client.get("/metrics")

    assert response.status_code == 200
    data = response.json()

    assert "http_requests_total" in data
    assert data["http_requests_total"] >= 1


def test_metrics_capture_triage_outcomes() -> None:
    payload = {
        "title": "High 5xx rate",
        "service": "payments-api",
        "severity": "P1",
        "timestamp": "2026-04-07T10:00:00Z",
        "summary": "Error rate increased after deploy",
        "signals": ["5xx > 12%"],
        "environment": "prod",
        "reporter": "oncall-engineer",
        "alert_payload": {},
        "links": [],
    }

    response = client.post("/incident", json=payload)
    assert response.status_code == 201

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200

    data = metrics_response.json()
    assert data.get("tool_calls_total", 0) >= 3
    assert data.get("triage_completed_total", 0) >= 1
