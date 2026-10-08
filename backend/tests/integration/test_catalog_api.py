"""Testes de API do catalogo global (listagem, filtros, paginacao, CA).

O catalogo e GLOBAL: as rotas sao publicas (sem auth/company_id) e somente
leitura. Usa dados de catalogo DEDICADOS (nao os seeds globais), inseridos sem
contexto de tenant, com datas de CA deterministicas (futuro/passado distantes)
para que as assercoes de validade nao dependam do relogio.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

from .conftest import PostgresInstance

_CAT_EPI = uuid.UUID("77777777-7777-4777-8777-777777777701")
_CAT_TOOLS = uuid.UUID("77777777-7777-4777-8777-777777777702")
_BRAND_A = uuid.UUID("77777777-7777-4777-8777-777777777703")
_BRAND_B = uuid.UUID("77777777-7777-4777-8777-777777777704")

_P_EPI_VALIDO = uuid.UUID("77777777-7777-4777-8777-777777777711")
_P_EPI_EXPIRADO = uuid.UUID("77777777-7777-4777-8777-777777777712")
_P_EPI_SEM_CA = uuid.UUID("77777777-7777-4777-8777-777777777713")
_P_NAO_EPI = uuid.UUID("77777777-7777-4777-8777-777777777714")
_P_INATIVO = uuid.UUID("77777777-7777-4777-8777-777777777715")

_FAR_FUTURE = date(2099, 12, 31)
_FAR_PAST = date(2000, 1, 1)


def _seed_catalog(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) VALUES "
            "(%s, 'EPIs Catalog', 'epis-catalog', true), "
            "(%s, 'Ferramentas Catalog', 'ferramentas-catalog', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT_EPI, _CAT_TOOLS),
        )
        conn.execute(
            "INSERT INTO brands (id, name, slug) VALUES "
            "(%s, 'Marca Alpha', 'marca-alpha'), (%s, 'Marca Beta', 'marca-beta') "
            "ON CONFLICT (id) DO NOTHING",
            (_BRAND_A, _BRAND_B),
        )
        products = [
            (
                _P_EPI_VALIDO,
                _CAT_EPI,
                _BRAND_A,
                "EPI-OK-001",
                "Capacete Teste",
                "ACTIVE",
                True,
                "CA-0001",
                _FAR_FUTURE,
                "24.90",
                1,
            ),
            (
                _P_EPI_EXPIRADO,
                _CAT_EPI,
                _BRAND_A,
                "EPI-EXP-002",
                "Respirador Vencido",
                "ACTIVE",
                True,
                "CA-0002",
                _FAR_PAST,
                "8.90",
                1,
            ),
            (
                _P_EPI_SEM_CA,
                _CAT_EPI,
                _BRAND_B,
                "EPI-NOCA-003",
                "Luva Sem CA",
                "ACTIVE",
                True,
                None,
                None,
                "12.50",
                1,
            ),
            (
                _P_NAO_EPI,
                _CAT_TOOLS,
                _BRAND_B,
                "FER-PAR-004",
                "Parafusadeira Teste",
                "ACTIVE",
                False,
                None,
                None,
                "899.00",
                1,
            ),
            (
                _P_INATIVO,
                _CAT_TOOLS,
                _BRAND_A,
                "FER-INA-005",
                "Produto Inativo",
                "INACTIVE",
                False,
                None,
                None,
                "10.00",
                1,
            ),
        ]
        for (
            product_id,
            category_id,
            brand_id,
            sku,
            name,
            status,
            is_epi,
            ca_number,
            ca_valid,
            price,
            min_qty,
        ) in products:
            conn.execute(
                "INSERT INTO products (id, category_id, brand_id, sku, name, slug, "
                "status, is_epi, ca_number, ca_valid_until, base_unit_price, min_order_qty) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (
                    product_id,
                    category_id,
                    brand_id,
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
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def catalog_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed_catalog(pg, migrated_domain_schema)


@pytest.fixture()
async def catalog_client(
    test_settings: Settings, catalog_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_listar_categorias(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/categories")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "EPIs Catalog" in names
    assert "Ferramentas Catalog" in names


async def test_listar_marcas(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/brands")
    assert response.status_code == 200
    names = [b["name"] for b in response.json()]
    assert "Marca Alpha" in names and "Marca Beta" in names


async def test_consultar_categoria_por_id(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/categories/{_CAT_EPI}")
    assert response.status_code == 200
    assert response.json()["slug"] == "epis-catalog"


async def test_categoria_inexistente_404(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(
        f"/api/v1/catalog/categories/{uuid.UUID('77777777-7777-4777-8777-777777777799')}"
    )
    assert response.status_code == 404
    assert response.json()["type"] == "urn:forja:problem:category_not_found"


async def test_consultar_marca_por_id(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/brands/{_BRAND_B}")
    assert response.status_code == 200
    assert response.json()["name"] == "Marca Beta"


async def test_marca_inexistente_404(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(
        f"/api/v1/catalog/brands/{uuid.UUID('77777777-7777-4777-8777-777777777799')}"
    )
    assert response.status_code == 404
    assert response.json()["type"] == "urn:forja:problem:brand_not_found"


async def test_listar_produtos_paginado(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/products", params={"page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["pages"] == 3
    assert len(body["items"]) == 2

    page3 = await catalog_client.get("/api/v1/catalog/products", params={"page": 3, "page_size": 2})
    assert page3.status_code == 200
    assert len(page3.json()["items"]) == 1


async def test_filtrar_por_categoria(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(
        "/api/v1/catalog/products", params={"category_id": str(_CAT_EPI)}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert all(item["category"]["id"] == str(_CAT_EPI) for item in body["items"])


async def test_filtrar_por_status_ativos(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/products", params={"status": "ACTIVE"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert all(item["status"] == "ACTIVE" for item in body["items"])


async def test_filtrar_por_is_epi(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/products", params={"is_epi": "true"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert all(item["is_epi"] is True for item in body["items"])


async def test_filtrar_por_busca(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get("/api/v1/catalog/products", params={"q": "parafusadeira"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sku"] == "FER-PAR-004"


async def test_ordenar_por_preco(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(
        "/api/v1/catalog/products",
        params={"status": "ACTIVE", "sort": "base_unit_price", "order": "asc"},
    )
    assert response.status_code == 200
    prices = [Decimal(item["base_unit_price"]) for item in response.json()["items"]]
    assert prices == sorted(prices)
    assert prices[0] == Decimal("8.90")  # EPI expirado e o mais barato


async def test_consultar_produto_com_ca_valido(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/products/{_P_EPI_VALIDO}")
    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "EPI-OK-001"
    assert body["is_epi"] is True
    assert body["ca_status"] == "VALID"
    assert body["ca_valid_until"] == _FAR_FUTURE.isoformat()
    assert body["category"]["id"] == str(_CAT_EPI)
    assert body["brand"]["id"] == str(_BRAND_A)


async def test_consultar_produto_ca_expirado(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/products/{_P_EPI_EXPIRADO}")
    assert response.status_code == 200
    assert response.json()["ca_status"] == "EXPIRED"


async def test_consultar_produto_epi_sem_ca(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/products/{_P_EPI_SEM_CA}")
    assert response.status_code == 200
    assert response.json()["ca_status"] == "MISSING"


async def test_consultar_produto_nao_epi(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/products/{_P_NAO_EPI}")
    assert response.status_code == 200
    body = response.json()
    assert body["is_epi"] is False
    assert body["ca_status"] == "NOT_APPLICABLE"


async def test_consultar_produto_inativo(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(f"/api/v1/catalog/products/{_P_INATIVO}")
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"


async def test_produto_inexistente_404(catalog_client: httpx.AsyncClient) -> None:
    response = await catalog_client.get(
        f"/api/v1/catalog/products/{uuid.UUID('77777777-7777-4777-8777-777777777799')}"
    )
    assert response.status_code == 404
    assert response.json()["type"] == "urn:forja:problem:product_not_found"


async def test_validacao_parametros(catalog_client: httpx.AsyncClient) -> None:
    # sort fora da whitelist -> 422
    assert (
        await catalog_client.get("/api/v1/catalog/products", params={"sort": "id;DROP"})
    ).status_code == 422
    # page_size acima do limite -> 422
    assert (
        await catalog_client.get("/api/v1/catalog/products", params={"page_size": 101})
    ).status_code == 422
    # status fora do enum -> 422
    assert (
        await catalog_client.get("/api/v1/catalog/products", params={"status": "BOGUS"})
    ).status_code == 422


async def test_catalogo_global_sem_company_id_sem_auth(catalog_client: httpx.AsyncClient) -> None:
    """Catalogo e global: acessivel sem header de autorizacao e sem company_id."""
    response = await catalog_client.get("/api/v1/catalog/products", params={"page_size": 100})
    assert response.status_code == 200
    assert response.json()["total"] == 5
