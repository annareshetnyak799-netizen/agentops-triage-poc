from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from src.config import settings
from src.domain.enums import ApprovalDecision, SessionStatus
from src.domain.schemas import (
    ApprovalInput,
    ApprovalRequest,
    FinalReport,
    IncidentInput,
    IncidentRecordView,
    InvestigationPlanView,
    Observation,
    SafetyEventView,
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
        incident_id = str(uuid5(NAMESPACE_URL, f"incident:{incident.service}:{incident.timestamp.isoformat()}:{incident.title}"))
        incident_record = IncidentRecordView(
            incident_id=incident_id,
            title=incident.title,
            service=incident.service,
            severity=incident.severity,
            timestamp=incident.timestamp,
            summary=incident.summary,
            signals=incident.signals,
            environment=incident.environment,
            reporter=incident.reporter,
            alert_payload=incident.alert_payload,
            links=incident.links,
            created_at=now,
        )
        session = SessionView(
            session_id=str(uuid4()),
            incident_id=incident_id,
            status=SessionStatus.NEW,
            created_at=now,
            updated_at=now,
            llm_provider=settings.llm_provider,
            policy_mode="strict",
            incident=incident,
            incident_record=incident_record,
        )
        trace = [
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
        self._sync_session_state(session, trace_len=len(trace))
        self._sessions[session.session_id] = session
        self._traces[session.session_id] = trace
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
        self._sync_session_state(
            session,
            trace_len=len(self._traces.get(session_id, [])),
        )
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
                "source_type": observation.source_type or "",
                "source_ref": observation.source_ref or "",
                "confidence": (
                    f"{observation.confidence:.2f}" if observation.confidence is not None else ""
                ),
                "observed_at": observation.observed_at.isoformat() if observation.observed_at else "",
                "refs_count": str(len(observation.refs)),
            },
        )
        return deepcopy(session)

    def update_session_state(
        self,
        session_id: str,
        *,
        budget_remaining: int | None = None,
        failure_reason: str | None = None,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.budget_remaining = budget_remaining
        session.failure_reason = failure_reason
        session.updated_at = datetime.now(UTC)
        self._sync_session_state(
            session,
            trace_len=len(self._traces.get(session_id, [])),
        )
        return deepcopy(session)

    def update_investigation_plan(
        self,
        session_id: str,
        plan: InvestigationPlanView,
    ) -> SessionView:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        session.investigation_plan = plan
        session.updated_at = datetime.now(UTC)
        self.append_trace(
            session_id=session_id,
            step_type="planning",
            status=plan.status,
            details="Investigation plan stored.",
            metadata={
                "plan_id": plan.plan_id,
                "plan_version": str(plan.version),
                "steps_count": str(len(plan.steps)),
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
        completed_at = datetime.now(UTC)
        started_at = completed_at - timedelta(milliseconds=tool_call.latency_ms)
        self._traces.setdefault(session_id, []).append(
            TraceStep(
                step_type="tool_call",
                status=tool_call.status.value,
                details=f"Executed {tool_call.tool_name}.",
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "tool_call_id": tool_call.tool_call_id or "",
                    "tool_name": tool_call.tool_name,
                    "normalized_status": tool_call.normalized_status or "",
                    "started_at": tool_call.started_at.isoformat(),
                    "completed_at": tool_call.completed_at.isoformat()
                    if tool_call.completed_at is not None
                    else "",
                    "latency_ms": str(tool_call.latency_ms),
                    "error_code": tool_call.error_code or "",
                    "error_type": tool_call.error_type or "",
                    "has_normalized_output": str(bool(tool_call.normalized_output)).lower(),
                },
            )
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

        final_report.normalize_legacy_fields()
        session.final_report = final_report
        session.safety_events = list(final_report.safety_note_items)
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
        session.waiting_for_approval = True
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
        if session.approval_request is None or session.approval_request.approval_id is None:
            raise ValueError("No pending approval request exists for this session.")
        if approval_input.approval_id != session.approval_request.approval_id:
            raise ValueError("Approval ID does not match the pending approval request.")

        self._approval_inputs[session_id] = approval_input
        session.approval_request.status = approval_input.decision.value
        session.iteration_count += 1
        session.updated_at = datetime.now(UTC)
        if session.final_report is not None:
            if approval_input.decision == ApprovalDecision.APPROVED:
                note = "Action was human-approved before continuation."
                severity = "low"
            else:
                note = "Suggested action was human-rejected and automatic continuation was limited."
                severity = "medium"
            session.final_report.safety_notes.append(note)
            session.final_report.safety_note_items.append(
                SafetyEventView(
                    safety_event_id=str(
                        uuid4()
                    ),
                    session_id=session.session_id,
                    type="policy",
                    message=note,
                    severity=severity,
                    related_ref="trace:approval_decision",
                    created_at=datetime.now(UTC),
                )
            )
            session.safety_events = list(session.final_report.safety_note_items)
        session.approval_request = None

        next_status = (
            SessionStatus.COMPLETED
            if approval_input.decision == ApprovalDecision.APPROVED
            else SessionStatus.PARTIAL_COMPLETED
        )
        self._sessions[session_id] = session
        session = self.update_status(session_id, next_status)
        self.append_trace(
            session_id=session_id,
            step_type="approval_decision",
            status=approval_input.decision.value,
            details=approval_input.comment or "Approval decision recorded.",
            metadata={
                "approval_id": approval_input.approval_id,
                "decision": approval_input.decision.value,
                "resulting_status": next_status.value,
                "comment_present": str(approval_input.comment is not None).lower(),
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
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        trace = self._traces.setdefault(session_id, [])
        trace.append(
            TraceStep(
                step_type=step_type,
                status=status,
                details=details,
                started_at=started_at or datetime.now(UTC),
                completed_at=completed_at or datetime.now(UTC),
                metadata=metadata or {},
            )
        )
        session = self._sessions.get(session_id)
        if session is not None:
            self._sync_session_state(session, trace_len=len(trace))

    @staticmethod
    def _sync_session_state(session: SessionView, *, trace_len: int) -> None:
        session.last_completed_step = trace_len
        session.waiting_for_approval = session.status == SessionStatus.WAITING_APPROVAL
        session.partial_result = session.status == SessionStatus.PARTIAL_COMPLETED
        if session.status in {
            SessionStatus.COMPLETED,
            SessionStatus.PARTIAL_COMPLETED,
        }:
            session.completed_at = session.completed_at or datetime.now(UTC)
        else:
            session.completed_at = None
