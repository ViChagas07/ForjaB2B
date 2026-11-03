"""Schemas HTTP do contexto de pedidos."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ordering.domain.coupon import (
    CouponRejectionReason,
    CouponType,
    DiscountKind,
)
from app.modules.ordering.domain.payment import PaymentMethod


class OrderItemInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemInputSchema] = Field(min_length=1)
    payment_method: PaymentMethod
    # Compatibilidade: clientes antigos enviam a chave no corpo. O header
    # `Idempotency-Key` e o mecanismo canonico e tem precedencia.
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=64)
    po_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    lang: str | None = Field(default=None, max_length=10)
    coupon_code: str | None = Field(default=None, max_length=32)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    product_name: str
    quantity: int
    # unit_price/line_total ja incluem o desconto automatico CNPJ.
    unit_price: Decimal
    base_unit_price: Decimal | None
    list_unit_price: Decimal | None = None
    list_line_total: Decimal | None = None
    cnpj_discount_percent: Decimal | None = None
    cnpj_discount_band: int | None = None
    cnpj_discount_amount: Decimal | None = None
    tier_min_quantity: int | None
    line_total: Decimal
    content_locale: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    currency: str
    subtotal: Decimal
    # Exibicao: ``subtotal`` ja e o valor final (com CNPJ).
    list_subtotal: Decimal = Decimal("0.00")
    cnpj_discount_total: Decimal = Decimal("0.00")
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[OrderItemResponse]
    created_at: datetime
    content_locale: str
    coupon_code: str | None = None
    coupon_type: CouponType | None = None
    coupon_percent: Decimal | None = None
    coupon_discount_amount: Decimal = Decimal("0.00")
    shipping_discount_amount: Decimal = Decimal("0.00")


class AvailableCouponResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    type: CouponType
    percent: Decimal
    max_discount_amount: Decimal | None = None
    min_order_amount: Decimal | None = None
    valid_until: datetime | None = None
    remaining_uses: int | None = None


class CustomerOverviewResponse(BaseModel):
    """Painel do comprador: gasto, compras recentes e cupons disponiveis."""

    model_config = ConfigDict(extra="forbid")

    total_spent: Decimal
    orders_count: int
    orders: list[OrderResponse]
    coupons: list[AvailableCouponResponse]


class CouponPreviewRequest(BaseModel):
    """Previa do cupom no carrinho do comprador autenticado."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=32)
    payment_method: PaymentMethod = PaymentMethod.PIX
    product_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class CouponPreviewResponse(BaseModel):
    """Validacao tipada + simulacao; ``valid=False`` traz apenas o motivo."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    reason: CouponRejectionReason | None = None
    missing_amount: Decimal | None = None
    subtotal: Decimal | None = None
    list_subtotal: Decimal | None = None
    cnpj_discount_total: Decimal | None = None
    recovery_discount: Decimal | None = None
    coupon_discount: Decimal | None = None
    shipping_discount: Decimal | None = None
    shipping_total: Decimal | None = None
    pix_discount: Decimal | None = None
    total: Decimal | None = None
    applied_discounts: list[DiscountKind] = Field(default_factory=list)
    currency: str = "BRL"
