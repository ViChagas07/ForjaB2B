"""Envio assincrono dos e-mails de recuperacao de conta.

O codigo em texto puro NAO e gravado em PostgreSQL/log/auditoria: ele viaja
somente no argumento da task Celery (broker) e o worker o usa apenas para
renderizar o e-mail. ``ignore_result`` evita persistir o resultado no backend
de resultados. Falhas de envio sao logadas sem destinatario/codigo e nao
alteram a resposta HTTP.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.identity.infrastructure.twilio_verify import (
    build_phone_verification_service,
)
from app.modules.notification.domain.notification import render_email
from app.modules.notification.infrastructure.email import (
    ResendEmailSender,
    build_email_sender,
)
from app.tasks.celery_app import celery_app

_logger = get_logger(__name__)

RESET_CODE_EVENT = "auth.password_reset_code"
PASSWORD_CHANGED_EVENT = "auth.password_changed"  # noqa: S105 - nome de evento
PHONE_UNLINKED_EVENT = "auth.phone_unlinked"


@celery_app.task(
    name="app.tasks.password_recovery.send_password_reset_code",
    ignore_result=True,
)
def send_password_reset_code(to: str, locale: str | None, code: str, expires_minutes: int) -> None:
    asyncio.run(
        _send(
            event_type=RESET_CODE_EVENT,
            to=to,
            locale=locale,
            slots={"code": code, "expires_minutes": str(expires_minutes)},
        )
    )


@celery_app.task(
    name="app.tasks.password_recovery.send_password_changed_notice",
    ignore_result=True,
)
def send_password_changed_notice(to: str, locale: str | None) -> None:
    asyncio.run(
        _send(
            event_type=PASSWORD_CHANGED_EVENT,
            to=to,
            locale=locale,
            slots={},
        )
    )


@celery_app.task(
    name="app.tasks.password_recovery.send_phone_unlinked_notice",
    ignore_result=True,
)
def send_phone_unlinked_notice(to: str, locale: str | None) -> None:
    asyncio.run(
        _send(
            event_type=PHONE_UNLINKED_EVENT,
            to=to,
            locale=locale,
            slots={},
        )
    )


@celery_app.task(
    name="app.tasks.password_recovery.send_password_reset_sms",
    ignore_result=True,
)
def send_password_reset_sms(to_phone: str, locale: str | None) -> None:
    asyncio.run(_send_sms(to_phone=to_phone, locale=locale))


async def _send_sms(*, to_phone: str, locale: str | None) -> None:
    try:
        service = build_phone_verification_service(get_settings())
        if service is None:
            _logger.warning("password_recovery_sms_not_configured")
            return
        started = await service.start(phone_e164=to_phone, locale=locale)
        if not started:
            _logger.warning("password_recovery_sms_failed", reason="provider")
    except Exception as exc:  # noqa: BLE001 - best-effort/log
        _logger.warning(
            "password_recovery_sms_failed",
            reason="exception",
            error_type=type(exc).__name__,
        )


async def _send(*, event_type: str, to: str, locale: str | None, slots: dict[str, str]) -> None:
    try:
        subject, body, html_body = render_email(event_type=event_type, locale=locale, slots=slots)
        settings = get_settings()
        if getattr(settings, "email_dry_run", False):
            # Dry-run do projeto loga o corpo do e-mail; aqui isso vazaria o
            # codigo. Para recuperacao, apenas registra o evento sem conteudo.
            _logger.info("password_recovery_email_dry_run", event_type=event_type)
            return
        sender = build_email_sender(settings)
        try:
            await sender.send(to=to, subject=subject, body=body, html=html_body)
        finally:
            if isinstance(sender, ResendEmailSender):
                await sender.aclose()
    except Exception as exc:  # noqa: BLE001 - best-effort/log
        _logger.warning(
            "password_recovery_email_failed",
            event_type=event_type,
            error_type=type(exc).__name__,
        )


class CeleryPasswordRecoveryEmailDispatcher:
    """Dispatcher da porta de e-mail: publica no broker, nunca envia na request."""

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        await self._enqueue(
            "app.tasks.password_recovery.send_password_reset_code",
            {"to": to, "locale": locale, "code": code, "expires_minutes": expires_minutes},
            event_type=RESET_CODE_EVENT,
        )

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        await self._enqueue(
            "app.tasks.password_recovery.send_password_changed_notice",
            {"to": to, "locale": locale},
            event_type=PASSWORD_CHANGED_EVENT,
        )

    async def _enqueue(self, task_name: str, kwargs: dict[str, object], *, event_type: str) -> None:
        try:
            await asyncio.to_thread(
                celery_app.send_task,
                task_name,
                kwargs=kwargs,
                ignore_result=True,
                retry=False,
            )
        except Exception as exc:  # noqa: BLE001 - enqueue best-effort
            _logger.warning(
                "password_recovery_email_enqueue_failed",
                event_type=event_type,
                error_type=type(exc).__name__,
            )


class CeleryAccountEmailDispatcher:
    """Dispatcher de e-mails de seguranca da conta (aviso de desvinculo)."""

    async def send_phone_unlinked(self, *, to: str, locale: str | None) -> None:
        try:
            await asyncio.to_thread(
                celery_app.send_task,
                "app.tasks.password_recovery.send_phone_unlinked_notice",
                kwargs={"to": to, "locale": locale},
                ignore_result=True,
                retry=False,
            )
        except Exception as exc:  # noqa: BLE001 - enqueue best-effort
            _logger.warning(
                "phone_unlink_email_enqueue_failed",
                error_type=type(exc).__name__,
            )


class CeleryPasswordRecoverySmsDispatcher:
    """Dispatcher do SMS de recuperacao; Twilio gera/confere o codigo."""

    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        try:
            await asyncio.to_thread(
                celery_app.send_task,
                "app.tasks.password_recovery.send_password_reset_sms",
                kwargs={"to_phone": to_phone, "locale": locale},
                ignore_result=True,
                retry=False,
            )
        except Exception as exc:  # noqa: BLE001 - enqueue best-effort
            _logger.warning(
                "password_recovery_sms_enqueue_failed",
                error_type=type(exc).__name__,
            )
