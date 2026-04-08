import pytest

from src.llm.base import LLMAnalysisInput
from src.llm.mock_adapter import MockLLMAdapter


@pytest.mark.anyio
async def test_mock_llm_adapter_returns_structured_analysis() -> None:
    adapter = MockLLMAdapter()

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
    assert len(result.hypotheses) >= 1
    assert len(result.next_steps) >= 1


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

    assert result.next_steps[0] == "Rollback the latest production deploy."
