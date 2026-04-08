from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from src.domain.enums import ApprovalDecision, SessionStatus
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
from src.orchestrator.transitions import validate_transition


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionView] = {}
        self._traces: dict[str, list[TraceStep]] = {}
        self._approval_inputs: dict[str, ApprovalInput] = {}

    def create_session(self, incident: IncidentInput) -> SessionView:
        now = datetime.now(UTC)
        session = SessionView(
            session_id=str(uuid4()),
            status=SessionStatus.NEW,
            created_at=now,
            updated_at=now,
            incident=incident,
        )
        self._sessions[session.session_id] = session
        self._traces[session.session_id] = [
            TraceStep(
                step_type="session_created",
                status=SessionStatus.NEW.value,
                details="Session created from incident input.",
                metadata={
                    "service": incident.service,
                    "severity": incident.severity.value,
                },
            )
        ]
        return deepcopy(session)

    def get_session(self, session_id: str) -> SessionView | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return deepcopy(session)

    def get_trace(self, session_id: str) -> list[TraceStep] | None:
        trace = self._traces.get(session_id)
        if trace is None:
            return None
        return deepcopy(trace)

    def update_status(
        self,
        session_id: str,
        next_status: SessionStatus,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        previous_status = session.status
        validate_transition(session.status, next_status)
        session.status = next_status
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="status_transition",
            status=next_status.value,
            details=f"Transitioned to {next_status.value}.",
            metadata={
                "from_status": previous_status.value,
                "to_status": next_status.value,
            },
        )
        return deepcopy(session)

    def add_observation(
        self,
        session_id: str,
        observation: Observation,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.observations.append(observation)
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="observation",
            status=session.status.value,
            details=f"Added observation from {observation.source}.",
            metadata={
                "source": observation.source,
                "refs_count": str(len(observation.refs)),
            },
        )
        return deepcopy(session)

    def add_tool_call(
        self,
        session_id: str,
        tool_call: ToolCallRecord,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.tool_calls.append(tool_call)
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="tool_call",
            status=tool_call.status.value,
            details=f"Executed {tool_call.tool_name}.",
            metadata={
                "tool_name": tool_call.tool_name,
                "latency_ms": str(tool_call.latency_ms),
                "error_type": tool_call.error_type or "",
            },
        )
        return deepcopy(session)

    def set_final_report(
        self,
        session_id: str,
        final_report: FinalReport,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.final_report = final_report
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="report",
            status=session.status.value,
            details="Final report stored.",
            metadata={
                "hypotheses_count": str(len(final_report.hypotheses)),
                "next_steps_count": str(len(final_report.next_steps)),
                "refs_count": str(len(final_report.refs)),
            },
        )
        return deepcopy(session)

    def set_approval_request(
        self,
        session_id: str,
        approval_request: ApprovalRequest,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.approval_request = approval_request
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="approval_request",
            status=session.status.value,
            details=approval_request.reason,
            metadata={
                "recommended_action": approval_request.recommended_action,
            },
        )
        return deepcopy(session)

    def apply_approval(
        self,
        session_id: str,
        approval_input: ApprovalInput,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        if session.status != SessionStatus.WAITING_APPROVAL:
            raise ValueError("Approval can only be applied in waiting_approval state.")

        self._approval_inputs[session_id] = approval_input

        next_status = (
            SessionStatus.COMPLETED
            if approval_input.decision == ApprovalDecision.APPROVED
            else SessionStatus.PARTIAL_COMPLETED
        )
        session = self.update_status(session_id, next_status)
        self.append_trace(
            session_id=session_id,
            step_type="approval_decision",
            status=approval_input.decision.value,
            details=approval_input.comment or "Approval decision recorded.",
            metadata={
                "decision": approval_input.decision.value,
            },
        )
        return session

    def append_trace(
        self,
        session_id: str,
        step_type: str,
        status: str,
        details: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._traces.setdefault(session_id, []).append(
            TraceStep(
                step_type=step_type,
                status=status,
                details=details,
                metadata=metadata or {},
            )
        )



