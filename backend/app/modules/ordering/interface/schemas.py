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
    unit_price: Decimal
    base_unit_price: Decimal | None
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


class CouponPreviewRequest(BaseModel):
    """Previa do cupom no carrinho do comprador autenticado."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=32)
    payment_method: PaymentMethod = PaymentMethod.PIX


class CouponPreviewResponse(BaseModel):
    """Validacao tipada + simulacao; ``valid=False`` traz apenas o motivo."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    reason: CouponRejectionReason | None = None
    missing_amount: Decimal | None = None
    subtotal: Decimal | None = None
    recovery_discount: Decimal | None = None
    coupon_discount: Decimal | None = None
    shipping_discount: Decimal | None = None
    shipping_total: Decimal | None = None
    pix_discount: Decimal | None = None
    total: Decimal | None = None
    applied_discounts: list[DiscountKind] = Field(default_factory=list)
    currency: str = "BRL"
