"""Mapeadores ORM do contexto de pagamento (Payment, PaymentEvent).

``payments`` registra a intencao de pagamento (PIX/CARD a vista ou BOLETO de
fatura) e o estado vigente. ``payment_events`` e a trilha de eventos de webhook
(append-only) que garante idempotencia por (provider, event_id).

Os repositorios usam SQL bruto; as relacoes ORM aqui sao minimas (apenas as
colunas/FKs), evitando acoplamento de relacionamento entre modelos de contextos
distintos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import (
    TimestampMixin,
    aggregate_money,
    currency_column,
    enum_check,
)
from app.modules.payment.domain.enums import PaymentEventOutcome, PaymentMethod, PaymentStatus


class Payment(TimestampMixin, Base):
    """Intencao de pagamento de um pedido/fatura (tenant-scoped)."""

    __tablename__ = "payments"
    __table_args__ = (
        enum_check("status", PaymentStatus),
        enum_check("method", PaymentMethod),
        CheckConstraint("amount >= 0", name="amount"),
        CheckConstraint("discount_amount >= 0", name="discount_amount"),
        Index(
            "uq_payments_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("uq_payments_provider_reference", "provider_reference", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT")
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        aggregate_money(), nullable=False, server_default=text("0")
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=PaymentStatus.PENDING.value,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = currency_column()
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(TimestampMixin, Base):
    """Evento de webhook processado (append-only, idempotente)."""

    __tablename__ = "payment_events"
    __table_args__ = (
        Index("uq_payment_events_provider_event", "provider", "event_id", unique=True),
        enum_check("outcome", PaymentEventOutcome),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[PaymentEventOutcome] = mapped_column(
        Enum(PaymentEventOutcome, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
