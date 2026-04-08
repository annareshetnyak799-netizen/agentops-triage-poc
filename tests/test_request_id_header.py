from fastapi.testclient import TestClient

from src.api.app import app


client = TestClient(app)


def test_request_id_header_is_present_on_health_response() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_request_id_header_is_present_on_metrics_response() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]
