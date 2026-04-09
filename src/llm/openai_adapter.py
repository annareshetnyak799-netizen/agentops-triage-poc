from __future__ import annotations

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.llm.base import (
    BaseLLMAdapter,
    LLMAnalysisInput,
    LLMAnalysisOutput,
    LLM_PROVIDER_FAILURE_SUMMARY,
    LLM_UNSTRUCTURED_OUTPUT_SUMMARY,
)
from src.observability.logging import get_logger
from src.observability.metrics import metrics_registry

logger = get_logger(__name__)

# Errors that are safe to retry: transient network / capacity issues.
_RETRIABLE = (APITimeoutError, APIConnectionError, RateLimitError)


class OpenAIRealLLMAdapter(BaseLLMAdapter):
    """OpenAI adapter using the Responses API with structured output (responses.parse).

    G27: uses client.responses.parse (OpenAI Responses API, available since openai>=1.51).
    This differs from the Chat Completions API (beta.chat.completions.parse).
    Requires openai>=1.51 — pinned in pyproject.toml. If the Responses API is
    unavailable in your deployment, switch to client.beta.chat.completions.parse
    with the same LLMAnalysisOutput response_format.
    """

    def __init__(self, model: str, api_key: str, timeout_s: int) -> None:
        self._model = model
        self._timeout_s = timeout_s
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_s)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        metrics_registry.increment("llm_calls_total")

        try:
            # G8: bounded retry for transient / rate-limit errors only.
            # Non-retriable APIErrors (4xx auth, bad request) propagate immediately.
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type(_RETRIABLE),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.responses.parse(
                        model=self._model,
                        input=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an incident triage assistant for SRE and platform teams. "
                                    "Return a structured JSON result with summary, hypotheses, and next_steps. "
                                    "Ground every conclusion in the provided context. "
                                    "Do not invent unsupported facts. "
                                    "Prefer diagnostic and validation steps before remediation. "
                                    "Do not recommend autonomous risky actions. "
                                    "If a risky action may be needed, express it as a recommendation "
                                    "that may require human approval. "
                                    "Keep outputs concise, operational, and safe."
                                ),
                            },
                            {"role": "user", "content": payload.prompt},
                        ],
                        text_format=LLMAnalysisOutput,
                    )

        except _RETRIABLE as exc:
            # All retry attempts exhausted.
            logger.warning(
                "LLM provider call failed after retries.",
                extra={"step_type": "llm_analysis", "status": "failed", "error_type": type(exc).__name__},
            )
            metrics_registry.increment("llm_calls_failed")
            metrics_registry.increment("fallback_total")
            metrics_registry.increment("llm_fallback_total")
            return LLMAnalysisOutput(
                summary=LLM_PROVIDER_FAILURE_SUMMARY,
                hypotheses=[f"Provider call failed after retries: {type(exc).__name__}."],
                next_steps=[
                    "Review the collected observations and references manually.",
                    "Retry triage after confirming provider availability.",
                ],
            )
        except APIError as exc:
            # Non-retriable (4xx, bad request, auth).
            logger.warning(
                "LLM provider returned a non-retriable error.",
                extra={"step_type": "llm_analysis", "status": "failed", "error_type": type(exc).__name__},
            )
            metrics_registry.increment("llm_calls_failed")
            metrics_registry.increment("fallback_total")
            metrics_registry.increment("llm_fallback_total")
            return LLMAnalysisOutput(
                summary=LLM_PROVIDER_FAILURE_SUMMARY,
                hypotheses=[f"Provider error: {type(exc).__name__}."],
                next_steps=[
                    "Review the collected observations and references manually.",
                    "Retry triage after confirming provider availability.",
                ],
            )

        parsed = response.output_parsed
        if parsed is not None:
            metrics_registry.increment("llm_structured_success_total")
            return parsed

        metrics_registry.increment("fallback_total")
        metrics_registry.increment("llm_fallback_total")
        return LLMAnalysisOutput(
            summary=LLM_UNSTRUCTURED_OUTPUT_SUMMARY,
            hypotheses=["Provider returned an unstructured or unparsable response."],
            next_steps=[
                "Review the collected observations and references manually.",
                "Retry triage or switch to mock backend for debugging.",
            ],
        )
