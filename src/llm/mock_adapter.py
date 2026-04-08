from __future__ import annotations

from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, LLMAnalysisOutput
from src.observability.metrics import metrics_registry


class MockLLMAdapter(BaseLLMAdapter):
    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        metrics_registry.increment("llm_calls_total")
        metrics_registry.increment("llm_structured_success_total")
        rollback_needed = "rollback" in payload.summary.lower()

        next_steps = [
            "Check deploy timeline for the affected service.",
            "Validate upstream dependency health.",
            "Inspect correlated error logs around the incident window.",
        ]
        if rollback_needed:
            next_steps.insert(0, "Rollback the latest production deploy.")

        return LLMAnalysisOutput(
            summary=(
                f"Initial triage completed for {payload.service}. "
                "Available observations suggest elevated error rate and "
                "dependency-related degradation."
            ),
            hypotheses=[
                "Recent deploy or upstream dependency issue caused elevated 5xx rate.",
            ],
            next_steps=next_steps,
        )
