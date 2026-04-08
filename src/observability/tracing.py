from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4


request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None = None) -> str:
    value = request_id or str(uuid4())
    request_id_ctx.set(value)
    return value


def get_request_id() -> str | None:
    return request_id_ctx.get()


def clear_request_id() -> None:
    request_id_ctx.set(None)
