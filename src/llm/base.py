from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

LLM_PROVIDER_FAILURE_SUMMARY = (
    "LLM provider call failed. Returning a safe degraded triage summary."
)
LLM_UNSTRUCTURED_OUTPUT_SUMMARY = (
    "Structured LLM output was unavailable. "
    "Returning a safe fallback summary based on the current incident context."
)


class LLMAnalysisInput(BaseModel):
    prompt: str = Field(min_length=1)
    incident_title: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    observations: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LLMAnalysisOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=4_000)
    hypotheses: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class BaseLLMAdapter(ABC):
    @abstractmethod
    async def analyze(self, payload: LLMAnalysisInput) -> LLMAnalysisOutput:
        raise NotImplementedError


def classify_llm_outcome(output: LLMAnalysisOutput) -> str:
    if output.summary == LLM_PROVIDER_FAILURE_SUMMARY:
        return "provider_fallback"
    if output.summary == LLM_UNSTRUCTURED_OUTPUT_SUMMARY:
        return "unstructured_fallback"
    return "structured_success"
