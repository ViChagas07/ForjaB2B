"""Integracao de precos por empresa (Fase 9A): busca, carrinho e isolamento.

Cobre o diferencial B2B com dados DEDICADOS:
- visitante recebe preco consultivo (nenhum valor);
- empresa A (preco negociado) e empresa B (desconto) veem valores distintos
  para o MESMO produto;
- carrinho revalida o preco no PostgreSQL (nunca confia no cliente);
- ``company_price_rules`` e isolada por RLS entre empresas.

Nenhum preco entra no indice de busca nem no texto de embedding (garantido por
testes unitarios proprios em tests/unit/test_search_documents.py).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import cast

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY_A = uuid.UUID("99990000-0000-4000-8000-000000000001")
_COMPANY_B = uuid.UUID("99990000-0000-4000-8000-000000000002")
_USER_A = uuid.UUID("99990000-0000-4000-8000-000000000003")
_USER_B = uuid.UUID("99990000-0000-4000-8000-000000000004")
_MEMBER_A = uuid.UUID("99990000-0000-4000-8000-000000000005")
_MEMBER_B = uuid.UUID("99990000-0000-4000-8000-000000000006")

_EMAIL_A = "pricing-a@teste.com"
_EMAIL_B = "pricing-b@teste.com"
_PASSWORD = "Senha@Forte123"

_CAT = uuid.UUID("99990000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("99990000-0000-4000-8000-000000000011")
_SKU = "PRC-DEMO-001"
_BASE_PRICE = Decimal("100.00")
_NEGOTIATED_A = Decimal("80.00")
_DISCOUNT_B = Decimal("10.00")


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    password_hash = Argon2PasswordHasher().hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Pricing Categoria', 'pricing-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty) "
            "VALUES (%s, %s, %s, 'Produto Pricing Demo', %s, 'ACTIVE', false, %s, 1) "
            "ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT, _SKU, _SKU.lower(), _BASE_PRICE),
        )
        for company_id, user_id, member_id, email, cnpj in (
            (_COMPANY_A, _USER_A, _MEMBER_A, _EMAIL_A, "19999999000180"),
            (_COMPANY_B, _USER_B, _MEMBER_B, _EMAIL_B, "19999999000181"),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute(
                "INSERT INTO companies (id, cnpj, legal_name, status) "
                "VALUES (%s, %s, 'Pricing Empresa', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (company_id, cnpj),
            )
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, "
                "password_hash, status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, company_id, email, email, _cpf_hash(email), password_hash),
            )
            conn.execute(
                "INSERT INTO company_members (id, company_id, user_id, role, status) "
                "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (member_id, company_id, user_id),
            )
            conn.execute("DELETE FROM carts WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM company_price_rules WHERE company_id = %s", (company_id,))
        conn.commit()
    finally:
        conn.close()

    # Regras de preco por empresa (tenant-scoped).
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        conn.execute(
            "INSERT INTO company_price_rules (id, company_id, rule_type, product_id, unit_price) "
            "VALUES (%s, %s, 'FIXED_PRICE', %s, %s)",
            (
                uuid.UUID("99990000-0000-4000-8000-000000000020"),
                _COMPANY_A,
                _PRODUCT,
                _NEGOTIATED_A,
            ),
        )
        conn.commit()

        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        conn.execute(
            "INSERT INTO company_price_rules (id, company_id, rule_type, category_id, percent) "
            "VALUES (%s, %s, 'PERCENT_DISCOUNT', NULL, %s)",
            (
                uuid.UUID("99990000-0000-4000-8000-000000000021"),
                _COMPANY_B,
                _DISCOUNT_B,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def pricing_seed(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    _seed(pg, migrated_domain_schema)
    yield
    conn = pg.connect_admin(autocommit=False)
    try:
        for company_id in (_COMPANY_A, _COMPANY_B):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute("DELETE FROM carts WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM company_price_rules WHERE company_id = %s", (company_id,))
        conn.execute("DELETE FROM products WHERE id = %s", (_PRODUCT,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def pricing_client(
    test_settings: Settings, pricing_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def _login(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    return str(response.json()["access_token"])


async def _search_price(client: httpx.AsyncClient, token: str | None) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.get(
        "/api/v1/search/products", params={"q": _SKU, "page_size": 100}, headers=headers
    )
    assert response.status_code == 200
    items = [item for item in response.json()["items"] if item["sku"] == _SKU]
    assert items, "produto de precificacao nao encontrado na busca"
    return cast(dict[str, object], items[0])


async def test_visitante_recebe_preco_consultivo(pricing_client: httpx.AsyncClient) -> None:
    item = await _search_price(pricing_client, None)
    assert item["price_on_request"] is True
    assert item["base_unit_price"] is None


async def test_empresa_com_preco_negociado(pricing_client: httpx.AsyncClient) -> None:
    token = await _login(pricing_client, _EMAIL_A)
    item = await _search_price(pricing_client, token)
    assert item["price_on_request"] is False
    assert Decimal(str(item["base_unit_price"])) == _NEGOTIATED_A


async def test_empresa_com_desconto_percentual(pricing_client: httpx.AsyncClient) -> None:
    token = await _login(pricing_client, _EMAIL_B)
    item = await _search_price(pricing_client, token)
    expected = (_BASE_PRICE * (Decimal("100") - _DISCOUNT_B) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    assert Decimal(str(item["base_unit_price"])) == expected


async def _catalog_detail(client: httpx.AsyncClient, token: str | None) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.get(f"/api/v1/catalog/products/{_PRODUCT}", headers=headers)
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


async def test_catalogo_visitante_recebe_preco_consultivo(
    pricing_client: httpx.AsyncClient,
) -> None:
    response = await pricing_client.get("/api/v1/catalog/products", params={"page_size": 100})
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["sku"] == _SKU for item in items)
    for item in items:
        assert item["price_on_request"] is True
        assert item["base_unit_price"] is None

    body = await _catalog_detail(pricing_client, None)
    assert body["price_on_request"] is True
    assert body["base_unit_price"] is None


async def test_catalogo_preco_por_empresa(pricing_client: httpx.AsyncClient) -> None:
    token_a = await _login(pricing_client, _EMAIL_A)
    body_a = await _catalog_detail(pricing_client, token_a)
    assert body_a["price_on_request"] is False
    assert Decimal(str(body_a["base_unit_price"])) == _NEGOTIATED_A

    token_b = await _login(pricing_client, _EMAIL_B)
    body_b = await _catalog_detail(pricing_client, token_b)
    expected_b = (_BASE_PRICE * (Decimal("100") - _DISCOUNT_B) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    assert Decimal(str(body_b["base_unit_price"])) == expected_b


async def test_carrinho_revalida_preco_por_empresa(pricing_client: httpx.AsyncClient) -> None:
    token = await _login(pricing_client, _EMAIL_A)
    response = await pricing_client.post(
        "/api/v1/cart/items",
        json={"product_id": str(_PRODUCT), "quantity": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert Decimal(item["unit_price"]) == _NEGOTIATED_A
    assert Decimal(item["line_total"]) == _NEGOTIATED_A * 2


async def test_imagem_resolvida_no_catalogo_busca_e_carrinho(
    pricing_client: httpx.AsyncClient,
) -> None:
    # Categoria sem ilustracao propria => placeholder generico.
    detail = await _catalog_detail(pricing_client, None)
    assert detail["image_url"] == "/static/catalog/generic.svg"
    assert detail["image_alt"] == "Produto Pricing Demo"

    item = await _search_price(pricing_client, None)
    assert item["image_url"] == "/static/catalog/generic.svg"
    assert item["image_alt"] == "Produto Pricing Demo"

    token = await _login(pricing_client, _EMAIL_A)
    response = await pricing_client.post(
        "/api/v1/cart/items",
        json={"product_id": str(_PRODUCT), "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    cart_item = response.json()["items"][0]
    assert cart_item["image_url"] == "/static/catalog/generic.svg"
    assert cart_item["image_alt"] == "Produto Pricing Demo"


def test_regras_de_preco_sao_isoladas_por_rls(pg: PostgresInstance, pricing_seed: None) -> None:
    # Empresa A enxerga apenas a propria regra.
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        rows = conn.execute(
            "SELECT rule_type, unit_price, percent FROM company_price_rules ORDER BY rule_type"
        ).fetchall()
        assert rows == [("FIXED_PRICE", _NEGOTIATED_A, None)]

        # Empresa B enxerga apenas a propria regra (nunca a de A).
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        rows_b = conn.execute(
            "SELECT rule_type, unit_price, percent FROM company_price_rules ORDER BY rule_type"
        ).fetchall()
        assert rows_b == [("PERCENT_DISCOUNT", None, _DISCOUNT_B)]
        conn.commit()
    finally:
        conn.close()

    # Sem contexto de tenant: nenhuma regra visivel (nem admin, FORCE RLS).
    conn = pg.connect_admin(autocommit=False)
    try:
        total = conn.execute("SELECT COUNT(*) FROM company_price_rules").fetchone()
        assert total is not None and total[0] == 0
        conn.commit()
    finally:
        conn.close()
