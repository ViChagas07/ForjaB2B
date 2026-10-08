"""Schemas HTTP do contexto de carrinho."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AddItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity: int = Field(ge=1)


class UpdateItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(ge=1)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    tier_min_quantity: int | None


class CartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cart_id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    items: list[CartItemResponse]
    subtotal: Decimal
