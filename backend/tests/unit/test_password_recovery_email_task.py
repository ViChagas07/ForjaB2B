"""Testes do envio assincrono e do dispatcher de e-mail da recuperacao."""

from __future__ import annotations

from typing import Any

import pytest
from structlog.testing import capture_logs

from app.tasks.celery_app import celery_app
from app.tasks.password_recovery import (
    PASSWORD_CHANGED_EVENT,
    PHONE_UNLINKED_EVENT,
    RESET_CODE_EVENT,
    CeleryAccountEmailDispatcher,
    CeleryPasswordRecoveryEmailDispatcher,
    CeleryPasswordRecoverySmsDispatcher,
    _send,
)


class _FakeSender:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def send(self, *, to: str, subject: str, body: str, html: str) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append({"to": to, "subject": subject, "body": body, "html": html})


async def test_send_renderiza_codigo_sem_logar_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = _FakeSender()
    monkeypatch.setattr("app.tasks.password_recovery.build_email_sender", lambda settings: sender)
    monkeypatch.setattr("app.tasks.password_recovery.get_settings", lambda: object())

    with capture_logs() as logs:
        await _send(
            event_type=RESET_CODE_EVENT,
            to="user@example.com",
            locale="pt-BR",
            slots={"code": "123456", "expires_minutes": "10"},
        )

    assert len(sender.calls) == 1
    call = sender.calls[0]
    assert call["to"] == "user@example.com"
    assert "123456" in call["body"]
    assert "123456" not in call["subject"]
    rendered = str(logs)
    assert "user@example.com" not in rendered
    assert "123456" not in rendered


async def test_send_de_aviso_nao_tem_codigo(monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _FakeSender()
    import app.tasks.password_recovery as module

    monkeypatch.setattr(module, "build_email_sender", lambda settings: sender)
    monkeypatch.setattr(module, "get_settings", lambda: object())
    await _send(
        event_type=PASSWORD_CHANGED_EVENT,
        to="user@example.com",
        locale="en",
        slots={},
    )

    assert len(sender.calls) == 1
    assert sender.calls[0]["body"].strip()


async def test_falha_de_envio_loga_sem_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _FakeSender(error=RuntimeError("provider fora"))
    monkeypatch.setattr("app.tasks.password_recovery.build_email_sender", lambda settings: sender)
    monkeypatch.setattr("app.tasks.password_recovery.get_settings", lambda: object())

    with capture_logs() as logs:
        await _send(
            event_type=RESET_CODE_EVENT,
            to="user@example.com",
            locale="pt-BR",
            slots={"code": "654321", "expires_minutes": "10"},
        )

    rendered = str(logs)
    assert "user@example.com" not in rendered
    assert "654321" not in rendered
    assert "password_recovery_email_failed" in rendered


async def test_dispatcher_publica_no_broker_sem_enviar_na_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_send_task(task_name: str, **kwargs: Any) -> None:
        calls.append((task_name, kwargs))

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)
    dispatcher = CeleryPasswordRecoveryEmailDispatcher()

    await dispatcher.send_reset_code(
        to="user@example.com", locale="pt-BR", code="123456", expires_minutes=10
    )

    assert len(calls) == 1
    task_name, kwargs = calls[0]
    assert task_name == "app.tasks.password_recovery.send_password_reset_code"
    assert kwargs["kwargs"]["to"] == "user@example.com"


async def test_falha_de_enqueue_loga_sem_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_send_task(task_name: str, **kwargs: Any) -> None:
        _ = (task_name, kwargs)
        raise RuntimeError("broker fora")

    monkeypatch.setattr(celery_app, "send_task", failing_send_task)
    dispatcher = CeleryPasswordRecoveryEmailDispatcher()

    with capture_logs() as logs:
        await dispatcher.send_reset_code(
            to="user@example.com", locale="pt-BR", code="123456", expires_minutes=10
        )

    rendered = str(logs)
    assert "user@example.com" not in rendered
    assert "123456" not in rendered
    assert "password_recovery_email_enqueue_failed" in rendered


async def test_dry_run_nao_loga_codigo_nem_chama_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import app.tasks.password_recovery as module

    called = False

    def build_sender(settings: Any) -> Any:
        nonlocal called
        called = True
        return _FakeSender()

    monkeypatch.setattr(module, "build_email_sender", build_sender)
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(email_dry_run=True))

    with capture_logs() as logs:
        await _send(
            event_type=RESET_CODE_EVENT,
            to="user@example.com",
            locale="pt-BR",
            slots={"code": "987654", "expires_minutes": "10"},
        )

    assert called is False
    rendered = str(logs)
    assert "user@example.com" not in rendered
    assert "987654" not in rendered
    assert "password_recovery_email_dry_run" in rendered


async def test_send_phone_unlinked_renderiza_sem_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = _FakeSender()
    monkeypatch.setattr("app.tasks.password_recovery.build_email_sender", lambda settings: sender)
    monkeypatch.setattr("app.tasks.password_recovery.get_settings", lambda: object())

    with capture_logs() as logs:
        await _send(
            event_type=PHONE_UNLINKED_EVENT,
            to="old@example.com",
            locale="pt-BR",
            slots={},
        )

    assert len(sender.calls) == 1
    assert sender.calls[0]["body"].strip()
    rendered = str(logs)
    assert "old@example.com" not in rendered


async def test_dispatcher_phone_unlinked_publica_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_send_task(task_name: str, **kwargs: Any) -> None:
        calls.append((task_name, kwargs))

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)
    dispatcher = CeleryAccountEmailDispatcher()

    await dispatcher.send_phone_unlinked(to="old@example.com", locale=None)

    assert calls[0][0] == "app.tasks.password_recovery.send_phone_unlinked_notice"
    assert calls[0][1]["kwargs"] == {"to": "old@example.com", "locale": None}


class _FakePhoneService:
    def __init__(self, *, started: bool = True) -> None:
        self.started = started
        self.calls: list[tuple[str, str | None]] = []

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        self.calls.append((phone_e164, locale))
        return self.started

    async def check(self, *, phone_e164: str, code: str) -> bool:
        _ = (phone_e164, code)
        return True


async def test_send_sms_usa_service_sem_logar_telefone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakePhoneService()
    import app.tasks.password_recovery as module

    monkeypatch.setattr(module, "build_phone_verification_service", lambda settings: service)
    monkeypatch.setattr(module, "get_settings", lambda: object())

    with capture_logs() as logs:
        await module._send_sms(to_phone="+5511999991234", locale="pt-BR")

    assert service.calls == [("+5511999991234", "pt-BR")]
    assert "+5511999991234" not in str(logs)


async def test_send_sms_falha_loga_sem_telefone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakePhoneService(started=False)
    import app.tasks.password_recovery as module

    monkeypatch.setattr(module, "build_phone_verification_service", lambda settings: service)
    monkeypatch.setattr(module, "get_settings", lambda: object())

    with capture_logs() as logs:
        await module._send_sms(to_phone="+5511999991234", locale=None)

    assert "password_recovery_sms_failed" in str(logs)
    assert "+5511999991234" not in str(logs)


async def test_dispatcher_sms_publica_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_send_task(task_name: str, **kwargs: Any) -> None:
        calls.append((task_name, kwargs))

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)
    dispatcher = CeleryPasswordRecoverySmsDispatcher()

    await dispatcher.send_reset_code(to_phone="+5511999991234", locale="pt-BR")

    assert calls[0][0] == "app.tasks.password_recovery.send_password_reset_sms"
    assert calls[0][1]["kwargs"] == {
        "to_phone": "+5511999991234",
        "locale": "pt-BR",
    }
