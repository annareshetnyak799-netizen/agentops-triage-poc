import pytest

from src.llm.base import LLMAnalysisInput
from src.llm.mock_adapter import MockLLMAdapter
from src.observability.metrics import metrics_registry


@pytest.mark.anyio
async def test_mock_llm_adapter_returns_structured_analysis() -> None:
    adapter = MockLLMAdapter()
    success_before = metrics_registry.get("llm_structured_success_total")

    result = await adapter.analyze(
        LLMAnalysisInput(
            prompt="Analyze safely.",
            incident_title="High 5xx rate",
            service="payments-api",
            summary="Error rate increased after deploy",
            observations=[
                "Retrieved mock metrics for service=payments-api in environment=prod.",
                "Retrieved mock logs for service=payments-api in environment=prod.",
            ],
            refs=[
                "runbooks/payments-api.md",
                "runbooks/5xx-spike.md",
            ],
        )
    )

    assert "payments-api" in result.summary
    # G6: mock adapter must return ≥2 distinct hypotheses (rubric criterion 2, EVALS.md §3).
    assert len(result.hypotheses) >= 2
    assert len(result.next_steps) >= 1
    assert metrics_registry.get("llm_structured_success_total") == success_before + 1


@pytest.mark.anyio
async def test_mock_llm_adapter_adds_rollback_step_when_summary_requires_it() -> None:
    adapter = MockLLMAdapter()

    result = await adapter.analyze(
        LLMAnalysisInput(
            prompt="Analyze safely.",
            incident_title="High 5xx rate",
            service="payments-api",
            summary="Rollback may be needed after deploy",
            observations=[],
            refs=[],
        )
    )

    assert result.next_steps[0] == "Roll back the latest production deploy."
    # Rollback scenario should still produce ≥2 hypotheses.
    assert len(result.hypotheses) >= 2
