"""Verificador Cloudflare Turnstile via httpx (fail-closed).

Nenhum detalhe do provedor e devolvido ao cliente e o token nunca e logado.
Qualquer timeout, erro de rede, resposta invalida ou ``success=false`` resulta
em ``False``; o caso de uso traduz em erro generico de anti-bot.
"""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.modules.identity.application.ports import TurnstileVerifier

_TURNSTILE_ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

_logger = get_logger(__name__)


class CloudflareTurnstileVerifier(TurnstileVerifier):
    """Cliente HTTP do endpoint siteverify, com timeout curto."""

    def __init__(
        self,
        *,
        secret_key: str,
        timeout_seconds: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._secret_key = secret_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def verify(self, *, token: str, remote_ip: str | None) -> bool:
        if not self._secret_key:
            _logger.warning("turnstile_misconfigured", reason="missing_secret")
            return False

        data = {"secret": self._secret_key, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_seconds),
                transport=self._transport,
            ) as client:
                response = await client.post(_TURNSTILE_ENDPOINT, data=data)
            if response.is_error:
                _logger.warning(
                    "turnstile_verification_failed",
                    reason="http_error",
                    status_code=response.status_code,
                )
                return False
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            _logger.warning(
                "turnstile_verification_failed",
                reason="transport_or_payload_error",
                error_type=type(exc).__name__,
            )
            return False

        if not isinstance(payload, dict) or payload.get("success") is not True:
            _logger.info("turnstile_rejected", reason="not_success")
            return False
        return True
