"""Painel do comprador: agregacao sem banco (repositorio fake)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.ordering.application.customer_overview import (
    DeleteCustomerOrder,
    GetCustomerOverview,
)
from app.modules.ordering.application.ports import (
    AvailableCouponView,
    OrderView,
)
from app.modules.ordering.domain.coupon import CouponType

_COMPANY = uuid.UUID("77770000-0000-4000-8000-000000007001")
_USER = uuid.UUID("77770000-0000-4000-8000-000000007002")
_NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _order(total: str) -> OrderView:
    return OrderView(
        id=uuid.uuid4(),
        company_id=_COMPANY,
        status="RECEIVED",
        currency="BRL",
        subtotal=Decimal(total),
        discount_total=Decimal("0.00"),
        shipping_total=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total=Decimal(total),
        created_at=_NOW,
        content_locale="pt-BR",
        items=[],
    )


class FakeRepository:
    def __init__(self) -> None:
        self.spend_args: tuple[uuid.UUID, uuid.UUID] | None = None
        self.order_args: tuple[uuid.UUID, uuid.UUID, int] | None = None
        self.coupon_args: tuple[uuid.UUID, datetime, int] | None = None
        self.delete_args: tuple[uuid.UUID, uuid.UUID, uuid.UUID] | None = None

    async def get_customer_spend(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID
    ) -> tuple[Decimal, int]:
        self.spend_args = (company_id, buyer_user_id)
        return Decimal("149.80"), 2

    async def list_customer_orders(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID, limit: int
    ) -> list[OrderView]:
        self.order_args = (company_id, buyer_user_id, limit)
        return [_order("49.80"), _order("100.00")]

    async def list_available_coupons(
        self, company_id: uuid.UUID, now: datetime, limit: int
    ) -> list[AvailableCouponView]:
        self.coupon_args = (company_id, now, limit)
        return [
            AvailableCouponView(
                code="FORJA10",
                type=CouponType.PRODUCT_TOTAL,
                percent=Decimal("10.00"),
                max_discount_amount=None,
                min_order_amount=Decimal("100.00"),
                valid_until=None,
                remaining_uses=20,
            )
        ]

    async def delete_customer_order(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool:
        self.delete_args = (company_id, buyer_user_id, order_id)
        return True


async def test_overview_agrega_gasto_pedidos_e_cupons() -> None:
    repository = FakeRepository()

    overview = await GetCustomerOverview(repository=repository, now=_NOW, coupon_limit=5).execute(
        company_id=_COMPANY, buyer_user_id=_USER, limit=2
    )

    assert overview.total_spent == Decimal("149.80")
    assert overview.orders_count == 2
    assert [order.total for order in overview.orders] == [Decimal("49.80"), Decimal("100.00")]
    assert overview.coupons[0].code == "FORJA10"
    assert overview.coupons[0].remaining_uses == 20
    assert repository.spend_args == (_COMPANY, _USER)
    assert repository.order_args == (_COMPANY, _USER, 2)
    assert repository.coupon_args == (_COMPANY, _NOW, 5)


async def test_delete_customer_order_uses_buyer_scope() -> None:
    repository = FakeRepository()
    order_id = uuid.uuid4()

    await DeleteCustomerOrder(repository=repository).execute(
        company_id=_COMPANY,
        buyer_user_id=_USER,
        order_id=order_id,
    )

    assert repository.delete_args == (_COMPANY, _USER, order_id)
