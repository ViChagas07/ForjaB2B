"""Integracao da busca lexical com fallback PostgreSQL real (Testcontainers).

Roda com `ELASTICSEARCH_ENABLED=False` (via `test_settings`), exercitando o
caminho de fallback do endpoint `/api/v1/search/products` sobre um PostgreSQL
real com as extensoes `unaccent`/`pg_trgm` e o indice `tsvector` da migration
0012. Reutiliza o catalogo dedicado de `test_catalog_api` (nao insere dados
novos, preservando as contagens exatas daquele modulo).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.application.security import AuthContext, TokenService
from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

from .conftest import PostgresInstance
from .test_catalog_api import _CAT_EPI, _P_EPI_VALIDO, _seed_catalog


@pytest.fixture()
def search_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed_catalog(pg, migrated_domain_schema)


@pytest.fixture()
async def search_client(
    test_settings: Settings, search_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_busca_texto_usa_fallback_postgres(search_client: httpx.AsyncClient) -> None:
    # O catalogo e global e compartilhado por outros modulos de integracao: o
    # teste NAO assume total exato, apenas o modo e a presenca do produto certo.
    response = await search_client.get(
        "/api/v1/search/products", params={"q": "parafusadeira", "page_size": 100}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["search_mode"] == "postgres_fallback"
    assert "FER-PAR-004" in {item["sku"] for item in body["items"]}


async def test_busca_nao_retorna_inativo_nem_epi_vencido(
    search_client: httpx.AsyncClient,
) -> None:
    # Idem: verifica SKUs especificos ausentes (inativo e EPI com CA vencido).
    for sku in ("FER-INA-005", "EPI-EXP-002"):
        response = await search_client.get(
            "/api/v1/search/products", params={"q": sku, "page_size": 100}
        )
        assert response.status_code == 200
        assert sku not in {item["sku"] for item in response.json()["items"]}


async def test_visitante_recebe_preco_consultivo(search_client: httpx.AsyncClient) -> None:
    response = await search_client.get("/api/v1/search/products", params={"q": "capacete"})
    item = response.json()["items"][0]
    assert item["price_on_request"] is True
    assert item["base_unit_price"] is None


async def test_autenticado_recebe_preco(
    search_client: httpx.AsyncClient, test_settings: Settings
) -> None:
    token = TokenService(
        secret_key=test_settings.secret_key,
        algorithm=test_settings.jwt_algorithm,
        expire_minutes=test_settings.access_token_expire_minutes,
    ).issue_access_token(
        AuthContext(
            user_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            role="BUYER",
            token_id="integration-token",  # noqa: S106 - id de token de teste
        )
    )
    response = await search_client.get(
        "/api/v1/search/products",
        params={"q": "capacete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    item = response.json()["items"][0]
    assert item["price_on_request"] is False
    assert item["base_unit_price"] is not None


async def test_filtro_categoria_exclui_nao_vendaveis(
    search_client: httpx.AsyncClient,
) -> None:
    response = await search_client.get(
        "/api/v1/search/products", params={"category_id": str(_CAT_EPI)}
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(_P_EPI_VALIDO)


async def test_autocomplete_minimo_dois_caracteres(search_client: httpx.AsyncClient) -> None:
    curto = await search_client.get("/api/v1/search/products/autocomplete", params={"q": "c"})
    assert curto.json()["items"] == []
    ok = await search_client.get("/api/v1/search/products/autocomplete", params={"q": "ca"})
    names = [item["name"] for item in ok.json()["items"]]
    assert "Capacete Teste" in names


async def test_validacao_de_paginacao_e_texto(search_client: httpx.AsyncClient) -> None:
    deep = await search_client.get("/api/v1/search/products", params={"page": 1000})
    assert deep.status_code == 400
    oversize = await search_client.get("/api/v1/search/products", params={"page_size": 101})
    assert oversize.status_code == 422
    long_query = await search_client.get("/api/v1/search/products", params={"q": "x" * 101})
    assert long_query.status_code == 422
