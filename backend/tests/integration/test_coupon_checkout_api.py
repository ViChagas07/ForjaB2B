"""Cupom no checkout: preview, criacao atomica, concorrencia e liberacao."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("77770000-0000-4000-8000-000000007001")
_BUYER = uuid.UUID("77770000-0000-4000-8000-000000007002")
_MEMBER = uuid.UUID("77770000-0000-4000-8000-000000007003")
_OTHER_COMPANY = uuid.UUID("77770000-0000-4000-8000-000000007004")
_CATEGORY = uuid.UUID("77770000-0000-4000-8000-000000007010")
_PRODUCT = uuid.UUID("77770000-0000-4000-8000-000000007011")
_CART = uuid.UUID("77770000-0000-4000-8000-000000007012")
_EMAIL = "coupon-checkout@teste.com"
_PASSWORD = "Senha@Forte123"
_WEBHOOK_SECRET = "dev_payment_webhook_secret_change_in_production"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _tenant(conn: object) -> None:
    conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '77666555000144', 'Cupom Checkout Empresa', 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (_COMPANY,),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, password_hash, "
            "status) VALUES (%s, %s, %s, 'Cupom Checkout', %s, %s, 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (_BUYER, _COMPANY, _EMAIL, _hash(_EMAIL), password_hash),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT DO NOTHING",
            (_MEMBER, _COMPANY, _BUYER),
        )
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_OTHER_COMPANY,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '77666555000225', 'Cupom Outra Empresa', 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (_OTHER_COMPANY,),
        )
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Cupom Checkout', 'cupom-checkout', true) ON CONFLICT DO NOTHING",
            (_CATEGORY,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg) VALUES "
            "(%s, %s, 'CPN-001', 'Produto Cupom', 'produto-cupom', 'ACTIVE', false, "
            "'100.00', 1, '2.0') ON CONFLICT DO NOTHING",
            (_PRODUCT, _CATEGORY),
        )
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        for table in (
            "payment_events",
            "payments",
            "invoices",
            "coupon_redemptions",
            "order_items",
            "orders",
            "notifications",
            "cart_recovery_attempts",
            "cart_recovery_offers",
            "cart_items",
            "carts",
            "credit_entries",
        ):
            conn.execute(f"DELETE FROM {table} WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM coupons WHERE created_by = %s", (_BUYER,))
        conn.execute(
            "INSERT INTO credit_accounts (company_id, credit_limit) "
            "VALUES (%s, 1000.00) ON CONFLICT DO NOTHING",
            (_COMPANY,),
        )
        conn.execute(
            "INSERT INTO carts (id, company_id, user_id, last_activity_at) "
            "VALUES (%s, %s, %s, now())",
            (_CART, _COMPANY, _BUYER),
        )
        conn.execute(
            "INSERT INTO cart_items (cart_id, company_id, product_id, quantity) "
            "VALUES (%s, %s, %s, 1)",
            (_CART, _COMPANY, _PRODUCT),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup(pg: PostgresInstance) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        for table in (
            "payment_events",
            "payments",
            "invoices",
            "coupon_redemptions",
            "order_items",
            "orders",
            "notifications",
            "cart_recovery_attempts",
            "cart_recovery_offers",
            "cart_items",
            "carts",
            "credit_entries",
        ):
            conn.execute(f"DELETE FROM {table} WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM credit_accounts WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM coupons WHERE created_by = %s", (_BUYER,))
        conn.execute("DELETE FROM company_members WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM users WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM companies WHERE id = %s", (_COMPANY,))
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_OTHER_COMPANY,))
        conn.execute("DELETE FROM companies WHERE id = %s", (_OTHER_COMPANY,))
        conn.execute("DELETE FROM products WHERE id = %s", (_PRODUCT,))
        conn.execute("DELETE FROM categories WHERE id = %s", (_CATEGORY,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def checkout_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def checkout_client(
    test_settings: Settings, checkout_seed: None, pg: PostgresInstance
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
            )
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            yield client
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)
        _cleanup(pg)


def _insert_coupon(
    pg: PostgresInstance,
    *,
    code: str,
    coupon_type: str = "PRODUCT_TOTAL",
    percent: str = "10.00",
    usage_limit_total: int | None = None,
    usage_limit_per_company: int | None = None,
    min_order_amount: str | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    restricted_company_id: uuid.UUID | None = None,
    is_active: bool = True,
) -> uuid.UUID:
    conn = pg.connect_admin(autocommit=False)
    try:
        coupon_id = conn.execute(
            "INSERT INTO coupons (code, type, percent, usage_limit_total, "
            "usage_limit_per_company, min_order_amount, valid_from, valid_until, "
            "restricted_company_id, is_active, created_by) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                code,
                coupon_type,
                percent,
                usage_limit_total,
                usage_limit_per_company,
                min_order_amount,
                valid_from,
                valid_until,
                restricted_company_id,
                is_active,
                _BUYER,
            ),
        ).fetchone()[0]
        conn.commit()
        return coupon_id
    finally:
        conn.close()


def _insert_redemption(
    pg: PostgresInstance, *, coupon_id: uuid.UUID, amount: str = "10.00"
) -> uuid.UUID:
    order_id = uuid.uuid4()
    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        conn.execute(
            "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total, "
            "idempotency_key) VALUES (%s, %s, %s, 100.00, 100.00, %s)",
            (order_id, _COMPANY, _BUYER, f"seed-{order_id}"),
        )
        conn.execute(
            "INSERT INTO coupon_redemptions "
            "(coupon_id, order_id, company_id, amount_discounted) "
            "VALUES (%s, %s, %s, %s)",
            (coupon_id, order_id, _COMPANY, amount),
        )
        conn.commit()
        return order_id
    finally:
        conn.close()


def _order_payload(code: str, *, key: str, method: str = "PIX") -> dict[str, object]:
    return {
        "items": [{"product_id": str(_PRODUCT), "quantity": 1}],
        "payment_method": method,
        "idempotency_key": key,
        "coupon_code": code,
    }


def _state(pg: PostgresInstance, sql: str, params: tuple[object, ...]) -> object:
    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        row = conn.execute(sql, params).fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        conn.close()


async def test_preview_sem_cupom_para_resumo(
    checkout_client: httpx.AsyncClient,
) -> None:
    response = await checkout_client.post("/api/v1/orders/coupon-preview", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["subtotal"] == "100.00"
    assert body["shipping_total"] == "25.00"
    assert body["coupon_discount"] == "0.00"
    assert body["pix_discount"] == "6.25"
    assert body["total"] == "118.75"


async def _post_webhook(
    client: httpx.AsyncClient,
    *,
    event_id: str,
    event_type: str,
    provider_reference: str,
) -> httpx.Response:
    payload = {
        "provider": "FAKE_PIX",
        "event_id": event_id,
        "event_type": event_type,
        "provider_reference": provider_reference,
        "company_id": str(_COMPANY),
    }
    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = (
        "sha256="
        + hmac.new(
            _WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
    )
    return await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Forja-Signature": signature,
            "X-Forja-Timestamp": str(timestamp),
        },
    )


async def test_preview_produto_valido_com_pix(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="CUPOM10")
    response = await checkout_client.post(
        "/api/v1/orders/coupon-preview", json={"code": "  cupom10 "}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["subtotal"] == "100.00"
    assert body["shipping_total"] == "25.00"
    assert body["coupon_discount"] == "10.00"
    assert body["pix_discount"] == "5.75"
    assert body["total"] == "109.25"
    assert _state(pg, "SELECT count(*) FROM orders WHERE company_id = %s", (_COMPANY,)) == 0
    assert (
        _state(
            pg,
            "SELECT count(*) FROM coupon_redemptions WHERE company_id = %s",
            (_COMPANY,),
        )
        == 0
    )


async def test_preview_frete_com_recovery(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="FRETE10", coupon_type="SHIPPING")
    conn = pg.connect_admin(autocommit=False)
    try:
        _tenant(conn)
        conn.execute(
            "INSERT INTO cart_recovery_offers (company_id, cart_id, type, percent, "
            "expires_at) VALUES (%s, %s, 'PERCENT_DISCOUNT', 3.00, now() + interval '1 day')",
            (_COMPANY, _CART),
        )
        conn.commit()
    finally:
        conn.close()

    response = await checkout_client.post("/api/v1/orders/coupon-preview", json={"code": "FRETE10"})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["recovery_discount"] == "3.00"
    assert body["shipping_discount"] == "2.50"
    assert body["shipping_total"] == "22.50"
    assert body["pix_discount"] == "5.98"
    assert body["total"] == "113.52"


async def test_preview_motivos_tipados(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    now = datetime.now(UTC)
    _insert_coupon(pg, code="INATIVO", is_active=False)
    _insert_coupon(pg, code="FUTURO", valid_from=now + timedelta(days=1))
    _insert_coupon(pg, code="EXPIRADO", valid_until=now - timedelta(seconds=1))
    exhausted = _insert_coupon(pg, code="ESGOTADO", usage_limit_total=1)
    _insert_redemption(pg, coupon_id=exhausted, amount="1.00")
    company = _insert_coupon(pg, code="LIMITE-EMPRESA", usage_limit_per_company=1)
    _insert_redemption(pg, coupon_id=company, amount="1.00")
    _insert_coupon(pg, code="MINIMO", min_order_amount="150.00")
    _insert_coupon(pg, code="OUTRA-EMPRESA", restricted_company_id=_OTHER_COMPANY)

    expectations = {
        "INATIVO": "INACTIVE",
        "FUTURO": "NOT_STARTED",
        "EXPIRADO": "EXPIRED",
        "ESGOTADO": "EXHAUSTED",
        "LIMITE-EMPRESA": "COMPANY_LIMIT_REACHED",
        # Restricao a outra empresa nao revela existencia (anti-enumeracao).
        "OUTRA-EMPRESA": "NOT_FOUND",
        "NAO-EXISTE": "NOT_FOUND",
    }
    for code, reason in expectations.items():
        response = await checkout_client.post("/api/v1/orders/coupon-preview", json={"code": code})
        assert response.status_code == 200, code
        assert response.json()["valid"] is False, code
        assert response.json()["reason"] == reason, code

    minimum = await checkout_client.post("/api/v1/orders/coupon-preview", json={"code": "MINIMO"})
    assert minimum.json()["reason"] == "MIN_ORDER_NOT_MET"
    assert minimum.json()["missing_amount"] == "50.00"


async def test_pedido_rejeita_cupom_restrito_a_outra_empresa(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(
        pg,
        code="RESTRITO",
        restricted_company_id=_OTHER_COMPANY,
    )
    response = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("RESTRITO", key="restricted-order"),
        headers={"Idempotency-Key": "restricted-order"},
    )
    assert response.status_code == 422
    assert response.json()["type"] == "urn:forja:problem:coupon_not_found"
    assert _state(pg, "SELECT count(*) FROM orders WHERE company_id = %s", (_COMPANY,)) == 0


async def test_criar_pedido_com_cupom_produto_e_resgate(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="CUPOM10")
    response = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("CUPOM10", key="order-coupon-product"),
        headers={"Idempotency-Key": "order-coupon-product"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["coupon_code"] == "CUPOM10"
    assert body["coupon_type"] == "PRODUCT_TOTAL"
    assert body["coupon_percent"] == "10.00"
    assert body["coupon_discount_amount"] == "10.00"
    assert body["shipping_discount_amount"] == "0.00"
    assert body["subtotal"] == "100.00"
    assert body["shipping_total"] == "25.00"
    assert body["total"] == "115.00"
    assert (
        _state(
            pg,
            "SELECT status FROM coupon_redemptions WHERE order_id = %s",
            (uuid.UUID(body["id"]),),
        )
        == "APPLIED"
    )
    assert _state(
        pg,
        "SELECT amount_discounted FROM coupon_redemptions WHERE order_id = %s",
        (uuid.UUID(body["id"]),),
    ) == Decimal("10.00")
    notification_payload = _state(
        pg,
        "SELECT payload FROM notifications WHERE aggregate_id = %s "
        "AND event_type = 'order.created'",
        (uuid.UUID(body["id"]),),
    )
    assert isinstance(notification_payload, dict)
    assert notification_payload["coupon_code"] == "CUPOM10"
    assert notification_payload["coupon_discount_amount"] == "10.00"


async def test_snapshot_do_pedido_nao_muda_apos_edicao(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    coupon_id = _insert_coupon(pg, code="SNAPSHOT")
    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("SNAPSHOT", key="snapshot-order"),
        headers={"Idempotency-Key": "snapshot-order"},
    )
    assert order.status_code == 201

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("UPDATE coupons SET percent = 50.00 WHERE id = %s", (coupon_id,))
        conn.commit()
    finally:
        conn.close()

    detail = await checkout_client.get(f"/api/v1/orders/{order.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["coupon_percent"] == "10.00"
    assert detail.json()["coupon_discount_amount"] == "10.00"
    assert detail.json()["total"] == "115.00"


async def test_criar_pedido_com_cupom_frete(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="FRETE10", coupon_type="SHIPPING")
    response = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("FRETE10", key="order-coupon-shipping"),
        headers={"Idempotency-Key": "order-coupon-shipping"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["shipping_total"] == "22.50"
    assert body["shipping_discount_amount"] == "2.50"
    assert body["coupon_discount_amount"] == "0.00"
    assert body["total"] == "122.50"


async def test_cupom_de_frete_100_por_cento(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="FRETE-GRATIS", coupon_type="SHIPPING", percent="100.00")
    response = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("FRETE-GRATIS", key="order-free-shipping"),
        headers={"Idempotency-Key": "order-free-shipping"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["shipping_total"] == "0.00"
    assert body["shipping_discount_amount"] == "25.00"
    assert body["total"] == "100.00"


async def test_boleto_reserva_credito_apos_cupom(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="BOLETO10")
    response = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("BOLETO10", key="order-coupon-boleto", method="BOLETO"),
        headers={"Idempotency-Key": "order-coupon-boleto"},
    )
    assert response.status_code == 201
    assert response.json()["total"] == "115.00"
    assert _state(
        pg,
        "SELECT amount FROM credit_entries WHERE company_id = %s AND entry_type = 'RESERVE'",
        (_COMPANY,),
    ) == Decimal("115.00")


async def test_pix_usa_base_apos_cupom_e_bate_com_preview(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="CUPOM10")
    preview = await checkout_client.post("/api/v1/orders/coupon-preview", json={"code": "CUPOM10"})
    assert preview.status_code == 200
    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("CUPOM10", key="order-coupon-pix"),
        headers={"Idempotency-Key": "order-coupon-pix"},
    )
    assert order.status_code == 201
    payment = await checkout_client.post(
        "/api/v1/payments",
        json={"order_id": order.json()["id"], "method": "PIX"},
        headers={"Idempotency-Key": "pay-coupon-pix"},
    )
    assert payment.status_code == 201
    assert payment.json()["amount"] == preview.json()["total"]
    assert payment.json()["discount_amount"] == "5.75"
    assert Decimal(payment.json()["amount"]) == Decimal("109.25")


async def test_webhook_pago_nao_altera_snapshots_nem_descontos(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="PAGO")
    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("PAGO", key="paid-order"),
        headers={"Idempotency-Key": "paid-order"},
    )
    assert order.status_code == 201
    order_id = order.json()["id"]
    payment = await checkout_client.post(
        "/api/v1/payments",
        json={"order_id": order_id, "method": "PIX"},
        headers={"Idempotency-Key": "paid-order-payment"},
    )
    assert payment.status_code == 201
    webhook = await _post_webhook(
        checkout_client,
        event_id="evt-paid-coupon",
        event_type="payment.paid",
        provider_reference=payment.json()["provider_reference"],
    )
    assert webhook.status_code == 200

    detail = await checkout_client.get(f"/api/v1/orders/{order_id}")
    body = detail.json()
    assert body["coupon_code"] == "PAGO"
    assert body["coupon_percent"] == "10.00"
    assert body["coupon_discount_amount"] == "10.00"
    assert body["shipping_discount_amount"] == "0.00"
    assert body["total"] == "115.00"
    assert (
        _state(
            pg,
            "SELECT status FROM coupon_redemptions WHERE order_id = %s",
            (uuid.UUID(order_id),),
        )
        == "APPLIED"
    )
    assert payment.json()["amount"] == "109.25"


async def test_concorrencia_do_ultimo_uso(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="ULTIMO-USO", usage_limit_total=1)
    responses = await asyncio.gather(
        *[
            checkout_client.post(
                "/api/v1/orders",
                json=_order_payload("ULTIMO-USO", key=f"race-{index}"),
                headers={"Idempotency-Key": f"race-{index}"},
            )
            for index in range(5)
        ]
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 422, 422, 422, 422]
    for response in responses:
        if response.status_code == 422:
            assert response.json()["type"] == "urn:forja:problem:coupon_exhausted"
    assert (
        _state(
            pg,
            "SELECT count(*) FROM coupon_redemptions WHERE company_id = %s",
            (_COMPANY,),
        )
        == 1
    )


async def test_limite_por_empresa(checkout_client: httpx.AsyncClient, pg: PostgresInstance) -> None:
    _insert_coupon(pg, code="LIMITE-EMPRESA", usage_limit_per_company=1)
    first = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("LIMITE-EMPRESA", key="company-1"),
        headers={"Idempotency-Key": "company-1"},
    )
    second = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("LIMITE-EMPRESA", key="company-2"),
        headers={"Idempotency-Key": "company-2"},
    )
    assert first.status_code == 201
    assert second.status_code == 422
    assert second.json()["type"] == "urn:forja:problem:coupon_company_limit_reached"


async def test_limite_por_empresa_concorrente(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="LIMITE-RACE", usage_limit_per_company=1)
    responses = await asyncio.gather(
        *[
            checkout_client.post(
                "/api/v1/orders",
                json=_order_payload("LIMITE-RACE", key=f"company-race-{index}"),
                headers={"Idempotency-Key": f"company-race-{index}"},
            )
            for index in range(3)
        ]
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 422, 422]
    for response in responses:
        if response.status_code == 422:
            assert response.json()["type"] == ("urn:forja:problem:coupon_company_limit_reached")
    assert (
        _state(
            pg,
            "SELECT count(*) FROM coupon_redemptions WHERE company_id = %s",
            (_COMPANY,),
        )
        == 1
    )


async def test_expira_entre_preview_e_compra(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    coupon_id = _insert_coupon(
        pg, code="EXPIRA", valid_until=datetime.now(UTC) + timedelta(hours=1)
    )
    preview = await checkout_client.post("/api/v1/orders/coupon-preview", json={"code": "EXPIRA"})
    assert preview.json()["valid"] is True

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "UPDATE coupons SET valid_until = now() - interval '1 second' WHERE id = %s",
            (coupon_id,),
        )
        conn.commit()
    finally:
        conn.close()

    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("EXPIRA", key="expires-order"),
        headers={"Idempotency-Key": "expires-order"},
    )
    assert order.status_code == 422
    assert order.json()["type"] == "urn:forja:problem:coupon_expired"
    assert _state(pg, "SELECT count(*) FROM orders WHERE company_id = %s", (_COMPANY,)) == 0
    assert (
        _state(
            pg,
            "SELECT count(*) FROM coupon_redemptions WHERE company_id = %s",
            (_COMPANY,),
        )
        == 0
    )


async def test_cancelamento_libera_resgate(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="CANCELA", usage_limit_total=1)
    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("CANCELA", key="cancel-order"),
        headers={"Idempotency-Key": "cancel-order"},
    )
    assert order.status_code == 201
    cancel = await checkout_client.post(f"/api/v1/orders/{order.json()['id']}/cancel")
    assert cancel.status_code == 200
    assert (
        _state(
            pg,
            "SELECT status FROM coupon_redemptions WHERE order_id = %s",
            (uuid.UUID(order.json()["id"]),),
        )
        == "RELEASED"
    )
    second_cancel = await checkout_client.post(f"/api/v1/orders/{order.json()['id']}/cancel")
    assert second_cancel.status_code == 409
    assert (
        _state(
            pg,
            "SELECT status FROM coupon_redemptions WHERE order_id = %s",
            (uuid.UUID(order.json()["id"]),),
        )
        == "RELEASED"
    )

    again = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("CANCELA", key="cancel-again"),
        headers={"Idempotency-Key": "cancel-again"},
    )
    assert again.status_code == 201


async def test_pagamento_falho_libera_e_cancela(
    checkout_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    _insert_coupon(pg, code="FALHA", usage_limit_total=1)
    order = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("FALHA", key="failed-order"),
        headers={"Idempotency-Key": "failed-order"},
    )
    assert order.status_code == 201
    payment = await checkout_client.post(
        "/api/v1/payments",
        json={"order_id": order.json()["id"], "method": "PIX"},
        headers={"Idempotency-Key": "failed-payment"},
    )
    assert payment.status_code == 201

    payload = {
        "provider": "FAKE_PIX",
        "event_id": "evt-failed-1",
        "event_type": "payment.failed",
        "provider_reference": payment.json()["provider_reference"],
        "company_id": str(_COMPANY),
    }
    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = (
        "sha256="
        + hmac.new(
            _WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
    )
    webhook = await checkout_client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Forja-Signature": signature,
            "X-Forja-Timestamp": str(timestamp),
        },
    )
    assert webhook.status_code == 200
    assert (
        _state(
            pg,
            "SELECT status FROM coupon_redemptions WHERE order_id = %s",
            (uuid.UUID(order.json()["id"]),),
        )
        == "RELEASED"
    )
    assert (
        _state(
            pg,
            "SELECT status FROM orders WHERE id = %s",
            (uuid.UUID(order.json()["id"]),),
        )
        == "CANCELLED"
    )

    again = await checkout_client.post(
        "/api/v1/orders",
        json=_order_payload("FALHA", key="failed-again"),
        headers={"Idempotency-Key": "failed-again"},
    )
    assert again.status_code == 201
