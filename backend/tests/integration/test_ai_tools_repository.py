"""Integracao das portas de IA no Postgres real (FASE 5b).

Prova que a hidratacao dos cartoes reusa a MESMA resolucao de preco do
SearchProducts (regra FIXED_PRICE da empresa logada; visitante sem preco),
alem de categorias e busca sanitizada via adapters da raiz de composicao.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

import pytest
from psycopg import Connection

from app.application.security import AuthContext
from app.modules.ai.application.product_cards import ProductCardService
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader
from app.wiring.ai_tools import SearchProductsToolAdapter
from tests.integration.helpers.ai_stub_search import StubSearchProducts

COMPANY = uuid.UUID("abcd0000-0000-4000-8000-00000000a001")
USER = uuid.UUID("abcd0000-0000-4000-8000-00000000a002")
CATEGORY = uuid.UUID("abcd0000-0000-4000-8000-00000000a003")
PRODUCT = uuid.UUID("abcd0000-0000-4000-8000-00000000a004")


@contextmanager
def db_tx(pg: object, company_id: uuid.UUID | None = None) -> Iterator[Connection]:
    conn = pg.connect_admin(autocommit=False)  # type: ignore[attr-defined]
    try:
        if company_id is not None:
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        yield conn
        conn.commit()
    finally:
        conn.close()


def seed(pg: object) -> None:
    with db_tx(pg, COMPANY) as conn:
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) VALUES "
            "(%s, '44444444000191', 'AI Cards', 'ACTIVE') ON CONFLICT DO NOTHING",
            (COMPANY,),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
            "VALUES (%s, %s, 'cards@test', 'Cards User', %s, 'ACTIVE') ON CONFLICT DO NOTHING",
            (USER, COMPANY, "0" * 64),
        )
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) VALUES (%s, 'EPI Cards', "
            "'epi-cards', true) ON CONFLICT DO NOTHING",
            (CATEGORY,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg, image_url) VALUES "
            "(%s, %s, 'CARD-001', 'Capacete Soldador', 'capacete-soldador', 'ACTIVE', false, "
            "'999.00', 1, 2.0, '/images/products/card-001.png') ON CONFLICT DO NOTHING",
            (PRODUCT, CATEGORY),
        )
        # Regra FIXED_PRICE (preco negociado) da empresa.
        conn.execute(
            "INSERT INTO company_price_rules (company_id, rule_type, product_id, unit_price) "
            "VALUES (%s, 'FIXED_PRICE', %s, '777.00') "
            "ON CONFLICT (company_id, product_id) WHERE rule_type = 'FIXED_PRICE' DO NOTHING",
            (COMPANY, PRODUCT),
        )


@pytest.fixture(autouse=True)
def _cleanup_after(pg: object, migrated_domain_schema: None) -> Iterator[None]:
    seed(pg)
    yield
    with db_tx(pg, COMPANY) as conn:
        conn.execute("DELETE FROM company_price_rules WHERE company_id = %s", (COMPANY,))
        conn.execute("DELETE FROM users WHERE company_id = %s", (COMPANY,))
    with db_tx(pg) as conn:
        conn.execute("DELETE FROM products WHERE id = %s", (PRODUCT,))
        conn.execute("DELETE FROM categories WHERE id = %s", (CATEGORY,))
    with db_tx(pg, COMPANY) as conn:
        conn.execute("DELETE FROM companies WHERE id = %s", (COMPANY,))


def adapter(uow_factory: object) -> SearchProductsToolAdapter:
    reader = SqlAlchemyProductReader(uow_factory)  # type: ignore[arg-type]
    return SearchProductsToolAdapter(
        search_products=StubSearchProducts(),  # type: ignore[arg-type]
        product_reader=reader,
        uow_factory=uow_factory,  # type: ignore[arg-type]
    )


async def test_visitante_hidrata_sem_preco_uow(uow_factory: object) -> None:
    hydrated = await adapter(uow_factory).hydrate(
        product_ids=[str(PRODUCT)], locale="pt-BR", auth=None
    )
    assert hydrated and hydrated[0].price == Decimal("999.00")
    # Cartao de visitante nunca expoe preco (regra aplicada em ProductCardService).
    service = ProductCardService(hydrator=adapter(uow_factory))
    cards = await service.build(
        requested_ids=[str(PRODUCT)], allowed_product_ids={str(PRODUCT)}, locale="pt-BR", auth=None
    )
    assert cards[0].price is None
    assert cards[0].price_on_request is True
    assert cards[0].link == f"/catalog/{PRODUCT}"


async def test_logado_recebe_preco_fixed_price_da_empresa(uow_factory: object) -> None:
    auth = AuthContext(company_id=COMPANY, user_id=USER, role="BUYER", token_id="test")
    service = ProductCardService(hydrator=adapter(uow_factory))
    cards = await service.build(
        requested_ids=[str(PRODUCT)],
        allowed_product_ids={str(PRODUCT)},
        locale="pt-BR",
        auth=auth,
    )
    assert cards[0].price == "777.00"  # FIXED_PRICE da propria empresa
    assert cards[0].price_on_request is False
    assert cards[0].ca_status
