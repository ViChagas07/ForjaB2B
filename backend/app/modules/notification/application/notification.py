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
)
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.domain.notification import build_email


class DispatchOutbox:
    """Caso de uso: despacha notificacoes pendentes de um tenant."""

    def __init__(
        self,
        *,
        repository: NotificationRepository,
        email_sender: EmailSender,
        max_attempts: int = 5,
    ) -> None:
        self._repository = repository
        self._email_sender = email_sender
        self._max_attempts = max_attempts

    async def dispatch(self, *, company_id: uuid.UUID, limit: int = 100) -> int:
        due = await self._repository.list_due(
            company_id=company_id, limit=limit, max_attempts=self._max_attempts
        )
        sent = 0
        for row in due:
            recipient = await self._repository.resolve_recipient(
                company_id=row.company_id, order_id=row.aggregate_id
            )
            if recipient is None or recipient.opted_out:
                await self._repository.mark(
                    company_id=row.company_id, outbox_id=row.id, status=NotificationStatus.SKIPPED
                )
                increment_notifications_dispatched(status="SKIPPED")
                continue
            subject, body = build_email(
                event_type=row.event_type, locale=recipient.locale, order_id=str(row.aggregate_id)
            )
            try:
                await self._email_sender.send(to=recipient.email, subject=subject, body=body)
            except EmailPermanentError as exc:
                await self._repository.mark(
                    company_id=row.company_id,
                    outbox_id=row.id,
                    status=NotificationStatus.DEAD_LETTERED,
                    error=str(exc),
                )
                increment_notifications_dispatched(status="DEAD_LETTERED")
                continue
            except EmailTransientError as exc:
                await self._repository.mark(
                    company_id=row.company_id,
                    outbox_id=row.id,
                    status=NotificationStatus.FAILED,
                    error=str(exc),
                )
                increment_notifications_dispatched(status="FAILED")
                continue
            await self._repository.mark(
                company_id=row.company_id, outbox_id=row.id, status=NotificationStatus.SENT
            )
            increment_notifications_dispatched(status="SENT")
            sent += 1
        return sent


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
