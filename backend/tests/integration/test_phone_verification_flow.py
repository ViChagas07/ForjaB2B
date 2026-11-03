"""Integracao do fluxo de verificacao de telefone (PostgreSQL + RLS + fake SMS)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.security import AuthContext
from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.main import create_app
from app.modules.identity.application.account import UpdateAccount, UpdateAccountCommand
from app.modules.identity.application.phone_verification import (
    CheckPhoneVerification,
    GetPhoneVerificationStatus,
    StartPhoneVerification,
)
from app.modules.identity.infrastructure.account_repository import SqlAlchemyAccountRepository
from app.modules.identity.infrastructure.phone_verification_repository import (
    SqlAlchemyPhoneVerificationRepository,
)

from .conftest import PostgresInstance

_PHONE = "+5511977771234"
_PHONE_OTHER = "+5511988887777"
_CODE = "123456"


class _Service:
    def __init__(self) -> None:
        self.started: set[str] = set()

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        _ = locale
        self.started.add(phone_e164)
        return True

    async def check(self, *, phone_e164: str, code: str) -> bool:
        return phone_e164 in self.started and code == _CODE


class _Limiter:
    async def check_start(self, *, ip: str, user_id: uuid.UUID) -> None:
        _ = (ip, user_id)

    async def reserve_cooldown(self, user_id: uuid.UUID) -> bool:
        _ = user_id
        return True

    async def release_cooldown(self, user_id: uuid.UUID) -> None:
        _ = user_id

    async def check_check(self, *, ip: str, user_id: uuid.UUID) -> None:
        _ = (ip, user_id)


class _Email:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_phone_unlinked(self, *, to: str, locale: str | None) -> None:
        self.calls.append((to, locale))


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed_user(pg: PostgresInstance) -> tuple[uuid.UUID, uuid.UUID, str]:
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = f"phone-{user_id.hex}@teste.com"
    cnpj = f"{uuid.uuid4().int % 10**14:014d}"
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, 'Phone Empresa', 'ACTIVE')",
            (company_id, cnpj),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, company_id, email, full_name, cpf_hash, status) "
            "VALUES (%s, %s, %s, 'Phone User', %s, 'ACTIVE')",
            (user_id, company_id, email, _cpf_hash(email)),
        )
        conn.commit()
    finally:
        conn.close()
    return company_id, user_id, email


def _auth(company_id: uuid.UUID, user_id: uuid.UUID) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        company_id=company_id,
        role="BUYER",
        token_id=f"phone-{user_id.hex}",
    )


def _verified_phone(pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        row = conn.execute(
            "SELECT phone_e164 FROM user_verified_phones WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        conn.commit()
        return None if row is None else str(row[0])
    finally:
        conn.close()


def _audit_actions(pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        rows = conn.execute(
            "SELECT action FROM audit_log WHERE actor_user_id = %s ORDER BY created_at",
            (user_id,),
        ).fetchall()
        conn.commit()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def _components(
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    service: _Service,
    email: _Email,
) -> tuple[
    StartPhoneVerification,
    CheckPhoneVerification,
    GetPhoneVerificationStatus,
    SqlAlchemyPhoneVerificationRepository,
]:
    repository = SqlAlchemyPhoneVerificationRepository(uow_factory)
    limiter = _Limiter()
    start = StartPhoneVerification(
        service=cast(Any, service),
        limiter=cast(Any, limiter),
        repository=repository,
        cooldown_seconds=60,
    )
    check = CheckPhoneVerification(
        service=cast(Any, service),
        limiter=cast(Any, limiter),
        repository=repository,
        email_dispatcher=cast(Any, email),
    )
    status = GetPhoneVerificationStatus(repository=repository)
    return start, check, status, repository


async def test_fluxo_completo_reivindica_telefone_e_desvincula_anterior(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    company_a, user_a, email_a = _seed_user(pg)
    company_b, user_b, email_b = _seed_user(pg)
    service = _Service()
    email = _Email()
    start, check, status, _repository = _components(session_factory, uow_factory, service, email)
    auth_a = _auth(company_a, user_a)
    auth_b = _auth(company_b, user_b)

    await start.execute(auth_a, phone_e164=_PHONE, locale="pt-BR", remote_ip="203.0.113.7")
    await check.execute(auth_a, phone_e164=_PHONE, code=_CODE, remote_ip="203.0.113.7")
    assert _verified_phone(pg, company_a, user_a) == _PHONE
    assert (await status.execute(auth_a)).phone_masked == "+55 ** *****-1234"
    assert "auth.phone_verified" in _audit_actions(pg, company_a, user_a)

    await start.execute(auth_b, phone_e164=_PHONE, locale="pt-BR", remote_ip="203.0.113.8")
    await check.execute(auth_b, phone_e164=_PHONE, code=_CODE, remote_ip="203.0.113.8")

    assert _verified_phone(pg, company_a, user_a) is None
    assert _verified_phone(pg, company_b, user_b) == _PHONE
    assert email.calls == [(email_a, None)]
    assert "auth.phone_unlinked" in _audit_actions(pg, company_a, user_a)
    assert "auth.phone_verified" in _audit_actions(pg, company_b, user_b)
    assert email_b not in str(email.calls)


async def test_patch_account_remove_vinculo_quando_telefone_muda(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    company_id, user_id, _email = _seed_user(pg)
    service = _Service()
    email = _Email()
    start, check, _status, repository = _components(session_factory, uow_factory, service, email)
    auth = _auth(company_id, user_id)
    await start.execute(auth, phone_e164=_PHONE, locale=None, remote_ip="203.0.113.7")
    await check.execute(auth, phone_e164=_PHONE, code=_CODE, remote_ip="203.0.113.7")

    account = UpdateAccount(
        repository=SqlAlchemyAccountRepository(uow_factory),
        phone_verification=repository,
    )
    await account.execute(
        auth,
        UpdateAccountCommand(full_name="Phone User", phone=_PHONE_OTHER),
    )

    assert _verified_phone(pg, company_id, user_id) is None


async def test_autenticacao_obrigatoria_nas_rotas_de_telefone(
    test_settings: Settings,
) -> None:
    app: FastAPI = create_app(test_settings)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/account/phone/verification")
        assert response.status_code == 401
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
