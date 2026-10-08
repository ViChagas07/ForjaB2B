"""Repositorio SQLAlchemy do carrinho (tenant-scoped) + leitura de produto/tiers.

Operacoes de carrinho usam SQL bruto dentro da UoW com contexto de tenant (RLS).
O preco NAO e persistido: no ``get_cart``, cada item tem o preco resolvido pelo
dominio de pricing (tier/base) a partir dos tiers atuais do catalogo.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import bindparam, text

from app.application.ports.tenant import TenantContext
from app.domain.pricing import PriceTier, resolve_unit_price
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.cart.application.ports import (
    CartItemView,
    CartView,
    ProductForCart,
)

_GET_PRODUCT = text(
    "SELECT id, sku, name, status, is_epi, ca_valid_until, base_unit_price, min_order_qty "
    "FROM products WHERE id = :product_id"
)
_GET_TIERS = text(
    "SELECT id, min_quantity, max_quantity, unit_price FROM product_price_tiers "
    "WHERE product_id = :product_id ORDER BY min_quantity"
)
_INSERT_CART = text(
    "INSERT INTO carts (company_id, user_id) VALUES (:company_id, :user_id) "
    "ON CONFLICT (company_id, user_id) DO NOTHING"
)
_SELECT_CART = text("SELECT id FROM carts WHERE company_id = :company_id AND user_id = :user_id")
_SELECT_ITEMS = text(
    "SELECT ci.product_id, ci.quantity, p.sku, p.name, p.status, p.is_epi, "
    "       p.ca_valid_until, p.base_unit_price, p.min_order_qty "
    "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
    "WHERE ci.cart_id = :cart_id ORDER BY ci.created_at, ci.id"
)
_UPSERT_ITEM = text(
    "INSERT INTO cart_items (cart_id, company_id, product_id, quantity) "
    "VALUES (:cart_id, :company_id, :product_id, :quantity) "
    "ON CONFLICT (cart_id, product_id) "
    "DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity"
)
_SET_QUANTITY = text(
    "UPDATE cart_items SET quantity = :quantity "
    "WHERE cart_id = :cart_id AND product_id = :product_id"
)
_REMOVE_ITEM = text("DELETE FROM cart_items WHERE cart_id = :cart_id AND product_id = :product_id")
_CLEAR = text("DELETE FROM cart_items WHERE cart_id = :cart_id")


class SqlAlchemyCartRepository:
    """Implementacao da porta CartRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_product_for_cart(self, product_id: uuid.UUID) -> ProductForCart | None:
        async with self._uow_factory.begin() as uow:
            product = (await uow.session.execute(_GET_PRODUCT, {"product_id": product_id})).first()
            tiers_rows = (await uow.session.execute(_GET_TIERS, {"product_id": product_id})).all()
            await uow.commit()
            if product is None:
                return None
            return ProductForCart(
                id=product.id,
                sku=product.sku,
                name=product.name,
                status=product.status,
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                base_unit_price=product.base_unit_price,
                min_order_qty=product.min_order_qty,
                tiers=[
                    PriceTier(
                        tier_id=r.id,
                        min_quantity=r.min_quantity,
                        max_quantity=r.max_quantity,
                        unit_price=r.unit_price,
                    )
                    for r in tiers_rows
                ],
            )

    async def get_or_create_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(_INSERT_CART, {"company_id": company_id, "user_id": user_id})
            cart_id = cast(
                uuid.UUID,
                (
                    await uow.session.execute(
                        _SELECT_CART, {"company_id": company_id, "user_id": user_id}
                    )
                ).scalar_one(),
            )
            await uow.commit()
            return cart_id

    async def get_cart(self, company_id: uuid.UUID, user_id: uuid.UUID) -> CartView | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            cart_row = (
                await uow.session.execute(
                    _SELECT_CART, {"company_id": company_id, "user_id": user_id}
                )
            ).first()
            if cart_row is None:
                await uow.commit()
                return None
            cart_id = cart_row[0]

            item_rows = (await uow.session.execute(_SELECT_ITEMS, {"cart_id": cart_id})).all()
            await uow.commit()

        items = await self._resolve_items_standalone(item_rows)
        subtotal = sum((item.line_total for item in items), Decimal("0.00"))
        return CartView(
            cart_id=cart_id,
            company_id=company_id,
            user_id=user_id,
            items=items,
            subtotal=subtotal,
        )

    async def _resolve_items_standalone(self, item_rows: Sequence[Any]) -> list[CartItemView]:
        product_ids = [r.product_id for r in item_rows]
        tiers_by_product = await self._tiers_by_products(product_ids)
        items: list[CartItemView] = []
        for r in item_rows:
            resolved = resolve_unit_price(
                base_unit_price=r.base_unit_price,
                tiers=tiers_by_product.get(r.product_id, []),
                quantity=r.quantity,
            )
            items.append(
                CartItemView(
                    product_id=r.product_id,
                    sku=r.sku,
                    name=r.name,
                    quantity=r.quantity,
                    unit_price=resolved.unit_price,
                    line_total=resolved.unit_price * r.quantity,
                    tier_min_quantity=resolved.tier_min_quantity,
                )
            )
        return items

    async def _tiers_by_products(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[PriceTier]]:
        result: dict[uuid.UUID, list[PriceTier]] = {pid: [] for pid in product_ids}
        if not product_ids:
            return result
        stmt = text(
            "SELECT product_id, id, min_quantity, max_quantity, unit_price "
            "FROM product_price_tiers WHERE product_id IN :ids ORDER BY min_quantity"
        ).bindparams(bindparam("ids", expanding=True))
        async with self._uow_factory.begin() as uow:
            rows = (
                await uow.session.execute(stmt, {"ids": [str(pid) for pid in product_ids]})
            ).all()
            await uow.commit()
        for r in rows:
            result[r.product_id].append(
                PriceTier(
                    tier_id=r.id,
                    min_quantity=r.min_quantity,
                    max_quantity=r.max_quantity,
                    unit_price=r.unit_price,
                )
            )
        return result

    async def upsert_item(
        self,
        *,
        cart_id: uuid.UUID,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _UPSERT_ITEM,
                {
                    "cart_id": cart_id,
                    "company_id": company_id,
                    "product_id": product_id,
                    "quantity": quantity,
                },
            )
            await uow.commit()

    async def set_quantity(
        self,
        *,
        cart_id: uuid.UUID,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _SET_QUANTITY,
                {"cart_id": cart_id, "product_id": product_id, "quantity": quantity},
            )
            await uow.commit()

    async def remove_item(
        self, *, cart_id: uuid.UUID, company_id: uuid.UUID, product_id: uuid.UUID
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(_REMOVE_ITEM, {"cart_id": cart_id, "product_id": product_id})
            await uow.commit()

    async def clear(self, *, cart_id: uuid.UUID, company_id: uuid.UUID) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(_CLEAR, {"cart_id": cart_id})
            await uow.commit()
