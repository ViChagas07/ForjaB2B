"""Middleware ASGI de rate limiting por classe de rota.

A classificacao usa o path normalizado (nunca o path cru com IDs) e a
identidade vem do JWT verificado (usuario) ou do IP real (visitante). Rotas
publicas de autenticacao usam IP; o bloqueio por conta+IP de login e aplicado
no endpoint, depois do parse do e-mail. Health e metricas ficam de fora.
"""

from __future__ import annotations

import json
from collections.abc import Callable, MutableMapping
from typing import Any
from urllib.parse import urlencode

from app.application.rate_limit import RateLimitClass, RateLimitDecision, RateLimiter
from app.application.security import TokenService
from app.core.config import Settings
from app.core.correlation import get_request_id
from app.core.request_context import client_ip
from app.interface.schemas import ProblemDetails

_EXCLUDED_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/favicon",
)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_OAUTH_PATHS = frozenset(
    {
        "/api/v1/auth/google",
        "/api/v1/auth/google/callback",
        "/api/v1/auth/oauth/exchange",
    }
)
_OAUTH_REDIRECT_PATHS = frozenset(
    {
        "/api/v1/auth/google",
        "/api/v1/auth/google/callback",
    }
)


def _classify_auth(path: str) -> RateLimitClass | None:
    if path in _OAUTH_PATHS:
        return RateLimitClass.OAUTH
    if path in {"/api/v1/auth", "/api/v1/auth/login"}:
        return RateLimitClass.AUTH
    if path.startswith("/api/v1/auth/"):
        return RateLimitClass.AUTH
    return None


def _classify_registration(path: str, method: str) -> RateLimitClass | None:
    if method == "POST" and path in {"/api/v1/companies", "/api/v1/consumers"}:
        return RateLimitClass.REGISTRATION
    return None


def _classify_admin_write(path: str, method: str) -> RateLimitClass | None:
    if path.startswith("/api/v1/admin") and method in _WRITE_METHODS:
        return RateLimitClass.ADMIN_WRITE
    if path.startswith("/api/v1/companies/") and path.endswith("/approve"):
        return RateLimitClass.ADMIN_WRITE
    return None


def _classify_webhook(path: str, method: str) -> RateLimitClass | None:
    if method == "POST" and path in {
        "/api/v1/payments/webhook",
        "/api/v1/payments/stripe/webhook",
    }:
        return RateLimitClass.WEBHOOK
    return None


def _classify_coupon_preview(path: str, method: str) -> RateLimitClass | None:
    if method == "POST" and path == "/api/v1/orders/coupon-preview":
        return RateLimitClass.COUPON_PREVIEW
    return None


def _classify_data(path: str, method: str) -> RateLimitClass | None:
    # O suggest tem balde PROPRIO (mais folgado): esgotar o balde digitando no
    # dropdown nao pode bloquear a busca da pagina de resultados.
    if path == "/api/v1/search/suggest":
        return RateLimitClass.SUGGEST
    if path.startswith("/api/v1/search"):
        return RateLimitClass.SEARCH
    if path.startswith("/api/v1/catalog"):
        if method == "GET":
            return RateLimitClass.PUBLIC_READ
        return RateLimitClass.AUTHENTICATED
    if path.startswith("/api/v1/"):
        return RateLimitClass.AUTHENTICATED
    return None


def classify_request(path: str, method: str) -> RateLimitClass | None:
    """Mapeia path/metodo para uma classe de limite (None = isento)."""
    if method == "OPTIONS" or any(path.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
        return None
    rate_class = _classify_auth(path)
    if rate_class is None:
        rate_class = _classify_registration(path, method)
    if rate_class is None:
        rate_class = _classify_webhook(path, method)
    if rate_class is None:
        rate_class = _classify_admin_write(path, method)
    if rate_class is None:
        rate_class = _classify_coupon_preview(path, method)
    if rate_class is None:
        rate_class = _classify_data(path, method)
    return rate_class


def _bearer(scope: MutableMapping[str, Any]) -> str | None:
    for name, value in scope.get("headers") or []:
        if name.lower() == b"authorization":
            raw = value.decode("latin-1").strip()
            if raw.startswith("Bearer "):
                return raw[len("Bearer ") :].strip() or None
    return None


def request_identity(scope: MutableMapping[str, Any], token_service: TokenService, ip: str) -> str:
    """Identidade do limite: usuario verificado ou IP real."""
    token = _bearer(scope)
    if token is not None:
        try:
            auth = token_service.decode_access_token(token)
        except Exception:  # noqa: BLE001 - token invalido cai no IP
            auth = None
        if auth is not None:
            return f"user:{auth.user_id}"
    return f"ip:{ip}"


def _problem_body(*, status: int, detail: str, path: str) -> bytes:
    problem = ProblemDetails(
        type="urn:forja:problem:rate_limit_exceeded",
        title="Too Many Requests",
        status=status,
        detail=detail,
        instance=path,
        request_id=get_request_id(),
        trace_id=get_request_id(),
    )
    return json.dumps(problem.model_dump(exclude_none=True)).encode("utf-8")


class RateLimitMiddleware:
    """Middleware ASGI puro: 429 padronizado e cabecalhos RateLimit-*."""

    def __init__(
        self,
        app: Callable[..., Any],
        *,
        limiter: RateLimiter,
        settings: Settings,
        token_service: TokenService,
    ) -> None:
        self._app = app
        self._limiter = limiter
        self._settings = settings
        self._token_service = token_service

    async def _coupon_preview_decision(
        self, scope: MutableMapping[str, Any], ip: str
    ) -> RateLimitDecision:
        """Aplica balde por IP e, se livre, o balde por usuario."""
        ip_decision = await self._limiter.check(
            rate_class=RateLimitClass.COUPON_PREVIEW_IP, identity=f"ip:{ip}"
        )
        if not ip_decision.allowed:
            return ip_decision
        return await self._limiter.check(
            rate_class=RateLimitClass.COUPON_PREVIEW,
            identity=request_identity(scope, self._token_service, ip),
        )

    async def _decision_for(
        self,
        scope: MutableMapping[str, Any],
        rate_class: RateLimitClass,
        ip: str,
    ) -> RateLimitDecision:
        if rate_class == RateLimitClass.COUPON_PREVIEW:
            return await self._coupon_preview_decision(scope, ip)
        if rate_class in {
            RateLimitClass.AUTH,
            RateLimitClass.OAUTH,
            RateLimitClass.REGISTRATION,
        }:
            identity = f"ip:{ip}"
        else:
            identity = request_identity(scope, self._token_service, ip)
        return await self._limiter.check(rate_class=rate_class, identity=identity)

    def _oauth_rate_limit_redirect(self, path: str) -> str | None:
        if path not in _OAUTH_REDIRECT_PATHS:
            return None
        base = self._settings.google_oauth_frontend_redirect
        if not base:
            return None
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}{urlencode({'error': 'rate_limited'})}"

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http" or not self._settings.rate_limit_enabled:
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        rate_class = classify_request(path, method)
        if rate_class is None:
            await self._app(scope, receive, send)
            return

        ip = client_ip(scope, self._settings.trusted_proxy_count)
        decision = await self._decision_for(scope, rate_class, ip)
        headers = [
            (b"ratelimit-limit", str(decision.limit).encode()),
            (b"ratelimit-remaining", str(decision.remaining).encode()),
            (b"ratelimit-reset", str(decision.reset_after_seconds).encode()),
        ]
        if not decision.allowed:
            retry = str(decision.retry_after_seconds)
            headers.append((b"retry-after", retry.encode()))
            redirect_url = self._oauth_rate_limit_redirect(path)
            if redirect_url is not None:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 302,
                        "headers": [
                            (b"location", redirect_url.encode()),
                            (b"content-length", b"0"),
                            (b"cache-control", b"no-store"),
                            *headers,
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return
            body = _problem_body(
                status=429,
                detail="Muitas requisicoes. Tente novamente mais tarde.",
                path=path,
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/problem+json"),
                        (b"content-length", str(len(body)).encode()),
                        *headers,
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_with_rate_headers(message: MutableMapping[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                message.setdefault("headers", []).extend(headers)
            await send(message)

        await self._app(scope, receive, send_with_rate_headers)
