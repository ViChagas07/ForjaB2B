"""Testes de API do contexto de pedidos (snapshot, credito, idempotencia).

Usa empresas/usuarios/catalogo DEDICADOS. Valida snapshot de preco, precificacao
por tier, produto inativo/EPI expirado/quantidade invalida, reserva e liberacao
de credito, credito insuficiente, idempotencia, snapshot imutavel e isolamento.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY_A = uuid.UUID("dddd0000-0000-4000-8000-000000000001")
_COMPANY_B = uuid.UUID("dddd0000-0000-4000-8000-000000000002")
_BUYER_A = uuid.UUID("dddd0000-0000-4000-8000-000000000003")
_BUYER_B = uuid.UUID("dddd0000-0000-4000-8000-000000000004")
_MEMBER_A = uuid.UUID("dddd0000-0000-4000-8000-000000000005")
_MEMBER_B = uuid.UUID("dddd0000-0000-4000-8000-000000000006")

_EMAIL_A = "order-a@teste.com"
_EMAIL_B = "order-b@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("dddd0000-0000-4000-8000-000000000010")
_P_NORMAL = uuid.UUID("dddd0000-0000-4000-8000-000000000011")
_P_SECOND = uuid.UUID("dddd0000-0000-4000-8000-000000000012")
_P_EPI_EXPIRADO = uuid.UUID("dddd0000-0000-4000-8000-000000000013")
_P_INATIVO = uuid.UUID("dddd0000-0000-4000-8000-000000000014")
_P_MIN_QTY = uuid.UUID("dddd0000-0000-4000-8000-000000000015")
_P_EXPENSIVE = uuid.UUID("dddd0000-0000-4000-8000-000000000016")
_TIER_1 = uuid.UUID("dddd0000-0000-4000-8000-000000000017")
_TIER_2 = uuid.UUID("dddd0000-0000-4000-8000-000000000018")


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        for company_id, cnpj, name, buyer_id, email, member_id in (
            (_COMPANY_A, "19999999000111", "Order Empresa A", _BUYER_A, _EMAIL_A, _MEMBER_A),
            (_COMPANY_B, "19999999000112", "Order Empresa B", _BUYER_B, _EMAIL_B, _MEMBER_B),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute(
                "INSERT INTO companies (id, cnpj, legal_name, status) "
                "VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (company_id, cnpj, name),
            )
            conn.execute(
                "INSERT INTO credit_accounts (company_id, credit_limit) "
                "VALUES (%s, %s) ON CONFLICT (company_id) DO NOTHING",
                (company_id, _LIMIT),
            )
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, "
                "password_hash, status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING",
                (buyer_id, company_id, email, email, _cpf_hash(email), password_hash),
            )
            conn.execute(
                "INSERT INTO company_members (id, company_id, user_id, role, status) "
                "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (member_id, company_id, buyer_id),
            )
            # Reseta pedidos e ledger de credito (isolamento entre testes).
            conn.execute("DELETE FROM order_items WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM orders WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM credit_entries WHERE company_id = %s", (company_id,))
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Order Categoria', 'order-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        products = [
            (_P_NORMAL, "ORD-NORMAL", "Produto Normal", "ACTIVE", False, None, None, "24.90", 1),
            (
                _P_SECOND,
                "ORD-SECOND",
                "Produto Secundario",
                "ACTIVE",
                False,
                None,
                None,
                "10.00",
                1,
            ),
            (
                _P_EPI_EXPIRADO,
                "ORD-EPI-EXP",
                "EPI Expirado",
                "ACTIVE",
                True,
                "CA-1",
                date(2000, 1, 1),
                "8.90",
                1,
            ),
            (
                _P_INATIVO,
                "ORD-INATIVO",
                "Produto Inativo",
                "INACTIVE",
                False,
                None,
                None,
                "5.00",
                1,
            ),
            (_P_MIN_QTY, "ORD-MIN", "Produto Min", "ACTIVE", False, None, None, "50.00", 6),
            (_P_EXPENSIVE, "ORD-EXP", "Produto Caro", "ACTIVE", False, None, None, "2000.00", 1),
        ]
        for pid, sku, name, status, is_epi, ca_number, ca_valid, price, min_qty in products:
            conn.execute(
                "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
                "ca_number, ca_valid_until, base_unit_price, min_order_qty) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (
                    pid,
                    _CAT,
                    sku,
                    name,
                    sku.lower(),
                    status,
                    is_epi,
                    ca_number,
                    ca_valid,
                    price,
                    min_qty,
                ),
            )
        conn.execute(
            "INSERT INTO product_price_tiers "
            "(id, product_id, min_quantity, max_quantity, unit_price) "
            "VALUES (%s, %s, 6, 23, '24.90'), (%s, %s, 24, NULL, '21.90') "
            "ON CONFLICT (id) DO NOTHING",
            (_TIER_1, _P_NORMAL, _TIER_2, _P_NORMAL),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def order_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def order_client(
    test_settings: Settings, order_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL_A, "password": _PASSWORD}
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


def _order(item: uuid.UUID, quantity: int) -> dict[str, object]:
    return {"product_id": str(item), "quantity": quantity}


async def test_criar_pedido_pix_snapshot(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 6)],
            "payment_method": "PIX",
            "idempotency_key": "ord-pix-1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["subtotal"] == "149.40"
    assert body["total"] == "149.40"
    item = body["items"][0]
    assert item["sku"] == "ORD-NORMAL"
    assert item["product_name"] == "Produto Normal"
    assert item["quantity"] == 6
    assert item["unit_price"] == "24.90"


async def test_pedido_multiplos_itens(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 6), _order(_P_SECOND, 2)],
            "payment_method": "PIX",
            "idempotency_key": "ord-pix-2",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "169.40"  # 149.40 + 20.00
    assert len(body["items"]) == 2


async def test_preco_recalculado_tier(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 24)],
            "payment_method": "PIX",
            "idempotency_key": "ord-pix-3",
        },
    )
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["unit_price"] == "21.90"
    assert item["tier_min_quantity"] == 24
    assert item["line_total"] == "525.60"


async def test_produto_inativo_409(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_INATIVO, 1)],
            "payment_method": "PIX",
            "idempotency_key": "ord-inativo-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:product_not_sellable"


async def test_epi_expirado_409(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_EPI_EXPIRADO, 1)],
            "payment_method": "PIX",
            "idempotency_key": "ord-epi-1",
        },
    )
    assert response.status_code == 409


async def test_quantidade_invalida_422(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_MIN_QTY, 3)],
            "payment_method": "PIX",
            "idempotency_key": "ord-min-1",
        },
    )
    assert response.status_code == 422
    assert response.json()["type"] == "urn:forja:problem:quantity_below_minimum"


async def test_boleto_reserva_credito(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 6)],
            "payment_method": "BOLETO",
            "idempotency_key": "ord-bol-1",
        },
    )
    assert response.status_code == 201
    account = await order_client.get("/api/v1/credit/account")
    assert account.json()["used"] == "149.40"
    assert account.json()["available"] == "850.60"


async def test_credito_insuficiente_409(order_client: httpx.AsyncClient) -> None:
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_EXPENSIVE, 1)],
            "payment_method": "BOLETO",
            "idempotency_key": "ord-bol-insuf-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:insufficient_credit"


async def test_cancelamento_libera_credito(order_client: httpx.AsyncClient) -> None:
    created = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 6)],
            "payment_method": "BOLETO",
            "idempotency_key": "ord-bol-cancel-1",
        },
    )
    order_id = created.json()["id"]

    cancelled = await order_client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    account = await order_client.get("/api/v1/credit/account")
    assert account.json()["used"] == "0.00"
    assert account.json()["available"] == "1000.00"


async def test_idempotencia_mesma_chave(order_client: httpx.AsyncClient) -> None:
    payload = {
        "items": [_order(_P_NORMAL, 6)],
        "payment_method": "PIX",
        "idempotency_key": "ord-idem-1",
    }
    first = await order_client.post("/api/v1/orders", json=payload)
    second = await order_client.post("/api/v1/orders", json=payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_idempotencia_payload_conflitante(order_client: httpx.AsyncClient) -> None:
    await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_NORMAL, 6)],
            "payment_method": "PIX",
            "idempotency_key": "ord-conflict-1",
        },
    )
    response = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_SECOND, 2)],
            "payment_method": "PIX",
            "idempotency_key": "ord-conflict-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:idempotency_conflict"


async def test_snapshot_preco_nao_muda(
    order_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    created = await order_client.post(
        "/api/v1/orders",
        json={
            "items": [_order(_P_SECOND, 1)],
            "payment_method": "PIX",
            "idempotency_key": "ord-snap-1",
        },
    )
    order_id = created.json()["id"]
    assert created.json()["items"][0]["unit_price"] == "10.00"

    # Muda o preco do produto depois do pedido.
    conn = pg.connect_admin(autocommit=True)
    try:
        conn.execute("UPDATE products SET base_unit_price = '50.00' WHERE id = %s", (_P_SECOND,))
    finally:
        conn.close()

    fetched = await order_client.get(f"/api/v1/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["items"][0]["unit_price"] == "10.00"
    assert fetched.json()["items"][0]["base_unit_price"] == "10.00"


async def test_isolamento_entre_empresas(test_settings: Settings, order_seed: None) -> None:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_a = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL_A, "password": _PASSWORD}
        )
        login_b = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL_B, "password": _PASSWORD}
        )
        token_a = login_a.json()["access_token"]
        token_b = login_b.json()["access_token"]

        client.headers["Authorization"] = f"Bearer {token_a}"
        created = await client.post(
            "/api/v1/orders",
            json={
                "items": [_order(_P_NORMAL, 6)],
                "payment_method": "PIX",
                "idempotency_key": "ord-iso-1",
            },
        )
        order_id = created.json()["id"]

        client.headers["Authorization"] = f"Bearer {token_b}"
        fetched = await client.get(f"/api/v1/orders/{order_id}")
        assert fetched.status_code == 404

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)
