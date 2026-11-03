"""Cliente Twilio Verify v2 e fake deterministico para testes/dry-run.

Usa a API REST com Basic auth (Account SID + Auth Token), sem SDK sincrono.
Timeout curto, sem retry. Respostas 404/429/5xx, timeout e rede sao falhas
genericas; telefone, codigo e credenciais nunca entram em log.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.identity.application.ports import PhoneVerificationService

_BASE_URL = "https://verify.twilio.com/v2/Services"
_TIMEOUT_SECONDS = 5.0

# Locales suportados pelo Twilio Verify (pt-BR e enviado como pt).
_LOCALE_MAP: dict[str, str] = {
    "pt-BR": "pt",
    "en": "en",
    "es": "es",
    "ar": "ar",
    "de": "de",
    "fr": "fr",
    "it": "it",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "zh-CN": "zh-CN",
}

_logger = get_logger(__name__)


def twilio_locale(locale: str | None) -> str | None:
    """Mapeia o locale do projeto para um suportado; desconhecido -> None."""
    if locale is None:
        return None
    return _LOCALE_MAP.get(locale)


class TwilioVerifyService(PhoneVerificationService):
    """Implementacao da porta PhoneVerificationService sobre Twilio Verify."""

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        service_sid: str,
        timeout_seconds: float = _TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._service_sid = service_sid
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        data = {"To": phone_e164, "Channel": "sms"}
        mapped_locale = twilio_locale(locale)
        if mapped_locale is not None:
            data["Locale"] = mapped_locale
        payload = await self._post("Verifications", data=data)
        if payload is None:
            return False
        status = payload.get("status")
        return status in {"pending", "approved"}

    async def check(self, *, phone_e164: str, code: str) -> bool:
        payload = await self._post("VerificationCheck", data={"To": phone_e164, "Code": code})
        if payload is None:
            return False
        return payload.get("status") == "approved"

    async def _post(self, action: str, *, data: dict[str, str]) -> dict[str, object] | None:
        url = f"{_BASE_URL}/{self._service_sid}/{action}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_seconds),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(self._account_sid, self._auth_token),
                )
        except httpx.HTTPError as exc:
            _logger.warning(
                "phone_verification_provider_failed",
                action=action,
                reason="transport",
                error_type=type(exc).__name__,
            )
            return None
        if response.status_code == 404:
            _logger.info(
                "phone_verification_provider_not_found",
                action=action,
                status_code=404,
            )
            return None
        if response.is_error:
            _logger.warning(
                "phone_verification_provider_failed",
                action=action,
                reason="http_error",
                status_code=response.status_code,
            )
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            _logger.warning(
                "phone_verification_provider_failed",
                action=action,
                reason="invalid_payload",
                error_type=type(exc).__name__,
            )
            return None
        return payload if isinstance(payload, dict) else None


class FakePhoneVerificationService(PhoneVerificationService):
    """Fake deterministico para testes e dry-run local (nunca producao)."""

    def __init__(self, *, fixed_code: str = "123456") -> None:
        self._fixed_code = fixed_code
        self._started: set[str] = set()

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        _ = locale
        self._started.add(phone_e164)
        return True

    async def check(self, *, phone_e164: str, code: str) -> bool:
        return phone_e164 in self._started and code == self._fixed_code


def build_phone_verification_service(
    settings: Settings,
) -> PhoneVerificationService | None:
    """Twilio real quando configurado; fake deterministico so fora de producao."""
    if settings.phone_verification_dry_run and not settings.is_production:
        return FakePhoneVerificationService()
    account_sid = _secret_value(settings.twilio_account_sid)
    auth_token = _secret_value(settings.twilio_auth_token)
    service_sid = _secret_value(settings.twilio_verify_service_sid)
    if account_sid is None or auth_token is None or service_sid is None:
        return None
    return TwilioVerifyService(
        account_sid=account_sid,
        auth_token=auth_token,
        service_sid=service_sid,
    )


def _secret_value(value: object) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    if getter is None:
        return None
    raw = str(getter()).strip()
    return raw or None
