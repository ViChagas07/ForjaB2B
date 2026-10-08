"""Portas do contexto de pedidos (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.pricing import PriceTier


@dataclass(frozen=True, kw_only=True)
class ProductForOrder:
    """Produto + tiers necessarios para validar e precificar um item."""

    id: uuid.UUID
    sku: str
    name: str
    status: str
    is_epi: bool
    ca_valid_until: date | None
    base_unit_price: Decimal
    min_order_qty: int
    weight_kg: Decimal | None
    tiers: list[PriceTier]


@dataclass(frozen=True, kw_only=True)
class OrderItemInput:
    product_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, kw_only=True)
class ResolvedItem:
    """Item com preco resolvido e snapshot pronto para persistir."""

    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price: Decimal
    base_unit_price: Decimal
    tier_min_quantity: int | None
    price_tier_id: uuid.UUID | None
    line_total: Decimal


@dataclass(frozen=True, kw_only=True)
class OrderItemView:
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    base_unit_price: Decimal | None
    tier_min_quantity: int | None
    line_total: Decimal


@dataclass(frozen=True, kw_only=True)
class OrderView:
    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[OrderItemView]
    created_at: datetime


class OrderingRepository(Protocol):
    """Persistencia de pedidos (snapshot + credito atomico)."""

    async def get_product_for_order(self, product_id: uuid.UUID) -> ProductForOrder | None:
        """Le produto + tiers para validacao/precificacao."""

    async def create_order(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        items: list[ResolvedItem],
        payment_method: str,
        idempotency_key: str,
        po_number: str | None,
        notes: str | None,
        subtotal: Decimal,
        shipping_total: Decimal,
        total: Decimal,
    ) -> OrderView:
        """Cria pedido (snapshot) + reserva credito (boleto) atomicamente."""

    async def get_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView | None:
        """Consulta um pedido do tenant (com itens)."""

    async def cancel_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        """Cancela o pedido e libera a reserva de credito (se houver)."""
