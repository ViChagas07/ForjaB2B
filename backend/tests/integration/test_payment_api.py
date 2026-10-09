"""Testes de API do fluxo de pagamento (PIX/CARD/BOLETO + webhook).

Cobre: desconto PIX calculado no backend, iniciacao idempotente, webhook com
assinatura HMAC, idempotencia de eventos (duplicados/fora de ordem), e
integracao transacional do boleto pago com fatura e ledger de credito.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("aaaa0000-0000-4000-8000-000000000001")
_BUYER = uuid.UUID("aaaa0000-0000-4000-8000-000000000002")
_MEMBER = uuid.UUID("aaaa0000-0000-4000-8000-000000000003")
_EMAIL = "payment@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("aaaa0000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("aaaa0000-0000-4000-8000-000000000011")

_WEBHOOK_SECRET = "dev_payment_webhook_secret_change_in_production"


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
            "VALUES (%s, '19999999000150', 'Payment Empresa', 'ACTIVE') "
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
        for table in (
            "payment_events",
            "payments",
            "invoices",
            "order_items",
            "orders",
            "credit_entries",
        ):
            conn.execute(f"DELETE FROM {table} WHERE company_id = %s", (_COMPANY,))
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Payment Categoria', 'payment-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg) VALUES (%s, %s, 'PAY-1', "
            "'Produto Pagamento', 'pay-1', 'ACTIVE', false, '10.00', 1, NULL) "
            "ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def payment_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def payment_client(
    test_settings: Settings, payment_seed: None
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


async def _create_order(client: httpx.AsyncClient, method: str, key: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_PRODUCT), "quantity": 1}],
            "payment_method": method,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


async def _initiate(
    client: httpx.AsyncClient, order_id: str, method: str, key: str
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/payments",
        json={"order_id": order_id, "method": method, "idempotency_key": key},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


async def _post_webhook(
    client: httpx.AsyncClient,
    *,
    provider_reference: str,
    event_id: str,
    event_type: str,
    secret: str = _WEBHOOK_SECRET,
) -> httpx.Response:
    payload = {
        "provider": "FAKE_PIX",
        "event_id": event_id,
        "event_type": event_type,
        "provider_reference": provider_reference,
        "company_id": str(_COMPANY),
    }
    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"content-type": "application/json", "X-Forja-Signature": signature},
    )


async def test_pix_pagamento_com_desconto(payment_client: httpx.AsyncClient) -> None:
    order = await _create_order(payment_client, "PIX", "pay-pix-1")
    assert order["total"] == "10.00"

    payment = await _initiate(payment_client, order["id"], "PIX", "pay-pix-init-1")
    assert payment["status"] == "PENDING"
    assert payment["discount_amount"] == "0.50"
    assert payment["amount"] == "9.50"
    assert payment["provider"] == "FAKE_PIX"
    assert payment["provider_reference"] == f"PIX-{order['id']}"


async def test_card_pagamento_sem_desconto(payment_client: httpx.AsyncClient) -> None:
    order = await _create_order(payment_client, "CARD", "pay-card-1")
    payment = await _initiate(payment_client, order["id"], "CARD", "pay-card-init-1")
    assert payment["discount_amount"] == "0.00"
    assert payment["amount"] == "10.00"
    assert payment["provider"] == "FAKE_CARD"


async def test_webhook_confirmacao_idempotente_e_fora_de_ordem(
    payment_client: httpx.AsyncClient,
) -> None:
    order = await _create_order(payment_client, "PIX", "pay-pix-2")
    payment = await _initiate(payment_client, order["id"], "PIX", "pay-pix-init-2")

    paid = await _post_webhook(
        payment_client,
        provider_reference=payment["provider_reference"],
        event_id="evt-1",
        event_type="payment.paid",
    )
    assert paid.status_code == 200
    assert paid.json()["outcome"] == "APPLIED"
    assert paid.json()["status"] == "PAID"

    duplicate = await _post_webhook(
        payment_client,
        provider_reference=payment["provider_reference"],
        event_id="evt-1",
        event_type="payment.paid",
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["outcome"] == "DUPLICATE"

    out_of_order = await _post_webhook(
        payment_client,
        provider_reference=payment["provider_reference"],
        event_id="evt-2",
        event_type="payment.failed",
    )
    assert out_of_order.status_code == 200
    assert out_of_order.json()["outcome"] == "REJECTED"
    assert out_of_order.json()["status"] == "PAID"


async def test_boleto_quita_fatura_e_reduz_credito(payment_client: httpx.AsyncClient) -> None:
    order = await _create_order(payment_client, "BOLETO", "pay-boleto-1")

    invoice = await payment_client.post(
        "/api/v1/invoices", json={"order_id": order["id"], "payment_terms": "NET_30"}
    )
    assert invoice.status_code == 201
    assert invoice.json()["status"] == "PENDING"

    payment = await _initiate(payment_client, order["id"], "BOLETO", "pay-boleto-init-1")
    assert payment["amount"] == "10.00"
    assert payment["invoice_id"] == invoice.json()["id"]

    paid = await _post_webhook(
        payment_client,
        provider_reference=payment["provider_reference"],
        event_id="evt-boleto-1",
        event_type="payment.paid",
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"

    after_invoice = await payment_client.get(f"/api/v1/invoices/{invoice.json()['id']}")
    assert after_invoice.json()["status"] == "PAID"
    assert after_invoice.json()["paid_at"] is not None

    account = await payment_client.get("/api/v1/credit/account")
    assert account.json()["used"] == "0.00"


async def test_webhook_assinatura_invalida_401(payment_client: httpx.AsyncClient) -> None:
    order = await _create_order(payment_client, "PIX", "pay-pix-3")
    payment = await _initiate(payment_client, order["id"], "PIX", "pay-pix-init-3")

    response = await _post_webhook(
        payment_client,
        provider_reference=payment["provider_reference"],
        event_id="evt-bad-sig",
        event_type="payment.paid",
        secret="wrong-secret",  # noqa: S106 - credencial dummy de teste
    )
    assert response.status_code == 401
    assert response.json()["type"] == "urn:forja:problem:invalid_webhook_signature"


async def test_webhook_pagamento_inexistente_404(payment_client: httpx.AsyncClient) -> None:
    response = await _post_webhook(
        payment_client,
        provider_reference="PIX-inexistente",
        event_id="evt-unknown",
        event_type="payment.paid",
    )
    assert response.status_code == 404
    assert response.json()["type"] == "urn:forja:problem:payment_not_found"
