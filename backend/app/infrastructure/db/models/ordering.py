"""Mapeadores ORM do contexto de pedidos (Order, OrderItem).

O pedido preserva o estado financeiro no momento da compra: ``order_items``
carrega snapshot de sku, nome, preco unitario, tier e impostos. O historico
nao depende de consultar o preco atual do produto.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
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
    unit_money,
)
from app.modules.ordering.domain.enums import OrderStatus

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.catalog import Product, ProductPriceTier
    from app.infrastructure.db.models.companies import Company
    from app.infrastructure.db.models.identity import User
    from app.infrastructure.db.models.invoicing import Invoice


class Order(TimestampMixin, Base):
    """Pedido de uma empresa (tenant-scoped)."""

    __tablename__ = "orders"
    __table_args__ = (
        enum_check("status", OrderStatus),
        CheckConstraint("subtotal >= 0", name="subtotal"),
        CheckConstraint("discount_total >= 0", name="discount_total"),
        CheckConstraint("shipping_total >= 0", name="shipping_total"),
        CheckConstraint("tax_total >= 0", name="tax_total"),
        CheckConstraint("total >= 0", name="total"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
        Index(
            "uq_orders_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    buyer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=OrderStatus.RECEIVED.value,
    )
    currency: Mapped[str] = currency_column()
    subtotal: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(
        aggregate_money(), nullable=False, server_default=text("0")
    )
    shipping_total: Mapped[Decimal] = mapped_column(
        aggregate_money(), nullable=False, server_default=text("0")
    )
    tax_total: Mapped[Decimal] = mapped_column(
        aggregate_money(), nullable=False, server_default=text("0")
    )
    total: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    shipping_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_addresses.id", ondelete="SET NULL")
    )
    billing_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_addresses.id", ondelete="SET NULL")
    )
    po_number: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="orders")
    buyer: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="order")


class OrderItem(TimestampMixin, Base):
    """Item de pedido com snapshot financeiro imutavel."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        CheckConstraint("unit_price >= 0", name="unit_price"),
        CheckConstraint("discount_amount >= 0", name="discount"),
        CheckConstraint("tax_amount >= 0", name="tax"),
        CheckConstraint("line_total >= 0", name="line_total"),
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
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    price_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_price_tiers.id", ondelete="SET NULL")
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(unit_money(), nullable=False)
    base_unit_price: Mapped[Decimal | None] = mapped_column(unit_money())
    discount_amount: Mapped[Decimal] = mapped_column(
        unit_money(), nullable=False, server_default=text("0")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        unit_money(), nullable=False, server_default=text("0")
    )
    line_total: Mapped[Decimal] = mapped_column(aggregate_money(), nullable=False)
    tier_min_quantity: Mapped[int | None] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    company: Mapped[Company] = relationship()
    product: Mapped[Product] = relationship(back_populates="order_items")
    price_tier: Mapped[ProductPriceTier | None] = relationship(back_populates="order_items")
