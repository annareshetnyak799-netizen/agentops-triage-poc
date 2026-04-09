from __future__ import annotations

from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse, Response

from src.api.contracts import error_envelope, http_error_code, validation_error_envelope
from src.api.routes.health import router as health_router
from src.api.routes.incident import router as incident_router
from src.config import settings
from src.observability.logging import configure_logging, get_logger
from src.observability.metrics import metrics_registry
from src.observability.tracing import clear_request_id, get_request_id, set_request_id
from src.persistence.factory import create_session_repository
from src.orchestrator.service import OrchestratorService

logger = get_logger(__name__)


def _setup_otel(app: FastAPI) -> None:
    """Wire OpenTelemetry tracing when AGENTOPS_OTEL_ENABLED=true (G14).

    Uses ConsoleSpanExporter for PoC; swap for OTLPSpanExporter in production.
    """
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing enabled.", extra={"step_type": "startup", "status": "otel_enabled"})
    except ImportError:
        logger.warning("OpenTelemetry packages not available; tracing disabled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    _setup_otel(app)
    repository = create_session_repository()
    app.state.repository = repository
    app.state.orchestrator = OrchestratorService(repository=repository)
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="AgentOps Triage PoC",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(http_error_code(exc), str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=validation_error_envelope(exc))


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled application error.",
        extra={
            "request_id": get_request_id(),
            "step_type": "http_request",
            "status": "failed",
            "error_type": exc.__class__.__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content=error_envelope("INTERNAL_ERROR", "Unexpected server-side failure."),
    )


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next) -> Response:
    request_id = set_request_id()
    started_at = monotonic()

    logger.info(
        "Request started.",
        extra={"request_id": request_id, "step_type": "http_request", "status": "started"},
    )

    try:
        response = await call_next(request)
    except Exception:
        metrics_registry.increment("http_requests_failed")
        logger.exception(
            "Request failed.",
            extra={"request_id": request_id, "step_type": "http_request", "status": "failed"},
        )
        clear_request_id()
        raise

    latency_ms = int((monotonic() - started_at) * 1000)
    metrics_registry.increment("http_requests_total")
    metrics_registry.observe_latency("end_to_end_latency_ms", latency_ms)

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
