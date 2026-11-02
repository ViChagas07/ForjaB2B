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
    # unit_price/line_total ja incluem o desconto automatico CNPJ.
    unit_price: Decimal
    line_total: Decimal
    # Valores calculados no servidor para exibicao.
    list_line_total: Decimal
    discount_amount: Decimal
    # Preco de tabela (pre-CNPJ), percentual/faixa e distancia para 30%.
    list_unit_price: Decimal
    discount_percent: Decimal
    discount_band: int | None = None
    units_to_volume_discount: int | None = None
    tier_min_quantity: int | None
    image_url: str
    image_alt: str
    content_locale: str


class CartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cart_id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    items: list[CartItemResponse]
    # ``subtotal`` ja e o valor final (com CNPJ).
    list_subtotal: Decimal
    cnpj_discount_total: Decimal
    subtotal: Decimal
