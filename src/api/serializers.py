from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid5, NAMESPACE_URL

from src.domain.enums import SessionStatus
from src.domain.schemas import (
    ApprovalRequestView,
    ApprovalResponseData,
    ApprovalView,
    FinalReport,
    HypothesisView,
    IncidentRecordView,
    IncidentResponseData,
    IncidentSummary,
    NextStepView,
    ReferenceView,
    SafetyEventView,
    SessionResponseData,
    SessionStateView,
    SessionView,
    ToolCallView,
    TraceResponseData,
    TraceResponseStep,
    TraceStep,
)
from src.safety.policy import find_risky_action


def _approval_id(session_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"approval:{session_id}"))


def _action_type(recommended_action: str) -> str:
    action = recommended_action.lower()
    if "roll back" in action or "rollback" in action or "rolling back" in action:
        return "rollback_deployment"
    if "restart" in action:
        return "restart_service"
    if "redeploy" in action or "revert" in action:
        return "redeploy_service"
    return "gated_action"


def _risk_level(recommended_action: str) -> str:
    action_type = _action_type(recommended_action)
    if action_type == "rollback_deployment":
        return "high"
    if action_type in {"restart_service", "redeploy_service"}:
        return "medium"
    return "medium"


def _trace_category(step_type: str) -> str:
    if step_type in {"planning", "prompt_build"}:
        return "planning"
    if step_type in {"retrieving", "executing_tools", "tool_call", "observation"}:
        return "tool_call"
    if step_type in {
        "context_assembly",
        "llm_analysis",
        "groundedness_check",
        "sanitization_check",
        "analyzing",
    }:
        return "analysis"
    if step_type in {"approval_request", "approval_decision", "policy_check"}:
        return "approval"
    if step_type in {"degradation"}:
        return "report"
    if step_type in {"report"}:
        return "report"
    return "session"


def _trace_duration_ms(item: TraceStep) -> int:
    duration = item.completed_at - item.started_at
    return max(0, int(duration.total_seconds() * 1000))


def _weakly_grounded(report: FinalReport) -> bool:
    return any(
        "groundedness" in note.lower() or "corroborat" in note.lower()
        for note in report.safety_notes
    )


def _hypothesis_confidence(index: int, *, weakly_grounded: bool = False) -> float:
    baseline = 0.85 - ((index - 1) * 0.1)
    if weakly_grounded:
        baseline -= 0.15
    return max(0.4, baseline)


def _hypothesis_status(index: int, *, weakly_grounded: bool = False) -> str:
    if weakly_grounded:
        return "weakened"
    if index == 1:
        return "active"
    return "weakened"


def _legacy_hypotheses_to_items(
    session: SessionView,
    report: FinalReport,
) -> list[HypothesisView]:
    supporting_refs = [ref.id for ref in (report.ref_items or _legacy_refs_to_items(report))]
    hypotheses: list[HypothesisView] = []
    weakly_grounded = _weakly_grounded(report)

    for index, statement in enumerate(report.hypotheses, start=1):
        hypotheses.append(
            HypothesisView(
                id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"hypothesis:{session.session_id}:{index}:{statement}",
                    )
                ),
                statement=statement,
                source="llm_analysis",
                confidence=_hypothesis_confidence(index, weakly_grounded=weakly_grounded),
                status=_hypothesis_status(index, weakly_grounded=weakly_grounded),
                supporting_refs=supporting_refs,
            )
        )

    return hypotheses


def _legacy_next_steps_to_items(report: FinalReport) -> list[NextStepView]:
    risky_action, _ = find_risky_action(report.next_steps)
    next_steps: list[NextStepView] = []

    for index, action in enumerate(report.next_steps, start=1):
        next_steps.append(
            NextStepView(
                priority=index,
                action=action,
                source="llm_analysis",
                rationale="Needed to reduce uncertainty and validate the current working hypotheses.",
                requires_approval=action == risky_action,
            )
        )

    return next_steps


def _legacy_refs_to_items(report: FinalReport) -> list[ReferenceView]:
    refs: list[ReferenceView] = []
    for index, ref in enumerate(report.refs, start=1):
        refs.append(
            ReferenceView(
                id=f"kb:{index}",
                type="kb_doc",
                source="runbook_retrieval_tool",
                title=ref.rsplit("/", maxsplit=1)[-1],
                snippet=ref,
            )
        )
    return refs


def _serialize_tool_calls(session: SessionView) -> list[ToolCallView]:
    tool_calls: list[ToolCallView] = []

    for tool_call in session.tool_calls:
        tool_calls.append(
            ToolCallView(
                tool_call_id=tool_call.tool_call_id or f"tool:{tool_call.tool_name}",
                tool_name=tool_call.tool_name,
                status=tool_call.normalized_status or tool_call.status.value,
                input_payload=tool_call.input_payload,
                started_at=tool_call.started_at,
                completed_at=tool_call.completed_at,
                latency_ms=tool_call.latency_ms,
                error_code=tool_call.error_code,
                error_message=tool_call.error_message,
                normalized_output=tool_call.normalized_output,
                has_normalized_output=bool(tool_call.normalized_output),
                raw_output_ref=tool_call.raw_output_ref,
            )
        )

    return tool_calls


def _serialize_session_state(session: SessionView) -> SessionStateView:
    return SessionStateView(
        session_id=session.session_id,
        lifecycle_state=session.status.value,
        budget_remaining=session.budget_remaining,
        last_completed_step=session.last_completed_step,
        waiting_for_approval=session.waiting_for_approval,
        partial_result=session.partial_result,
        failure_reason=session.failure_reason,
    )


def _serialize_investigation_plan(session: SessionView):
    return session.investigation_plan


def _serialize_incident_record(session: SessionView) -> IncidentRecordView:
    if session.incident_record is not None:
        return session.incident_record

    return IncidentRecordView(
        incident_id=session.incident_id or f"incident:{session.session_id}",
        title=session.incident.title,
        service=session.incident.service,
        severity=session.incident.severity,
        timestamp=session.incident.timestamp,
        summary=session.incident.summary,
        signals=session.incident.signals,
        environment=session.incident.environment,
        reporter=session.incident.reporter,
        alert_payload=session.incident.alert_payload,
        links=session.incident.links,
        created_at=session.created_at,
    )


def _legacy_safety_notes_to_items(
    session: SessionView,
    report: FinalReport,
) -> list[SafetyEventView]:
    notes: list[SafetyEventView] = []

    for index, note in enumerate(report.safety_notes, start=1):
        lowered = note.lower()
        note_type = "uncertainty"
        severity = "low"
        related_ref = "report"
        if "degraded mode" in lowered or "partial result" in lowered:
            note_type = "degradation"
            severity = "medium"
            related_ref = "trace:degradation"
        elif "groundedness" in lowered or "corroborat" in lowered:
            note_type = "groundedness"
            severity = "medium"
            related_ref = "trace:groundedness_check"
        elif "untrusted instruction-like content" in lowered:
            note_type = "sanitization"
            severity = "medium"
            related_ref = "trace:sanitization_check"
        elif "approval" in lowered or "modify system state" in lowered:
            note_type = "policy"
            severity = "medium"
            related_ref = "trace:policy_check"
        elif "redact" in lowered:
            note_type = "redaction"
            severity = "medium"
            related_ref = "trace:redaction"

        notes.append(
            SafetyEventView(
                safety_event_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"safety-event:{session.session_id}:{index}:{note}",
                    )
                ),
                session_id=session.session_id,
                type=note_type,
                message=note,
                severity=severity,
                related_ref=related_ref,
                created_at=datetime.now(UTC),
            )
        )

    return notes


def _serialize_approval_requests(session: SessionView) -> list[ApprovalRequestView]:
    if session.approval_request is None:
        return []

    return [
        ApprovalRequestView(
            approval_id=session.approval_request.approval_id or _approval_id(session.session_id),
            action_type=(
                session.approval_request.action_type
                or _action_type(session.approval_request.recommended_action)
            ),
            reason=session.approval_request.reason,
            risk_level=(
                session.approval_request.risk_level
                or _risk_level(session.approval_request.recommended_action)
            ),
            status=session.approval_request.status or "pending",
        )
    ]


def _serialize_unknowns(session: SessionView, report: FinalReport) -> list[str]:
    if report.unknowns:
        return report.unknowns

    unknowns: list[str] = []
    if session.status == SessionStatus.PARTIAL_COMPLETED:
        unknowns.extend(report.safety_notes)
    elif not report.refs:
        unknowns.append("No corroborating runbook or knowledge-base references were available.")

    seen: set[str] = set()
    ordered_unknowns: list[str] = []
    for item in unknowns:
        if item and item not in seen:
            ordered_unknowns.append(item)
            seen.add(item)
    return ordered_unknowns


def serialize_report(session: SessionView) -> dict[str, object]:
    report = session.final_report or FinalReport(summary="No triage report available.")
    report.normalize_legacy_fields()
    refs = report.ref_items or _legacy_refs_to_items(report)
    hypotheses = report.hypothesis_items or _legacy_hypotheses_to_items(session, report)
    next_steps = report.next_step_items or _legacy_next_steps_to_items(report)
    safety_notes = report.safety_note_items or _legacy_safety_notes_to_items(session, report)
    triage_report: dict[str, object] = {
        "incident_summary": IncidentSummary(
            title=session.incident.title,
            service=session.incident.service,
            severity=session.incident.severity,
        ).model_dump(mode="json"),
        "summary": report.summary,
        "status": session.status.value,
        "hypotheses": [item.model_dump(mode="json") for item in hypotheses],
        "next_steps": [item.model_dump(mode="json") for item in next_steps],
        "refs": [item.model_dump(mode="json") for item in refs],
        "safety_notes": [item.model_dump(mode="json") for item in safety_notes],
        "approval_requests": [
            item.model_dump(mode="json") for item in _serialize_approval_requests(session)
        ],
        "unknowns": _serialize_unknowns(session, report),
    }
    return triage_report


def serialize_incident_result(session: SessionView) -> dict[str, object]:
    return IncidentResponseData(
        session_id=session.session_id,
        incident_id=session.incident_id or _serialize_incident_record(session).incident_id,
        incident=_serialize_incident_record(session),
        lifecycle_state=session.status,
        session_state=_serialize_session_state(session),
        investigation_plan=_serialize_investigation_plan(session),
        report=serialize_report_model(session),
        tool_calls=_serialize_tool_calls(session),
    ).model_dump(mode="json")


def serialize_session(session: SessionView) -> dict[str, object]:
    return SessionResponseData(
        session_id=session.session_id,
        incident_id=session.incident_id or _serialize_incident_record(session).incident_id,
        incident=_serialize_incident_record(session),
        lifecycle_state=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
        iteration_count=session.iteration_count,
        llm_provider=session.llm_provider,
        policy_mode=session.policy_mode,
        session_state=_serialize_session_state(session),
        investigation_plan=_serialize_investigation_plan(session),
        report=serialize_report_model(session),
        tool_calls=_serialize_tool_calls(session),
    ).model_dump(mode="json")


def serialize_report_model(session: SessionView):
    from src.domain.schemas import TriageReportView

    return TriageReportView.model_validate(serialize_report(session))


def serialize_trace(session_id: str, trace: list[TraceStep]) -> dict[str, object]:
    steps = [
        TraceResponseStep(
            step=index,
            type=_trace_category(item.step_type),
            step_type=item.step_type,
            status=item.status,
            started_at=item.started_at.isoformat(),
            completed_at=item.completed_at.isoformat(),
            duration_ms=_trace_duration_ms(item),
            summary=item.details,
            details=item.details,
            tool_name=item.metadata.get("tool_name"),
            metadata=item.metadata,
        )
        for index, item in enumerate(trace, start=1)
    ]
    return TraceResponseData(
        session_id=session_id,
        trace=steps,
    ).model_dump(mode="json")


def serialize_approval(approval: ApprovalView, session: SessionView) -> dict[str, object]:
    return ApprovalResponseData(
        session_id=session.session_id,
        approval_id=(
            session.approval_request.approval_id
            if session.approval_request is not None and session.approval_request.approval_id
            else _approval_id(session.session_id)
        ),
        decision=approval.decision,
        lifecycle_state=session.status,
        report=serialize_report_model(session),
    ).model_dump(mode="json")


def serialize_root(
    *,
    service: str,
    version: str,
    environment: str,
    docs_url: str,
    health_url: str,
    metrics_url: str,
) -> dict[str, str]:
    return {
        "service": service,
        "version": version,
        "environment": environment,
        "docs_url": docs_url,
        "health_url": health_url,
        "metrics_url": metrics_url,
    }


def serialize_health(
    *,
    service: str,
    version: str,
    environment: str,
) -> dict[str, object]:
    return {
        "service": service,
        "healthy": True,
        "version": version,
        "environment": environment,
    }


def serialize_readiness(
    *,
    service: str,
    version: str,
    environment: str,
    ready: bool,
    readiness_state: str,
) -> dict[str, object]:
    return {
        "service": service,
        "ready": ready,
        "readiness_state": readiness_state,
        "version": version,
        "environment": environment,
    }
