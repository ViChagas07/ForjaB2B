"""Schemas HTTP do contexto de pedidos."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ordering.domain.payment import PaymentMethod


class OrderItemInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemInputSchema] = Field(min_length=1)
    payment_method: PaymentMethod
    idempotency_key: str = Field(min_length=1, max_length=64)
    po_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    base_unit_price: Decimal | None
    tier_min_quantity: int | None
    line_total: Decimal


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
