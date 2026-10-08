"""Testes de API do carrinho (CRUD + validacao + precificacao + isolamento).

Usa empresa/usuario/catalogo DEDICADOS. O preco e resolvido no servidor (tier);
nenhum preco e aceito do cliente. Valida produto inexistente/inativo, EPI
expirado, quantidade abaixo do lote minimo e isolamento entre usuarios.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import date

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("cccc0000-0000-4000-8000-000000000001")
_USER_A = uuid.UUID("cccc0000-0000-4000-8000-000000000002")
_USER_B = uuid.UUID("cccc0000-0000-4000-8000-000000000003")
_MEMBER_A = uuid.UUID("cccc0000-0000-4000-8000-000000000004")
_MEMBER_B = uuid.UUID("cccc0000-0000-4000-8000-000000000005")

_EMAIL_A = "cart-a@teste.com"
_EMAIL_B = "cart-b@teste.com"
_PASSWORD = "Senha@Forte123"

_CAT = uuid.UUID("cccc0000-0000-4000-8000-000000000010")
_P_NORMAL = uuid.UUID("cccc0000-0000-4000-8000-000000000011")
_P_EPI_VALIDO = uuid.UUID("cccc0000-0000-4000-8000-000000000012")
_P_EPI_EXPIRADO = uuid.UUID("cccc0000-0000-4000-8000-000000000013")
_P_INATIVO = uuid.UUID("cccc0000-0000-4000-8000-000000000014")
_P_MIN_QTY = uuid.UUID("cccc0000-0000-4000-8000-000000000015")
_TIER_1 = uuid.UUID("cccc0000-0000-4000-8000-000000000016")
_TIER_2 = uuid.UUID("cccc0000-0000-4000-8000-000000000017")


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
            "VALUES (%s, '19999999000103', 'Cart Empresa', 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING",
            (_COMPANY,),
        )
        # Reseta carrinhos da empresa (isolamento entre testes).
        conn.execute("DELETE FROM carts WHERE company_id = %s", (_COMPANY,))
        for user_id, email, member_id in (
            (_USER_A, _EMAIL_A, _MEMBER_A),
            (_USER_B, _EMAIL_B, _MEMBER_B),
        ):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, "
                "password_hash, status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, _COMPANY, email, email, _cpf_hash(email), password_hash),
            )
            conn.execute(
                "INSERT INTO company_members (id, company_id, user_id, role, status) "
                "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (member_id, _COMPANY, user_id),
            )
        conn.commit()
    finally:
        conn.close()

    # Catalogo global (sem tenant context).
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Cart Categoria', 'cart-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        products = [
            (_P_NORMAL, "CART-NORMAL", "Produto Normal", "ACTIVE", False, None, None, "24.90", 1),
            (
                _P_EPI_VALIDO,
                "CART-EPI-OK",
                "EPI Valido",
                "ACTIVE",
                True,
                "CA-1",
                date(2099, 1, 1),
                "10.00",
                1,
            ),
            (
                _P_EPI_EXPIRADO,
                "CART-EPI-EXP",
                "EPI Expirado",
                "ACTIVE",
                True,
                "CA-2",
                date(2000, 1, 1),
                "8.90",
                1,
            ),
            (
                _P_INATIVO,
                "CART-INATIVO",
                "Produto Inativo",
                "INACTIVE",
                False,
                None,
                None,
                "5.00",
                1,
            ),
            (_P_MIN_QTY, "CART-MIN", "Produto Min", "ACTIVE", False, None, None, "50.00", 6),
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
        # Tiers do produto normal: 6-23 -> 24.90, 24+ -> 21.90.
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
def cart_seed(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    _seed(pg, migrated_domain_schema)
    yield
    # Cleanup: remove carrinhos e produtos dedicados para nao interferir nos
    # testes de catalogo global (que rodam depois e contam produtos).
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        conn.execute("DELETE FROM carts WHERE company_id = %s", (_COMPANY,))
        conn.execute(
            "DELETE FROM products WHERE id IN (%s, %s, %s, %s, %s)",
            (_P_NORMAL, _P_EPI_VALIDO, _P_EPI_EXPIRADO, _P_INATIVO, _P_MIN_QTY),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def cart_client(test_settings: Settings, cart_seed: None) -> AsyncIterator[httpx.AsyncClient]:
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


async def test_carrinho_vazio(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.get("/api/v1/cart")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["subtotal"] == "0.00"


async def test_adicionar_item_resolve_preco(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 6}
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["product_id"] == str(_P_NORMAL)
    assert item["quantity"] == 6
    assert item["unit_price"] == "24.90"
    assert item["line_total"] == "149.40"
    assert response.json()["subtotal"] == "149.40"


async def test_tier_por_quantidade(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 24}
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["unit_price"] == "21.90"
    assert item["tier_min_quantity"] == 24
    assert item["line_total"] == "525.60"


async def test_atualizar_quantidade(cart_client: httpx.AsyncClient) -> None:
    await cart_client.post("/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 6})
    response = await cart_client.put(f"/api/v1/cart/items/{_P_NORMAL}", json={"quantity": 12})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == 12


async def test_remover_item(cart_client: httpx.AsyncClient) -> None:
    await cart_client.post("/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 6})
    response = await cart_client.delete(f"/api/v1/cart/items/{_P_NORMAL}")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_limpar_carrinho(cart_client: httpx.AsyncClient) -> None:
    await cart_client.post("/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 6})
    response = await cart_client.delete("/api/v1/cart")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["subtotal"] == "0.00"


async def test_produto_inexistente_404(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items",
        json={"product_id": str(uuid.UUID("cccc0000-0000-4000-8000-000000000099")), "quantity": 1},
    )
    assert response.status_code == 404
    assert response.json()["type"] == "urn:forja:problem:product_not_found"


async def test_produto_inativo_409(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_INATIVO), "quantity": 1}
    )
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:product_not_sellable"


async def test_epi_ca_expirado_409(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_EPI_EXPIRADO), "quantity": 1}
    )
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:product_not_sellable"


async def test_quantidade_abaixo_do_minimo_422(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_MIN_QTY), "quantity": 3}
    )
    assert response.status_code == 422
    assert response.json()["type"] == "urn:forja:problem:quantity_below_minimum"


async def test_epi_valido_adicionado(cart_client: httpx.AsyncClient) -> None:
    response = await cart_client.post(
        "/api/v1/cart/items", json={"product_id": str(_P_EPI_VALIDO), "quantity": 2}
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["unit_price"] == "10.00"


async def test_isolamento_entre_usuarios(test_settings: Settings, cart_seed: None) -> None:
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

        # A adiciona um item; B nao ve.
        client.headers["Authorization"] = f"Bearer {token_a}"
        await client.post("/api/v1/cart/items", json={"product_id": str(_P_NORMAL), "quantity": 6})

        client.headers["Authorization"] = f"Bearer {token_b}"
        cart_b = await client.get("/api/v1/cart")
        assert cart_b.json()["items"] == []

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)
