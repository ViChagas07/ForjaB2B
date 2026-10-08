"""Casos de uso do contexto de carrinho (validacao + precificacao no servidor).

Nenhum preco enviado pelo cliente e aceito: o preco e resolvido pelo dominio de
pricing (tier/base) no momento da leitura. A validacao de produto (ativo/CA/lote
minimo) usa as regras compartilhadas de disponibilidade.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.domain.product_availability import is_sellable
from app.modules.cart.application.errors import (
    CartNotFoundError,
    ProductNotFoundError,
    ProductNotSellableError,
    QuantityBelowMinimumError,
)
from app.modules.cart.application.ports import CartRepository, CartView


class CartService:
    """Casos de uso de carrinho (CRUD + consulta), orquestrando validacoes."""

    def __init__(self, *, repository: CartRepository, today: date | None = None) -> None:
        self._repository = repository
        self._today = today or date.today()

    async def get_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> CartView:
        await self._repository.get_or_create_cart(company_id, user_id)
        cart = await self._repository.get_cart(company_id, user_id)
        if cart is None:
            cart_id = await self._repository.get_or_create_cart(company_id, user_id)
            return CartView(
                cart_id=cart_id,
                company_id=company_id,
                user_id=user_id,
                items=[],
                subtotal=Decimal("0.00"),
            )
        return cart

    async def add_item(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> CartView:
        await self._validate_product(product_id, quantity)
        cart_id = await self._repository.get_or_create_cart(company_id, user_id)
        await self._repository.upsert_item(
            cart_id=cart_id, company_id=company_id, product_id=product_id, quantity=quantity
        )
        return await self._load_cart(company_id, user_id)

    async def update_quantity(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> CartView:
        await self._validate_product(product_id, quantity)
        cart_id = await self._repository.get_or_create_cart(company_id, user_id)
        await self._repository.set_quantity(
            cart_id=cart_id, company_id=company_id, product_id=product_id, quantity=quantity
        )
        return await self._load_cart(company_id, user_id)

    async def remove_item(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID, product_id: uuid.UUID
    ) -> CartView:
        cart_id = await self._repository.get_or_create_cart(company_id, user_id)
        await self._repository.remove_item(
            cart_id=cart_id, company_id=company_id, product_id=product_id
        )
        return await self._load_cart(company_id, user_id)

    async def clear(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> CartView:
        cart_id = await self._repository.get_or_create_cart(company_id, user_id)
        await self._repository.clear(cart_id=cart_id, company_id=company_id)
        return await self._load_cart(company_id, user_id)

    async def _load_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> CartView:
        cart = await self._repository.get_cart(company_id, user_id)
        if cart is None:
            raise CartNotFoundError()
        return cart

    async def _validate_product(self, product_id: uuid.UUID, quantity: int) -> None:
        product = await self._repository.get_product_for_cart(product_id)
        if product is None:
            raise ProductNotFoundError()
        if not is_sellable(
            status=product.status,
            is_epi=product.is_epi,
            ca_valid_until=product.ca_valid_until,
            today=self._today,
        ):
            raise ProductNotSellableError()
        if quantity < product.min_order_qty:
            raise QuantityBelowMinimumError()
