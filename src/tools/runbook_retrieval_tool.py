from __future__ import annotations

from time import monotonic

from src.domain.enums import ToolCallStatus
from src.tools.base import BaseTool, ToolRequest, ToolResult


RUNBOOK_PROFILES: dict[str, list[dict[str, str]]] = {
    "payments-api": [
        {
            "title": "Payments API incident triage",
            "content": (
                "Correlate error-rate increase with deploy timeline. "
                "Validate upstream payment provider health before rollback."
            ),
            "ref": "runbooks/payments-api.md",
        },
        {
            "title": "5xx spike investigation",
            "content": (
                "Check whether 5xx increase is isolated to a single endpoint. "
                "Review dependency timeout patterns and retry saturation."
            ),
            "ref": "runbooks/5xx-spike.md",
        },
    ],
    "inventory-api": [
        {
            "title": "Inventory API latency regression",
            "content": (
                "Correlate release timing with read replica lag, cache misses, "
                "and availability lookup slowdowns before any rollback decision."
            ),
            "ref": "runbooks/inventory-api.md",
        },
        {
            "title": "Latency spike investigation",
            "content": (
                "Check whether latency is isolated to /availability and validate "
                "cache behavior, replica health, and queue depth."
            ),
            "ref": "runbooks/latency-spike.md",
        },
    ],
    "checkout-api": [
        {
            "title": "Checkout API incident triage",
            "content": (
                "Correlate checkout failures with deploy timing and payment "
                "authorization health before considering rollback."
            ),
            "ref": "runbooks/checkout-api.md",
        },
        {
            "title": "5xx spike investigation",
            "content": (
                "Check whether failures concentrate on /submit-order and review "
                "retry saturation, downstream auth failures, and user impact."
            ),
            "ref": "runbooks/5xx-spike.md",
        },
    ],
}


class RunbookRetrievalTool(BaseTool):
    name = "runbook_retrieval_tool"

    async def execute(self, request: ToolRequest) -> ToolResult:
        started_at = monotonic()

        service = request.payload.get("service", "unknown-service")

        latency_ms = int((monotonic() - started_at) * 1000)
        snippets = RUNBOOK_PROFILES.get(
            service,
            [
                {
                    "title": "Generic service triage",
                    "content": (
                        "Correlate the incident window with recent deploys, dependency "
                        "health, and endpoint-specific degradation before risky actions."
                    ),
                    "ref": "runbooks/service-triage.md",
                },
                {
                    "title": "Latency and 5xx investigation",
                    "content": (
                        "Review endpoint concentration, timeout patterns, retry behavior, "
                        "and immediate customer impact."
                    ),
                    "ref": "runbooks/5xx-spike.md",
                },
            ],
        )

        return ToolResult(
            tool_name=self.name,
            status=ToolCallStatus.SUCCESS,
            latency_ms=latency_ms,
            summary=(
                f"Retrieved {len(snippets)} relevant runbook snippets for {service}. "
                "Suggested actions include checking deploy correlation, dependency health, "
                "endpoint-specific failures, and retry saturation."
            ),
            data={
                "service": service,
                "snippets": snippets,
            },
        )
