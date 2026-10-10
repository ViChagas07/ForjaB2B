"""Integracao da imagem de produto (Fase 9A-2): resolucao nos endpoints.

Dados DEDICADOS, inseridos sem contexto de tenant (catalogo global). Valida a
precedencia produto > categoria > generico e o texto alternativo nas respostas
do catalogo e da busca. O produto com `image_url` preenchido cobre o caso de
foto real (Fase 9A-3).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

from .conftest import PostgresInstance

_CAT_KNOWN = uuid.UUID("aaaa1111-0000-4000-8000-000000000010")
_CAT_UNKNOWN = uuid.UUID("aaaa1111-0000-4000-8000-000000000011")

_P_KNOWN_CAT = uuid.UUID("aaaa1111-0000-4000-8000-000000000011")
_P_WITH_IMAGE = uuid.UUID("aaaa1111-0000-4000-8000-000000000012")
_P_UNKNOWN_CAT = uuid.UUID("aaaa1111-0000-4000-8000-000000000013")

_SKU_KNOWN = "IMG-KNOWN-001"
_SKU_WITH_IMAGE = "IMG-PHOTO-002"
_SKU_UNKNOWN = "IMG-UNKNOWN-003"
_IMAGE_URL = "https://cdn.example.com/produto-foto.jpg"

_KNOWN_PATH = "/static/catalog/protecao-cabeca.svg"
_GENERIC_PATH = "/static/catalog/generic.svg"


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) VALUES "
            "(%s, 'Protecao da Cabeca IMG', 'protecao-cabeca', true), "
            "(%s, 'Categoria Sem Ilustracao', 'categoria-sem-ilustracao', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT_KNOWN, _CAT_UNKNOWN),
        )
        products = [
            (_P_KNOWN_CAT, _CAT_KNOWN, _SKU_KNOWN, "Capacete Demo Imagem", None),
            (_P_WITH_IMAGE, _CAT_UNKNOWN, _SKU_WITH_IMAGE, "Foto Real Demo", _IMAGE_URL),
            (_P_UNKNOWN_CAT, _CAT_UNKNOWN, _SKU_UNKNOWN, "Produto Sem Mapa", None),
        ]
        for product_id, category_id, sku, name, image_url in products:
            conn.execute(
                "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
                "base_unit_price, min_order_qty, image_url) "
                "VALUES (%s, %s, %s, %s, %s, 'ACTIVE', false, '10.00', 1, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (product_id, category_id, sku, name, sku.lower(), image_url),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def image_seed(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    _seed(pg, migrated_domain_schema)
    yield
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "DELETE FROM products WHERE id IN (%s, %s, %s)",
            (_P_KNOWN_CAT, _P_WITH_IMAGE, _P_UNKNOWN_CAT),
        )
        conn.execute("DELETE FROM categories WHERE id IN (%s, %s)", (_CAT_KNOWN, _CAT_UNKNOWN))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def image_client(
    test_settings: Settings, image_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_detalhe_usa_imagem_da_categoria(image_client: httpx.AsyncClient) -> None:
    response = await image_client.get(f"/api/v1/catalog/products/{_P_KNOWN_CAT}")
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == _KNOWN_PATH
    assert body["image_alt"] == "Capacete Demo Imagem"


async def test_detalhe_usa_imagem_do_produto_quando_presente(
    image_client: httpx.AsyncClient,
) -> None:
    response = await image_client.get(f"/api/v1/catalog/products/{_P_WITH_IMAGE}")
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == _IMAGE_URL
    assert body["image_alt"] == "Foto Real Demo"


async def test_detalhe_usa_placeholder_quando_categoria_sem_mapa(
    image_client: httpx.AsyncClient,
) -> None:
    response = await image_client.get(f"/api/v1/catalog/products/{_P_UNKNOWN_CAT}")
    assert response.status_code == 200
    assert response.json()["image_url"] == _GENERIC_PATH


async def test_lista_e_busca_carregam_imagem(image_client: httpx.AsyncClient) -> None:
    listing = await image_client.get("/api/v1/catalog/products", params={"page_size": 100})
    assert listing.status_code == 200
    for item in listing.json()["items"]:
        assert item["image_url"]
        assert item["image_alt"]

    search = await image_client.get("/api/v1/search/products", params={"q": _SKU_KNOWN})
    assert search.status_code == 200
    items = [i for i in search.json()["items"] if i["sku"] == _SKU_KNOWN]
    assert items
    assert items[0]["image_url"] == _KNOWN_PATH
    assert items[0]["image_alt"] == "Capacete Demo Imagem"
