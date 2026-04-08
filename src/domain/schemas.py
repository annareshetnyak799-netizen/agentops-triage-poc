from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import (
    ApprovalDecision,
    SessionStatus,
    Severity,
    ToolCallStatus,
)


class IncidentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=100)
    severity: Severity
    timestamp: datetime
    summary: str = Field(min_length=1, max_length=2_000)

    signals: list[str] = Field(default_factory=list)
    environment: str | None = Field(default=None, max_length=50)
    reporter: str | None = Field(default=None, max_length=100)

    alert_payload: dict[str, Any] = Field(default_factory=dict)
    links: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class Observation(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2_000)
    refs: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ToolCallRecord(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    status: ToolCallStatus
    latency_ms: int = Field(ge=0)
    error_type: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")


class ApprovalRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1_000)
    recommended_action: str = Field(min_length=1, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


class ApprovalInput(BaseModel):
    decision: ApprovalDecision
    comment: str | None = Field(default=None, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


class FinalReport(BaseModel):
    summary: str = Field(min_length=1, max_length=4_000)
    hypotheses: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SessionView(BaseModel):
    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    incident: IncidentInput
    observations: list[Observation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    approval_request: ApprovalRequest | None = None
    final_report: FinalReport | None = None

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

    model_config = ConfigDict(extra="forbid")

class TraceStep(BaseModel):
    step_type: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    details: str = Field(min_length=1, max_length=2_000)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")



class ApprovalView(BaseModel):
    session_id: str
    status: SessionStatus
    decision: ApprovalDecision
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")

class RootResponse(BaseModel):
    service: str
    version: str
    environment: str
    docs_url: str
    health_url: str
    metrics_url: str

    model_config = ConfigDict(extra="forbid")
