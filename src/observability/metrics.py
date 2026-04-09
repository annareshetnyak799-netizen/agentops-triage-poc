from __future__ import annotations

from dataclasses import dataclass, field

# Prometheus metric type declarations (docs/SYSTEM-DESIGN.md §10.2).
# Each entry: metric_suffix → ("type", "help text").
# Suffixes without a leading "agentops_" — that prefix is added at render time.
_METRIC_META: dict[str, tuple[str, str]] = {
    # Latency histograms (observe_latency creates _bucket_le_* + _bucket_le_inf counters)
    "ttfa_ms": ("histogram", "Time-to-first-action in milliseconds"),
    "end_to_end_latency_ms": ("histogram", "End-to-end request latency in milliseconds"),
    # Counters — triage outcomes
    "triage_completed_total": ("counter", "Triage sessions completed successfully"),
    "triage_partial_completed_total": ("counter", "Triage sessions completed in degraded mode"),
    "triage_waiting_approval_total": ("counter", "Triage sessions waiting for human approval"),
    # Counters — tool calls
    "tool_calls_total": ("counter", "Total tool call attempts"),
    "tool_calls_failed": ("counter", "Tool call failures"),
    # Counters — LLM
    "llm_calls_total": ("counter", "Total LLM call attempts"),
    "llm_calls_failed": ("counter", "LLM call failures"),
    "llm_structured_success_total": ("counter", "LLM calls returning structured output"),
    "llm_fallback_total": ("counter", "LLM calls that fell back to degraded output"),
    # Counters — safety
    "pii_redactions_total": ("counter", "PII items redacted from text"),
    "policy_blocks_total": ("counter", "Policy checks that required approval"),
    "approval_requests_total": ("counter", "Approval requests created"),
    "untrusted_instruction_inputs_total": ("counter", "Inputs with detected instruction injection"),
    # Counters — reliability
    "fallback_total": ("counter", "Total fallback activations"),
    "degraded_sessions_total": ("counter", "Sessions that finished in degraded mode"),
    "session_budget_exhausted_total": ("counter", "Sessions where budget was exhausted"),
    # Counters — HTTP
    "http_requests_total": ("counter", "Total HTTP requests handled"),
    "http_requests_failed": ("counter", "HTTP requests that resulted in an error"),
}

LATENCY_BUCKETS_MS = (1000, 5000, 10000, 30000)


@dataclass(slots=True)
class MetricsRegistry:
    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def observe_latency(
        self,
        name: str,
        value_ms: int,
        buckets_ms: tuple[int, ...] = LATENCY_BUCKETS_MS,
    ) -> None:
        bounded = max(0, value_ms)
        self.increment(name, bounded)
        for bucket in buckets_ms:
            if bounded <= bucket:
                self.increment(f"{name}_bucket_le_{bucket}")
        self.increment(f"{name}_bucket_le_inf")

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)


metrics_registry = MetricsRegistry()
