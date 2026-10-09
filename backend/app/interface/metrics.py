"""Middleware ASGI de coleta de metricas Prometheus.

Registra contador e histograma de latencia por metodo/status. Nao inclui
path para evitar cardinalidade explosiva. Aplicado globalmente na factory.
"""

from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping
from typing import Any

from app.core.metrics import increment_request_counter, observe_request_duration


class PrometheusMiddleware:
    """Middleware ASGI puro (sem BaseHTTPMiddleware) para metricas HTTP."""

    def __init__(self, app: Callable[..., Any]) -> None:
        self._app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        start = time.perf_counter()

        async def send_capture_status(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                status_code = message.get("status", 500)
                _record(method, int(status_code), start)
            await send(message)

        try:
            await self._app(scope, receive, send_capture_status)
        except Exception:
            _record(method, 500, start)
            raise


def _record(method: str, status_code: int, start: float) -> None:
    duration = time.perf_counter() - start
    increment_request_counter(method=method, status_code=status_code)
    observe_request_duration(method=method, status_code=status_code, duration=duration)
