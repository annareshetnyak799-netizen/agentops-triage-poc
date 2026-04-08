from fastapi import APIRouter, HTTPException, status

from src.domain.schemas import ApprovalInput, ApprovalView, IncidentInput, SessionView, TraceStep
from src.orchestrator.service import OrchestratorService
from src.persistence.factory import create_session_repository

router = APIRouter(prefix="", tags=["incident"])

repository = create_session_repository()
orchestrator = OrchestratorService(repository=repository)


@router.post(
    "/incident",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident_session(incident: IncidentInput) -> SessionView:
    session = repository.create_session(incident)
    session = await orchestrator.run_initial_triage(session.session_id)
    return session


@router.get("/sessions/{session_id}", response_model=SessionView)
async def get_session(session_id: str) -> SessionView:
    session = repository.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return session


@router.get("/sessions/{session_id}/trace", response_model=list[TraceStep])
async def get_session_trace(session_id: str) -> list[TraceStep]:
    trace = repository.get_trace(session_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return trace


@router.post(
    "/sessions/{session_id}/approval",
    response_model=ApprovalView,
)
async def approve_session(
    session_id: str,
    approval_input: ApprovalInput,
) -> ApprovalView:
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

    return ApprovalView(
        session_id=session.session_id,
        status=session.status,
        decision=approval_input.decision,
        comment=approval_input.comment,
    )



