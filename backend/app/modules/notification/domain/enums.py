"""Vocabulario de estado do modulo notification (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class NotificationChannel(StrEnum):
    """Canais de entrega suportados (apenas e-mail nesta fase)."""

    EMAIL = "EMAIL"


class NotificationStatus(StrEnum):
    """Ciclo de vida de uma notificacao na outbox."""

    PENDING = "PENDING"  # aguardando envio
    SENT = "SENT"  # entregue ao canal (Mailpit/fake)
    FAILED = "FAILED"  # falha transitoria (sera retentada)
    DEAD_LETTERED = "DEAD_LETTERED"  # falha permanente (sem novo retry)
    SKIPPED = "SKIPPED"  # nao enviada (opt-out)


class NotificationEventType(StrEnum):
    """Eventos de negocio que produzem notificacoes (contrato de outbox)."""

    ORDER_CREATED = "order.created"
    INVOICE_ISSUED = "invoice.issued"
    PAYMENT_CONFIRMED = "payment.confirmed"
