from __future__ import annotations

from openai import APIError, APITimeoutError, AsyncOpenAI

from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, LLMAnalysisOutput


class OpenAIRealLLMAdapter(BaseLLMAdapter):
    def __init__(
        self,
        model: str,
        api_key: str,
        timeout_s: int,
    ) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_s,
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        try:
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
                            "If a risky action may be needed, express it as a recommendation that may require human approval. "
                            "Keep outputs concise, operational, and safe."
                        ),
                    },
                    {
                        "role": "user",
                        "content": payload.prompt,
                    },
                ],
                text_format=LLMAnalysisOutput,
            )
        except (APIError, APITimeoutError) as exc:
            return LLMAnalysisOutput(
                summary=(
                    "LLM provider call failed. Returning a safe degraded triage summary."
                ),
                hypotheses=[
                    f"Provider call failed: {exc.__class__.__name__}.",
                ],
                next_steps=[
                    "Review the collected observations and references manually.",
                    "Retry triage after confirming provider availability.",
                ],
            )

        parsed = response.output_parsed
        if parsed is not None:
            return parsed

        return LLMAnalysisOutput(
            summary=(
                "Structured LLM output was unavailable. "
                "Returning a safe fallback summary based on the current incident context."
            ),
            hypotheses=[
                "Provider returned an unstructured or unparsable response.",
            ],
            next_steps=[
                "Review the collected observations and references manually.",
                "Retry triage or switch to mock backend for debugging.",
            ],
        )


