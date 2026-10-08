"""Middleware ASGI de correlacao: request ID por requisicao.

Le `X-Request-ID` quando presente (propagacao de proxies/edge) ou gera um
novo identificador, expoe em app.core.correlation para logs e devolve no
header `X-Request-ID` da resposta. O trace context W3C (`traceparent`) e
tratado pela instrumentacao OpenTelemetry, nao por este middleware.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

from app.core.correlation import new_request_id, reset_request_id, set_request_id

REQUEST_ID_HEADER = "x-request-id"

_SCOPE_HEADERS_LIMIT = 100  # defesa contra headers absurdamente grandes


def _extract_request_id(scope: MutableMapping[str, Any]) -> str:
    headers: list[tuple[bytes, bytes]] = scope.get("headers") or []
    for name, value in headers[:_SCOPE_HEADERS_LIMIT]:
        if name.lower() == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1").strip()
            if candidate:
                return candidate
    return new_request_id()


class CorrelationIdMiddleware:
    """Middleware ASGI puro (sem BaseHTTPMiddleware, menor overhead)."""

    def __init__(self, app: Callable[..., Any]) -> None:
        self._app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)
        token = set_request_id(request_id)

        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode("latin-1")))
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            reset_request_id(token)
