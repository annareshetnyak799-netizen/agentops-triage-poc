from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from src.observability.tracing import get_request_id


class ResponseMeta(BaseModel):
    request_id: str | None = None
    session_id: str | None = None
    generated_at: str

    model_config = ConfigDict(extra="forbid")


class SuccessEnvelope(BaseModel):
    status: str = "ok"
    data: Any
    meta: ResponseMeta

    model_config = ConfigDict(extra="forbid")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ErrorEnvelope(BaseModel):
    status: str = "error"
    error: ErrorBody
    meta: ResponseMeta

    model_config = ConfigDict(extra="forbid")


def build_meta(session_id: str | None = None) -> ResponseMeta:
    return ResponseMeta(
        request_id=get_request_id(),
        session_id=session_id,
        generated_at=datetime.now(UTC).isoformat(),
    )


def success_envelope(data: Any, session_id: str | None = None) -> dict[str, Any]:
    return SuccessEnvelope(
        data=data,
        meta=build_meta(session_id=session_id),
    ).model_dump(mode="json")


def error_envelope(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    return ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or {},
        ),
        meta=build_meta(session_id=session_id),
    ).model_dump(mode="json")


def http_error_code(exc: HTTPException) -> str:
    mapping = {
        400: "INVALID_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_FAILED",
        500: "INTERNAL_ERROR",
        504: "TIMEOUT",
    }
    return mapping.get(exc.status_code, "INTERNAL_ERROR")


def validation_error_envelope(exc: RequestValidationError) -> dict[str, Any]:
    return error_envelope(
        "VALIDATION_FAILED",
        "Request validation failed.",
        details={"errors": exc.errors()},
    )
