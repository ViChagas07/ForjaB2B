"""Portas do contexto de notificacao (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.notification.domain.enums import NotificationStatus


@dataclass(frozen=True, kw_only=True)
class OutboxView:
    """Linha da outbox de notificacoes (evento + estado de entrega)."""

    id: uuid.UUID
    company_id: uuid.UUID
    event_type: str
    aggregate_id: uuid.UUID
    payload: dict[str, object] | None
    status: str
    attempts: int
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class RecipientView:
    """Destinatario resolvido no momento do envio (email + preferencia)."""

    email: str
    locale: str | None
    opted_out: bool


@dataclass(frozen=True, kw_only=True)
class DueNotification:
    """Par (notification_id, company_id) para enumeracao cross-tenant do worker."""

    notification_id: uuid.UUID
    company_id: uuid.UUID


class NotificationRepository(Protocol):
    """Persistencia da outbox de notificacoes + resolucao de destinatario."""

    async def list_due(
        self, *, company_id: uuid.UUID, limit: int, max_attempts: int
    ) -> list[OutboxView]:
        """Devolve notificacoes PENDING (ou FAILED ainda retentaveis) do tenant."""

    async def list_due_tenants(self, *, limit: int, max_attempts: int) -> set[uuid.UUID]:
        """Enumera tenants com notificacoes pendentes (via SECURITY DEFINER)."""

    async def resolve_recipient(
        self, *, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> RecipientView | None:
        """Resolve email/idioma/opt-out do comprador do pedido."""

    async def mark(
        self,
        *,
        company_id: uuid.UUID,
        outbox_id: uuid.UUID,
        status: NotificationStatus,
        error: str | None = None,
    ) -> None:
        """Atualiza o estado de entrega (attempts/sent_at/error)."""

    async def list_notifications(self, company_id: uuid.UUID) -> list[OutboxView]:
        """Historico de notificacoes do tenant (admin)."""

    async def get_notification(
        self, company_id: uuid.UUID, outbox_id: uuid.UUID
    ) -> OutboxView | None:
        """Consulta uma notificacao do tenant (admin)."""

    async def reset_for_resend(self, company_id: uuid.UUID, outbox_id: uuid.UUID) -> None:
        """Reabre uma notificacao (PENDING, attempts=0) para reenvio (admin)."""


class EmailSender(Protocol):
    """Porta do canal de e-mail (Fake/local ou SMTP Mailpit)."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        """Envia um e-mail; falhas levantam EmailTransientError/EmailPermanentError."""
