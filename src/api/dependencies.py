from __future__ import annotations

from fastapi import FastAPI, Request

from src.orchestrator.service import OrchestratorService
from src.persistence.factory import create_session_repository
from src.persistence.protocols import SessionRepository


def _resolve_app(target: Request | FastAPI) -> FastAPI:
    return target.app if isinstance(target, Request) else target


def ensure_app_services(target: Request | FastAPI) -> None:
    app = _resolve_app(target)
    if not hasattr(app.state, "repository"):
        repository = create_session_repository()
        app.state.repository = repository
        app.state.orchestrator = OrchestratorService(repository=repository)


def get_repository(request: Request) -> SessionRepository:
    ensure_app_services(request)
    return request.app.state.repository


def get_orchestrator(request: Request) -> OrchestratorService:
    ensure_app_services(request)
    return request.app.state.orchestrator
