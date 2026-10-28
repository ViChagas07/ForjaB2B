"""Integracao do agente de recuperacao de carrinho (FASE 4).

Cobre: last_activity_at em cada operacao de item, idempotencia do job
(2a execucao nao duplica envio), carrinho com pedido depois nao recuperado e
resgate de oferta no checkout (frete gratis, 3% so em linha nao negociada,
expirada/resgatada rejeitadas). RLS: leituras/escritas administrativas sempre
com app.set_tenant_context na MESMA transacao.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from psycopg import Connection

import app.tasks.cart_recovery as cart_recovery_task
from app.modules.cart.application.cart import CartService
from app.modules.cart.infrastructure.repository import SqlAlchemyCartRepository
from app.modules.ordering.application.order import CreateOrder
from app.modules.ordering.application.ports import OrderItemInput
from app.modules.ordering.domain.payment import PaymentMethod
from app.modules.ordering.infrastructure.repository import SqlAlchemyOrderingRepository

COMPANY = uuid.UUID("cccc0000-0000-4000-8000-00000000c001")
USER_A = uuid.UUID("cccc0000-0000-4000-8000-00000000c011")
USER_B = uuid.UUID("cccc0000-0000-4000-8000-00000000c012")
CATEGORY = uuid.UUID("cccc0000-0000-4000-8000-00000000c021")
PRODUCT = uuid.UUID("cccc0000-0000-4000-8000-00000000c031")
CART = uuid.UUID("cccc0000-0000-4000-8000-00000000c041")


@contextmanager
def tenant_tx(pg: object) -> Iterator[Connection]:
    conn = pg.connect_admin(autocommit=False)  # type: ignore[attr-defined]
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (COMPANY,))
        yield conn
        conn.commit()
    finally:
        conn.close()


def seed(pg: object) -> None:
    with tenant_tx(pg) as conn:
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '11222333000191', 'Recovery Alfa', 'ACTIVE') ON CONFLICT DO NOTHING",
            (COMPANY,),
        )
        for user_id, email, tag in (
            (USER_A, "buyer-a@recovery.test", "a"),
            (USER_B, "buyer-b@recovery.test", "b"),
        ):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
                "VALUES (%s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT DO NOTHING",
                (user_id, COMPANY, email, f"Buyer {tag}", f"{tag}" * 64),
            )
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) VALUES (%s, %s, %s, true) "
            "ON CONFLICT DO NOTHING",
            (CATEGORY, "EPI", "epi-recovery"),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg) VALUES (%s, %s, %s, %s, %s, "
            "'ACTIVE', false, %s, 1, %s) ON CONFLICT DO NOTHING",
            (PRODUCT, CATEGORY, "REC-001", "Capacete Recovery", "rec-001", "1600.00", "2.0"),
        )
        # Estado limpo a cada teste (o banco e compartilhado na sessao).
        for table in (
            "agent_audit_log",
            "cart_recovery_attempts",
            "notifications",
            "cart_recovery_offers",
            "cart_items",
            "carts",
            "order_items",
            "orders",
        ):
            conn.execute(f"DELETE FROM {table} WHERE company_id = %s", (COMPANY,))
        conn.execute(
            "INSERT INTO carts (id, company_id, user_id, last_activity_at) VALUES (%s, %s, %s, %s)",
            (CART, COMPANY, USER_A, datetime.now(UTC) - timedelta(hours=25)),
        )
        conn.execute(
            "INSERT INTO cart_items (cart_id, company_id, product_id, quantity) "
            "VALUES (%s, %s, %s, 1)",
            (CART, COMPANY, PRODUCT),
        )


def scalar(pg: object, sql: str, params: tuple[object, ...] = ()) -> object:
    with tenant_tx(pg) as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


async def test_cada_operacao_de_item_toca_last_activity(
    pg: object, uow_factory: object, migrated_domain_schema: None
) -> None:
    seed(pg)
    service = CartService(repository=SqlAlchemyCartRepository(uow_factory))  # type: ignore[arg-type]
    for operation in ("add", "update", "remove", "clear"):
        old = datetime.now(UTC) - timedelta(days=30)
        with tenant_tx(pg) as conn:
            conn.execute("UPDATE carts SET last_activity_at = %s WHERE id = %s", (old, CART))
        if operation == "add":
            await service.add_item(
                company_id=COMPANY, user_id=USER_A, product_id=PRODUCT, quantity=1
            )
        elif operation == "update":
            await service.update_quantity(
                company_id=COMPANY, user_id=USER_A, product_id=PRODUCT, quantity=2
            )
        elif operation == "remove":
            await service.remove_item(company_id=COMPANY, user_id=USER_A, product_id=PRODUCT)
        else:
            await service.clear(company_id=COMPANY, user_id=USER_A)
        last = scalar(pg, "SELECT last_activity_at FROM carts WHERE id = %s", (CART,))
        assert last is not None and last > old + timedelta(days=29), operation
        if operation in ("remove", "clear"):
            await service.add_item(
                company_id=COMPANY, user_id=USER_A, product_id=PRODUCT, quantity=1
            )
    assert scalar(pg, "SELECT count(*) FROM cart_items WHERE cart_id = %s", (CART,)) == 1


async def test_job_e_idempotente_e_envia_um_email(
    pg: object, test_settings: object, migrated_domain_schema: None
) -> None:
    seed(pg)
    first = await cart_recovery_task._run(test_settings)  # type: ignore[arg-type]
    assert first == 1
    assert (
        scalar(pg, "SELECT count(*) FROM cart_recovery_attempts WHERE cart_id = %s", (CART,)) == 1
    )
    assert scalar(pg, "SELECT count(*) FROM notifications WHERE event_type = 'cart.recovery'") == 1
    second = await cart_recovery_task._run(test_settings)  # type: ignore[arg-type]
    assert second == 0
    assert (
        scalar(pg, "SELECT count(*) FROM cart_recovery_attempts WHERE cart_id = %s", (CART,)) == 1
    )


async def test_carrinho_com_pedido_depois_nao_e_recuperado(
    pg: object, test_settings: object, migrated_domain_schema: None
) -> None:
    seed(pg)
    with tenant_tx(pg) as conn:
        conn.execute(
            "INSERT INTO orders (company_id, buyer_user_id, subtotal, total, idempotency_key, "
            "created_at) VALUES (%s, %s, 10, 10, %s, now())",
            (COMPANY, USER_A, f"order-{uuid.uuid4()}"),
        )
    assert await cart_recovery_task._run(test_settings) == 0  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("offer_type", "percent", "expect_free_shipping", "expected_discount"),
    [
        ("FREE_SHIPPING", None, True, Decimal("0.00")),
        ("PERCENT_DISCOUNT", Decimal("3.00"), False, Decimal("48.00")),
    ],
)
async def test_checkout_aplica_oferta_uma_vez(
    pg: object,
    uow_factory: object,
    migrated_domain_schema: None,
    offer_type: str,
    percent: Decimal | None,
    expect_free_shipping: bool,
    expected_discount: Decimal,
) -> None:
    seed(pg)
    with tenant_tx(pg) as conn:
        offer_id = conn.execute(
            "INSERT INTO cart_recovery_offers (company_id, cart_id, type, percent, expires_at) "
            "VALUES (%s, %s, %s, %s, now() + interval '72 hours') RETURNING id",
            (COMPANY, CART, offer_type, percent),
        ).fetchone()[0]
    create = CreateOrder(repository=SqlAlchemyOrderingRepository(uow_factory))  # type: ignore[arg-type]
    order = await create.create(
        company_id=COMPANY,
        buyer_user_id=USER_A,
        items=[OrderItemInput(product_id=PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key=f"k-{offer_type}",
    )
    assert order.discount_total == expected_discount
    if expect_free_shipping:
        assert order.shipping_total == Decimal("0.00")
    assert order.total == order.subtotal - order.discount_total + order.shipping_total
    assert scalar(pg, "SELECT redeemed_at FROM cart_recovery_offers WHERE id = %s", (offer_id,))
    again = await create.create(
        company_id=COMPANY,
        buyer_user_id=USER_A,
        items=[OrderItemInput(product_id=PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key=f"k2-{offer_type}",
    )
    assert again.discount_total == Decimal("0.00")
    assert again.shipping_total > 0


async def test_oferta_expirada_nao_aplica(
    pg: object, uow_factory: object, migrated_domain_schema: None
) -> None:
    seed(pg)
    with tenant_tx(pg) as conn:
        conn.execute(
            "INSERT INTO cart_recovery_offers (company_id, cart_id, type, expires_at) "
            "VALUES (%s, %s, 'FREE_SHIPPING', now() - interval '1 hour')",
            (COMPANY, CART),
        )
    create = CreateOrder(repository=SqlAlchemyOrderingRepository(uow_factory))  # type: ignore[arg-type]
    order = await create.create(
        company_id=COMPANY,
        buyer_user_id=USER_A,
        items=[OrderItemInput(product_id=PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key="k-expired",
    )
    assert order.shipping_total > 0


async def test_oferta_de_outro_comprador_nao_aplica(
    pg: object, uow_factory: object, migrated_domain_schema: None
) -> None:
    seed(pg)
    with tenant_tx(pg) as conn:
        # Oferta do carrinho do USER_B (outro comprador): nao vale para USER_A.
        other_cart = uuid.uuid4()
        conn.execute(
            "INSERT INTO carts (id, company_id, user_id, last_activity_at) "
            "VALUES (%s, %s, %s, now())",
            (other_cart, COMPANY, USER_B),
        )
        conn.execute(
            "INSERT INTO cart_recovery_offers (company_id, cart_id, type, expires_at) "
            "VALUES (%s, %s, 'FREE_SHIPPING', now() + interval '72 hours')",
            (COMPANY, other_cart),
        )
    create = CreateOrder(repository=SqlAlchemyOrderingRepository(uow_factory))  # type: ignore[arg-type]
    order = await create.create(
        company_id=COMPANY,
        buyer_user_id=USER_A,
        items=[OrderItemInput(product_id=PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key="k-other",
    )
    assert order.shipping_total > 0
