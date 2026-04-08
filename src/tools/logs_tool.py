from __future__ import annotations

from time import monotonic

from src.domain.enums import ToolCallStatus
from src.tools.base import BaseTool, ToolRequest, ToolResult


LOG_PROFILES: dict[str, dict[str, object]] = {
    "payments-api": {
        "endpoint": "/charge",
        "error_signatures": [
            "PaymentProviderTimeout",
            "RetryBudgetExceeded",
            "UpstreamDependencyUnavailable",
        ],
        "entries": [
            "PaymentProviderTimeout after deploy in /charge",
            "RetryBudgetExceeded for upstream dependency",
            "UpstreamDependencyUnavailable from provider gateway",
        ],
    },
    "inventory-api": {
        "endpoint": "/availability",
        "error_signatures": [
            "InventoryReadTimeout",
            "CacheMissStorm",
            "ReplicaLagThresholdExceeded",
        ],
        "entries": [
            "InventoryReadTimeout while checking /availability",
            "CacheMissStorm on hot SKU lookups after release",
            "ReplicaLagThresholdExceeded for inventory read replica",
        ],
    },
    "checkout-api": {
        "endpoint": "/submit-order",
        "error_signatures": [
            "OrderSubmissionTimeout",
            "RetryBudgetExceeded",
            "PaymentAuthorizationUnavailable",
        ],
        "entries": [
            "OrderSubmissionTimeout after deploy in /submit-order",
            "RetryBudgetExceeded during downstream checkout retries",
            "PaymentAuthorizationUnavailable from checkout dependency chain",
        ],
    },
}


class LogsTool(BaseTool):
    name = "logs_tool"

    async def execute(self, request: ToolRequest) -> ToolResult:
        started_at = monotonic()

        service = request.payload.get("service", "unknown-service")
        environment = request.payload.get("environment", "unknown")

        latency_ms = int((monotonic() - started_at) * 1000)
        profile = LOG_PROFILES.get(
            service,
            {
                "endpoint": "/health",
                "error_signatures": [
                    "RequestTimeout",
                    "RetryBudgetExceeded",
                    "UpstreamDependencyUnavailable",
                ],
                "entries": [
                    "RequestTimeout on /health dependency path",
                    "RetryBudgetExceeded while retrying upstream requests",
                    "UpstreamDependencyUnavailable from shared platform service",
                ],
            },
        )
        error_signatures = profile["error_signatures"]
        endpoint = profile["endpoint"]

        return ToolResult(
            tool_name=self.name,
            status=ToolCallStatus.SUCCESS,
            latency_ms=latency_ms,
            summary=(
                f"{service} in {environment}: logs show repeated "
                f"{error_signatures[0]}, {error_signatures[1]} and "
                f"{error_signatures[2]} after the latest deploy. "
                f"Errors are concentrated around the {endpoint} endpoint."
            ),
            data={
                "service": service,
                "environment": environment,
                "entries": profile["entries"],
                "error_signatures": error_signatures,
                "window": "last_15m",
            },
        )
