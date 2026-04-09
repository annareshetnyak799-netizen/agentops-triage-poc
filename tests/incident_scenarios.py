from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentScenario:
    name: str
    payload: dict[str, object]
    expected_status: str
    expected_ref: str
    acceptable_statuses: tuple[str, ...]


SCENARIOS: tuple[IncidentScenario, ...] = (
    IncidentScenario(
        name="payments_dependency_degradation",
        payload={
            "title": "Payments timeout spike",
            "service": "payments-api",
            "severity": "P1",
            "timestamp": "2026-04-08T12:00:00Z",
            "summary": (
                "Payment failures increased after a deploy and upstream timeouts "
                "are appearing on the /charge path."
            ),
            "signals": [
                "5xx > 12%",
                "PaymentProviderTimeout in /charge",
                "latency p95 up 3x",
            ],
            "environment": "prod",
            "reporter": "oncall-engineer",
            "alert_payload": {},
            "links": [],
        },
        expected_status="completed",
        expected_ref="kb/runbooks/payments-api.md",
        acceptable_statuses=("completed", "waiting_approval"),
    ),
    IncidentScenario(
        name="inventory_latency_regression",
        payload={
            "title": "Inventory read latency regression",
            "service": "inventory-api",
            "severity": "P2",
            "timestamp": "2026-04-08T12:05:00Z",
            "summary": (
                "Latency increased after a release and item availability checks "
                "are timing out for some requests."
            ),
            "signals": [
                "latency p95 up 2.5x",
                "timeouts on /availability",
                "request queue depth rising",
            ],
            "environment": "prod",
            "reporter": "sre-bot",
            "alert_payload": {},
            "links": [],
        },
        expected_status="completed",
        expected_ref="kb/runbooks/inventory-api.md",
        acceptable_statuses=("completed",),
    ),
    IncidentScenario(
        name="checkout_deploy_rollback_candidate",
        payload={
            "title": "Checkout failure surge after deploy",
            "service": "checkout-api",
            "severity": "P1",
            "timestamp": "2026-04-08T12:10:00Z",
            "summary": (
                "Rollback may be needed after deploy because checkout failures "
                "spiked and order submissions are failing."
            ),
            "signals": [
                "5xx > 18%",
                "timeouts on /submit-order",
                "customer checkout failures rising",
            ],
            "environment": "prod",
            "reporter": "oncall-engineer",
            "alert_payload": {},
            "links": [],
        },
        expected_status="waiting_approval",
        expected_ref="kb/runbooks/checkout-api.md",
        acceptable_statuses=("waiting_approval", "completed"),
    ),
)


def scenario_names() -> list[str]:
    return [scenario.name for scenario in SCENARIOS]
