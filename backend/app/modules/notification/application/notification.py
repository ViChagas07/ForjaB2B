"""Casos de uso do contexto de notificacao.

``DispatchOutbox`` consome a outbox transacional (padrao outbox) de um tenant e
envia as notificacoes pendentes respeitando opt-out, com retentativa de falhas
transitorias e dead-letter para falhas permanentes. Os demais casos de uso
cobrem a operacao administrativa (consulta e reenvio).
"""

from __future__ import annotations

import uuid

from app.core.metrics import increment_notifications_dispatched
from app.modules.notification.application.errors import (
    EmailPermanentError,
    EmailTransientError,
    NotificationNotFoundError,
)
from app.modules.notification.application.ports import (
    EmailSender,
    NotificationRepository,
    OutboxView,
    RecipientView,
    WhatsAppSender,
)
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.domain.notification import (
    cart_url,
    render_email,
    render_personal_note,
    render_text,
)


class DispatchOutbox:
    """Caso de uso: despacha notificacoes pendentes de um tenant.

    Canais: EMAIL (sempre) e WHATSAPP (somente se habilitado, com numero E.164
    e opt-in explicito do usuario). Falha de provedor nunca derruba o worker:
    vira FAILED (retry) ou DEAD_LETTERED, e o lote continua. Os slots do e-mail
    vem do payload gravado no write (dados do backend); {personal_note} e o
    unico trecho possivelmente vindo de LLM e passa pelo output guard; links
    ({cart_url}) sao gerados aqui, com o dominio em config — nunca pelo LLM.
    """

    def __init__(
        self,
        *,
        repository: NotificationRepository,
        email_sender: EmailSender,
        whatsapp_sender: WhatsAppSender | None = None,
        frontend_base_url: str = "",
        max_attempts: int = 5,
    ) -> None:
        self._repository = repository
        self._email_sender = email_sender
        self._whatsapp_sender = whatsapp_sender
        self._frontend_base_url = frontend_base_url
        self._max_attempts = max_attempts

    async def dispatch(self, *, company_id: uuid.UUID, limit: int = 100) -> int:
        due = await self._repository.list_due(
            company_id=company_id, limit=limit, max_attempts=self._max_attempts
        )
        sent = 0
        for row in due:
            recipient = await self._repository.resolve_recipient(
                company_id=row.company_id,
                event_type=row.event_type,
                aggregate_id=row.aggregate_id,
                channel=row.channel,
            )
            if recipient is None or recipient.opted_out:
                await self._skip(row)
                continue
            if row.channel == "WHATSAPP":
                delivered = await self._dispatch_whatsapp(row, recipient)
            else:
                delivered = await self._dispatch_email(row, recipient)
            if delivered:
                sent += 1
        return sent

    async def _dispatch_email(self, row: OutboxView, recipient: RecipientView) -> bool:
        slots = self._slots_for(row, recipient)
        subject, text, html_body = render_email(
            event_type=row.event_type, locale=recipient.locale, slots=slots
        )
        try:
            await self._email_sender.send(
                to=recipient.email, subject=subject, body=text, html=html_body
            )
        except EmailPermanentError as exc:
            await self._dead_letter(row, str(exc))
            return False
        except EmailTransientError as exc:
            await self._fail(row, str(exc))
            return False
        await self._sent(row)
        return True

    async def _dispatch_whatsapp(self, row: OutboxView, recipient: RecipientView) -> bool:
        # Regras de negocio ANTES do provedor: sem opt-in/numero valido nao ha
        # envio (opt-out sempre respeitado; mecanismo existente por canal).
        if (
            self._whatsapp_sender is None
            or not recipient.whatsapp_opt_in
            or not is_e164(recipient.whatsapp_phone or "")
        ):
            await self._skip(row)
            return False
        _subject, message = render_text(
            event_type=row.event_type,
            locale=recipient.locale,
            slots=self._slots_for(row, recipient),
        )
        try:
            await self._whatsapp_sender.send(phone=str(recipient.whatsapp_phone), message=message)
        except EmailPermanentError as exc:
            await self._dead_letter(row, str(exc))
            return False
        except EmailTransientError as exc:
            await self._fail(row, str(exc))
            return False
        await self._sent(row)
        return True

    def _slots_for(self, row: OutboxView, recipient: RecipientView) -> dict[str, str]:
        payload = row.payload or {}
        locale = recipient.locale
        if row.event_type == "cart.recovery":
            note = render_personal_note(
                str(payload.get("personal_note", "")) if payload.get("personal_note") else None,
                locale=locale,
            )
            return {
                "company_name": str(payload.get("company_name", "Forja")),
                "items_summary": str(payload.get("items_summary", "")),
                "cart_url": cart_url(locale, frontend_base_url=self._frontend_base_url),
                "offer_text": str(payload.get("offer_text", "")),
                "personal_note": note,
            }
        return {"order_id": str(row.aggregate_id)}

    async def _skip(self, row: OutboxView) -> None:
        await self._repository.mark(
            company_id=row.company_id, outbox_id=row.id, status=NotificationStatus.SKIPPED
        )
        increment_notifications_dispatched(status="SKIPPED")

    async def _sent(self, row: OutboxView) -> None:
        await self._repository.mark(
            company_id=row.company_id, outbox_id=row.id, status=NotificationStatus.SENT
        )
        increment_notifications_dispatched(status="SENT")

    async def _fail(self, row: OutboxView, error: str) -> None:
        await self._repository.mark(
            company_id=row.company_id,
            outbox_id=row.id,
            status=NotificationStatus.FAILED,
            error=error,
        )
        increment_notifications_dispatched(status="FAILED")

    async def _dead_letter(self, row: OutboxView, error: str) -> None:
        await self._repository.mark(
            company_id=row.company_id,
            outbox_id=row.id,
            status=NotificationStatus.DEAD_LETTERED,
            error=error,
        )
        increment_notifications_dispatched(status="DEAD_LETTERED")


def is_e164(phone: str) -> bool:
    """E.164: '+' seguido de 8 a 15 digitos, sem espacos/mascara."""
    cleaned = phone.strip()
    if not cleaned.startswith("+"):
        return False
    digits = cleaned[1:]
    return digits.isdigit() and 8 <= len(digits) <= 15


class ListNotifications:
    """Caso de uso (admin): lista as notificacoes do tenant."""

    def __init__(self, *, repository: NotificationRepository) -> None:
        self._repository = repository

    async def list(self, company_id: uuid.UUID) -> list[OutboxView]:
        return await self._repository.list_notifications(company_id)


class ResendNotification:
    """Caso de uso (admin): reabre uma notificacao para reenvio."""

    def __init__(self, *, repository: NotificationRepository) -> None:
        self._repository = repository

    async def resend(self, company_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        existing = await self._repository.get_notification(company_id, notification_id)
        if existing is None:
            raise NotificationNotFoundError()
        await self._repository.reset_for_resend(company_id, notification_id)
