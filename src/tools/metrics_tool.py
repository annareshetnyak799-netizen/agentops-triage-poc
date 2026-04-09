from __future__ import annotations

from time import monotonic

from src.domain.enums import ToolCallStatus
from src.tools.base import BaseTool, ToolRequest, ToolResult


METRICS_PROFILES: dict[str, dict[str, int | float | str]] = {
    "payments-api": {
        "focus_area": "/charge",
        "error_rate_before_pct": 0.8,
        "error_rate_after_pct": 12.4,
        "latency_p95_before_ms": 320,
        "latency_p95_after_ms": 1250,
        "requests_per_minute": 3200,
    },
    "inventory-api": {
        "focus_area": "/availability",
        "error_rate_before_pct": 0.2,
        "error_rate_after_pct": 3.1,
        "latency_p95_before_ms": 140,
        "latency_p95_after_ms": 410,
        "requests_per_minute": 5400,
    },
    "checkout-api": {
        "focus_area": "/submit-order",
        "error_rate_before_pct": 0.6,
        "error_rate_after_pct": 18.2,
        "latency_p95_before_ms": 280,
        "latency_p95_after_ms": 1480,
        "requests_per_minute": 2900,
    },
}


class MetricsTool(BaseTool):
    name = "metrics_tool"

    async def execute(self, request: ToolRequest) -> ToolResult:
        started_at = monotonic()

        service = request.payload.get("service", "unknown-service")
        environment = request.payload.get("environment", "unknown")

        latency_ms = int((monotonic() - started_at) * 1000)
        profile = METRICS_PROFILES.get(
            service,
            {
                "focus_area": "/health",
                "error_rate_before_pct": 0.4,
                "error_rate_after_pct": 4.8,
                "latency_p95_before_ms": 180,
                "latency_p95_after_ms": 620,
                "requests_per_minute": 1800,
            },
        )

        error_rate_before = profile["error_rate_before_pct"]
        error_rate_after = profile["error_rate_after_pct"]
        latency_p95_before = profile["latency_p95_before_ms"]
        latency_p95_after = profile["latency_p95_after_ms"]
        requests_per_minute = profile["requests_per_minute"]
        focus_area = profile["focus_area"]

        return ToolResult(
            tool_name=self.name,
            status=ToolCallStatus.SUCCESS,
            latency_ms=latency_ms,
            summary=(
                f"{service} in {environment}: error rate increased from "
                f"{error_rate_before}% to {error_rate_after}% and latency p95 "
                f"increased from {latency_p95_before}ms to {latency_p95_after}ms "
                f"over the last 15 minutes. Request volume is {requests_per_minute} rpm "
                f"with the sharpest degradation around {focus_area}."
            ),
            data={
                "service": service,
                "environment": environment,
                "metrics": {
                    "error_rate_before_pct": error_rate_before,
                    "error_rate_after_pct": error_rate_after,
                    "latency_p95_before_ms": latency_p95_before,
                    "latency_p95_after_ms": latency_p95_after,
                    "requests_per_minute": requests_per_minute,
                    "focus_area": focus_area,
                },
                "window": "last_15m",
            },
        )
