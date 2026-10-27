"""Integracao HTTP do suggest com fallback PostgreSQL real (Testcontainers).

Roda com ``ELASTICSEARCH_ENABLED=False`` (via ``test_settings``), exercitando o
caminho de fallback do endpoint ``/api/v1/search/suggest`` sobre um PostgreSQL
real com `unaccent`/`pg_trgm`. Reutiliza o catalogo dedicado de
``test_catalog_api`` (nao insere dados novos). A tolerancia a typo (fuzziness)
e do Elasticsearch e e coberta em ``test_search_index_es`` (ES real).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest

from app.application.security import AuthContext, TokenService
from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

from .conftest import PostgresInstance
from .test_catalog_api import _seed_catalog


@pytest.fixture()
def suggest_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed_catalog(pg, migrated_domain_schema)


@pytest.fixture()
async def suggest_client(
    test_settings: Settings, suggest_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_suggest_minimo_de_dois_caracteres(
    suggest_client: httpx.AsyncClient,
) -> None:
    curto = await suggest_client.get("/api/v1/search/suggest", params={"q": "a"})
    assert curto.status_code == 200
    body = curto.json()
    assert body["terms"] == []
    assert body["categories"] == []
    assert body["products"] == []
    assert body["query"] == "a"
    ok = await suggest_client.get("/api/v1/search/suggest", params={"q": "cap"})
    assert ok.status_code == 200
    body = ok.json()
    assert any(
        term["text"] == "Capacete Teste" and term["kind"] == "product" for term in body["terms"]
    )
    # O catalogo e global e compartilhado por outros modulos de integracao:
    # nao assume total exato, apenas a presenca da categoria do seed.
    assert "epis-catalog" in {category["slug"] for category in body["categories"]}
    assert all({"name", "slug", "count"} == set(category) for category in body["categories"])


async def test_suggest_anonimo_recebe_preco_de_lista(
    suggest_client: httpx.AsyncClient,
) -> None:
    response = await suggest_client.get("/api/v1/search/suggest", params={"q": "cap"})
    body = response.json()
    assert body["products"]
    products = {product["sku"]: product for product in body["products"]}
    product = products["EPI-OK-001"]
    assert product["price_on_request"] is False
    assert Decimal(str(product["base_unit_price"])) == Decimal("24.90")
    assert product["image_url"]
    assert product["min_order_qty"] >= 1


async def test_suggest_autenticado_recebe_preco(
    suggest_client: httpx.AsyncClient, test_settings: Settings
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
    response = await suggest_client.get(
        "/api/v1/search/suggest",
        params={"q": "cap"},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()
    assert body["products"]
    assert body["products"][0]["base_unit_price"] is not None


async def test_suggest_respeita_locale(
    suggest_client: httpx.AsyncClient,
) -> None:
    response = await suggest_client.get("/api/v1/search/suggest", params={"q": "cap", "lang": "en"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "cap"
    # O seed de teste nao tem traducao para en: nome original (fallback) e
    # mantido; o importante e o contrato aceitar locale sem erro.
    assert body["terms"]


async def test_suggest_fallback_nao_tem_fuzzy_mas_nao_falha(
    suggest_client: httpx.AsyncClient,
) -> None:
    # Typo ("capacte") so e tolerado pelo Elasticsearch (fuzziness). No
    # fallback PostgreSQL a resposta e vazia e SEM erro 500.
    response = await suggest_client.get("/api/v1/search/suggest", params={"q": "capacte"})
    assert response.status_code == 200
    body = response.json()
    assert body["terms"] == []
    assert body["categories"] == []
    assert body["products"] == []


async def test_suggest_exclui_inativo_e_epi_vencido(
    suggest_client: httpx.AsyncClient,
) -> None:
    # O catalogo e global: em vez de assumir resultado exato, verifica que os
    # SKUs especificos (inativo e EPI com CA vencido) nunca aparecem.
    for query in ("produto", "respirador", "cap"):
        response = await suggest_client.get("/api/v1/search/suggest", params={"q": query})
        assert response.status_code == 200
        body = response.json()
        skus = {product["sku"] for product in body["products"]}
        assert "FER-INA-005" not in skus
        assert "EPI-EXP-002" not in skus
        assert "EPI-NOCA-003" not in skus
        texts = {term["text"] for term in body["terms"]}
        assert "Produto Inativo" not in texts
        assert "Respirador Vencido" not in texts


async def test_suggest_valida_tamanho_do_texto(
    suggest_client: httpx.AsyncClient,
) -> None:
    long_query = await suggest_client.get("/api/v1/search/suggest", params={"q": "x" * 101})
    assert long_query.status_code == 422
