"""Testes de consistencia financeira da captura de invoice (ledger de credito).

Provam os invariantes do ledger: exposicao preservada na conversao
RESERVE -> (RELEASE + INVOICE_CAPTURE), atomicidade (rollback) e serializacao
entre cancelamento e captura concorrentes.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.main import create_app
from app.modules.credit.infrastructure.repository import SqlAlchemyCreditRepository
from app.modules.identity.infrastructure.password import Argon2PasswordHasher
from app.modules.invoicing.application.errors import OrderNotInvoiceableError
from app.modules.invoicing.domain.enums import InvoiceTerms
from app.modules.invoicing.infrastructure.repository import SqlAlchemyInvoicingRepository
from app.modules.ordering.application.errors import InvalidOrderStateError
from app.modules.ordering.infrastructure.repository import SqlAlchemyOrderingRepository

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("dddd1000-0000-4000-8000-000000000001")
_BUYER = uuid.UUID("dddd1000-0000-4000-8000-000000000002")
_MEMBER = uuid.UUID("dddd1000-0000-4000-8000-000000000003")
_EMAIL = "capture@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")
_CAT = uuid.UUID("dddd1000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("dddd1000-0000-4000-8000-000000000011")


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
            "VALUES (%s, '19999999000141', 'Capture Empresa', 'ACTIVE') "
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
        conn.execute("DELETE FROM invoices WHERE company_id = %s", (_COMPANY,))
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
            "VALUES (%s, 'Capture Categoria', 'capture-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty) VALUES (%s, %s, 'CAP-PROD', 'Produto Capture', "
            "'cap-prod', 'ACTIVE', false, '24.90', 1) ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def capture_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def capture_client(
    test_settings: Settings, capture_seed: None
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


@pytest.fixture()
async def concurrent_factory(app_database_url: str) -> AsyncIterator[SqlAlchemyUnitOfWorkFactory]:
    engine = create_async_engine(app_database_url, pool_size=4, max_overflow=0)
    try:
        yield SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    finally:
        await engine.dispose()


async def _create_boleto_order(client: httpx.AsyncClient, idempotency_key: str) -> str:
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_PRODUCT), "quantity": 6}],
            "payment_method": "BOLETO",
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_exposicao_e_disponivel_no_ciclo_reserva_captura(
    capture_client: httpx.AsyncClient,
) -> None:
    # Antes da reserva: exposicao zero, disponivel = limite.
    before = await capture_client.get("/api/v1/credit/account")
    assert Decimal(before.json()["used"]) == Decimal("0.00")
    assert Decimal(before.json()["available"]) == Decimal("1000.00")

    # Reserva (pedido boleto).
    order_id = await _create_boleto_order(capture_client, "cap-ciclo-1")
    after_reserve = await capture_client.get("/api/v1/credit/account")
    assert Decimal(after_reserve.json()["used"]) == Decimal("149.40")
    assert Decimal(after_reserve.json()["available"]) == Decimal("850.60")

    # Captura (faturamento): exposicao preservada (conversao net-zero).
    await capture_client.post(
        "/api/v1/invoices", json={"order_id": order_id, "payment_terms": "NET_30"}
    )
    after_capture = await capture_client.get("/api/v1/credit/account")
    assert Decimal(after_capture.json()["used"]) == Decimal("149.40")
    assert Decimal(after_capture.json()["available"]) == Decimal("850.60")

    entries = (await capture_client.get("/api/v1/credit/entries")).json()
    types = [e["entry_type"] for e in entries]
    assert types.count("RESERVE") == 1
    assert types.count("RELEASE") == 1
    assert types.count("INVOICE_CAPTURE") == 1


async def test_rollback_apos_falha_intermediaria(
    capture_client: httpx.AsyncClient,
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    pg: PostgresInstance,
) -> None:
    order_id = uuid.UUID(await _create_boleto_order(capture_client, "cap-rollback-1"))

    # Forca falha no meio da captura: pre-ocupa a idempotency_key do
    # INVOICE_CAPTURE para violar a constraint unica apos o RELEASE.
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        conn.execute(
            "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
            "reference_type, reference_id, idempotency_key) VALUES (%s, %s, 'ADJUSTMENT', "
            "'1.00', 'test', NULL, %s)",
            (_COMPANY, _COMPANY, f"invoice_capture:{order_id}"),
        )
        conn.commit()
    finally:
        conn.close()

    repo = SqlAlchemyInvoicingRepository(uow_factory)
    with pytest.raises(IntegrityError):
        await repo.create_invoice(
            company_id=_COMPANY,
            order_id=order_id,
            amount=Decimal("149.40"),
            terms=InvoiceTerms.NET_30,
            issued_at=datetime.now(UTC),
        )

    # Nada parcial: pedido segue RECEIVED, sem fatura e sem RELEASE/CAPTURE.
    order = await capture_client.get(f"/api/v1/orders/{order_id}")
    assert order.json()["status"] == "RECEIVED"
    by_order = await capture_client.get(f"/api/v1/invoices/order/{order_id}")
    assert by_order.status_code == 404

    entries = (await capture_client.get("/api/v1/credit/entries")).json()
    assert [e["entry_type"] for e in entries].count("RELEASE") == 0
    assert [e["entry_type"] for e in entries].count("INVOICE_CAPTURE") == 0


async def test_cancelamento_e_captura_concorrentes_consistentes(
    concurrent_factory: SqlAlchemyUnitOfWorkFactory,
    capture_client: httpx.AsyncClient,
) -> None:
    order_id = uuid.UUID(await _create_boleto_order(capture_client, "cap-conc-1"))

    ordering_repo = SqlAlchemyOrderingRepository(concurrent_factory)
    invoicing_repo = SqlAlchemyInvoicingRepository(concurrent_factory)
    credit_repo = SqlAlchemyCreditRepository(concurrent_factory)

    async def cancel() -> str:
        try:
            await ordering_repo.cancel_order(_COMPANY, order_id)
            return "cancelled"
        except (InvalidOrderStateError, OrderNotInvoiceableError):
            return "conflict"

    async def capture() -> str:
        try:
            await invoicing_repo.create_invoice(
                company_id=_COMPANY,
                order_id=order_id,
                amount=Decimal("149.40"),
                terms=InvoiceTerms.NET_30,
                issued_at=datetime.now(UTC),
            )
            return "captured"
        except OrderNotInvoiceableError:
            return "conflict"

    results = await asyncio.gather(cancel(), capture())
    # Exatamente uma operacao vence; a outra e rejeitada.
    assert results.count("conflict") == 1

    view = await credit_repo.get_account(_COMPANY)
    assert view is not None
    # Exposicao nunca negativa e consistente com o resultado.
    assert view.used in (Decimal("0.00"), Decimal("149.40"))

    entries = await credit_repo.list_entries(_COMPANY)
    captures = [e for e in entries if e.entry_type == "INVOICE_CAPTURE"]
    assert len(captures) <= 1
