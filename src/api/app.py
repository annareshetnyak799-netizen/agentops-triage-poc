from __future__ import annotations

from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Request
from starlette.responses import Response

from src.api.routes.health import router as health_router
from src.api.routes.incident import router as incident_router
from src.observability.logging import configure_logging, get_logger
from src.observability.metrics import metrics_registry
from src.observability.tracing import clear_request_id, set_request_id

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="AgentOps Triage PoC",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_observability_middleware(
    request: Request,
    call_next,
) -> Response:
    request_id = set_request_id()
    started_at = monotonic()

    logger.info(
        "Request started.",
        extra={
            "request_id": request_id,
            "step_type": "http_request",
            "status": "started",
        },
    )

    try:
        response = await call_next(request)
    except Exception:
        metrics_registry.increment("http_requests_failed")
        logger.exception(
            "Request failed.",
            extra={
                "request_id": request_id,
                "step_type": "http_request",
                "status": "failed",
            },
        )
        clear_request_id()
        raise

    latency_ms = int((monotonic() - started_at) * 1000)
    metrics_registry.increment("http_requests_total")

    logger.info(
        "Request completed.",
        extra={
            "request_id": request_id,
            "step_type": "http_request",
            "status": response.status_code,
            "latency_ms": latency_ms,
        },
    )

    response.headers["X-Request-ID"] = request_id
    clear_request_id()
    return response


app.include_router(health_router)
app.include_router(incident_router)

