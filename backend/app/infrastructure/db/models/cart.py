"""Mapeadores ORM do carrinho e do agente de recuperacao (Fase 12, FASE 4).

Um carrinho ativo por (company_id, user_id). Itens guardam produto + quantidade;
o PRECO nao e persistido (resolvido no momento da leitura/checkout pelo dominio
de pricing). `carts.last_activity_at` e tocado por TODA operacao de item
(add/update/remove/clear) para o agente de recuperacao medir o abandono.
`cart_recovery_attempts` registra cada tentativa (idempotencia/auditoria) e
`cart_recovery_offers` as ofertas de uso unico (frete gratis / 3%). Operacoes
sao feitas via SQL bruto na infraestrutura; estes mapeadores existem para o
``Base.metadata`` (drift detection do Alembic).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin


class Cart(TimestampMixin, Base):
    __tablename__ = "carts"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_carts_company_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Ultima atividade de ITEM (add/update/remove/clear); base do agente.
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class CartItem(TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class CartRecoveryAttempt(Base):
    """Tentativa do agente de recuperacao (append-only, auditavel)."""

    __tablename__ = "cart_recovery_attempts"
    __table_args__ = (
        CheckConstraint(
            "chosen_action IN ('REMIND', 'FREE_SHIPPING', 'DISCOUNT_3PCT', 'ESCALATE_HUMAN')",
            name="chosen_action",
        ),
        CheckConstraint("status IN ('SENT', 'SKIPPED', 'FAILED')", name="status"),
        CheckConstraint("channel IN ('EMAIL', 'WHATSAPP')", name="channel"),
        CheckConstraint(
            "guard_verdict IS NULL OR guard_verdict IN ('ALLOW', 'BLOCK')", name="guard_verdict"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    chosen_action: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'EMAIL'"))
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cart_recovery_offers.id", ondelete="SET NULL"),
        index=True,
    )
    guard_verdict: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CartRecoveryOffer(Base):
    """Oferta de recuperacao de uso unico (frete gratis ou 3% em linhas nao negociadas)."""

    __tablename__ = "cart_recovery_offers"
    __table_args__ = (
        CheckConstraint("type IN ('FREE_SHIPPING', 'PERCENT_DISCOUNT')", name="type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
