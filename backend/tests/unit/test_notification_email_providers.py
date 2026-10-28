"""Testes dos provedores de e-mail (Fase 3, item 2) — NENHUM teste chama rede.

ResendEmailSender e testado com httpx.MockTransport; selecao via
EMAIL_PROVIDER=smtp|resend; falha de provedor vira EmailTransient/Permanent
(o outbox retenta; o worker nunca derruba).
"""

import httpx
import pytest

from app.core.config import Settings
from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError
from app.modules.notification.infrastructure.email import (
    FakeEmailSender,
    ResendEmailSender,
    SmtpEmailSender,
    build_email_sender,
)


def resend_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "email_provider": "resend",
        "resend_api_key": "re_test_placeholder",
        "resend_from": "Forja <no-reply@forja.test>",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def ok_transport(captured: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "email-1"})

    return httpx.MockTransport(handler)


async def test_resend_envia_via_api_com_auth() -> None:
    captured: list[httpx.Request] = []
    sender = ResendEmailSender(
        api_key="re_test_placeholder",
        from_email="Forja <no-reply@forja.test>",
        transport=ok_transport(captured),
    )
    await sender.send(to="cliente@empresa.test", subject="Olá", body="texto", html="<p>oi</p>")
    request = captured[0]
    assert request.url.path == "/emails"
    assert request.headers["Authorization"] == "Bearer re_test_placeholder"
    payload = __import__("json").loads(request.content)
    assert payload["from"] == "Forja <no-reply@forja.test>"
    assert payload["to"] == ["cliente@empresa.test"]
    assert payload["text"] == "texto"
    assert payload["html"] == "<p>oi</p>"


async def test_resend_429_ou_5xx_e_transient() -> None:
    for status in (429, 500, 503):

        def handler(request: httpx.Request, status: int = status) -> httpx.Response:
            return httpx.Response(status)

        sender = ResendEmailSender(
            api_key="k", from_email="a@b.test", transport=httpx.MockTransport(handler)
        )
        with pytest.raises(EmailTransientError):
            await sender.send(to="c@d.test", subject="s", body="b")


async def test_resend_4xx_e_permanente() -> None:
    sender = ResendEmailSender(
        api_key="k",
        from_email="a@b.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(422)),
    )
    with pytest.raises(EmailPermanentError):
        await sender.send(to="c@d.test", subject="s", body="b")


async def test_resend_erro_de_rede_e_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    sender = ResendEmailSender(
        api_key="k", from_email="a@b.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(EmailTransientError):
        await sender.send(to="c@d.test", subject="s", body="b")


def test_fabrica_escolhe_provedor_por_config() -> None:
    smtp_sender = build_email_sender(Settings(_env_file=None))
    assert isinstance(smtp_sender, SmtpEmailSender)
    resend_sender = build_email_sender(resend_settings())
    assert isinstance(resend_sender, ResendEmailSender)


def test_fabrica_resend_sem_credenciais_falha_rapido() -> None:
    with pytest.raises(EmailPermanentError):
        build_email_sender(Settings(email_provider="resend", _env_file=None))


def test_provedor_invalido_rejeitado_na_config() -> None:
    with pytest.raises(ValueError):
        Settings(email_provider="sendgrid", _env_file=None)


def test_smtp_padrao_dev_e_mailpit() -> None:
    settings = Settings(_env_file=None)
    assert settings.email_provider == "smtp"
    assert settings.email_smtp_port == 1025
    fake = FakeEmailSender()
    assert fake.sent == []
