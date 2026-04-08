from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.incident_scenarios import IncidentScenario, SCENARIOS, scenario_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run incident quality scenarios against a live local API server.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the running API server.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenario_names",
        help="Scenario name to run. May be passed multiple times.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def select_scenarios(names: list[str] | None) -> list[IncidentScenario]:
    if not names:
        return list(SCENARIOS)

    requested = set(names)
    selected = [scenario for scenario in SCENARIOS if scenario.name in requested]

    missing = sorted(requested - {scenario.name for scenario in selected})
    if missing:
        available = ", ".join(scenario_names())
        raise SystemExit(
            f"Unknown scenario(s): {', '.join(missing)}. Available: {available}",
        )

    return selected


def format_items(items: Iterable[str]) -> str:
    values = list(items)
    if not values:
        return "none"
    return "; ".join(values)


def format_status_result(actual_status: str, acceptable_statuses: tuple[str, ...]) -> str:
    marker = "PASS" if actual_status in acceptable_statuses else "WARN"
    expected = ", ".join(acceptable_statuses)
    return f"{marker}: {actual_status} (acceptable: {expected})"


def main() -> int:
    args = parse_args()
    scenarios = select_scenarios(args.scenario_names)

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for scenario in scenarios:
            print(f"=== {scenario.name} ===")

            response = client.post("/incident", json=scenario.payload)
            response.raise_for_status()
            session = response.json()
            session_id = session["session_id"]

            trace_response = client.get(f"/sessions/{session_id}/trace")
            trace_response.raise_for_status()
            trace = trace_response.json()

            llm_step = next(
                (step for step in trace if step["step_type"] == "llm_analysis"),
                None,
            )
            policy_step = next(
                (step for step in trace if step["step_type"] == "policy_check"),
                None,
            )

            final_report = session.get("final_report") or {}
            approval_request = session.get("approval_request")

            print(
                "status: "
                f"{format_status_result(session['status'], scenario.acceptable_statuses)}"
            )
            print(f"service: {session['incident']['service']}")
            print(f"refs: {format_items(final_report.get('refs', []))}")
            print(f"summary: {final_report.get('summary', 'missing')}")
            print(f"hypotheses: {format_items(final_report.get('hypotheses', []))}")
            print(f"next_steps: {format_items(final_report.get('next_steps', []))}")

            if llm_step is not None:
                metadata = llm_step.get("metadata", {})
                print(
                    "llm: "
                    f"{metadata.get('backend', 'unknown')} "
                    f"provider={metadata.get('provider', 'unknown')} "
                    f"model={metadata.get('model', 'unknown')} "
                    f"structured={metadata.get('structured_output', 'unknown')}"
                )

            if approval_request is not None:
                print(f"approval_reason: {approval_request['reason']}")
                print(f"approval_action: {approval_request['recommended_action']}")

            if policy_step is not None:
                policy_metadata = policy_step.get("metadata", {})
                print(
                    "policy: "
                    f"status={policy_step.get('status', 'unknown')} "
                    f"trigger={policy_metadata.get('policy_trigger', 'unknown')}"
                )

            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
