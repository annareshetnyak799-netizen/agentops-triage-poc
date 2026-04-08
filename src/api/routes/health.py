from fastapi import APIRouter

from src.config import settings
from src.domain.schemas import HealthResponse, RootResponse
from src.observability.metrics import metrics_registry

router = APIRouter(tags=["health"])


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version="0.1.0",
        environment=settings.environment,
        docs_url="/docs",
        health_url="/health",
        metrics_url="/metrics",
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.get("/metrics", response_model=dict[str, int])
async def metrics() -> dict[str, int]:
    return metrics_registry.snapshot()
