"""Testes de API do contexto de faturamento (boleto + captura de credito).

Usa empresa/usuarios/catalogo dedicados. Valida criacao de fatura, vinculo
order/invoice, termos 30/60, idempotencia, captura (net-zero), credito
insuficiente, dupla captura, isolamento entre tenants e PIX nao faturavel.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY_A = uuid.UUID("eeee0000-0000-4000-8000-000000000001")
_COMPANY_B = uuid.UUID("eeee0000-0000-4000-8000-000000000002")
_BUYER_A = uuid.UUID("eeee0000-0000-4000-8000-000000000003")
_BUYER_B = uuid.UUID("eeee0000-0000-4000-8000-000000000004")
_MEMBER_A = uuid.UUID("eeee0000-0000-4000-8000-000000000005")
_MEMBER_B = uuid.UUID("eeee0000-0000-4000-8000-000000000006")

_EMAIL_A = "invoice-a@teste.com"
_EMAIL_B = "invoice-b@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("eeee0000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("eeee0000-0000-4000-8000-000000000011")


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        for company_id, cnpj, name, buyer_id, email, member_id in (
            (_COMPANY_A, "19999999000121", "Invoice Empresa A", _BUYER_A, _EMAIL_A, _MEMBER_A),
            (_COMPANY_B, "19999999000122", "Invoice Empresa B", _BUYER_B, _EMAIL_B, _MEMBER_B),
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
            conn.execute("DELETE FROM invoices WHERE company_id = %s", (company_id,))
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
            "VALUES (%s, 'Invoice Categoria', 'invoice-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty) VALUES (%s, %s, 'INV-PROD', 'Produto Invoice', "
            "'inv-prod', 'ACTIVE', false, '24.90', 1) ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def invoice_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def invoice_client(
    test_settings: Settings, invoice_seed: None
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


async def test_criar_invoice_boleto_net30(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-bol-1")

    response = await invoice_client.post(
        "/api/v1/invoices", json={"order_id": order_id, "payment_terms": "NET_30"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["order_id"] == order_id
    assert body["amount"] == "149.40"
    assert body["status"] == "PENDING"
    assert body["payment_terms"] == "NET_30"
    assert body["number"] == f"INV-{order_id}"
    issued = datetime.fromisoformat(body["issued_at"])
    due = datetime.fromisoformat(body["due_at"])
    assert due - issued == timedelta(days=30)

    order = await invoice_client.get(f"/api/v1/orders/{order_id}")
    assert order.json()["status"] == "INVOICED"


async def test_invoice_net60(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-bol-60")
    response = await invoice_client.post(
        "/api/v1/invoices", json={"order_id": order_id, "payment_terms": "NET_60"}
    )
    assert response.status_code == 201
    issued = datetime.fromisoformat(response.json()["issued_at"])
    due = datetime.fromisoformat(response.json()["due_at"])
    assert due - issued == timedelta(days=60)


async def test_consulta_invoice_por_order(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-consulta")
    created = await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    invoice_id = created.json()["id"]

    by_order = await invoice_client.get(f"/api/v1/invoices/order/{order_id}")
    assert by_order.status_code == 200
    assert by_order.json()["id"] == invoice_id

    by_id = await invoice_client.get(f"/api/v1/invoices/{invoice_id}")
    assert by_id.status_code == 200
    assert by_id.json()["number"] == f"INV-{order_id}"


async def test_idempotencia_retry(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-idem")
    first = await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    second = await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_captura_credito_net_zero(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-captura")

    account_before = await invoice_client.get("/api/v1/credit/account")
    assert account_before.json()["used"] == "149.40"

    await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})

    account_after = await invoice_client.get("/api/v1/credit/account")
    assert account_after.json()["used"] == "149.40"

    entries = (await invoice_client.get("/api/v1/credit/entries")).json()
    captures = [e for e in entries if e["entry_type"] == "INVOICE_CAPTURE"]
    releases = [e for e in entries if e["entry_type"] == "RELEASE"]
    assert len(captures) == 1
    assert len(releases) == 1
    assert captures[0]["amount"] == "149.40"


async def test_dupla_captura_nao_duplica(invoice_client: httpx.AsyncClient) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-dupla")
    await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})

    entries = (await invoice_client.get("/api/v1/credit/entries")).json()
    captures = [e for e in entries if e["entry_type"] == "INVOICE_CAPTURE"]
    assert len(captures) == 1

    account = await invoice_client.get("/api/v1/credit/account")
    assert account.json()["used"] == "149.40"


async def test_pix_nao_faturavel(invoice_client: httpx.AsyncClient) -> None:
    response = await invoice_client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_PRODUCT), "quantity": 6}],
            "payment_method": "PIX",
            "idempotency_key": "inv-pix-1",
        },
    )
    order_id = response.json()["id"]

    invoice = await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    assert invoice.status_code == 409
    assert invoice.json()["type"] == "urn:forja:problem:order_not_invoiceable"


async def test_credito_insuficiente(
    invoice_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    order_id = await _create_boleto_order(invoice_client, "inv-insuf")

    # Libera parte da reserva diretamente, tornando a reserva < valor do pedido.
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        conn.execute(
            "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
            "reference_type, reference_id, idempotency_key) VALUES (%s, %s, 'RELEASE', '100.00', "
            "'order', %s, 'manual_release_invoice_test')",
            (_COMPANY_A, _COMPANY_A, uuid.UUID(order_id)),
        )
        conn.commit()
    finally:
        conn.close()

    response = await invoice_client.post("/api/v1/invoices", json={"order_id": order_id})
    assert response.status_code == 409
    assert response.json()["type"] == "urn:forja:problem:insufficient_credit"


async def test_isolamento_entre_empresas(test_settings: Settings, invoice_seed: None) -> None:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_a = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL_A, "password": _PASSWORD}
        )
        login_b = await client.post(
            "/api/v1/auth/login", json={"email": _EMAIL_B, "password": _PASSWORD}
        )

        client.headers["Authorization"] = f"Bearer {login_a.json()['access_token']}"
        created_order = await client.post(
            "/api/v1/orders",
            json={
                "items": [{"product_id": str(_PRODUCT), "quantity": 6}],
                "payment_method": "BOLETO",
                "idempotency_key": "inv-iso-1",
            },
        )
        order_id = created_order.json()["id"]
        created_invoice = await client.post("/api/v1/invoices", json={"order_id": order_id})
        invoice_id = created_invoice.json()["id"]

        client.headers["Authorization"] = f"Bearer {login_b.json()['access_token']}"
        by_id = await client.get(f"/api/v1/invoices/{invoice_id}")
        assert by_id.status_code == 404
        by_order = await client.get(f"/api/v1/invoices/order/{order_id}")
        assert by_order.status_code == 404

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)
