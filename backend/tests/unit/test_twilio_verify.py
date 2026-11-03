"""Testes do adaptador Twilio Verify (httpx mockado, sem rede real)."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest
from structlog.testing import capture_logs

from app.modules.identity.infrastructure.twilio_verify import (
    FakePhoneVerificationService,
    TwilioVerifyService,
    twilio_locale,
)

_SID = "AC-test-account"
_TOKEN = "test-auth-token"
_SERVICE = "VA-test-service"
_PHONE = "+5511999991234"
_CODE = "123456"


def _service(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    timeout_seconds: float = 5.0,
) -> TwilioVerifyService:
    return TwilioVerifyService(
        account_sid=_SID,
        auth_token=_TOKEN,
        service_sid=_SERVICE,
        timeout_seconds=timeout_seconds,
        transport=httpx.MockTransport(handler),
    )


def test_locale_map_cobre_os_11_idiomas() -> None:
    assert twilio_locale("pt-BR") == "pt"
    for locale in ("en", "es", "ar", "de", "fr", "it", "ja", "ko", "ru", "zh-CN"):
        assert twilio_locale(locale) == locale
    assert twilio_locale("xx") is None
    assert twilio_locale(None) is None


async def test_start_envia_basic_auth_to_channel_e_locale() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(201, json={"status": "pending", "sid": "VE1"})

    service = _service(handler)
    assert await service.start(phone_e164=_PHONE, locale="pt-BR")

    request = captured[0]
    assert request.method == "POST"
    assert request.url.path.endswith(f"/Services/{_SERVICE}/Verifications")
    assert request.headers["authorization"].startswith("Basic ")
    body = parse_qs(request.content.decode())
    assert body["To"] == [_PHONE]
    assert body["Channel"] == ["sms"]
    assert body["Locale"] == ["pt"]


async def test_start_sem_locale_suportado_omite_campo() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(201, json={"status": "pending"})

    service = _service(handler)
    assert await service.start(phone_e164=_PHONE, locale="xx")
    assert "Locale" not in parse_qs(captured[0].content.decode())


@pytest.mark.parametrize("status", ["pending", "approved"])
async def test_start_aceita_pending_e_approved(status: str) -> None:
    service = _service(lambda request: httpx.Response(201, json={"status": status}))
    assert await service.start(phone_e164=_PHONE, locale="en")


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(201, json={"status": "canceled"}),
        lambda request: httpx.Response(201, content=b"not-json"),
        lambda request: httpx.Response(429, json={"message": "too many"}),
        lambda request: httpx.Response(500, json={"message": "boom"}),
    ],
)
async def test_start_falhas_genericas(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    service = _service(handler)
    with capture_logs() as logs:
        assert not await service.start(phone_e164=_PHONE, locale="en")
    rendered = str(logs)
    assert _PHONE not in rendered
    assert _SID not in rendered
    assert _TOKEN not in rendered


async def test_check_approved() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"status": "approved"})

    service = _service(handler)
    assert await service.check(phone_e164=_PHONE, code=_CODE)
    request = captured[0]
    assert request.url.path.endswith(f"/Services/{_SERVICE}/VerificationCheck")
    body = parse_qs(request.content.decode())
    assert body["To"] == [_PHONE]
    assert body["Code"] == [_CODE]


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(200, json={"status": "pending"}),
        lambda request: httpx.Response(404, json={"message": "not found"}),
        lambda request: httpx.Response(429, json={"message": "too many"}),
        lambda request: httpx.Response(503, json={"message": "unavailable"}),
        lambda request: httpx.Response(200, content=b"not-json"),
    ],
)
async def test_check_falhas_genericas(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    service = _service(handler)
    with capture_logs() as logs:
        assert not await service.check(phone_e164=_PHONE, code=_CODE)
    rendered = str(logs)
    assert _PHONE not in rendered
    assert _CODE not in rendered
    assert _TOKEN not in rendered


async def test_timeout_e_rede_sao_falsos() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    def network(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    with capture_logs() as logs:
        assert not await _service(timeout).check(phone_e164=_PHONE, code=_CODE)
        assert not await _service(network).start(phone_e164=_PHONE, locale="en")

    assert _PHONE not in str(logs)
    assert _CODE not in str(logs)


async def test_fake_deterministico_para_testes() -> None:
    fake = FakePhoneVerificationService()
    assert not await fake.check(phone_e164=_PHONE, code="123456")
    assert await fake.start(phone_e164=_PHONE, locale="pt-BR")
    assert not await fake.check(phone_e164=_PHONE, code="000000")
    assert await fake.check(phone_e164=_PHONE, code="123456")
