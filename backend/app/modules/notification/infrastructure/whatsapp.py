"""Adaptador do canal WhatsApp via Z-API (item 3).

Construtor usa ZAPI_INSTANCE_ID + ZAPI_TOKEN (montam a URL send-text) e
ZAPI_CLIENT_TOKEN no header `Client-Token` (esquema Z-API). A chave/token
ficam SOMENTE no backend, nunca em logs; erros com mensagem estatica e o
retry fica no mecanismo do outbox (FAILED + max_attempts). O canal so e
instalado com WHATSAPP_ENABLED=true E numero E.164 E opt-in explicito —
regras verificadas ANTES, no DispatchOutbox.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError


class ZApiWhatsAppSender:
    """Envia mensagem de texto puro via Z-API (send-text)."""

    def __init__(
        self,
        *,
        instance_id: str,
        token: str,
        client_token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = "https://api.z-api.io",
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=f"{base_url}/instances/{instance_id}/token/{token}",
            headers={"Client-Token": client_token},
            timeout=timeout,
            transport=transport,
        )

    async def send(self, *, phone: str, message: str) -> None:
        payload = {"phone": phone, "message": message}
        try:
            response = await self._client.post("/send-text", json=payload)
        except httpx.TimeoutException as exc:
            raise EmailTransientError("whatsapp provider timeout") from exc
        except httpx.HTTPError as exc:
            raise EmailTransientError("whatsapp provider unavailable") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise EmailTransientError("whatsapp provider busy")
        if response.status_code >= 400:
            raise EmailPermanentError("whatsapp rejected")

    async def aclose(self) -> None:
        await self._client.aclose()


def build_whatsapp_sender(settings: Settings) -> ZApiWhatsAppSender | None:
    """Fabrica: canal DESLIGADO por padrao (WHATSAPP_ENABLED=false)."""
    if not settings.whatsapp_enabled:
        return None
    if not settings.zapi_instance_id or not settings.zapi_token or not settings.zapi_client_token:
        raise EmailPermanentError("whatsapp misconfigured")
    return ZApiWhatsAppSender(
        instance_id=settings.zapi_instance_id,
        token=settings.zapi_token,
        client_token=settings.zapi_client_token,
    )
