"""Request ID / correlation ID por requisicao, baseado em contextvars.

O middleware de interface (app.interface.middleware) preenche o contexto;
logging e handlers leem daqui. Trace context W3C (traceparent) e propagado
pela instrumentacao OpenTelemetry; aqui fica apenas o request ID.
"""

from __future__ import annotations

import contextvars
import uuid

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "forja_request_id", default=None
)


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_var.reset(token)


def get_request_id() -> str | None:
    return _request_id_var.get()
