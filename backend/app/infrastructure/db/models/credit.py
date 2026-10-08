"""Mapeadores ORM do contexto de credito (CreditAccount, CreditEntry).

Ledger append-only (MEGA-PROMPT, secao 5/6): ``credit_entries`` e imutavel
por desenho (sem ``updated_at``). O saldo/disponivel deriva do somatorio
consolidado do ledger na Fase 2; nao ha coluna materializada de saldo.
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
    Text,
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
from app.modules.credit.domain.enums import CreditEntryType

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.companies import Company


class CreditAccount(TimestampMixin, Base):
    """Conta de credito faturado de uma empresa (uma por empresa)."""

    __tablename__ = "credit_accounts"
    __table_args__ = (CheckConstraint("credit_limit >= 0", name="credit_limit"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), primary_key=True
    )
    credit_limit: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    currency: Mapped[str] = currency_column()

    company: Mapped[Company] = relationship(back_populates="credit_account")
    entries: Mapped[list[CreditEntry]] = relationship(back_populates="credit_account")


class CreditEntry(Base):
    """Lancamento imutavel do ledger de credito (append-only)."""

    __tablename__ = "credit_entries"
    __table_args__ = (
        enum_check("entry_type", CreditEntryType),
        Index(
            "uq_credit_entries_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    credit_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_accounts.company_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    entry_type: Mapped[CreditEntryType] = mapped_column(
        Enum(CreditEntryType, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    credit_account: Mapped[CreditAccount] = relationship(back_populates="entries")
    company: Mapped[Company] = relationship(back_populates="credit_entries")
