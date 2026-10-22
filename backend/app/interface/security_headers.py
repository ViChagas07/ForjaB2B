"""Middleware ASGI de cabecalhos de seguranca do backend.

Aplica headers de baixo risco a todas as respostas e impede que respostas com
dados pessoais/sessao sejam cacheadas. HSTS so e emitido quando a requisicao
chega por HTTPS em producao (considerando proxies confiaveis). O cabecalho
`Server` e removido para nao revelar a versao do servidor.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

from app.core.config import Settings
from app.core.request_context import request_scheme

_SENSITIVE_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/admin",
    "/api/v1/privacy",
    "/api/v1/payments",
    "/api/v1/orders",
    "/api/v1/invoicing",
    "/api/v1/credit",
    "/api/v1/notifications",
    "/api/v1/cart",
    "/api/v1/companies",
)

_REMOVED_HEADERS = {b"server", b"x-powered-by"}

_PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=(), "
    "interest-cohort=()"
)


def _has_header(scope: MutableMapping[str, Any], name: bytes) -> bool:
    return any(key.lower() == name for key, _ in scope.get("headers") or [])


def _is_sensitive_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _SENSITIVE_PREFIXES)


def _security_headers(
    settings: Settings, scheme: str, path: str, authenticated: bool
) -> list[tuple[bytes, bytes]]:
    headers: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", _PERMISSIONS_POLICY.encode("latin-1")),
        (b"cross-origin-resource-policy", b"same-site"),
        (b"x-permitted-cross-domain-policies", b"none"),
    ]
    if authenticated or _is_sensitive_path(path):
        headers.append((b"cache-control", b"no-store"))
        headers.append((b"pragma", b"no-cache"))

    if settings.is_production and settings.security_hsts_enabled and scheme == "https":
        value = f"max-age={settings.security_hsts_max_age_seconds}"
        if settings.security_hsts_include_subdomains:
            value += "; includeSubDomains"
        headers.append((b"strict-transport-security", value.encode("latin-1")))
    return headers


class SecurityHeadersMiddleware:
    """Middleware ASGI puro: headers na resposta e remocao de fingerprinting."""

    def __init__(self, app: Callable[..., Any], settings: Settings) -> None:
        self._app = app
        self._settings = settings

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        scheme = request_scheme(scope, self._settings.trusted_proxy_count)
        path = scope.get("path", "")
        authenticated = _has_header(scope, b"authorization")
        security_headers = _security_headers(self._settings, scheme, path, authenticated)

        async def send_with_security_headers(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                existing = [
                    (key, value)
                    for key, value in message.get("headers") or []
                    if key.lower() not in _REMOVED_HEADERS
                ]
                security_names = {key for key, _ in security_headers}
                # Headers do middleware vencem duplicatas do app (ex.: cache).
                filtered = [(key, value) for key, value in existing if key not in security_names]
                message["headers"] = [*filtered, *security_headers]
            await send(message)

        await self._app(scope, receive, send_with_security_headers)
