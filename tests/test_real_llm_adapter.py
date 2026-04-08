import pytest
from openai import APIError

from src.llm.base import LLMAnalysisInput, LLMAnalysisOutput
from src.llm.openai_adapter import OpenAIRealLLMAdapter
from src.llm.real_adapter import RealLLMAdapter
from src.observability.metrics import metrics_registry


@pytest.mark.anyio
async def test_generic_real_llm_adapter_raises_not_implemented() -> None:
    adapter = RealLLMAdapter(
        provider="unknown",
        model="test-model",
        api_key="test-key",
        timeout_s=10,
    )

    with pytest.raises(NotImplementedError, match="Generic RealLLMAdapter is not implemented"):
        await adapter.analyze(
            LLMAnalysisInput(
                prompt="Analyze safely.",
                incident_title="High 5xx rate",
                service="payments-api",
                summary="Error rate increased after deploy",
                observations=[],
                refs=[],
            )
        )


@pytest.mark.anyio
async def test_openai_adapter_returns_parsed_structured_output(monkeypatch) -> None:
    adapter = OpenAIRealLLMAdapter(
        model="gpt-5-mini",
        api_key="test-key",
        timeout_s=10,
    )

    class FakeParsedResponse:
        output_parsed = LLMAnalysisOutput(
            summary="Structured summary",
            hypotheses=["Hypothesis 1"],
            next_steps=["Step 1", "Step 2"],
        )

    async def fake_parse(**kwargs):
        assert kwargs["model"] == "gpt-5-mini"
        assert kwargs["text_format"] is LLMAnalysisOutput
        return FakeParsedResponse()

    monkeypatch.setattr(adapter._client.responses, "parse", fake_parse)
    success_before = metrics_registry.get("llm_structured_success_total")

    result = await adapter.analyze(
        LLMAnalysisInput(
            prompt="Analyze safely.",
            incident_title="High 5xx rate",
            service="payments-api",
            summary="Error rate increased after deploy",
            observations=["obs-1"],
            refs=["runbooks/payments-api.md"],
        )
    )

    assert result.summary == "Structured summary"
    assert result.hypotheses == ["Hypothesis 1"]
    assert result.next_steps == ["Step 1", "Step 2"]
    assert metrics_registry.get("llm_structured_success_total") == success_before + 1


@pytest.mark.anyio
async def test_openai_adapter_returns_safe_fallback_when_output_is_not_parsed(
    monkeypatch,
) -> None:
    adapter = OpenAIRealLLMAdapter(
        model="gpt-5-mini",
        api_key="test-key",
        timeout_s=10,
    )

    class FakeUnparsedResponse:
        output_parsed = None

    async def fake_parse(**kwargs):
        assert kwargs["model"] == "gpt-5-mini"
        return FakeUnparsedResponse()

    monkeypatch.setattr(adapter._client.responses, "parse", fake_parse)
    fallback_before = metrics_registry.get("llm_fallback_total")

    result = await adapter.analyze(
        LLMAnalysisInput(
            prompt="Analyze safely.",
            incident_title="High 5xx rate",
            service="payments-api",
            summary="Error rate increased after deploy",
            observations=["obs-1"],
            refs=["runbooks/payments-api.md"],
        )
    )

    assert "Structured LLM output was unavailable" in result.summary
    assert len(result.hypotheses) == 1
    assert len(result.next_steps) >= 1
    assert metrics_registry.get("llm_fallback_total") == fallback_before + 1


@pytest.mark.anyio
async def test_openai_adapter_returns_safe_fallback_on_provider_error(
    monkeypatch,
) -> None:
    adapter = OpenAIRealLLMAdapter(
        model="gpt-5-mini",
        api_key="test-key",
        timeout_s=10,
    )

    async def fake_parse(**kwargs):
        raise APIError("provider failure", request=None, body=None)

    monkeypatch.setattr(adapter._client.responses, "parse", fake_parse)
    fallback_before = metrics_registry.get("llm_fallback_total")

    result = await adapter.analyze(
        LLMAnalysisInput(
            prompt="Analyze safely.",
            incident_title="High 5xx rate",
            service="payments-api",
            summary="Error rate increased after deploy",
            observations=["obs-1"],
            refs=["runbooks/payments-api.md"],
        )
    )

    assert "LLM provider call failed" in result.summary
    assert len(result.hypotheses) == 1
    assert len(result.next_steps) >= 1
    assert metrics_registry.get("llm_fallback_total") == fallback_before + 1

