from __future__ import annotations

from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, LLMAnalysisOutput


class RealLLMAdapter(BaseLLMAdapter):
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
            "Generic RealLLMAdapter is not implemented. "
            f"provider={self._provider}, model={self._model}"
        )
        raise NotImplementedError(msg)

