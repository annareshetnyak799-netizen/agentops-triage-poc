from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from src.config import settings
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
from src.persistence.db import Base, create_engine_and_sessionmaker
from src.persistence.models import SessionRecord
from src.persistence.protocols import SessionRepository


class SQLiteSessionRepository(SessionRepository):
    def __init__(self, sqlite_url: str | None = None) -> None:
        db_url = sqlite_url or settings.sqlite_url
        self._engine, self._session_local = create_engine_and_sessionmaker(db_url)
        Base.metadata.create_all(bind=self._engine)

    def create_session(self, incident: IncidentInput) -> SessionView:
        now = datetime.now(UTC)
        session = SessionView(
            session_id=str(uuid4()),
            status=SessionStatus.NEW,
            created_at=now,
            updated_at=now,
            incident=incident,
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
        self._save(session, trace)
        return deepcopy(session)

    def get_session(self, session_id: str) -> SessionView | None:
        record = self._get_record(session_id)
        if record is None:
            return None
        return self._deserialize_session(record.session_json)

    def get_trace(self, session_id: str) -> list[TraceStep] | None:
        record = self._get_record(session_id)
        if record is None:
            return None
        return self._deserialize_trace(record.trace_json)

    def update_status(
        self,
        session_id: str,
        next_status: SessionStatus,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)
        previous_status = session.status
        validate_transition(session.status, next_status)

        session.status = next_status
        session.updated_at = datetime.now(UTC)
        trace.append(
            TraceStep(
                step_type="status_transition",
                status=next_status.value,
                details=f"Transitioned to {next_status.value}.",
                metadata={
                    "from_status": previous_status.value,
                    "to_status": next_status.value,
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def add_observation(
        self,
        session_id: str,
        observation: Observation,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)

        session.observations.append(observation)
        session.updated_at = datetime.now(UTC)
        trace.append(
            TraceStep(
                step_type="observation",
                status=session.status.value,
                details=f"Added observation from {observation.source}.",
                metadata={
                    "source": observation.source,
                    "refs_count": str(len(observation.refs)),
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def add_tool_call(
        self,
        session_id: str,
        tool_call: ToolCallRecord,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)

        session.tool_calls.append(tool_call)
        session.updated_at = datetime.now(UTC)
        trace.append(
            TraceStep(
                step_type="tool_call",
                status=tool_call.status.value,
                details=f"Executed {tool_call.tool_name}.",
                metadata={
                    "tool_name": tool_call.tool_name,
                    "latency_ms": str(tool_call.latency_ms),
                    "error_type": tool_call.error_type or "",
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def set_final_report(
        self,
        session_id: str,
        final_report: FinalReport,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)

        session.final_report = final_report
        session.updated_at = datetime.now(UTC)
        trace.append(
            TraceStep(
                step_type="report",
                status=session.status.value,
                details="Final report stored.",
                metadata={
                    "hypotheses_count": str(len(final_report.hypotheses)),
                    "next_steps_count": str(len(final_report.next_steps)),
                    "refs_count": str(len(final_report.refs)),
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def set_approval_request(
        self,
        session_id: str,
        approval_request: ApprovalRequest,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)

        session.approval_request = approval_request
        session.updated_at = datetime.now(UTC)
        trace.append(
            TraceStep(
                step_type="approval_request",
                status=session.status.value,
                details=approval_request.reason,
                metadata={
                    "recommended_action": approval_request.recommended_action,
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def apply_approval(
        self,
        session_id: str,
        approval_input: ApprovalInput,
    ) -> SessionView:
        session, trace = self._load_session_and_trace(session_id)

        if session.status != SessionStatus.WAITING_APPROVAL:
            raise ValueError("Approval can only be applied in waiting_approval state.")

        next_status = (
            SessionStatus.COMPLETED
            if approval_input.decision == ApprovalDecision.APPROVED
            else SessionStatus.PARTIAL_COMPLETED
        )

        validate_transition(session.status, next_status)
        session.status = next_status
        session.updated_at = datetime.now(UTC)

        trace.append(
            TraceStep(
                step_type="approval_decision",
                status=approval_input.decision.value,
                details=approval_input.comment or "Approval decision recorded.",
                metadata={
                    "decision": approval_input.decision.value,
                },
            )
        )
        self._save(session, trace)
        return deepcopy(session)

    def append_trace(
        self,
        session_id: str,
        step_type: str,
        status: str,
        details: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        session, trace = self._load_session_and_trace(session_id)
        trace.append(
            TraceStep(
                step_type=step_type,
                status=status,
                details=details,
                metadata=metadata or {},
            )
        )
        self._save(session, trace)

    def _get_record(self, session_id: str) -> SessionRecord | None:
        with self._session_local() as db:
            stmt = select(SessionRecord).where(SessionRecord.session_id == session_id)
            return db.scalar(stmt)

    def _load_session_and_trace(
        self,
        session_id: str,
    ) -> tuple[SessionView, list[TraceStep]]:
        record = self._get_record(session_id)
        if record is None:
            raise KeyError(f"Session not found: {session_id}")

        session = self._deserialize_session(record.session_json)
        trace = self._deserialize_trace(record.trace_json)
        return session, trace

    def _save(
        self,
        session: SessionView,
        trace: list[TraceStep],
    ) -> None:
        session_json = session.model_dump_json()
        trace_json = json.dumps(
            [step.model_dump(mode="json") for step in trace],
            ensure_ascii=False,
        )

        with self._session_local() as db:
            record = db.get(SessionRecord, session.session_id)
            if record is None:
                record = SessionRecord(
                    session_id=session.session_id,
                    status=session.status.value,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    session_json=session_json,
                    trace_json=trace_json,
                )
                db.add(record)
            else:
                record.status = session.status.value
                record.updated_at = session.updated_at
                record.session_json = session_json
                record.trace_json = trace_json

            db.commit()

    @staticmethod
    def _deserialize_session(payload: str) -> SessionView:
        return SessionView.model_validate_json(payload)

    @staticmethod
    def _deserialize_trace(payload: str) -> list[TraceStep]:
        raw = json.loads(payload)
        return [TraceStep.model_validate(item) for item in raw]

