from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import ToolCallStatus


class ToolRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ToolResult(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    status: ToolCallStatus
    latency_ms: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=2_000)
    data: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(extra="forbid")


class BaseTool(ABC):
    name: str

    @abstractmethod
    async def execute(self, request: ToolRequest) -> ToolResult:
        raise NotImplementedError
