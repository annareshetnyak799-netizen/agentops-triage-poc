from __future__ import annotations

from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, LLMAnalysisOutput
from src.observability.metrics import metrics_registry


class MockLLMAdapter(BaseLLMAdapter):
    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        metrics_registry.increment("llm_calls_total")
        metrics_registry.increment("llm_structured_success_total")

        rollback_needed = "rollback" in payload.summary.lower()

        # Rubric criterion 2: always return ≥2 distinct hypotheses (docs/EVALS.md §3)
        hypotheses = [
            "Recent deploy or upstream dependency issue caused elevated error rate.",
            "Retry saturation from cascading timeouts amplified the initial degradation.",
        ]
        if rollback_needed:
            hypotheses.append(
                "Faulty deployment artifact requires rollback to restore service health."
            )

        next_steps = [
            "Check deploy timeline and correlate with error rate spike.",
            "Validate upstream dependency health and check service interconnects.",
            "Inspect correlated error logs around the incident window.",
        ]
        if rollback_needed:
            next_steps.insert(0, "Roll back the latest production deploy.")

        return LLMAnalysisOutput(
            summary=(
                f"Initial triage completed for {payload.service}. "
                "Available observations suggest elevated error rate and "
                "dependency-related degradation."
            ),
            hypotheses=hypotheses,
            next_steps=next_steps,
        )
