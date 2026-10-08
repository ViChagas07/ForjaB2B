"""Mapeadores ORM do catalogo (Category, Brand, Product, ProductPriceTier).

Estas tabelas sao GLOBAIS (catalogo da distribuidora, compartilhado por todos
os tenants): NAO tem RLS nem ``company_id``. A escrita e restrita a
``forja_admin`` por REVOKE nas migrations; ``forja_app`` apenas le.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import (
    TimestampMixin,
    currency_column,
    enum_check,
    unit_money,
)
from app.modules.catalog.domain.enums import ProductStatus

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.ordering import OrderItem


class Category(TimestampMixin, Base):
    """Categoria hierarquica do catalogo (global)."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))

    parent: Mapped[Category | None] = relationship(remote_side="Category.id")
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Brand(TimestampMixin, Base):
    """Marca parceira do catalogo (global)."""

    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    products: Mapped[list[Product]] = relationship(back_populates="brand")


class Product(TimestampMixin, Base):
    """Produto do catalogo (global).

    Campos fixos de catalogacao + ``attributes`` JSONB para atributos
    variaveis (ADR-001). CA de EPI e representado por ``is_epi``,
    ``ca_number`` e ``ca_valid_until``; o status de vencimento e DERIVADO
    (comparado com a data corrente), nao armazenado.
    """

    __tablename__ = "products"
    __table_args__ = (
        enum_check("status", ProductStatus),
        CheckConstraint("min_order_qty >= 1", name="min_order_qty"),
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="weight"),
        CheckConstraint("base_unit_price >= 0", name="base_price"),
        Index("ix_products_attributes_gin", "attributes", postgresql_using="gin"),
        Index(
            "ix_products_ca_valid_until",
            "ca_valid_until",
            postgresql_where=text("is_epi"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=ProductStatus.ACTIVE.value,
    )
    is_epi: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    ca_number: Mapped[str | None] = mapped_column(String(64))
    ca_valid_until: Mapped[date | None] = mapped_column(Date)
    ncm: Mapped[str | None] = mapped_column(String(8))
    unit_of_measure: Mapped[str | None] = mapped_column(String(10))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    min_order_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    base_unit_price: Mapped[Decimal] = mapped_column(unit_money(), nullable=False)
    currency: Mapped[str] = currency_column()
    attributes: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    category: Mapped[Category] = relationship(back_populates="products")
    brand: Mapped[Brand | None] = relationship(back_populates="products")
    price_tiers: Mapped[list[ProductPriceTier]] = relationship(back_populates="product")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="product")


class ProductPriceTier(TimestampMixin, Base):
    """Faixa de preco progressivo de um produto (global).

    Invariantes estruturais garantidas pelo banco: quantidade minima >= 1,
    ``max_quantity`` ausente ou >= ``min_quantity``, preco > 0 e faixa de
    inicio unica por produto. Contiguidade/sem sobreposicao completas sao
    validadas no dominio (Fase 2).
    """

    __tablename__ = "product_price_tiers"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "min_quantity", name="uq_product_price_tiers_product_min_qty"
        ),
        CheckConstraint("min_quantity >= 1", name="min_qty"),
        CheckConstraint(
            "max_quantity IS NULL OR max_quantity >= min_quantity",
            name="range",
        ),
        CheckConstraint("unit_price > 0", name="unit_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(unit_money(), nullable=False)
    currency: Mapped[str] = currency_column()
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="price_tiers")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="price_tier")
