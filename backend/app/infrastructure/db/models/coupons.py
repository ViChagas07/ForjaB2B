"""Mapeadores ORM de cupons (globais) e resgates (tenant-scoped).

``coupons`` e GLOBAL como o catalogo: administrada pelo backoffice com a role
``forja_admin``; a role de runtime (``forja_app``) apenas le. ``restricted_company_id``
limita o uso a uma empresa, mas nao transforma a tabela em tenant-scoped.
``coupon_redemptions`` e TENANT-SCOPED (FORCE RLS por ``company_id``) e guarda
o uso do cupom no pedido. O pedido tambem recebe um snapshot do cupom para que
edicoes posteriores no cadastro nao alterem o historico.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import (
    TimestampMixin,
    aggregate_money,
    enum_check,
)
from app.modules.ordering.domain.coupon import CouponRedemptionStatus, CouponType


class Coupon(TimestampMixin, Base):
    """Cupom de desconto criado pelo admin (global, opcionalmente restrito)."""

    __tablename__ = "coupons"
    __table_args__ = (
        enum_check("type", CouponType),
        CheckConstraint("code ~ '^[A-Z0-9_-]{4,32}$'", name="code_format"),
        CheckConstraint("percent > 0 AND percent <= 100", name="percent_range"),
        CheckConstraint(
            "max_discount_amount IS NULL OR max_discount_amount > 0",
            name="max_discount_amount_positive",
        ),
        CheckConstraint(
            "min_order_amount IS NULL OR min_order_amount >= 0",
            name="min_order_amount_non_negative",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="validity_window",
        ),
        CheckConstraint(
            "usage_limit_total IS NULL OR usage_limit_total > 0",
            name="usage_limit_total_positive",
        ),
        CheckConstraint(
            "usage_limit_per_company IS NULL OR usage_limit_per_company > 0",
            name="usage_limit_per_company_positive",
        ),
        UniqueConstraint("code", name="uq_coupons_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[CouponType] = mapped_column(
        Enum(CouponType, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(aggregate_money())
    min_order_amount: Mapped[Decimal | None] = mapped_column(aggregate_money())
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_limit_total: Mapped[int | None] = mapped_column(Integer)
    usage_limit_per_company: Mapped[int | None] = mapped_column(Integer)
    restricted_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class CouponRedemption(Base):
    """Resgate de um cupom em um pedido (um cupom por pedido)."""

    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        enum_check("status", CouponRedemptionStatus),
        CheckConstraint("amount_discounted >= 0", name="amount_discounted_non_negative"),
        UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),
        Index("ix_coupon_redemptions_coupon_status", "coupon_id", "status"),
        Index(
            "ix_coupon_redemptions_coupon_company_status",
            "coupon_id",
            "company_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    amount_discounted: Mapped[Decimal] = mapped_column(
        aggregate_money(), nullable=False, server_default=text("0")
    )
    status: Mapped[CouponRedemptionStatus] = mapped_column(
        Enum(CouponRedemptionStatus, native_enum=False, create_constraint=False, length=16),
        nullable=False,
        server_default=CouponRedemptionStatus.APPLIED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
