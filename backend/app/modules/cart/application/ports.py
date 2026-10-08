"""Portas do contexto de carrinho (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.pricing import PriceTier


@dataclass(frozen=True, kw_only=True)
class ProductForCart:
    """Produto + tiers necessarios para validar e precificar um item."""

    id: uuid.UUID
    sku: str
    name: str
    status: str
    is_epi: bool
    ca_valid_until: date | None
    base_unit_price: Decimal
    min_order_qty: int
    tiers: list[PriceTier]


@dataclass(frozen=True, kw_only=True)
class CartItemView:
    """Item do carrinho com preco resolvido (nunca persistido)."""

    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    tier_min_quantity: int | None


@dataclass(frozen=True, kw_only=True)
class CartView:
    """Carrinho ativo com itens e subtotal calculados."""

    cart_id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    items: list[CartItemView]
    subtotal: Decimal


class CartRepository(Protocol):
    """Persistencia do carrinho (tenant-scoped) + leitura de produto/tiers."""

    async def get_product_for_cart(self, product_id: uuid.UUID) -> ProductForCart | None:
        """Le produto + tiers para validacao/precificacao."""

    async def get_or_create_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        """Devolve o carrinho ativo do usuario (cria se ausente)."""

    async def get_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> CartView | None:
        """Le o carrinho com itens e precos resolvidos."""

    async def upsert_item(
        self,
        *,
        cart_id: uuid.UUID,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> None:
        """Adiciona produto ou incrementa a quantidade existente."""

    async def set_quantity(
        self,
        *,
        cart_id: uuid.UUID,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> None:
        """Define a quantidade exata de um item (> 0)."""

    async def remove_item(
        self, *, cart_id: uuid.UUID, company_id: uuid.UUID, product_id: uuid.UUID
    ) -> None:
        """Remove um item do carrinho."""

    async def clear(self, *, cart_id: uuid.UUID, company_id: uuid.UUID) -> None:
        """Remove todos os itens do carrinho."""
