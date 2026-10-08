"""Testes de API de autenticacao (login/refresh/logout) e RBAC.

Usa PostgreSQL + Redis reais (Testcontainers) com dados de tenant DEDICADOS a
este arquivo (nao dependem dos seeds globais, evitando interferencia entre
testes). Cobre: login valido/invalido, usuario inexistente/inativo, hash
invalido, rotacao e revogacao de refresh, derivacao do contexto a partir do
token (nao do cliente) e autorizacao por papel.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import pytest
from fastapi import Depends

from app.application.security import AuthContext, require_role
from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.interface.deps import get_current_auth
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

AUTH_COMPANY_ID = uuid.UUID("99999999-9999-4999-8999-999999999901")
AUTH_ADMIN_USER_ID = uuid.UUID("99999999-9999-4999-8999-999999999902")
AUTH_BUYER_USER_ID = uuid.UUID("99999999-9999-4999-8999-999999999903")
AUTH_ADMIN_MEMBER_ID = uuid.UUID("99999999-9999-4999-8999-999999999904")
AUTH_BUYER_MEMBER_ID = uuid.UUID("99999999-9999-4999-8999-999999999905")
AUTH_SUSPENDED_USER_ID = uuid.UUID("99999999-9999-4999-8999-999999999906")
AUTH_BAD_HASH_USER_ID = uuid.UUID("99999999-9999-4999-8999-999999999907")
AUTH_SUSPENDED_MEMBER_ID = uuid.UUID("99999999-9999-4999-8999-999999999908")
AUTH_BAD_HASH_MEMBER_ID = uuid.UUID("99999999-9999-4999-8999-999999999909")

AUTH_ADMIN_EMAIL = "auth-admin@teste.com"
AUTH_BUYER_EMAIL = "auth-buyer@teste.com"
AUTH_SUSPENDED_EMAIL = "auth-suspenso@teste.com"
AUTH_BAD_HASH_EMAIL = "auth-badhash@teste.com"
AUTH_PASSWORD = "Senha@Forte123"
AUTH_CNPJ = "19999999000199"

_PROBLEM_JSON = "application/problem+json"


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture()
def auth_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    """Cria empresa + usuarios (ADMIN/BUYER) com senha conhecida, isolados."""
    hasher = Argon2PasswordHasher()
    admin_hash = hasher.hash(AUTH_PASSWORD)
    buyer_hash = hasher.hash(AUTH_PASSWORD)

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (AUTH_COMPANY_ID,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (AUTH_COMPANY_ID, AUTH_CNPJ, "Auth Empresa Ltda"),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, company_id, email, full_name, cpf_hash, password_hash, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                AUTH_ADMIN_USER_ID,
                AUTH_COMPANY_ID,
                AUTH_ADMIN_EMAIL,
                "Admin Auth",
                _cpf_hash(AUTH_ADMIN_EMAIL),
                admin_hash,
            ),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, company_id, email, full_name, cpf_hash, password_hash, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                AUTH_BUYER_USER_ID,
                AUTH_COMPANY_ID,
                AUTH_BUYER_EMAIL,
                "Buyer Auth",
                _cpf_hash(AUTH_BUYER_EMAIL),
                buyer_hash,
            ),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (AUTH_ADMIN_MEMBER_ID, AUTH_COMPANY_ID, AUTH_ADMIN_USER_ID),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (AUTH_BUYER_MEMBER_ID, AUTH_COMPANY_ID, AUTH_BUYER_USER_ID),
        )
        # Usuarios dedicados aos testes de estado mutavel (inativo / hash ruim)
        # para nao contaminar o BUYER usado pelos testes de RBAC.
        for user_id, email, full_name, member_id in (
            (
                AUTH_SUSPENDED_USER_ID,
                AUTH_SUSPENDED_EMAIL,
                "Suspenso Auth",
                AUTH_SUSPENDED_MEMBER_ID,
            ),
            (AUTH_BAD_HASH_USER_ID, AUTH_BAD_HASH_EMAIL, "BadHash Auth", AUTH_BAD_HASH_MEMBER_ID),
        ):
            conn.execute(
                "INSERT INTO users "
                "(id, company_id, email, full_name, cpf_hash, password_hash, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (user_id, AUTH_COMPANY_ID, email, full_name, _cpf_hash(email), buyer_hash),
            )
            conn.execute(
                "INSERT INTO company_members (id, company_id, user_id, role, status) "
                "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (member_id, AUTH_COMPANY_ID, user_id),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def auth_client(test_settings: Settings, auth_seed: None) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def _login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def test_login_sucesso_retorna_tokens_e_perfil(auth_client: httpx.AsyncClient) -> None:
    response = await _login(auth_client, AUTH_ADMIN_EMAIL, AUTH_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0
    assert body["user"]["role"] == "ADMIN"
    assert body["user"]["email"] == AUTH_ADMIN_EMAIL
    assert body["user"]["id"] == str(AUTH_ADMIN_USER_ID)


async def test_login_senha_incorreta_401(auth_client: httpx.AsyncClient) -> None:
    response = await _login(auth_client, AUTH_ADMIN_EMAIL, "Senha@Errada000")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(_PROBLEM_JSON)
    assert response.json()["type"] == "urn:forja:problem:invalid_credentials"


async def test_login_usuario_inexistente_401(auth_client: httpx.AsyncClient) -> None:
    response = await _login(auth_client, "ninguem@teste.com", "Qualquer@123")
    assert response.status_code == 401
    assert response.json()["type"] == "urn:forja:problem:invalid_credentials"


async def test_login_usuario_inativo_403(
    auth_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (AUTH_COMPANY_ID,))
        conn.execute(
            "UPDATE users SET status = 'SUSPENDED' WHERE id = %s", (AUTH_SUSPENDED_USER_ID,)
        )
        conn.commit()
    finally:
        conn.close()

    response = await _login(auth_client, AUTH_SUSPENDED_EMAIL, AUTH_PASSWORD)
    assert response.status_code == 403
    assert response.json()["type"] == "urn:forja:problem:user_inactive"


async def test_login_hash_invalido_401(
    auth_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (AUTH_COMPANY_ID,))
        conn.execute(
            "UPDATE users SET password_hash = 'hash-malformado' WHERE id = %s",
            (AUTH_BAD_HASH_USER_ID,),
        )
        conn.commit()
    finally:
        conn.close()

    response = await _login(auth_client, AUTH_BAD_HASH_EMAIL, AUTH_PASSWORD)
    assert response.status_code == 401
    assert response.json()["type"] == "urn:forja:problem:invalid_credentials"


async def test_refresh_rotaciona_e_invalida_anterior(auth_client: httpx.AsyncClient) -> None:
    login = await _login(auth_client, AUTH_ADMIN_EMAIL, AUTH_PASSWORD)
    old_refresh = login.json()["refresh_token"]

    refresh = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh.status_code == 200
    new_refresh = refresh.json()["refresh_token"]
    assert new_refresh != old_refresh
    assert refresh.json()["access_token"]

    # Reuso do token antigo deve ser rejeitado (rotacao).
    replay = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_logout_revoga_refresh(auth_client: httpx.AsyncClient) -> None:
    login = await _login(auth_client, AUTH_ADMIN_EMAIL, AUTH_PASSWORD)
    refresh_token = login.json()["refresh_token"]

    logout = await auth_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    after = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert after.status_code == 401


async def test_contexto_deriva_do_token_nao_do_cliente(
    test_settings: Settings, auth_seed: None
) -> None:
    """O company_id/role expostos saem do token assinado, nunca do request."""
    app = create_app(test_settings)

    @app.get("/__whoami", include_in_schema=False)
    async def whoami(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> dict[str, str]:
        return {"user_id": str(auth.user_id), "company_id": str(auth.company_id), "role": auth.role}

    @app.get("/__admin-only", include_in_schema=False)
    async def admin_only(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> dict[str, str]:
        require_role(auth, "ADMIN")
        return {"ok": "true"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await _login(client, AUTH_ADMIN_EMAIL, AUTH_PASSWORD)
        token = login.json()["access_token"]

        # O header tenta indicar outra empresa; o backend ignora e usa o token.
        whoami_resp = await client.get(
            "/__whoami",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Company-Id": "11111111-1111-1111-1111-111111111111",
            },
        )
        assert whoami_resp.status_code == 200
        assert whoami_resp.json()["company_id"] == str(AUTH_COMPANY_ID)
        assert whoami_resp.json()["user_id"] == str(AUTH_ADMIN_USER_ID)
        assert whoami_resp.json()["role"] == "ADMIN"

        admin_only_resp = await client.get(
            "/__admin-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert admin_only_resp.status_code == 200

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_rbac_role_insuficiente_403(test_settings: Settings, auth_seed: None) -> None:
    app = create_app(test_settings)

    @app.get("/__admin-only", include_in_schema=False)
    async def admin_only(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> dict[str, str]:
        require_role(auth, "ADMIN")
        return {"ok": "true"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await _login(client, AUTH_BUYER_EMAIL, AUTH_PASSWORD)
        token = login.json()["access_token"]

        response = await client.get("/__admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["type"] == "urn:forja:problem:forbidden"

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_token_invalido_rejeitado_401(test_settings: Settings, auth_seed: None) -> None:
    app = create_app(test_settings)

    @app.get("/__whoami", include_in_schema=False)
    async def whoami(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> dict[str, str]:
        return {"user_id": str(auth.user_id)}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/__whoami", headers={"Authorization": "Bearer token-forjado"})
        assert response.status_code == 401

    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)
