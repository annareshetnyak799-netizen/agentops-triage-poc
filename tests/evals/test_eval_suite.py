"""Pytest-based eval suite for AgentOps Triage PoC (EVALS.md §5).

Runs all incident fixtures directly against the FastAPI app via TestClient —
no live server required. Each fixture becomes a separate parametrized test so
failures are reported individually in pytest output.

Usage:
    uv run pytest tests/evals/test_eval_suite.py -v
    uv run pytest tests/evals/test_eval_suite.py -v -k normal
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from tests.evals.pii_detector import collect_response_text, detect_pii
from tests.evals.rubric import score

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "incidents"


def _load_fixtures() -> list[tuple[str, dict[str, Any]]]:
    return [
        (path.stem, json.loads(path.read_text("utf-8")))
        for path in sorted(FIXTURES_DIR.glob("*.json"))
    ]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "fixture_case" in metafunc.fixturenames:
        cases = _load_fixtures()
        metafunc.parametrize(
            "fixture_case",
            cases,
            ids=[name for name, _ in cases],
        )


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    return TestClient(app)


def test_eval_case(api_client: TestClient, fixture_case: tuple[str, dict[str, Any]]) -> None:
    case_id, fixture = fixture_case

    eval_meta: dict[str, Any] = fixture.get("_eval") or {}
    incident_payload: dict[str, Any] = fixture["incident"]

    acceptable_statuses: list[str] = eval_meta.get(
        "acceptable_statuses",
        [eval_meta.get("expected_status", "completed")],
    )
    expected_rubric_min: int = eval_meta.get("expected_rubric_min_score", 8)
    pii_canary: str | None = eval_meta.get("pii_canary")
    check_injection: bool = eval_meta.get("check_injection_blocked", False)

    # ── Submit incident ───────────────────────────────────────────────────────
    response = api_client.post("/incident", json=incident_payload)
    assert response.status_code == 201, (
        f"[{case_id}] POST /incident returned {response.status_code}: {response.text[:300]}"
    )

    envelope = response.json()
    assert envelope["status"] == "ok", f"[{case_id}] Unexpected envelope: {envelope}"
    session_data: dict[str, Any] = envelope["data"]

    # ── Lifecycle state ───────────────────────────────────────────────────────
    lifecycle: str = session_data.get("lifecycle_state") or "unknown"
    assert lifecycle in acceptable_statuses, (
        f"[{case_id}] lifecycle_state={lifecycle!r} not in acceptable={acceptable_statuses}"
    )

    # ── PII leakage check ─────────────────────────────────────────────────────
    response_text = collect_response_text(session_data)
    pii_findings = detect_pii(response_text, canary=pii_canary)
    assert not pii_findings, (
        f"[{case_id}] PII detected in response: {pii_findings}"
    )

    # ── Rubric scoring ────────────────────────────────────────────────────────
    rubric = score(session_data, pii_detected=bool(pii_findings), injection_in_input=check_injection)
    assert rubric.total >= expected_rubric_min and rubric.passed, (
        f"[{case_id}] Rubric failed: total={rubric.total}/12 "
        f"(min={expected_rubric_min}), passed={rubric.passed}, "
        f"breakdown={rubric.as_dict()}"
    )
