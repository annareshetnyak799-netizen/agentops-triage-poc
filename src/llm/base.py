from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


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

