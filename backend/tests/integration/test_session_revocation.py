"""Integracao da revogacao de sessoes apos reset de senha (HTTP + RLS + Redis)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI

from app.application.security import TokenService
from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.infrastructure.security.credential_epoch import CredentialEpochSessionRevoker
from app.main import create_app
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryCommand,
    RequestPasswordRecovery,
    ResetPassword,
    VerifyPasswordRecoveryCode,
)
from app.modules.identity.infrastructure.identity_resolver import SqlAlchemyUserIdentityResolver
from app.modules.identity.infrastructure.password import Argon2PasswordHasher
from app.modules.identity.infrastructure.password_recovery_repository import (
    SqlAlchemyPasswordResetRepository,
)
from app.modules.identity.infrastructure.password_recovery_store import (
    RedisPasswordRecoveryStore,
)
from app.modules.identity.infrastructure.verified_phone_resolver import (
    SqlAlchemyVerifiedPhoneResolver,
)

from .conftest import PostgresInstance

_COMPANY_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
_MEMBER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
_EMAIL = "revocation@teste.com"
_OLD_PASSWORD = "SenhaAntiga@123"
_NEW_PASSWORD = "SenhaNova@456"
_CNPJ = "88999999000188"

_PROBLEM_JSON = "application/problem+json"


class _Verifier:
    async def verify(self, *, token: str, remote_ip: str | None) -> bool:
        _ = (token, remote_ip)
        return True


class _Limiter:
    async def check_ip(self, ip: str) -> None:
        _ = ip

    async def check_identifier(self, *, kind: str, value: str) -> None:
        _ = (kind, value)

    async def check_verify_ip(self, ip: str) -> None:
        _ = ip

    async def check_verify_identifier(self, *, kind: str, value: str) -> None:
        _ = (kind, value)

    async def check_reset_ip(self, ip: str) -> None:
        _ = ip


class _Dispatcher:
    def __init__(self) -> None:
        self.codes: list[str] = []
        self.changed: list[dict[str, Any]] = []

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        _ = (to, locale, expires_minutes)
        self.codes.append(code)

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        self.changed.append({"to": to, "locale": locale})


class _SmsDispatcher:
    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        _ = (to_phone, locale)


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture()
def revocation_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_ID,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, 'Revocation Empresa', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_COMPANY_ID, _CNPJ),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, company_id, email, full_name, cpf_hash, password_hash, status) "
            "VALUES (%s, %s, %s, 'Revocation User', %s, %s, 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING",
            (
                _USER_ID,
                _COMPANY_ID,
                _EMAIL,
                _cpf_hash(_EMAIL),
                hasher.hash(_OLD_PASSWORD),
            ),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_MEMBER_ID, _COMPANY_ID, _USER_ID),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def revocation_app(test_settings: Settings, revocation_seed: None) -> AsyncIterator[FastAPI]:
    app = create_app(test_settings)
    try:
        yield app
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


def _components(
    app: FastAPI, dispatcher: _Dispatcher
) -> tuple[RequestPasswordRecovery, VerifyPasswordRecoveryCode, ResetPassword]:
    store = RedisPasswordRecoveryStore(cast(Any, app.state.redis_client))
    resolver = SqlAlchemyUserIdentityResolver(app.state.session_factory)
    phone_resolver = SqlAlchemyVerifiedPhoneResolver(app.state.session_factory)
    repository = SqlAlchemyPasswordResetRepository(app.state.uow_factory)
    request = RequestPasswordRecovery(
        verifier=cast(Any, _Verifier()),
        limiter=cast(Any, _Limiter()),
        resolver=resolver,
        phone_resolver=phone_resolver,
        store=store,
        email_dispatcher=cast(Any, dispatcher),
        sms_dispatcher=cast(Any, _SmsDispatcher()),
        audit=repository,
        pepper=app.state.settings.pepper,
        code_ttl_seconds=600,
        resend_cooldown_seconds=60,
    )
    verify = VerifyPasswordRecoveryCode(
        resolver=resolver,
        phone_resolver=phone_resolver,
        phone_service=None,
        store=store,
        limiter=cast(Any, _Limiter()),
        audit=repository,
        pepper=app.state.settings.pepper,
        reset_token_ttl_seconds=600,
        max_attempts=5,
        code_ttl_seconds=600,
    )
    reset = ResetPassword(
        store=store,
        repository=repository,
        hasher=Argon2PasswordHasher(),
        email_dispatcher=cast(Any, dispatcher),
        limiter=cast(Any, _Limiter()),
        session_revoker=CredentialEpochSessionRevoker(
            redis_client=cast(Any, app.state.redis_client)
        ),
    )
    return request, verify, reset


async def _login(client: httpx.AsyncClient, password: str) -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": password})


async def test_reset_invalida_access_e_refresh_antigos_e_login_novo_funciona(
    revocation_app: FastAPI,
) -> None:
    dispatcher = _Dispatcher()
    request, verify, reset = _components(revocation_app, dispatcher)
    token_service = TokenService(
        secret_key=revocation_app.state.settings.secret_key,
        algorithm=revocation_app.state.settings.jwt_algorithm,
        expire_minutes=revocation_app.state.settings.access_token_expire_minutes,
    )

    transport = httpx.ASGITransport(app=revocation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await _login(client, _OLD_PASSWORD)
        assert login.status_code == 200
        old_access = login.json()["access_token"]
        old_refresh = login.json()["refresh_token"]
        assert token_service.decode_access_token(old_access).credential_epoch == 0

        await request.execute(
            PasswordRecoveryCommand(
                email=_EMAIL,
                phone_e164=None,
                turnstile_token="turnstile",
                remote_ip="203.0.113.7",
                locale="pt-BR",
            )
        )
        assert dispatcher.codes
        verified = await verify.execute(
            email=_EMAIL, code=dispatcher.codes[0], remote_ip="203.0.113.7"
        )
        await reset.execute(
            reset_token=verified.reset_token,
            new_password=_NEW_PASSWORD,
            remote_ip="203.0.113.7",
        )

        old_access_response = await client.get(
            "/api/v1/account", headers={"Authorization": f"Bearer {old_access}"}
        )
        assert old_access_response.status_code == 401
        assert old_access_response.headers["content-type"].startswith(_PROBLEM_JSON)
        assert old_access_response.json()["type"].endswith("invalid_token")

        old_refresh_response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert old_refresh_response.status_code == 401
        assert old_refresh_response.headers["content-type"].startswith(_PROBLEM_JSON)
        assert old_refresh_response.json()["type"].endswith("invalid_refresh_token")

        new_login = await _login(client, _NEW_PASSWORD)
        assert new_login.status_code == 200
        new_access = new_login.json()["access_token"]
        assert token_service.decode_access_token(new_access).credential_epoch == 1
        new_access_response = await client.get(
            "/api/v1/account", headers={"Authorization": f"Bearer {new_access}"}
        )
        assert new_access_response.status_code == 200
