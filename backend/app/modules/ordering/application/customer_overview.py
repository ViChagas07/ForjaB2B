"""Painel do comprador: gasto total, compras recentes e cupons disponiveis.

A leitura e sempre escopada ao tenant autenticado e ao proprio comprador. O
total gasto ignora pedidos cancelados ou com credito recusado; o historico
preserva todos os estados para que o cliente acompanhe cada compra.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.ordering.application.ports import (
    AvailableCouponView,
    CustomerOverviewRepository,
    OrderView,
)


@dataclass(frozen=True, kw_only=True)
class CustomerOverview:
    total_spent: Decimal
    orders_count: int
    orders: list[OrderView]
    coupons: list[AvailableCouponView]


class GetCustomerOverview:
    def __init__(
        self,
        *,
        repository: CustomerOverviewRepository,
        coupon_limit: int = 20,
        now: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._coupon_limit = coupon_limit
        self._now = now

    async def execute(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        limit: int = 10,
    ) -> CustomerOverview:
        total_spent, orders_count = await self._repository.get_customer_spend(
            company_id, buyer_user_id
        )
        orders = await self._repository.list_customer_orders(company_id, buyer_user_id, limit)
        coupons = await self._repository.list_available_coupons(
            company_id, self._now or datetime.now(UTC), self._coupon_limit
        )
        return CustomerOverview(
            total_spent=total_spent,
            orders_count=orders_count,
            orders=orders,
            coupons=coupons,
        )
