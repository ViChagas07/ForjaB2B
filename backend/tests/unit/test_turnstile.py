"""Testes do verificador Cloudflare Turnstile (sem rede real)."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest
from structlog.testing import capture_logs

from app.modules.identity.infrastructure.turnstile import CloudflareTurnstileVerifier


def _verifier(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    secret: str = "test-turnstile-secret",  # noqa: S107 - valor de teste
    timeout_seconds: float = 5.0,
) -> CloudflareTurnstileVerifier:
    return CloudflareTurnstileVerifier(
        secret_key=secret,
        timeout_seconds=timeout_seconds,
        transport=httpx.MockTransport(handler),
    )


async def test_sucesso_envia_secret_response_e_remoteip() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"success": True})

    verifier = _verifier(handler)
    assert await verifier.verify(token="tok-abc", remote_ip="203.0.113.7")

    request = captured[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/turnstile/v0/siteverify")
    body = parse_qs(request.content.decode())
    assert body["secret"] == ["test-turnstile-secret"]
    assert body["response"] == ["tok-abc"]
    assert body["remoteip"] == ["203.0.113.7"]


async def test_sucesso_sem_remoteip_omite_campo() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"success": True})

    verifier = _verifier(handler)
    assert await verifier.verify(token="tok-abc", remote_ip=None)

    body = parse_qs(captured[0].content.decode())
    assert "remoteip" not in body


async def test_success_false_e_recusado() -> None:
    verifier = _verifier(lambda request: httpx.Response(200, json={"success": False}))
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-abc", remote_ip="203.0.113.7")
    assert "tok-abc" not in str(logs)


async def test_json_invalido_e_recusado() -> None:
    verifier = _verifier(
        lambda request: httpx.Response(
            200, content=b"not-json", headers={"content-type": "text/plain"}
        )
    )
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-secret", remote_ip=None)
    assert "tok-secret" not in str(logs)


async def test_timeout_e_recusado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    verifier = _verifier(handler)
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-timeout", remote_ip=None)
    assert "tok-timeout" not in str(logs)


async def test_erro_de_rede_e_recusado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    verifier = _verifier(handler)
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-network", remote_ip=None)
    assert "tok-network" not in str(logs)


async def test_http_error_e_recusado() -> None:
    verifier = _verifier(lambda request: httpx.Response(503))
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-http", remote_ip=None)
    assert "tok-http" not in str(logs)


async def test_secret_ausente_falha_fechado_sem_chamar_rede() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"success": True})

    verifier = _verifier(handler, secret="")
    with capture_logs() as logs:
        assert not await verifier.verify(token="tok-secret", remote_ip=None)
    assert called is False
    assert "tok-secret" not in str(logs)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"success": "true"},
        {"success": 1},
        [],
        None,
    ],
)
async def test_resposta_inesperada_e_recusada(payload: object) -> None:
    verifier = _verifier(lambda request: httpx.Response(200, json=payload))
    assert not await verifier.verify(token="tok-payload", remote_ip=None)
