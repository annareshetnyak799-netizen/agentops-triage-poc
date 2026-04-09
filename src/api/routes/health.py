from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import PlainTextResponse

from src.api.contracts import SuccessEnvelope, success_envelope
from src.api.serializers import serialize_health, serialize_readiness, serialize_root
from src.config import settings
from src.observability.metrics import _METRIC_META, metrics_registry

router = APIRouter(tags=["health"])


def render_metrics(snapshot: dict[str, int]) -> str:
    """Render metrics in Prometheus text format (version 0.0.4).

    Emits # HELP and # TYPE lines for all known metrics, followed by the value line.
    Unknown metrics (e.g. histogram bucket sub-series) are rendered without metadata
    and grouped under their parent metric's # TYPE block if already emitted.
    """
    lines: list[str] = []
    emitted_types: set[str] = set()

    # Emit known metrics first (with # HELP / # TYPE).
    for suffix, (metric_type, help_text) in sorted(_METRIC_META.items()):
        full_name = f"agentops_{suffix}"
        lines.append(f"# HELP {full_name} {help_text}")
        lines.append(f"# TYPE {full_name} {metric_type}")
        emitted_types.add(full_name)
        value = snapshot.get(suffix, 0)
        lines.append(f"{full_name} {value}")

        # Emit histogram bucket sub-series right after the parent.
        if metric_type == "histogram":
            for key, val in sorted(snapshot.items()):
                if key.startswith(f"{suffix}_bucket_"):
                    lines.append(f"agentops_{key} {val}")

    # Emit any remaining counters not covered by _METRIC_META.
    for key, value in sorted(snapshot.items()):
        full_name = f"agentops_{key}"
        if full_name not in emitted_types and not any(
            key.startswith(f"{s}_bucket_") for s in _METRIC_META
        ):
            lines.append(f"# TYPE {full_name} counter")
            lines.append(f"{full_name} {value}")

    return "\n".join(lines) + "\n"


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
