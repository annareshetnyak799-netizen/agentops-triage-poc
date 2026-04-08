from __future__ import annotations

from typing import Protocol

from src.domain.enums import SessionStatus
from src.domain.schemas import (
    ApprovalInput,
    ApprovalRequest,
    FinalReport,
    IncidentInput,
    Observation,
    SessionView,
    ToolCallRecord,
    TraceStep,
)


class SessionRepository(Protocol):
    def create_session(self, incident: IncidentInput) -> SessionView:
        ...

    def get_session(self, session_id: str) -> SessionView | None:
        ...

    def get_trace(self, session_id: str) -> list[TraceStep] | None:
        ...

    def update_status(
        self,
        session_id: str,
        next_status: SessionStatus,
    ) -> SessionView:
        ...

    def add_observation(
        self,
        session_id: str,
        observation: Observation,
    ) -> SessionView:
        ...

    def add_tool_call(
        self,
        session_id: str,
        tool_call: ToolCallRecord,
    ) -> SessionView:
        ...

    def set_final_report(
        self,
        session_id: str,
        final_report: FinalReport,
    ) -> SessionView:
        ...

    def set_approval_request(
        self,
        session_id: str,
        approval_request: ApprovalRequest,
    ) -> SessionView:
        ...

    def apply_approval(
        self,
        session_id: str,
        approval_input: ApprovalInput,
    ) -> SessionView:
        ...
    
    def append_trace(
        self,
        session_id: str,
        step_type: str,
        status: str,
        details: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        ...

