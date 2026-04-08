from fastapi import APIRouter, HTTPException, Request
from starlette.responses import PlainTextResponse

from src.api.contracts import SuccessEnvelope, success_envelope
from src.api.serializers import serialize_health, serialize_readiness, serialize_root
from src.config import settings
from src.observability.metrics import metrics_registry

router = APIRouter(tags=["health"])


def render_metrics(snapshot: dict[str, int]) -> str:
    lines = [f"agentops_{name} {value}" for name, value in sorted(snapshot.items())]
    return "\n".join(lines) + ("\n" if lines else "")


@router.get("/", response_model=SuccessEnvelope)
async def root() -> dict[str, object]:
    return success_envelope(
        serialize_root(
            service=settings.app_name,
            version="0.1.0",
            environment=settings.environment,
            docs_url="/docs",
            health_url="/health",
            metrics_url="/metrics",
        ),
    )


@router.get("/health", response_model=SuccessEnvelope)
async def health() -> dict[str, object]:
    return success_envelope(
        serialize_health(
            service=settings.app_name,
            version="0.1.0",
            environment=settings.environment,
        )
    )


@router.get("/ready", response_model=SuccessEnvelope)
async def ready(request: Request) -> dict[str, object]:
    has_repository = hasattr(request.app.state, "repository")
    has_orchestrator = hasattr(request.app.state, "orchestrator")

    if not (has_repository and has_orchestrator):
        raise HTTPException(status_code=503, detail="Service is not ready to accept new sessions.")

    degraded = (
        metrics_registry.get("degraded_sessions_total") > 0
        or metrics_registry.get("tool_calls_failed") > 0
        or metrics_registry.get("llm_calls_failed") > 0
    )

    readiness_state = "degraded" if degraded else "ready"
    return success_envelope(
        serialize_readiness(
            service=settings.app_name,
            version="0.1.0",
            environment=settings.environment,
            ready=True,
            readiness_state=readiness_state,
        )
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        render_metrics(metrics_registry.snapshot()),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
