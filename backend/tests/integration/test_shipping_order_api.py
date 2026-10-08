"""Testes de API da integracao de frete no pedido (peso real do catalogo).

O frete e calculado no backend a partir de ``products.weight_kg`` x quantidade
(nunca do cliente). Valida peso de um item, multiplos itens, pedido sem peso e
integracao do frete no total (incluindo reserva de credito no boleto).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("ffff0000-0000-4000-8000-000000000001")
_BUYER = uuid.UUID("ffff0000-0000-4000-8000-000000000002")
_MEMBER = uuid.UUID("ffff0000-0000-4000-8000-000000000003")
_EMAIL = "shipping@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("ffff0000-0000-4000-8000-000000000010")
_P_WEIGHT_1 = uuid.UUID("ffff0000-0000-4000-8000-000000000011")
_P_WEIGHT_2 = uuid.UUID("ffff0000-0000-4000-8000-000000000012")
_P_NO_WEIGHT = uuid.UUID("ffff0000-0000-4000-8000-000000000013")


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '19999999000131', 'Shipping Empresa', 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING",
            (_COMPANY,),
        )
        conn.execute(
            "INSERT INTO credit_accounts (company_id, credit_limit) "
            "VALUES (%s, %s) ON CONFLICT (company_id) DO NOTHING",
            (_COMPANY, _LIMIT),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, password_hash, "
            "status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_BUYER, _COMPANY, _EMAIL, _EMAIL, _cpf_hash(_EMAIL), password_hash),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_MEMBER, _COMPANY, _BUYER),
        )
        conn.execute("DELETE FROM order_items WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM orders WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM credit_entries WHERE company_id = %s", (_COMPANY,))
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Shipping Categoria', 'shipping-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        products = [
            (_P_WEIGHT_1, "SHP-W1", "Peso 2kg", "shp-w1", "10.00", "2.000"),
            (_P_WEIGHT_2, "SHP-W2", "Peso 500g", "shp-w2", "20.00", "0.500"),
            (_P_NO_WEIGHT, "SHP-NW", "Sem peso", "shp-nw", "5.00", None),
        ]
        for pid, sku, name, slug, price, weight in products:
            conn.execute(
                "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
                "base_unit_price, min_order_qty, weight_kg) VALUES (%s, %s, %s, %s, %s, "
                "'ACTIVE', false, %s, 1, %s) ON CONFLICT (id) DO NOTHING",
                (pid, _CAT, sku, name, slug, price, weight),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def shipping_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def shipping_client(
    test_settings: Settings, shipping_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_frete_de_um_item(shipping_client: httpx.AsyncClient) -> None:
    response = await shipping_client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_P_WEIGHT_1), "quantity": 3}],
            "payment_method": "PIX",
            "idempotency_key": "shp-1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "30.00"
    assert body["shipping_total"] == "45.00"  # 15 + 5*6kg
    assert body["total"] == "75.00"


async def test_frete_de_multiplos_itens(shipping_client: httpx.AsyncClient) -> None:
    response = await shipping_client.post(
        "/api/v1/orders",
        json={
            "items": [
                {"product_id": str(_P_WEIGHT_1), "quantity": 2},
                {"product_id": str(_P_WEIGHT_2), "quantity": 2},
            ],
            "payment_method": "PIX",
            "idempotency_key": "shp-2",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "60.00"  # 20 + 40
    # peso total = 4.0 + 1.0 = 5.0 -> 15 + 25 = 40
    assert body["shipping_total"] == "40.00"
    assert body["total"] == "100.00"


async def test_pedido_sem_peso_frete_zero(shipping_client: httpx.AsyncClient) -> None:
    response = await shipping_client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_P_NO_WEIGHT), "quantity": 2}],
            "payment_method": "PIX",
            "idempotency_key": "shp-3",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "10.00"
    assert body["shipping_total"] == "0.00"
    assert body["total"] == "10.00"


async def test_frete_entra_na_reserva_boleto(shipping_client: httpx.AsyncClient) -> None:
    response = await shipping_client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_P_WEIGHT_1), "quantity": 1}],
            "payment_method": "BOLETO",
            "idempotency_key": "shp-4",
        },
    )
    assert response.status_code == 201
    body = response.json()
    # subtotal 10.00 + frete (15 + 5*2kg = 25) = 35.00
    assert body["shipping_total"] == "25.00"
    assert body["total"] == "35.00"

    account = await shipping_client.get("/api/v1/credit/account")
    assert account.json()["used"] == "35.00"
