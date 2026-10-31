"""API do perfil da conta: leitura, atualizaÃ§Ã£o e validaÃ§Ã£o."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("cccc0000-0000-4000-8000-00000000c001")
_USER = uuid.UUID("cccc0000-0000-4000-8000-00000000c002")
_MEMBER = uuid.UUID("cccc0000-0000-4000-8000-00000000c003")
_EMAIL = "account-api@test.local"
_PASSWORD = "Senha@Forte123"


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (_COMPANY, _USER))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '66555444000133', 'Conta Teste', 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (_COMPANY,),
        )
        password_hash = Argon2PasswordHasher().hash(_PASSWORD)
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, phone, cpf_hash, "
            "password_hash, status, postal_code, birth_date, gender) VALUES "
            "(%s, %s, %s, 'Conta Teste', '+55 11 99999-0000', %s, %s, 'ACTIVE', "
            "'01310100', '1990-01-01', 'PREFIRO_NAO_INFORMAR') "
            "ON CONFLICT DO NOTHING",
            (
                _USER,
                _COMPANY,
                _EMAIL,
                hashlib.sha256(_EMAIL.encode()).hexdigest(),
                password_hash,
            ),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT DO NOTHING",
            (_MEMBER, _COMPANY, _USER),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup(pg: PostgresInstance) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (_COMPANY, _USER))
        conn.execute("DELETE FROM company_members WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM users WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM companies WHERE id = %s", (_COMPANY,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def account_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def account_client(
    test_settings: Settings, account_seed: None, pg: PostgresInstance
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
            )
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            yield client
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)
        _cleanup(pg)


async def test_get_account(account_client: httpx.AsyncClient) -> None:
    response = await account_client.get("/api/v1/account")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == _EMAIL
    assert body["postal_code"] == "01310100"
    assert body["birth_date"] == "1990-01-01"
    assert body["display_currency"] == "BRL"


async def test_update_account(account_client: httpx.AsyncClient, pg: PostgresInstance) -> None:
    response = await account_client.patch(
        "/api/v1/account",
        json={
            "full_name": "  Novo Nome  ",
            "phone": "+55 11 98888-7777",
            "birth_date": "1992-05-10",
            "gender": "FEMININO",
            "postal_code": "01310-100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Novo Nome"
    assert body["postal_code"] == "01310100"
    assert body["gender"] == "FEMININO"

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (_COMPANY, _USER))
        row = conn.execute(
            "SELECT full_name, postal_code FROM users WHERE id = %s", (_USER,)
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    assert row is not None and row[0] == "Novo Nome" and row[1] == "01310100"


async def test_update_account_cep_invalido(
    account_client: httpx.AsyncClient,
) -> None:
    response = await account_client.patch(
        "/api/v1/account",
        json={"full_name": "Nome", "postal_code": "123"},
    )
    assert response.status_code == 422
    assert response.json()["type"] == "urn:forja:problem:invalid_account_profile"


async def test_update_account_preferences(
    account_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    response = await account_client.patch(
        "/api/v1/account/preferences",
        json={"display_currency": "USD"},
    )
    assert response.status_code == 200
    assert response.json()["display_currency"] == "USD"

    profile = await account_client.get("/api/v1/account")
    assert profile.status_code == 200
    assert profile.json()["display_currency"] == "USD"

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (_COMPANY, _USER))
        row = conn.execute(
            "SELECT display_currency FROM users WHERE id = %s", (_USER,)
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    assert row is not None and row[0] == "USD"


async def test_update_account_preferences_moeda_invalida(
    account_client: httpx.AsyncClient,
) -> None:
    response = await account_client.patch(
        "/api/v1/account/preferences",
        json={"display_currency": "CHF"},
    )
    assert response.status_code == 200
    assert response.json()["display_currency"] == "BRL"

    profile = await account_client.get("/api/v1/account")
    assert profile.json()["display_currency"] == "BRL"


async def test_update_account_preferences_string_especial_cai_em_brl(
    account_client: httpx.AsyncClient,
) -> None:
    response = await account_client.patch(
        "/api/v1/account/preferences",
        json={"display_currency": "' OR 1=1 --"},
    )
    assert response.status_code == 200
    assert response.json()["display_currency"] == "BRL"


async def test_update_account_preferences_valor_enorme_cai_em_brl(
    account_client: httpx.AsyncClient,
) -> None:
    response = await account_client.patch(
        "/api/v1/account/preferences",
        json={"display_currency": "USD" * 5_000},
    )
    assert response.status_code == 200
    assert response.json()["display_currency"] == "BRL"
