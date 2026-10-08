"""Testes de API do contexto de empresas (onboarding + consulta + isolamento).

Cobre: registro (normalizacao de CNPJ, hash de senha/CPF), CNPJ duplicado
(409), CNPJ invalido (400) e isolamento por tenant em GET /companies/me.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

from .conftest import PostgresInstance

_CNPJ_A = "11222333000181"
_CNPJ_DUP = "23456789000195"
_CNPJ_TENANT_A = "34567890000130"
_CNPJ_TENANT_B = "45678900000120"
_PASSWORD = "Senha@Forte123"


def _payload(cnpj: str, email: str, legal_name: str, cpf: str = "529.982.247-25") -> dict[str, str]:
    return {
        "cnpj": cnpj,
        "legal_name": legal_name,
        "trade_name": legal_name,
        "admin_full_name": "Admin " + legal_name,
        "admin_email": email,
        "admin_cpf": cpf,
        "password": _PASSWORD,
    }


@pytest.fixture()
async def companies_client(
    test_settings: Settings, migrated_domain_schema: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


def _approve(pg: PostgresInstance, company_id: uuid.UUID, admin_user_id: uuid.UUID) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        conn.execute("UPDATE companies SET status = 'ACTIVE' WHERE id = %s", (company_id,))
        conn.execute("UPDATE users SET status = 'ACTIVE' WHERE id = %s", (admin_user_id,))
        conn.commit()
    finally:
        conn.close()


async def test_registro_empresa_normaliza_e_hash(
    companies_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    response = await companies_client.post(
        "/api/v1/companies", json=_payload("11.222.333/0001-81", "a@empresa-a.com", "Empresa A")
    )
    assert response.status_code == 201
    body = response.json()
    company_id = uuid.UUID(body["company"]["id"])
    admin_user_id = uuid.UUID(body["admin_user_id"])
    assert body["company"]["cnpj"] == _CNPJ_A
    assert body["company"]["status"] == "PENDING"

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        company = conn.execute(
            "SELECT cnpj, status FROM companies WHERE id = %s", (company_id,)
        ).fetchone()
        user = conn.execute(
            "SELECT password_hash, cpf_hash, status FROM users WHERE id = %s", (admin_user_id,)
        ).fetchone()
        conn.commit()
    finally:
        conn.close()

    assert company == (_CNPJ_A, "PENDING")
    assert user is not None
    password_hash, cpf_hash, user_status = user
    assert password_hash.startswith("$argon2id$")
    assert _PASSWORD not in password_hash
    assert cpf_hash != "52998224725"
    assert user_status == "PENDING_APPROVAL"


async def test_registro_cnpj_duplicado_409(companies_client: httpx.AsyncClient) -> None:
    first = await companies_client.post(
        "/api/v1/companies",
        json=_payload(_CNPJ_DUP, "dup@empresa-a.com", "Empresa A", "11144477735"),
    )
    assert first.status_code == 201

    second = await companies_client.post(
        "/api/v1/companies",
        json=_payload(_CNPJ_DUP, "dup2@empresa-a.com", "Empresa A", "31096288851"),
    )
    assert second.status_code == 409
    assert second.json()["type"] == "urn:forja:problem:company_already_exists"


async def test_registro_cnpj_invalido_400(companies_client: httpx.AsyncClient) -> None:
    response = await companies_client.post(
        "/api/v1/companies", json=_payload("11222333000182", "inv@empresa.com", "Invalida")
    )
    assert response.status_code == 400
    assert response.json()["type"] == "urn:forja:problem:invalid_cnpj"


async def test_empresa_me_isolada_por_tenant(
    companies_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    reg_a = await companies_client.post(
        "/api/v1/companies",
        json=_payload(_CNPJ_TENANT_A, "b@empresa-a.com", "Empresa A", "66677788899"),
    )
    reg_b = await companies_client.post(
        "/api/v1/companies",
        json=_payload(_CNPJ_TENANT_B, "b@empresa-b.com", "Empresa B", "77788899900"),
    )
    assert reg_a.status_code == 201 and reg_b.status_code == 201

    company_a = uuid.UUID(reg_a.json()["company"]["id"])
    admin_a = uuid.UUID(reg_a.json()["admin_user_id"])
    company_b = uuid.UUID(reg_b.json()["company"]["id"])
    admin_b = uuid.UUID(reg_b.json()["admin_user_id"])
    _approve(pg, company_a, admin_a)
    _approve(pg, company_b, admin_b)

    login = await companies_client.post(
        "/api/v1/auth/login", json={"email": "b@empresa-b.com", "password": _PASSWORD}
    )
    token = login.json()["access_token"]

    me = await companies_client.get(
        "/api/v1/companies/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert uuid.UUID(body["id"]) == company_b
    assert body["cnpj"] == _CNPJ_TENANT_B
    assert body["id"] != str(company_a)
