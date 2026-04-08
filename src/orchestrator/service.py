from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from src.config import settings
from src.domain.enums import SessionStatus, ToolCallStatus
from src.domain.schemas import (
    ApprovalRequest,
    FinalReport,
    HypothesisView,
    InvestigationPlanView,
    Observation,
    NextStepView,
    ReferenceView,
    SafetyEventView,
    SessionView,
    ToolCallRecord,
)
from src.llm.base import BaseLLMAdapter, LLMAnalysisInput, classify_llm_outcome
from src.llm.factory import create_llm_adapter
from src.llm.prompt_builder import build_analysis_prompt
from src.observability.logging import get_logger
from src.observability.metrics import metrics_registry
from src.orchestrator.budget import SessionBudget
from src.orchestrator.context import build_session_context
from src.orchestrator.transitions import can_transition
from src.persistence.protocols import SessionRepository
from src.prompts.loader import load_prompt
from src.safety.policy import evaluate_next_steps
from src.safety.groundedness import evaluate_groundedness
from src.safety.sanitization import detect_untrusted_instructions
from src.safety.redaction import redact_list, redact_text
from src.tools.base import ToolRequest
from src.tools.logs_tool import LogsTool
from src.tools.metrics_tool import MetricsTool
from src.tools.runbook_retrieval_tool import RunbookRetrievalTool

logger = get_logger(__name__)


class OrchestratorService:
    def __init__(
        self,
        repository: SessionRepository,
        llm_adapter: BaseLLMAdapter | None = None,
    ) -> None:
        self._repository = repository
        self._metrics_tool = MetricsTool()
        self._logs_tool = LogsTool()
        self._runbook_tool = RunbookRetrievalTool()
        self._llm_adapter = llm_adapter or create_llm_adapter()

        self._planning_prompt = load_prompt("planning.txt")
        self._analysis_prompt = load_prompt("analysis.txt")
        self._report_prompt = load_prompt("report.txt")


    async def run_initial_triage(self, session_id: str) -> SessionView:
        session = self._repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        logger.info(
            "Initial triage started.",
            extra={
                "session_id": session_id,
                "step_type": "triage",
                "status": "started",
            },
        )

        budget = SessionBudget()
        session = self._sync_budget_state(session, budget)

        session = self._update_status(session_id, SessionStatus.VALIDATING_INPUT)
        session = self._update_status(session_id, SessionStatus.PLANNING)
        session = self._repository.update_investigation_plan(
            session_id=session.session_id,
            plan=self._build_investigation_plan(session),
        )

        if budget.exhausted:
            metrics_registry.increment("session_budget_exhausted_total")
            return self._finalize_partial(
                session=session,
                reason="Budget exhausted before investigation started.",
                budget=budget,
            )

        if "force_tool_failure" in session.incident.summary.lower():
            session = self._update_status(session_id, SessionStatus.EXECUTING_TOOLS)
            session = self._update_status(session_id, SessionStatus.TOOL_FAILED)
            return self._finalize_partial(
                session=session,
                reason="Forced tool failure triggered for degraded-path testing.",
                budget=budget,
            )

        session = self._update_status(session_id, SessionStatus.RETRIEVING)
        session = await self._run_tool(
            session=session,
            budget=budget,
            tool_name=self._runbook_tool.name,
            tool_payload={
                "service": session.incident.service,
                "summary": session.incident.summary,
                "signals": session.incident.signals,
            },
        )

        session = self._update_status(session_id, SessionStatus.EXECUTING_TOOLS)
        session = await self._run_tool(
            session=session,
            budget=budget,
            tool_name=self._metrics_tool.name,
            tool_payload={
                "service": session.incident.service,
                "environment": session.incident.environment or "unknown",
            },
        )
        session = await self._run_tool(
            session=session,
            budget=budget,
            tool_name=self._logs_tool.name,
            tool_payload={
                "service": session.incident.service,
                "environment": session.incident.environment or "unknown",
            },
        )

        session = self._update_status(session_id, SessionStatus.ANALYZING)

        context_started_at = datetime.now(UTC)
        context = build_session_context(session)
        context_completed_at = datetime.now(UTC)
        self._append_trace(
            session_id=session.session_id,
            step_type="context_assembly",
            status="completed",
            details="Session context assembled for LLM analysis.",
            metadata={
                "observations_count": str(len(context.observations)),
                "refs_count": str(len(context.refs)),
                "known_facts_count": str(len(context.known_facts)),
            },
            started_at=context_started_at,
            completed_at=context_completed_at,
        )

        prompt_started_at = datetime.now(UTC)
        analysis_prompt = build_analysis_prompt(
            template=self._analysis_prompt,
            context=context,
        )
        prompt_completed_at = datetime.now(UTC)

        self._append_trace(
            session_id=session.session_id,
            step_type="prompt_build",
            status="completed",
            details="Analysis prompt built from template and session context.",
            metadata={
                "prompt_template": "analysis.txt",
                "prompt_length": str(len(analysis_prompt)),
            },
            started_at=prompt_started_at,
            completed_at=prompt_completed_at,
        )

        sanitization_result = detect_untrusted_instructions(
            session.incident.summary,
            *[observation.summary for observation in session.observations],
        )
        self._append_trace(
            session_id=session.session_id,
            step_type="sanitization_check",
            status="warning" if sanitization_result.contains_untrusted_instructions else "passed",
            details=(
                sanitization_result.warnings[0]
                if sanitization_result.warnings
                else "No instruction-like untrusted content detected."
            ),
            metadata={
                "contains_untrusted_instructions": str(
                    sanitization_result.contains_untrusted_instructions
                ).lower(),
                "warnings_count": str(len(sanitization_result.warnings)),
            },
        )

        llm_started_at = datetime.now(UTC)
        llm_result = await self._llm_adapter.analyze(
            LLMAnalysisInput(
                prompt=analysis_prompt,
                incident_title=context.incident_title,
                service=context.service,
                summary=context.summary,
                observations=context.observations,
                refs=context.refs,
            )
        )
        llm_completed_at = datetime.now(UTC)

        self._append_trace(
            session_id=session.session_id,
            step_type="llm_analysis",
            status="completed",
            details="LLM analysis completed.",
            metadata={
                "backend": type(self._llm_adapter).__name__,
                "provider": getattr(self._llm_adapter, "provider_name", settings.llm_provider),
                "model": getattr(self._llm_adapter, "model_name", settings.llm_model),
                "llm_outcome": classify_llm_outcome(llm_result),
                "structured_output": "true",
                "hypotheses_count": str(len(llm_result.hypotheses)),
                "next_steps_count": str(len(llm_result.next_steps)),
            },
            started_at=llm_started_at,
            completed_at=llm_completed_at,
        )

        policy_result = evaluate_next_steps(llm_result.next_steps)
        refs = self._collect_refs(session)
        groundedness_result = evaluate_groundedness(
            observations_count=len(session.observations),
            refs_count=len(refs),
            hypotheses_count=len(llm_result.hypotheses),
        )
        self._append_trace(
            session_id=session.session_id,
            step_type="groundedness_check",
            status="warning" if groundedness_result.weakly_grounded else "passed",
            details=(
                groundedness_result.warnings[0]
                if groundedness_result.warnings
                else "Groundedness check passed."
            ),
            metadata={
                "weakly_grounded": str(groundedness_result.weakly_grounded).lower(),
                "warnings_count": str(len(groundedness_result.warnings)),
                "observations_count": str(len(session.observations)),
                "refs_count": str(len(refs)),
            },
        )
        report_safety_notes = self._build_report_safety_notes(
            base_notes=policy_result.safety_notes,
            hypotheses=llm_result.hypotheses,
            refs=refs,
            groundedness_warnings=groundedness_result.warnings,
            sanitization_warnings=sanitization_result.warnings,
        )
        ref_items = self._build_reference_items(session)
        hypothesis_items = self._build_hypothesis_items(
            session_id=session.session_id,
            hypotheses=llm_result.hypotheses,
            ref_items=ref_items,
            weakly_grounded=groundedness_result.weakly_grounded,
        )
        next_step_items = self._build_next_step_items(
            next_steps=llm_result.next_steps,
            recommended_action=policy_result.recommended_action,
        )
        safety_note_items = self._build_safety_note_items(
            session.session_id,
            report_safety_notes,
        )

        report = FinalReport(
            summary=redact_text(llm_result.summary),
            hypotheses=redact_list(llm_result.hypotheses),
            next_steps=redact_list(llm_result.next_steps),
            refs=refs,
            safety_notes=redact_list(report_safety_notes),
            unknowns=self._build_unknowns(
                status=session.status,
                refs=refs,
                safety_notes=report_safety_notes,
            ),
            hypothesis_items=hypothesis_items,
            next_step_items=next_step_items,
            ref_items=ref_items,
            safety_note_items=safety_note_items,
        )

        session = self._repository.set_final_report(
            session_id=session.session_id,
            final_report=report,
        )
        self._record_ttfa(session)

        if policy_result.requires_approval:
            metrics_registry.increment("policy_blocks_total")
            metrics_registry.increment("approval_requests_total")
            approval_reason = self._approval_reason(
                trigger=policy_result.trigger,
                weakly_grounded=groundedness_result.weakly_grounded,
            )

            session = self._repository.set_approval_request(
                session_id=session.session_id,
                approval_request=ApprovalRequest(
                    approval_id=str(uuid5(NAMESPACE_URL, f"approval:{session.session_id}")),
                    action_type=self._action_type(
                        policy_result.recommended_action or llm_result.next_steps[0]
                    ),
                    reason=approval_reason,
                    risk_level=self._risk_level(
                        policy_result.recommended_action or llm_result.next_steps[0]
                    ),
                    status="pending",
                    recommended_action=(
                        policy_result.recommended_action or llm_result.next_steps[0]
                    ),
                ),
            )
            self._append_trace(
                session_id=session.session_id,
                step_type="policy_check",
                status="approval_required",
                details=approval_reason,
                metadata={
                    "policy_trigger": policy_result.trigger or "unknown",
                    "weakly_grounded": str(groundedness_result.weakly_grounded).lower(),
                    "recommended_action": (
                        policy_result.recommended_action or llm_result.next_steps[0]
                    ),
                },
            )
            session = self._update_status(
                session.session_id,
                SessionStatus.WAITING_APPROVAL,
            )
            metrics_registry.increment("triage_waiting_approval_total")
            logger.info(
                "Triage requires approval.",
                extra={
                    "session_id": session.session_id,
                    "step_type": "triage",
                    "status": "waiting_approval",
                    "safety_event_type": "approval_required",
                },
            )
            return session

        session = self._update_status(session.session_id, SessionStatus.COMPLETED)
        metrics_registry.increment("triage_completed_total")
        logger.info(
            "Triage completed.",
            extra={
                "session_id": session.session_id,
                "step_type": "triage",
                "status": "completed",
            },
        )
        return session

    async def _run_tool(
        self,
        session: SessionView,
        budget: SessionBudget,
        tool_name: str,
        tool_payload: dict[str, object],
    ) -> SessionView:
        tool_map = {
            self._metrics_tool.name: self._metrics_tool,
            self._logs_tool.name: self._logs_tool,
            self._runbook_tool.name: self._runbook_tool,
        }
        tool = tool_map[tool_name]

        if budget.exhausted:
            return self._finalize_partial(
                session=session,
                reason="Budget exhausted before tool execution.",
                budget=budget,
            )

        logger.info(
            "Tool execution started.",
            extra={
                "session_id": session.session_id,
                "step_type": "tool_call",
                "tool_name": tool_name,
                "status": "started",
            },
        )

        budget.consume_tool_call()
        tool_started_at = datetime.now(UTC)
        result = await tool.execute(
            ToolRequest(
                tool_name=tool.name,
                payload=tool_payload,
            )
        )
        tool_completed_at = datetime.now(UTC)

        metrics_registry.increment("tool_calls_total")
        if result.status.value != "success":
            metrics_registry.increment("tool_calls_failed")

        tool_call = ToolCallRecord(
            tool_call_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"tool-call:{session.session_id}:{result.tool_name}:{budget.tool_calls_used}",
                )
            ),
            tool_name=result.tool_name,
            input_payload=tool_payload,
            status=result.status,
            normalized_status=self._normalized_tool_status(result.status),
            started_at=tool_started_at,
            completed_at=tool_completed_at,
            latency_ms=result.latency_ms,
            error_code=result.error_type,
            error_type=result.error_type,
            error_message=result.error_type,
            normalized_output=result.data,
            summary=redact_text(result.summary),
        )
        observation = Observation(
            observation_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"observation:{session.session_id}:{result.tool_name}:{budget.tool_calls_used}",
                )
            ),
            source=result.tool_name,
            source_type="tool",
            source_ref=tool_call.tool_call_id,
            title=result.tool_name.replace("_", " "),
            summary=redact_text(result.summary),
            confidence=0.9 if result.status.value == "success" else 0.5,
            observed_at=tool_completed_at,
            refs=self._extract_refs(result.data),
        )

        session = self._repository.add_tool_call(
            session_id=session.session_id,
            tool_call=tool_call,
        )
        session = self._sync_budget_state(session, budget)
        session = self._repository.add_observation(
            session_id=session.session_id,
            observation=observation,
        )

        logger.info(
            "Tool execution completed.",
            extra={
                "session_id": session.session_id,
                "step_type": "tool_call",
                "tool_name": result.tool_name,
                "status": result.status.value,
                "latency_ms": result.latency_ms,
                "error_type": result.error_type,
            },
        )
        return session

    def _update_status(
        self,
        session_id: str,
        next_status: SessionStatus,
    ) -> SessionView:
        session = self._repository.update_status(session_id, next_status)
        logger.info(
            "Session status updated.",
            extra={
                "session_id": session_id,
                "step_type": "status_transition",
                "status": next_status.value,
            },
        )
        return session

    @staticmethod
    def _extract_refs(data: dict[str, object]) -> list[str]:
        snippets = data.get("snippets")
        if not isinstance(snippets, list):
            return []

        refs: list[str] = []
        for snippet in snippets:
            if isinstance(snippet, dict):
                ref = snippet.get("ref")
                if isinstance(ref, str):
                    refs.append(ref)
        return refs

    @staticmethod
    def _collect_refs(session: SessionView) -> list[str]:
        refs: list[str] = []
        for observation in session.observations:
            refs.extend(observation.refs)
        return sorted(set(refs))

    def _finalize_partial(
        self,
        session: SessionView,
        reason: str,
        budget: SessionBudget | None = None,
    ) -> SessionView:
        safety_notes = [
            "Triage completed in degraded mode; additional investigation is required.",
            (
                "Groundedness is weak; generated hypotheses are not corroborated by "
                "observations or references."
            ),
            reason,
        ]
        report = FinalReport(
            summary="Partial triage result generated.",
            hypotheses=["Insufficient evidence for a confident conclusion."],
            next_steps=["Collect more telemetry and rerun triage."],
            refs=[],
            safety_notes=safety_notes,
            unknowns=[reason],
            safety_note_items=self._build_safety_note_items(
                session.session_id,
                safety_notes,
            ),
        )
        session = self._repository.set_final_report(
            session_id=session.session_id,
            final_report=report,
        )
        session = self._repository.update_session_state(
            session.session_id,
            budget_remaining=(
                budget.snapshot().tool_calls_remaining if budget is not None else None
            ),
            failure_reason=reason,
        )
        self._record_ttfa(session)
        self._append_trace(
            session_id=session.session_id,
            step_type="degradation",
            status="degraded",
            details="Triage entered degraded mode and produced a partial result.",
            metadata={
                "reason": reason,
                "degradation_type": self._degradation_type(reason),
                **self._budget_metadata(budget),
            },
        )
        session = self._normalize_partial_transition(session)
        session = self._update_status(
            session.session_id,
            SessionStatus.PARTIAL_COMPLETED,
        )

        metrics_registry.increment("fallback_total")
        metrics_registry.increment("degraded_sessions_total")
        metrics_registry.increment("triage_partial_completed_total")
        logger.info(
            "Triage partial result generated.",
            extra={
                "session_id": session.session_id,
                "step_type": "triage",
                "status": "partial_completed",
                "fallback_used": True,
            },
        )
        return session

    def _sync_budget_state(
        self,
        session: SessionView,
        budget: SessionBudget,
    ) -> SessionView:
        return self._repository.update_session_state(
            session.session_id,
            budget_remaining=budget.snapshot().tool_calls_remaining,
            failure_reason=session.failure_reason,
        )

    @staticmethod
    def _build_investigation_plan(session: SessionView) -> InvestigationPlanView:
        service = session.incident.service
        goal = f"Determine the likely cause of the {service} incident and identify safe next steps."
        steps = [
            f"Collect runbook context for {service} and the reported signals.",
            f"Query live metrics and logs for {service} in {session.incident.environment or 'unknown'}.",
            "Synthesize evidence into grounded hypotheses and recommended next steps.",
        ]
        return InvestigationPlanView(
            plan_id=str(uuid5(NAMESPACE_URL, f"plan:{session.session_id}:v1")),
            session_id=session.session_id,
            version=1,
            goal=goal,
            steps=steps,
            status="active",
            created_at=datetime.now(UTC),
        )

    def _normalize_partial_transition(self, session: SessionView) -> SessionView:
        if can_transition(session.status, SessionStatus.PARTIAL_COMPLETED):
            return session

        if can_transition(session.status, SessionStatus.TOOL_FAILED):
            return self._update_status(session.session_id, SessionStatus.TOOL_FAILED)

        if can_transition(session.status, SessionStatus.ANALYZING):
            return self._update_status(session.session_id, SessionStatus.ANALYZING)

        return session

    @staticmethod
    def _record_ttfa(session: SessionView) -> None:
        ttfa_ms = max(
            0,
            int((datetime.now(UTC) - session.created_at).total_seconds() * 1000),
        )
        metrics_registry.observe_latency("ttfa_ms", ttfa_ms)
    
    def _append_trace(
        self,
        session_id: str,
        step_type: str,
        status: str,
        details: str,
        metadata: dict[str, str] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self._repository.append_trace(
            session_id=session_id,
            step_type=step_type,
            status=status,
            details=details,
            metadata=metadata,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _action_type(recommended_action: str) -> str:
        action = recommended_action.lower()
        if "roll back" in action or "rollback" in action or "rolling back" in action:
            return "rollback_deployment"
        if "restart" in action:
            return "restart_service"
        if "redeploy" in action or "revert" in action:
            return "redeploy_service"
        return "gated_action"

    def _risk_level(self, recommended_action: str) -> str:
        action_type = self._action_type(recommended_action)
        if action_type == "rollback_deployment":
            return "high"
        if action_type in {"restart_service", "redeploy_service"}:
            return "medium"
        return "medium"

    @staticmethod
    def _build_hypothesis_items(
        *,
        session_id: str,
        hypotheses: list[str],
        ref_items: list[ReferenceView],
        weakly_grounded: bool,
    ) -> list[HypothesisView]:
        supporting_refs = [item.id for item in ref_items]
        items: list[HypothesisView] = []

        for index, statement in enumerate(hypotheses, start=1):
            items.append(
                HypothesisView(
                    id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"hypothesis:{session_id}:{index}:{statement}",
                        )
                    ),
                    statement=statement,
                    source="llm_analysis",
                    confidence=OrchestratorService._hypothesis_confidence(
                        index,
                        weakly_grounded=weakly_grounded,
                    ),
                    status=OrchestratorService._hypothesis_status(
                        index,
                        weakly_grounded=weakly_grounded,
                    ),
                    supporting_refs=supporting_refs,
                )
            )

        return items

    @staticmethod
    def _hypothesis_confidence(index: int, *, weakly_grounded: bool = False) -> float:
        baseline = 0.85 - ((index - 1) * 0.1)
        if weakly_grounded:
            baseline -= 0.15
        return max(0.4, baseline)

    @staticmethod
    def _hypothesis_status(index: int, *, weakly_grounded: bool = False) -> str:
        if weakly_grounded:
            return "weakened"
        if index == 1:
            return "active"
        return "weakened"

    @staticmethod
    def _build_next_step_items(
        *,
        next_steps: list[str],
        recommended_action: str | None,
    ) -> list[NextStepView]:
        return [
            NextStepView(
                priority=index,
                action=action,
                source="llm_analysis",
                rationale=OrchestratorService._build_next_step_rationale(action),
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

    @staticmethod
    def _degradation_type(reason: str) -> str:
        lowered = reason.lower()
        if "budget exhausted" in lowered:
            return "budget_exhausted"
        if "tool failure" in lowered or "dependency" in lowered:
            return "tool_failure"
        return "degraded_partial"

    @staticmethod
    def _approval_reason(*, trigger: str | None, weakly_grounded: bool) -> str:
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

    @staticmethod
    def _budget_metadata(budget: SessionBudget | None) -> dict[str, str]:
        if budget is None:
            return {}

        snapshot = budget.snapshot()
        return {
            "tool_calls_used": str(snapshot.tool_calls_used),
            "tool_calls_remaining": str(snapshot.tool_calls_remaining),
            "elapsed_ms": str(int(snapshot.elapsed_seconds * 1000)),
            "time_remaining_ms": str(int(snapshot.time_remaining_seconds * 1000)),
        }

    def _build_reference_items(self, session: SessionView) -> list[ReferenceView]:
        refs: list[ReferenceView] = []

        for index, ref in enumerate(self._collect_refs(session), start=1):
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
                    snippet=tool_call.summary or self._tool_result_snippet(tool_call),
                    target_ref=tool_call.raw_output_ref or tool_call.tool_call_id,
                )
            )

        seen: set[str] = set()
        ordered_refs: list[ReferenceView] = []
        for ref in refs:
            if ref.id not in seen:
                ordered_refs.append(ref)
                seen.add(ref.id)
        return ordered_refs

    @staticmethod
    def _tool_result_snippet(tool_call: ToolCallRecord) -> str:
        if tool_call.summary:
            return tool_call.summary
        if tool_call.normalized_output:
            return str(tool_call.normalized_output)
        return tool_call.tool_name

    @staticmethod
    def _normalized_tool_status(status: ToolCallStatus) -> str:
        mapping = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.SUCCESS: "completed",
            ToolCallStatus.FAILED: "failed",
            ToolCallStatus.TIMEOUT: "timed_out",
            ToolCallStatus.SKIPPED: "skipped",
        }
        return mapping[status]

    @staticmethod
    def _build_safety_note_items(
        session_id: str,
        notes: list[str],
    ) -> list[SafetyEventView]:
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
            elif "not confirmed yet" in lowered or "preliminary" in lowered:
                note_type = "uncertainty"
                severity = "low"

            items.append(
                SafetyEventView(
                    safety_event_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"safety-event:{session_id}:{index}:{note}",
                        )
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
    def _build_unknowns(
        *,
        status: SessionStatus,
        refs: list[str],
        safety_notes: list[str],
    ) -> list[str]:
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
        ordered_unknowns: list[str] = []
        for item in unknowns:
            if item not in seen:
                ordered_unknowns.append(item)
                seen.add(item)
        return ordered_unknowns

    @staticmethod
    def _build_report_safety_notes(
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
                "Knowledge-base corroboration was unavailable; recommendations rely on live observations only."
            )

        seen: set[str] = set()
        ordered_notes: list[str] = []
        for note in notes:
            if note not in seen:
                ordered_notes.append(note)
                seen.add(note)
        return ordered_notes
