"""Testes de integracao de privacidade (LGPD): exportacao, retificacao,
exclusao/anonimizacao e consentimento versionado.

Usa PostgreSQL real (Testcontainers). Valida isolamento por tenant/titular,
preservacao de registros financeiros na exclusao e trilha de auditoria.
"""

from __future__ import annotations

import hashlib
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

_COMPANY = uuid.UUID("cccc0000-0000-4000-8000-000000000001")
_BUYER = uuid.UUID("cccc0000-0000-4000-8000-000000000002")
_OTHER = uuid.UUID("cccc0000-0000-4000-8000-000000000003")
_BUYER_MEMBER = uuid.UUID("cccc0000-0000-4000-8000-000000000004")
_OTHER_MEMBER = uuid.UUID("cccc0000-0000-4000-8000-000000000005")
_BUYER_EMAIL = "privacy-buyer@teste.com"
_OTHER_EMAIL = "privacy-other@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("cccc0000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("cccc0000-0000-4000-8000-000000000011")


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
            "VALUES (%s, '19999999000170', 'Privacy Empresa', 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING",
            (_COMPANY,),
        )
        conn.execute(
            "INSERT INTO credit_accounts (company_id, credit_limit) "
            "VALUES (%s, %s) ON CONFLICT (company_id) DO NOTHING",
            (_COMPANY, _LIMIT),
        )
        for user_id, email, full_name in (
            (_BUYER, _BUYER_EMAIL, "Buyer Privacy"),
            (_OTHER, _OTHER_EMAIL, "Other Privacy"),
        ):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, password_hash, "
                "status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (user_id, _COMPANY, email, full_name, _cpf_hash(email), password_hash),
            )
            conn.execute(
                "UPDATE users SET email = %s, full_name = %s, phone = NULL, status = 'ACTIVE' "
                "WHERE id = %s",
                (email, full_name, user_id),
            )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_BUYER_MEMBER, _COMPANY, _BUYER),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_OTHER_MEMBER, _COMPANY, _OTHER),
        )
        for table in (
            "consent_records",
            "audit_log",
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
            "VALUES (%s, 'Privacy Categoria', 'privacy-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg) VALUES (%s, %s, 'PRIV-1', "
            "'Produto Privacy', 'priv-1', 'ACTIVE', false, '10.00', 1, NULL) "
            "ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def privacy_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def privacy_client(
    test_settings: Settings, privacy_seed: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": _BUYER_EMAIL, "password": _PASSWORD}
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_export_retorna_dados_do_titular(privacy_client: httpx.AsyncClient) -> None:
    response = await privacy_client.get("/api/v1/privacy/export")
    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    assert body["email"] == _BUYER_EMAIL
    assert body["full_name"] == "Buyer Privacy"
    assert body["user_id"] == str(_BUYER)
    assert body["consents"] == []


async def test_retificacao_atualiza_nome_e_telefone(privacy_client: httpx.AsyncClient) -> None:
    response = await privacy_client.patch(
        "/api/v1/privacy/me", json={"full_name": "Novo Nome", "phone": "11999999999"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Novo Nome"
    assert response.json()["phone"] == "11999999999"


async def test_consentimento_versionado(privacy_client: httpx.AsyncClient) -> None:
    record = await privacy_client.post(
        "/api/v1/privacy/consent",
        json={
            "purpose": "TERMS",
            "action": "GRANTED",
            "version": "2026-10-01",
            "document_hash": "a" * 64,
        },
    )
    assert record.status_code == 204

    state = await privacy_client.get("/api/v1/privacy/consent")
    assert state.status_code == 200
    body = state.json()
    assert body[0]["purpose"] == "TERMS"
    assert body[0]["action"] == "GRANTED"
    assert body[0]["version"] == "2026-10-01"


async def test_exclusao_anonimiza_e_preserva_registros(
    privacy_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    order = await privacy_client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_PRODUCT), "quantity": 1}],
            "payment_method": "PIX",
            "idempotency_key": "privacy-order-1",
        },
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    deleted = await privacy_client.delete("/api/v1/privacy/me")
    assert deleted.status_code == 204

    # Verifica anonimizacao + preservacao do pedido via conexao admin.
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        row = conn.execute(
            "SELECT email, full_name, phone, status FROM users WHERE id = %s", (_BUYER,)
        ).fetchone()
        assert row is not None
        assert row[0] == f"deleted+{_BUYER}@anonymized.forja.local"
        assert row[1] == "Usuario Removido"
        assert row[2] is None
        assert row[3] == "SUSPENDED"

        order_row = conn.execute("SELECT id FROM orders WHERE id = %s", (order_id,)).fetchone()
        assert order_row is not None

        audit = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE actor_user_id = %s "
            "AND action = 'personal_data.delete'",
            (_BUYER,),
        ).fetchone()
        assert audit is not None
        assert audit[0] >= 1
        conn.commit()
    finally:
        conn.close()


async def test_export_nao_vaza_dados_de_outro_titular(
    privacy_client: httpx.AsyncClient,
) -> None:
    response = await privacy_client.get("/api/v1/privacy/export")
    body = cast(dict[str, Any], response.json())
    assert body["email"] == _BUYER_EMAIL
    assert body["email"] != _OTHER_EMAIL
