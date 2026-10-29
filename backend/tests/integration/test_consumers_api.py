"""Testes de API do cadastro de cliente consumidor (conta CPF).

Cobre: criacao atomica da conta pessoal (tenant + usuario + perfil +
consentimentos), login com o tipo PERSON, unicidade de e-mail/CPF e validacoes
de CPF/idade feitas no servidor.
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

_PASSWORD = "Senha@Forte123"


def _payload(
    *,
    email: str,
    cpf: str,
    full_name: str = "Cliente Teste",
    birth_date: str = "1990-01-01",
) -> dict[str, object]:
    return {
        "full_name": full_name,
        "email": email,
        "password": _PASSWORD,
        "cpf": cpf,
        "birth_date": birth_date,
        "postal_code": "01001000",
        "gender": "PREFIRO_NAO_INFORMAR",
        "consent": True,
    }


@pytest.fixture()
async def consumers_client(
    test_settings: Settings, migrated_domain_schema: None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_registro_consumidor_cria_conta_pessoal_e_permite_login(
    consumers_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    response = await consumers_client.post(
        "/api/v1/consumers",
        json=_payload(email="consumidor-a@teste.com", cpf="98765432100"),
    )
    assert response.status_code == 201
    body = response.json()
    company_id = uuid.UUID(body["company_id"])
    user_id = uuid.UUID(body["user_id"])

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (company_id, user_id))
        company = conn.execute(
            "SELECT account_type, cnpj, status, legal_name FROM companies WHERE id = %s",
            (company_id,),
        ).fetchone()
        user = conn.execute(
            "SELECT email, status FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        member = conn.execute(
            "SELECT role, status FROM company_members WHERE user_id = %s", (user_id,)
        ).fetchone()
        profile = conn.execute(
            "SELECT birth_date::text, gender, postal_code FROM consumer_profiles "
            "WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        consents = conn.execute(
            "SELECT purpose, action FROM consent_records WHERE user_id = %s ORDER BY purpose",
            (user_id,),
        ).fetchall()
        conn.commit()
    finally:
        conn.close()

    assert company == ("PERSON", None, "ACTIVE", "Cliente Teste")
    assert user == ("consumidor-a@teste.com", "ACTIVE")
    assert member == ("BUYER", "ACTIVE")
    assert profile == ("1990-01-01", "PREFIRO_NAO_INFORMAR", "01001000")
    assert consents == [("PRIVACY", "GRANTED"), ("TERMS", "GRANTED")]

    login = await consumers_client.post(
        "/api/v1/auth/login",
        json={
            "email": "consumidor-a@teste.com",
            "password": _PASSWORD,
            "account_type": "PERSON",
        },
    )
    assert login.status_code == 200
    login_body = login.json()
    assert login_body["user"]["account_type"] == "PERSON"
    assert login_body["user"]["role"] == "BUYER"


async def test_registro_consumidor_email_duplicado_409(
    consumers_client: httpx.AsyncClient,
) -> None:
    first = await consumers_client.post(
        "/api/v1/consumers",
        json=_payload(email="consumidor-b@teste.com", cpf="15935745682"),
    )
    assert first.status_code == 201

    second = await consumers_client.post(
        "/api/v1/consumers",
        json=_payload(email="consumidor-b@teste.com", cpf="85274196373"),
    )
    assert second.status_code == 409
    assert second.json()["type"] == "urn:forja:problem:email_already_exists"


async def test_registro_consumidor_cpf_invalido_400(
    consumers_client: httpx.AsyncClient,
) -> None:
    response = await consumers_client.post(
        "/api/v1/consumers",
        json=_payload(email="consumidor-c@teste.com", cpf="98765432101"),
    )
    assert response.status_code == 400
    assert response.json()["type"] == "urn:forja:problem:invalid_cpf"


async def test_registro_consumidor_menor_de_idade_400(
    consumers_client: httpx.AsyncClient,
) -> None:
    response = await consumers_client.post(
        "/api/v1/consumers",
        json=_payload(
            email="consumidor-d@teste.com",
            cpf="45678912364",
            birth_date="2015-01-01",
        ),
    )
    assert response.status_code == 400
    assert response.json()["type"] == "urn:forja:problem:invalid_birth_date"
