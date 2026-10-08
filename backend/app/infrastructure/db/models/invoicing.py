"""Mapeadores ORM do contexto de faturamento (Invoice).

A fatura representa o boleto faturado (30/60 dias) de um pedido. A logica de
concessao de credito e geracao do boleto e da Fase 2; aqui ficam os dados.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import (
    TimestampMixin,
    aggregate_money,
    currency_column,
    enum_check,
)
from app.modules.invoicing.domain.enums import InvoiceStatus, InvoiceTerms

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.companies import Company
    from app.infrastructure.db.models.ordering import Order


class Invoice(TimestampMixin, Base):
    """Fatura/duplicata de um pedido (tenant-scoped)."""

    __tablename__ = "invoices"
    __table_args__ = (
        enum_check("status", InvoiceStatus),
        enum_check("payment_terms", InvoiceTerms),
        CheckConstraint("amount >= 0", name="amount"),
        Index("ix_invoices_due_at", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=InvoiceStatus.PENDING.value,
    )
    payment_terms: Mapped[InvoiceTerms] = mapped_column(
        Enum(InvoiceTerms, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    currency: Mapped[str] = currency_column()
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    boleto_reference: Mapped[str | None] = mapped_column(String(100))

    order: Mapped[Order] = relationship(back_populates="invoices")
    company: Mapped[Company] = relationship(back_populates="invoices")
