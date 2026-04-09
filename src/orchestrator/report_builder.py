"""Report assembly logic for the triage orchestrator.

ReportBuilder contains all the pure transformation methods that convert LLM output,
tool call records, and observations into the structured FinalReport domain objects.
It has no async I/O or repository dependencies and can be tested without mocking.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from src.domain.enums import ToolCallStatus
from src.domain.schemas import (
    HypothesisView,
    NextStepView,
    ReferenceView,
    SafetyEventView,
    SessionView,
    ToolCallRecord,
)


class ReportBuilder:
    """Transforms raw triage data into structured report components.

    All methods are static — ReportBuilder carries no mutable state.
    Instantiate once and share across the lifetime of OrchestratorService.
    """

    # ------------------------------------------------------------------ hypotheses

    @staticmethod
    def build_hypothesis_items(
        *,
        session_id: str,
        hypotheses: list[str],
        ref_items: list[ReferenceView],
        weakly_grounded: bool,
        observations_count: int = 0,
        refs_count: int = 0,
    ) -> list[HypothesisView]:
        """Build hypothesis views with evidence-based confidence (G10).

        Confidence reflects actual evidence quality, not only hypothesis position.
        G23: only the primary hypothesis receives the full ref list; others get
        an empty list since per-hypothesis ref matching is out of PoC scope.
        """
        all_ref_ids = [item.id for item in ref_items]
        items: list[HypothesisView] = []
        for index, statement in enumerate(hypotheses, start=1):
            items.append(
                HypothesisView(
                    id=str(
                        uuid5(NAMESPACE_URL, f"hypothesis:{session_id}:{index}:{statement}")
                    ),
                    statement=statement,
                    source="llm_analysis",
                    confidence=ReportBuilder._hypothesis_confidence(
                        index,
                        weakly_grounded=weakly_grounded,
                        observations_count=observations_count,
                        refs_count=refs_count,
                    ),
                    status=ReportBuilder._hypothesis_status(
                        index, weakly_grounded=weakly_grounded
                    ),
                    # Primary hypothesis gets all refs; secondary hypotheses get none
                    # to avoid misleading grounding claims (full NLP matching is out of scope).
                    supporting_refs=all_ref_ids if index == 1 else [],
                )
            )
        return items

    @staticmethod
    def _hypothesis_confidence(
        index: int,
        *,
        weakly_grounded: bool = False,
        observations_count: int = 0,
        refs_count: int = 0,
    ) -> float:
        """Evidence-based confidence: starts from evidence quality, not position."""
        if observations_count >= 2 and refs_count >= 1:
            base = 0.82
        elif observations_count >= 1 or refs_count >= 1:
            base = 0.65
        else:
            base = 0.45

        # Small positional discount: capped at 0.10 so ordering still matters slightly.
        positional_discount = min((index - 1) * 0.05, 0.10)
        result = base - positional_discount
        if weakly_grounded:
            result -= 0.10
        return round(max(0.30, result), 2)

    @staticmethod
    def _hypothesis_status(index: int, *, weakly_grounded: bool = False) -> str:
        if weakly_grounded:
            return "weakened"
        # G22: top-2 hypotheses are "active" when evidence is sufficient.
        if index <= 2:
            return "active"
        return "weakened"

    # ------------------------------------------------------------------ next steps

    @staticmethod
    def build_next_step_items(
        *,
        next_steps: list[str],
        recommended_action: str | None,
    ) -> list[NextStepView]:
        return [
            NextStepView(
                priority=index,
                action=action,
                source="llm_analysis",
                rationale=ReportBuilder._build_next_step_rationale(action),
                requires_approval=action == recommended_action,
            )
            for index, action in enumerate(next_steps, start=1)
        ]

    @staticmethod
    def _build_next_step_rationale(action: str) -> str:
        lowered = action.lower()
        if "deploy" in lowered or "rollback" in lowered or "roll back" in lowered:
            return "Needed to confirm whether the latest deployment correlates with the incident."
        if "dependency" in lowered or "provider" in lowered:
            return "Needed to validate whether an upstream dependency is contributing to the failure."
        if "log" in lowered:
            return "Needed to confirm the failure mode and identify endpoint-specific error patterns."
        if "retry" in lowered or "saturation" in lowered:
            return "Needed to determine whether retry pressure is amplifying the incident."
        if "metric" in lowered or "latency" in lowered:
            return "Needed to quantify the current impact and confirm the scope of degradation."
        return "Needed to reduce uncertainty and validate the current working hypotheses."

    # ------------------------------------------------------------------ safety notes

    @staticmethod
    def build_safety_note_items(session_id: str, notes: list[str]) -> list[SafetyEventView]:
        items: list[SafetyEventView] = []
        for index, note in enumerate(notes, start=1):
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
            items.append(
                SafetyEventView(
                    safety_event_id=str(
                        uuid5(NAMESPACE_URL, f"safety-event:{session_id}:{index}:{note}")
                    ),
                    session_id=session_id,
                    type=note_type,
                    message=note,
                    severity=severity,
                    related_ref=related_ref,
                    created_at=datetime.now(UTC),
                )
            )
        return items

    @staticmethod
    def build_report_safety_notes(
        *,
        base_notes: list[str],
        hypotheses: list[str],
        refs: list[str],
        groundedness_warnings: list[str],
        sanitization_warnings: list[str],
    ) -> list[str]:
        notes = list(base_notes)
        notes.extend(groundedness_warnings)
        notes.extend(sanitization_warnings)
        if hypotheses:
            notes.append(
                "Root cause is not confirmed yet; hypotheses are evidence-backed but preliminary."
            )
        if not refs:
            notes.append(
                "Knowledge-base corroboration was unavailable; "
                "recommendations rely on live observations only."
            )
        seen: set[str] = set()
        ordered: list[str] = []
        for note in notes:
            if note not in seen:
                ordered.append(note)
                seen.add(note)
        return ordered

    # ------------------------------------------------------------------ references

    @staticmethod
    def build_reference_items(session: SessionView) -> list[ReferenceView]:
        refs: list[ReferenceView] = []
        for index, ref in enumerate(ReportBuilder._collect_refs(session), start=1):
            refs.append(
                ReferenceView(
                    id=f"kb:{index}",
                    type="kb_doc",
                    source="runbook_retrieval_tool",
                    title=ref.rsplit("/", maxsplit=1)[-1],
                    snippet=ref,
                    target_ref=ref,
                )
            )
        for index, observation in enumerate(session.observations, start=1):
            refs.append(
                ReferenceView(
                    id=observation.observation_id or f"obs:{observation.source}:{index}",
                    type="observation",
                    source=observation.source,
                    title=observation.title or observation.source.replace("_", " "),
                    snippet=observation.summary,
                    target_ref=observation.source_ref,
                )
            )
        for index, tool_call in enumerate(session.tool_calls, start=1):
            refs.append(
                ReferenceView(
                    id=tool_call.tool_call_id or f"tool:{tool_call.tool_name}:{index}",
                    type="tool_result",
                    source=tool_call.tool_name,
                    title=tool_call.tool_name.replace("_", " "),
                    snippet=tool_call.summary or ReportBuilder._tool_result_snippet(tool_call),
                    target_ref=tool_call.raw_output_ref or tool_call.tool_call_id,
                )
            )
        seen: set[str] = set()
        ordered: list[ReferenceView] = []
        for item in refs:
            if item.id not in seen:
                ordered.append(item)
                seen.add(item.id)
        return ordered

    @staticmethod
    def _collect_refs(session: SessionView) -> list[str]:
        refs: list[str] = []
        for observation in session.observations:
            refs.extend(observation.refs)
        return sorted(set(refs))

    @staticmethod
    def _tool_result_snippet(tool_call: ToolCallRecord) -> str:
        if tool_call.summary:
            return tool_call.summary
        if tool_call.normalized_output:
            return str(tool_call.normalized_output)
        return tool_call.tool_name

    # ------------------------------------------------------------------ unknowns

    @staticmethod
    def build_unknowns(
        *,
        status: object,
        refs: list[str],
        safety_notes: list[str],
    ) -> list[str]:
        from src.domain.enums import SessionStatus  # local import to avoid circular
        unknowns: list[str] = []
        if status == SessionStatus.ANALYZING and not refs:
            unknowns.append("No corroborating runbook or knowledge-base references were available.")
        for note in safety_notes:
            lowered = note.lower()
            if "insufficient" in lowered or "unavailable" in lowered or "incomplete" in lowered:
                unknowns.append(note)
            if "groundedness" in lowered or "corroborat" in lowered:
                unknowns.append(note)
            if "untrusted instruction-like content" in lowered:
                unknowns.append(note)
        seen: set[str] = set()
        ordered: list[str] = []
        for item in unknowns:
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    # ------------------------------------------------------------------ action classification

    @staticmethod
    def action_type(recommended_action: str) -> str:
        action = recommended_action.lower()
        if "roll back" in action or "rollback" in action or "rolling back" in action:
            return "rollback_deployment"
        if "restart" in action:
            return "restart_service"
        if "redeploy" in action or "revert" in action:
            return "redeploy_service"
        return "gated_action"

    @staticmethod
    def risk_level(recommended_action: str) -> str:
        action_type = ReportBuilder.action_type(recommended_action)
        if action_type == "rollback_deployment":
            return "high"
        if action_type in {"restart_service", "redeploy_service"}:
            return "medium"
        # G30: diagnostic / gated actions that don't directly modify service state.
        return "low"

    @staticmethod
    def approval_reason(*, trigger: str | None, weakly_grounded: bool) -> str:
        if trigger == "rollback":
            base_reason = (
                "Suggested next step includes a deployment rollback and "
                "requires explicit human approval."
            )
        else:
            base_reason = "Suggested next step may modify system state."
        if weakly_grounded:
            return (
                f"{base_reason} Evidence is limited, so the recommendation must be "
                "reviewed carefully by a human."
            )
        return base_reason

    # ------------------------------------------------------------------ tool status

    @staticmethod
    def normalized_tool_status(status: ToolCallStatus) -> str:
        mapping = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.SUCCESS: "completed",
            ToolCallStatus.FAILED: "failed",
            ToolCallStatus.TIMEOUT: "timed_out",
            ToolCallStatus.SKIPPED: "skipped",
        }
        return mapping[status]
