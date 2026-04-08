from __future__ import annotations

from datetime import UTC, datetime
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


class IncidentSummary(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    service: str = Field(min_length=1, max_length=100)
    severity: Severity

    model_config = ConfigDict(extra="forbid")


class Observation(BaseModel):
    observation_id: str | None = Field(default=None, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    source_type: str | None = Field(default=None, max_length=100)
    source_ref: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    refs: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ToolCallRecord(BaseModel):
    tool_call_id: str | None = Field(default=None, max_length=200)
    tool_name: str = Field(min_length=1, max_length=100)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus
    normalized_status: str | None = Field(default=None, max_length=50)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    latency_ms: int = Field(ge=0)
    error_code: str | None = Field(default=None, max_length=100)
    error_type: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=2_000)
    normalized_output: dict[str, Any] = Field(default_factory=dict)
    raw_output_ref: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")


class ApprovalRequest(BaseModel):
    approval_id: str | None = Field(default=None, max_length=200)
    action_type: str | None = Field(default=None, max_length=200)
    reason: str = Field(min_length=1, max_length=1_000)
    risk_level: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)
    recommended_action: str = Field(min_length=1, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


class ApprovalInput(BaseModel):
    approval_id: str = Field(min_length=1, max_length=200)
    decision: ApprovalDecision
    comment: str | None = Field(default=None, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


class FinalReport(BaseModel):
    summary: str = Field(min_length=1, max_length=4_000)
    hypotheses: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    hypothesis_items: list[HypothesisView] = Field(default_factory=list)
    next_step_items: list[NextStepView] = Field(default_factory=list)
    ref_items: list[ReferenceView] = Field(default_factory=list)
    safety_note_items: list[SafetyEventView] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class HypothesisView(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=4_000)
    source: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(min_length=1, max_length=100)
    supporting_refs: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class NextStepView(BaseModel):
    priority: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=2_000)
    source: str = Field(min_length=1, max_length=100)
    rationale: str | None = Field(default=None, max_length=2_000)
    requires_approval: bool

    model_config = ConfigDict(extra="forbid")


class ReferenceView(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    snippet: str | None = Field(default=None, max_length=2_000)
    target_ref: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class ToolCallView(BaseModel):
    tool_call_id: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=2_000)
    normalized_output: dict[str, Any] = Field(default_factory=dict)
    has_normalized_output: bool = False
    raw_output_ref: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class SafetyEventView(BaseModel):
    safety_event_id: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2_000)
    severity: str = Field(min_length=1, max_length=50)
    related_ref: str | None = Field(default=None, max_length=500)
    created_at: datetime

    model_config = ConfigDict(extra="forbid")


class ApprovalRequestView(BaseModel):
    approval_id: str = Field(min_length=1, max_length=200)
    action_type: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1_000)
    risk_level: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=50)

    model_config = ConfigDict(extra="forbid")


class TriageReportView(BaseModel):
    incident_summary: IncidentSummary
    summary: str = Field(min_length=1, max_length=4_000)
    status: str = Field(min_length=1, max_length=100)
    hypotheses: list[HypothesisView] = Field(default_factory=list)
    next_steps: list[NextStepView] = Field(default_factory=list)
    refs: list[ReferenceView] = Field(default_factory=list)
    safety_notes: list[SafetyEventView] = Field(default_factory=list)
    approval_requests: list[ApprovalRequestView] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class InvestigationPlanView(BaseModel):
    plan_id: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    goal: str = Field(min_length=1, max_length=2_000)
    steps: list[str] = Field(default_factory=list)
    status: str = Field(min_length=1, max_length=100)
    created_at: datetime

    model_config = ConfigDict(extra="forbid")


class SessionStateView(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    lifecycle_state: str = Field(min_length=1, max_length=100)
    budget_remaining: int | None = Field(default=None, ge=0)
    last_completed_step: int | None = Field(default=None, ge=0)
    waiting_for_approval: bool = False
    partial_result: bool = False
    failure_reason: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")


class SessionView(BaseModel):
    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    iteration_count: int = Field(ge=1, default=1)
    llm_provider: str | None = Field(default=None, max_length=100)
    policy_mode: str | None = Field(default=None, max_length=100)
    budget_remaining: int | None = Field(default=None, ge=0)
    last_completed_step: int | None = Field(default=None, ge=0)
    waiting_for_approval: bool = False
    partial_result: bool = False
    failure_reason: str | None = Field(default=None, max_length=2_000)
    incident: IncidentInput
    investigation_plan: InvestigationPlanView | None = None
    observations: list[Observation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    safety_events: list[SafetyEventView] = Field(default_factory=list)
    approval_request: ApprovalRequest | None = None
    final_report: FinalReport | None = None

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

    model_config = ConfigDict(extra="forbid")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TraceStep(BaseModel):
    step_type: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    details: str = Field(min_length=1, max_length=2_000)
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")



class ApprovalView(BaseModel):
    session_id: str
    status: SessionStatus
    decision: ApprovalDecision
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")


class IncidentResponseData(BaseModel):
    session_id: str
    lifecycle_state: SessionStatus
    session_state: SessionStateView
    investigation_plan: InvestigationPlanView | None = None
    report: TriageReportView
    tool_calls: list[ToolCallView] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SessionResponseData(BaseModel):
    session_id: str
    lifecycle_state: SessionStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    iteration_count: int = Field(ge=0, default=1)
    llm_provider: str | None = Field(default=None, max_length=100)
    policy_mode: str | None = Field(default=None, max_length=100)
    session_state: SessionStateView
    investigation_plan: InvestigationPlanView | None = None
    report: TriageReportView
    tool_calls: list[ToolCallView] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class TraceResponseStep(BaseModel):
    step: int = Field(ge=1)
    type: str = Field(min_length=1, max_length=100)
    step_type: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1, max_length=2_000)
    details: str = Field(min_length=1, max_length=2_000)
    tool_name: str | None = Field(default=None, max_length=100)
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class TraceResponseData(BaseModel):
    session_id: str
    trace: list[TraceResponseStep] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ApprovalResponseData(BaseModel):
    session_id: str
    approval_id: str = Field(min_length=1, max_length=200)
    decision: ApprovalDecision
    lifecycle_state: SessionStatus
    report: TriageReportView

    model_config = ConfigDict(extra="forbid")

class RootResponse(BaseModel):
    service: str
    version: str
    environment: str
    docs_url: str
    health_url: str
    metrics_url: str

    model_config = ConfigDict(extra="forbid")
