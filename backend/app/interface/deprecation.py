"""Marcacao de rotas depreciadas com cabecalhos RFC 8594/9745.

Uso:

    @router.post("/webhook", deprecated=True)
    @deprecated_route(sunset=date(2027, 4, 30), successor="/api/v1/payments/stripe/webhook")
    async def legacy_webhook(...): ...

O decorator apenas anexa metadados ao endpoint; o middleware
``DeprecationMiddleware`` encontra as rotas marcadas no app e adiciona:

- ``Deprecation: true``
- ``Sunset: <HTTP-date>``
- ``Link: <sucessor>; rel="successor-version"``

A metrica ``forja_deprecated_route_requests_total`` conta o uso por rota.
"""

from __future__ import annotations

import re
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from email.utils import format_datetime
from typing import Any, TypeVar

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.core.metrics import increment_deprecated_route_request

F = TypeVar("F", bound=Callable[..., Any])

DEPRECATION_ATTRIBUTE = "__forja_deprecation__"


@dataclass(frozen=True, kw_only=True)
class DeprecationInfo:
    """Metadados de uma rota depreciada."""

    sunset: date
    successor: str | None = None
    reason: str | None = None

    def headers(self) -> dict[str, str]:
        sunset_dt = datetime.combine(self.sunset, time.min, tzinfo=UTC)
        headers = {
            "Deprecation": "true",
            "Sunset": format_datetime(sunset_dt, usegmt=True),
        }
        if self.successor:
            headers["Link"] = f'<{self.successor}>; rel="successor-version"'
        if self.reason:
            headers["Warning"] = f'299 - "{self.reason}"'
        return headers


def deprecated_route(
    *,
    sunset: date,
    successor: str | None = None,
    reason: str | None = None,
) -> Callable[[F], F]:
    """Anexa metadados de depreciacao ao endpoint (sem alterar a assinatura)."""
    info = DeprecationInfo(sunset=sunset, successor=successor, reason=reason)

    def decorator(func: F) -> F:
        setattr(func, DEPRECATION_ATTRIBUTE, info)
        return func

    return decorator


def _path_pattern(path: str) -> re.Pattern[str]:
    escaped = re.escape(path)
    escaped = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", escaped)
    return re.compile(f"^{escaped}$")


@dataclass(frozen=True, kw_only=True)
class _DeprecatedRoute:
    method: str
    pattern: re.Pattern[str]
    info: DeprecationInfo


def _collect(app: FastAPI) -> list[_DeprecatedRoute]:
    routes: list[_DeprecatedRoute] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        info = getattr(route.endpoint, DEPRECATION_ATTRIBUTE, None)
        if not isinstance(info, DeprecationInfo):
            continue
        for method in route.methods or ():
            routes.append(
                _DeprecatedRoute(
                    method=method.upper(), pattern=_path_pattern(route.path), info=info
                )
            )
    return routes


class DeprecationMiddleware:
    """ASGI puro: adiciona cabecalhos e metricas em rotas depreciadas."""

    def __init__(self, app: Callable[..., Any], *, routes: list[_DeprecatedRoute]) -> None:
        self._app = app
        self._routes = routes

    def _match(self, method: str, path: str) -> DeprecationInfo | None:
        for route in self._routes:
            if route.method == method and route.pattern.match(path):
                return route.info
        return None

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        info = self._match(method, path)
        if info is None:
            await self._app(scope, receive, send)
            return

        increment_deprecated_route_request(method=method, route=path)
        headers = list(info.headers().items())

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                message_headers = message.setdefault("headers", [])
                for name, value in headers:
                    message_headers.append(
                        (name.lower().encode("latin-1"), value.encode("latin-1"))
                    )
            await send(message)

        await self._app(scope, receive, send_with_headers)


def register_deprecation(app: FastAPI) -> None:
    """Instala o middleware com o registro de rotas marcadas no app."""
    routes = _collect(app)
    app.add_middleware(DeprecationMiddleware, routes=routes)
