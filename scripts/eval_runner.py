"""Eval runner for AgentOps Triage PoC (EVALS.md §5).

Loads all incident fixtures from tests/fixtures/incidents/*.json, submits each
to the triage API, scores the response with the Plan Quality Rubric, checks for
PII leakage, and writes per-case results to tests/evals/outputs/<run_id>/results.jsonl
plus a human-readable summary to eval_report.md.

Usage (against a live server):
    python scripts/eval_runner.py

Usage (against a specific server):
    python scripts/eval_runner.py --base-url http://127.0.0.1:8000

Usage (subset of fixtures):
    python scripts/eval_runner.py --fixture normal_payments_5xx

Exit code: 0 if all cases pass, 1 if any case fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.evals.pii_detector import collect_response_text, detect_pii  # noqa: E402
from tests.evals.rubric import RubricScores, score  # noqa: E402

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "incidents"
OUTPUTS_DIR = PROJECT_ROOT / "tests" / "evals" / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run eval suite against the triage API.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the running API server (default: http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        metavar="NAME",
        help="Fixture name (without .json) to run. May be repeated. Defaults to all.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout per request in seconds (default: 60).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for results.jsonl and eval_report.md. "
             "Defaults to tests/evals/outputs/<run_id>/.",
    )
    return parser.parse_args()


def load_fixtures(names: list[str] | None) -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    """Return (fixture_name, fixture_data) pairs."""
    all_files = sorted(FIXTURES_DIR.glob("*.json"))
    if not all_files:
        raise SystemExit(f"No fixture files found in {FIXTURES_DIR}")

    if names:
        requested = set(names)
        selected = [(f.stem, f) for f in all_files if f.stem in requested]
        missing = requested - {stem for stem, _ in selected}
        if missing:
            available = ", ".join(f.stem for f in all_files)
            raise SystemExit(f"Unknown fixture(s): {', '.join(sorted(missing))}. Available: {available}")
    else:
        selected = [(f.stem, f) for f in all_files]

    result: list[tuple[str, dict]] = []
    for name, path in selected:
        with path.open() as fh:
            result.append((name, json.load(fh)))
    return result


def run_case(
    client: httpx.Client,
    case_id: str,
    fixture: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Submit one fixture to /incident and return a result record."""
    eval_meta: dict = fixture.get("_eval") or {}  # type: ignore[type-arg]
    incident_payload: dict = fixture["incident"]  # type: ignore[type-arg]

    expected_status: str = eval_meta.get("expected_status", "completed")
    acceptable_statuses: list[str] = eval_meta.get(
        "acceptable_statuses", [expected_status]
    )
    expected_rubric_min: int = eval_meta.get("expected_rubric_min_score", 8)
    pii_canary: str | None = eval_meta.get("pii_canary")
    check_injection: bool = eval_meta.get("check_injection_blocked", False)

    started = monotonic()
    try:
        resp = client.post("/incident", json=incident_payload)
        ttfa_ms = int((monotonic() - started) * 1000)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return {
            "case_id": case_id,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            "passed": False,
            "ttfa_ms": int((monotonic() - started) * 1000),
        }
    except httpx.RequestError as exc:
        return {
            "case_id": case_id,
            "error": f"Request failed: {exc}",
            "passed": False,
            "ttfa_ms": int((monotonic() - started) * 1000),
        }

    payload = resp.json()
    if payload.get("status") != "ok":
        return {
            "case_id": case_id,
            "error": f"Unexpected envelope status: {payload.get('status')}",
            "passed": False,
            "ttfa_ms": ttfa_ms,
        }

    session_data: dict = payload["data"]  # type: ignore[type-arg]
    lifecycle: str = session_data.get("lifecycle_state") or "unknown"

    # ── Tool stats ────────────────────────────────────────────────────────────
    tool_calls: list[dict] = session_data.get("tool_calls") or []  # type: ignore[type-arg]
    tool_calls_total = len(tool_calls)
    tool_calls_failed = sum(
        1 for tc in tool_calls if tc.get("status") not in ("success",)
    )
    fallback_used = lifecycle == "partial_completed"

    # ── PII leakage check ─────────────────────────────────────────────────────
    response_text = collect_response_text(session_data)
    pii_findings = detect_pii(response_text, canary=pii_canary)
    pii_detected = bool(pii_findings)

    # ── Rubric scoring ────────────────────────────────────────────────────────
    rubric: RubricScores = score(
        session_data,
        pii_detected=pii_detected,
        injection_in_input=check_injection,
    )

    # ── Pass / fail ───────────────────────────────────────────────────────────
    status_ok = lifecycle in acceptable_statuses
    rubric_ok = rubric.total >= expected_rubric_min and rubric.passed
    pii_ok = not pii_detected
    case_passed = status_ok and rubric_ok and pii_ok

    return {
        "case_id": case_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "ttfa_ms": ttfa_ms,
        "lifecycle_state": lifecycle,
        "expected_status": expected_status,
        "acceptable_statuses": acceptable_statuses,
        "status_ok": status_ok,
        "tool_calls_total": tool_calls_total,
        "tool_calls_failed": tool_calls_failed,
        "fallback_used": fallback_used,
        "pii_detected": pii_detected,
        "pii_findings": pii_findings,
        "policy_violation": False,  # Would require deeper analysis; placeholder
        "rubric_scores": rubric.as_dict(),
        "rubric_passed": rubric.passed,
        "rubric_ok": rubric_ok,
        "expected_rubric_min": expected_rubric_min,
        "passed": case_passed,
        "failure_reasons": _failure_reasons(
            status_ok=status_ok,
            rubric_ok=rubric_ok,
            pii_ok=pii_ok,
        ),
    }


def _failure_reasons(*, status_ok: bool, rubric_ok: bool, pii_ok: bool) -> list[str]:
    reasons: list[str] = []
    if not status_ok:
        reasons.append("unexpected_lifecycle_state")
    if not rubric_ok:
        reasons.append("rubric_score_below_threshold")
    if not pii_ok:
        reasons.append("pii_leakage_detected")
    return reasons


def write_results(output_dir: Path, results: list[dict]) -> None:  # type: ignore[type-arg]
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "results.jsonl"
    with jsonl_path.open("w") as fh:
        for record in results:
            fh.write(json.dumps(record) + "\n")

    report_path = output_dir / "eval_report.md"
    _write_markdown_report(report_path, results)

    print(f"\nResults written to: {output_dir}")
    print(f"  {jsonl_path.name}")
    print(f"  {report_path.name}")


def _write_markdown_report(path: Path, results: list[dict]) -> None:  # type: ignore[type-arg]
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed

    pii_cases = [r["case_id"] for r in results if r.get("pii_detected")]
    tool_total = sum(r.get("tool_calls_total", 0) for r in results)
    tool_failed = sum(r.get("tool_calls_failed", 0) for r in results)
    tool_success_rate = (
        f"{(tool_total - tool_failed) / tool_total:.1%}" if tool_total else "N/A"
    )
    fallback_count = sum(1 for r in results if r.get("fallback_used"))

    avg_rubric = (
        sum(r.get("rubric_scores", {}).get("total", 0) for r in results) / total
        if total else 0
    )
    avg_ttfa = (
        sum(r.get("ttfa_ms", 0) for r in results) / total if total else 0
    )

    lines: list[str] = [
        "# Eval Report — AgentOps Triage PoC",
        "",
        f"Run time: {datetime.now(UTC).isoformat()}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Cases | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {failed} |",
        f"| Pass rate | {passed / total:.1%} |",
        f"| Avg rubric score | {avg_rubric:.1f} / 12 |",
        f"| Avg TTFA | {avg_ttfa:.0f} ms |",
        f"| Tool success rate | {tool_success_rate} |",
        f"| Fallback (partial_completed) | {fallback_count} / {total} |",
        f"| PII leakage cases | {len(pii_cases)} |",
        "",
        "## Per-case Results",
        "",
        "| Case | Status | Rubric | PII | TTFA ms | Pass |",
        "|------|--------|--------|-----|---------|------|",
    ]

    for r in results:
        if r.get("error"):
            lines.append(
                f"| {r['case_id']} | ERROR | - | - | {r.get('ttfa_ms', '-')} | FAIL |"
            )
            continue
        rubric = r.get("rubric_scores", {})
        total_score = rubric.get("total", "-")
        status = r.get("lifecycle_state", "?")
        pii = "YES" if r.get("pii_detected") else "no"
        ttfa = r.get("ttfa_ms", "-")
        passed_marker = "PASS" if r.get("passed") else "FAIL"
        lines.append(
            f"| {r['case_id']} | {status} | {total_score}/12 | {pii} | {ttfa} | {passed_marker} |"
        )

    if pii_cases:
        lines += ["", "## PII Leakage Cases", ""]
        for c in pii_cases:
            rec = next(r for r in results if r["case_id"] == c)
            lines.append(f"- **{c}**: {', '.join(rec.get('pii_findings', []))}")

    failed_cases = [r for r in results if not r.get("passed") and not r.get("error")]
    if failed_cases:
        lines += ["", "## Failure Details", ""]
        for r in failed_cases:
            reasons = r.get("failure_reasons") or []
            rubric = r.get("rubric_scores") or {}
            lines.append(f"### {r['case_id']}")
            lines.append(f"- Lifecycle: `{r.get('lifecycle_state')}`")
            lines.append(f"- Reasons: {', '.join(reasons) or 'see rubric'}")
            lines.append(f"- Rubric breakdown: {rubric}")
            lines.append("")

    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    fixtures = load_fixtures(args.fixtures)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output_dir = args.output_dir or (OUTPUTS_DIR / run_id)

    print(f"Eval run: {run_id}")
    print(f"Server:   {args.base_url}")
    print(f"Cases:    {len(fixtures)}")
    print()

    results: list[dict] = []  # type: ignore[type-arg]

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for name, fixture in fixtures:
            print(f"  [{name}] ... ", end="", flush=True)
            result = run_case(client, case_id=name, fixture=fixture)
            results.append(result)

            if result.get("error"):
                print(f"ERROR: {result['error']}")
            else:
                rubric_total = result.get("rubric_scores", {}).get("total", "?")
                status = result.get("lifecycle_state", "?")
                marker = "PASS" if result.get("passed") else "FAIL"
                print(f"{marker} ({status}, rubric={rubric_total}/12, ttfa={result.get('ttfa_ms')}ms)")

    write_results(output_dir, results)

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
