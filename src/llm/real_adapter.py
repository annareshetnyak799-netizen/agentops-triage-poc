from __future__ import annotations

from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, LLMAnalysisOutput


class RealLLMAdapter(BaseLLMAdapter):
    """Stub for non-OpenAI providers — not implemented in PoC scope.

    G26: this file exists as a factory fallback for provider strings other than "openai".
    For OpenAI, the factory routes to OpenAIRealLLMAdapter (openai_adapter.py).
    To add a new provider, subclass BaseLLMAdapter and register it in factory.py.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        timeout_s: int,
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        del payload

        msg = (
            f"RealLLMAdapter does not implement provider={self._provider!r}. "
            "Add a dedicated adapter and register it in src/llm/factory.py."
        )
        raise NotImplementedError(msg)

