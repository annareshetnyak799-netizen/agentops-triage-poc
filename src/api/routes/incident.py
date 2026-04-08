from fastapi import APIRouter, Depends, HTTPException, status

from src.api.contracts import SuccessEnvelope, success_envelope
from src.api.dependencies import get_orchestrator, get_repository
from src.api.serializers import (
    serialize_approval,
    serialize_incident_result,
    serialize_session,
    serialize_trace,
)
from src.domain.schemas import ApprovalInput, ApprovalView, IncidentInput
from src.orchestrator.service import OrchestratorService
from src.persistence.protocols import SessionRepository

router = APIRouter(prefix="", tags=["incident"])


@router.post(
    "/incident",
    response_model=SuccessEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident_session(
    incident: IncidentInput,
    repository: SessionRepository = Depends(get_repository),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
) -> dict[str, object]:
    session = repository.create_session(incident)
    session = await orchestrator.run_initial_triage(session.session_id)
    return success_envelope(
        serialize_incident_result(session),
        session_id=session.session_id,
    )


@router.get("/sessions/{session_id}", response_model=SuccessEnvelope)
async def get_session(
    session_id: str,
    repository: SessionRepository = Depends(get_repository),
) -> dict[str, object]:
    session = repository.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return success_envelope(
        serialize_session(session),
        session_id=session.session_id,
    )


@router.get("/sessions/{session_id}/trace", response_model=SuccessEnvelope)
async def get_session_trace(
    session_id: str,
    repository: SessionRepository = Depends(get_repository),
) -> dict[str, object]:
    trace = repository.get_trace(session_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return success_envelope(
        serialize_trace(session_id, trace),
        session_id=session_id,
    )


@router.post(
    "/sessions/{session_id}/approval",
    response_model=SuccessEnvelope,
)
async def approve_session(
    session_id: str,
    approval_input: ApprovalInput,
    repository: SessionRepository = Depends(get_repository),
) -> dict[str, object]:
    try:
        session = repository.apply_approval(session_id, approval_input)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    approval = ApprovalView(
        session_id=session.session_id,
        status=session.status,
        decision=approval_input.decision,
        comment=approval_input.comment,
    )
    return success_envelope(
        serialize_approval(approval, session),
        session_id=session.session_id,
    )
