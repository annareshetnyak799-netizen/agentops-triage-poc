from __future__ import annotations

from src.config import settings
from src.domain.enums import SessionStatus
from src.domain.schemas import (
    ApprovalRequest,
    FinalReport,
    Observation,
    SessionView,
    ToolCallRecord,
)
from src.llm.base import BaseLLMAdapter, LLMAnalysisInput
from src.llm.factory import create_llm_adapter
from src.llm.prompt_builder import build_analysis_prompt
from src.observability.logging import get_logger
from src.observability.metrics import metrics_registry
from src.orchestrator.budget import SessionBudget
from src.orchestrator.context import build_session_context
from src.persistence.protocols import SessionRepository
from src.prompts.loader import load_prompt
from src.safety.policy import evaluate_next_steps
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

        session = self._update_status(session_id, SessionStatus.VALIDATING_INPUT)
        session = self._update_status(session_id, SessionStatus.PLANNING)

        if budget.exhausted:
            return self._finalize_partial(
                session=session,
                reason="Budget exhausted before investigation started.",
            )

        if "force_tool_failure" in session.incident.summary.lower():
            session = self._update_status(session_id, SessionStatus.EXECUTING_TOOLS)
            session = self._update_status(session_id, SessionStatus.TOOL_FAILED)
            return self._finalize_partial(
                session=session,
                reason="Forced tool failure triggered for degraded-path testing.",
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

        context = build_session_context(session)
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
        )

        analysis_prompt = build_analysis_prompt(
            template=self._analysis_prompt,
            context=context,
        )

        self._append_trace(
            session_id=session.session_id,
            step_type="prompt_build",
            status="completed",
            details="Analysis prompt built from template and session context.",
            metadata={
                "prompt_template": "analysis.txt",
                "prompt_length": str(len(analysis_prompt)),
            },
        )

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

        self._append_trace(
            session_id=session.session_id,
            step_type="llm_analysis",
            status="completed",
            details="LLM analysis completed.",
            metadata={
                "backend": type(self._llm_adapter).__name__,
                "provider": getattr(self._llm_adapter, "provider_name", settings.llm_provider),
                "model": getattr(self._llm_adapter, "model_name", settings.llm_model),
                "structured_output": "true",
                "hypotheses_count": str(len(llm_result.hypotheses)),
                "next_steps_count": str(len(llm_result.next_steps)),
            },
        )

        policy_result = evaluate_next_steps(llm_result.next_steps)

        report = FinalReport(
            summary=redact_text(llm_result.summary),
            hypotheses=redact_list(llm_result.hypotheses),
            next_steps=redact_list(llm_result.next_steps),
            refs=self._collect_refs(session),
            safety_notes=redact_list(policy_result.safety_notes),
        )

        session = self._repository.set_final_report(
            session_id=session.session_id,
            final_report=report,
        )

        if policy_result.requires_approval:
            approval_reason = "Suggested next step may modify system state."
            if policy_result.trigger == "rollback":
                approval_reason = (
                    "Suggested next step includes a deployment rollback and "
                    "requires explicit human approval."
                )

            session = self._repository.set_approval_request(
                session_id=session.session_id,
                approval_request=ApprovalRequest(
                    reason=approval_reason,
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
        result = await tool.execute(
            ToolRequest(
                tool_name=tool.name,
                payload=tool_payload,
            )
        )

        metrics_registry.increment("tool_calls_total")
        if result.status.value != "success":
            metrics_registry.increment("tool_calls_failed")

        tool_call = ToolCallRecord(
            tool_name=result.tool_name,
            status=result.status,
            latency_ms=result.latency_ms,
            error_type=result.error_type,
            summary=redact_text(result.summary),
        )
        observation = Observation(
            source=result.tool_name,
            summary=redact_text(result.summary),
            refs=self._extract_refs(result.data),
        )

        session = self._repository.add_tool_call(
            session_id=session.session_id,
            tool_call=tool_call,
        )
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
    ) -> SessionView:
        report = FinalReport(
            summary="Partial triage result generated.",
            hypotheses=["Insufficient evidence for a confident conclusion."],
            next_steps=["Collect more telemetry and rerun triage."],
            refs=[],
            safety_notes=[reason],
        )
        session = self._repository.set_final_report(
            session_id=session.session_id,
            final_report=report,
        )
        session = self._update_status(
            session.session_id,
            SessionStatus.PARTIAL_COMPLETED,
        )

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
    
    def _append_trace(
        self,
        session_id: str,
        step_type: str,
        status: str,
        details: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._repository.append_trace(
            session_id=session_id,
            step_type=step_type,
            status=status,
            details=details,
            metadata=metadata,
        )
