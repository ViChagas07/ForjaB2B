"""Integracao do fluxo de recuperacao por e-mail (PostgreSQL + Redis reais)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog.testing import capture_logs

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.security.credential_epoch import CredentialEpochSessionRevoker
from app.modules.identity.application.errors import (
    PasswordRecoveryCodeError,
    PasswordResetTokenError,
)
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryCommand,
    RequestPasswordRecovery,
    ResetPassword,
    VerifyPasswordRecoveryCode,
)
from app.modules.identity.domain.enums import UserStatus
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

_OLD_PASSWORD = "SenhaAntiga@123"
_NEW_PASSWORD = "SenhaNova@456"
_PEPPER = "pepper-integracao"
_PHONE = "+5511999991234"
_PHONE_2 = "+5511988887777"
_CODE = "123456"


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
        self.codes: list[dict[str, Any]] = []
        self.changed: list[dict[str, Any]] = []

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        self.codes.append(
            {"to": to, "locale": locale, "code": code, "expires_minutes": expires_minutes}
        )

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        self.changed.append({"to": to, "locale": locale})


class _SmsDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        self.calls.append((to_phone, locale))


class _PhoneService:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.checks: list[tuple[str, str]] = []

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        _ = (phone_e164, locale)
        return True

    async def check(self, *, phone_e164: str, code: str) -> bool:
        self.checks.append((phone_e164, code))
        return self.approved


@pytest.fixture()
async def recovery_redis(redis_url: str) -> AsyncIterator[Any]:
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await cast(Any, client).aclose()


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed_user(
    pg: PostgresInstance,
    *,
    status: str = "ACTIVE",
    password_hash: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = f"recovery-{user_id.hex}@teste.com"
    cnpj = f"{uuid.uuid4().int % 10**14:014d}"
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, 'Recovery Integracao', 'ACTIVE')",
            (company_id, cnpj),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, company_id, email, full_name, cpf_hash, password_hash, status) "
            "VALUES (%s, %s, %s, 'Recovery User', %s, %s, %s)",
            (user_id, company_id, email, _cpf_hash(email), password_hash, status),
        )
        conn.commit()
    finally:
        conn.close()
    return company_id, user_id, email


def _components(
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    redis_client: Any,
    dispatcher: _Dispatcher,
    *,
    sms_dispatcher: _SmsDispatcher | None = None,
    phone_service: _PhoneService | None = None,
) -> tuple[
    RequestPasswordRecovery, VerifyPasswordRecoveryCode, ResetPassword, RedisPasswordRecoveryStore
]:
    store = RedisPasswordRecoveryStore(cast(Any, redis_client))
    resolver = SqlAlchemyUserIdentityResolver(session_factory)
    phone_resolver = SqlAlchemyVerifiedPhoneResolver(session_factory)
    repository = SqlAlchemyPasswordResetRepository(uow_factory)
    request = RequestPasswordRecovery(
        verifier=cast(Any, _Verifier()),
        limiter=cast(Any, _Limiter()),
        resolver=resolver,
        phone_resolver=phone_resolver,
        store=store,
        email_dispatcher=cast(Any, dispatcher),
        sms_dispatcher=cast(Any, sms_dispatcher or _SmsDispatcher()),
        audit=repository,
        pepper=_PEPPER,
        code_ttl_seconds=600,
        resend_cooldown_seconds=60,
    )
    verify = VerifyPasswordRecoveryCode(
        resolver=resolver,
        phone_resolver=phone_resolver,
        phone_service=cast(Any, phone_service),
        store=store,
        limiter=cast(Any, _Limiter()),
        audit=repository,
        pepper=_PEPPER,
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
        session_revoker=CredentialEpochSessionRevoker(redis_client=cast(Any, redis_client)),
    )
    return request, verify, reset, store


def _audit_actions(
    pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID
) -> list[tuple[str, str]]:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        rows = conn.execute(
            "SELECT action, details::text FROM audit_log "
            "WHERE actor_user_id = %s ORDER BY created_at",
            (user_id,),
        ).fetchall()
        conn.commit()
        return [(str(row[0]), str(row[1])) for row in rows]
    finally:
        conn.close()


def _password_hash(pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        row = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,)).fetchone()
        conn.commit()
        return None if row is None else cast(str | None, row[0])
    finally:
        conn.close()


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


def _notification_count(pg: PostgresInstance, company_id: uuid.UUID) -> int:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        row = conn.execute(
            "SELECT count(*) FROM notifications WHERE company_id = %s", (company_id,)
        ).fetchone()
        conn.commit()
        return 0 if row is None else int(row[0])
    finally:
        conn.close()


async def test_fluxo_completo_email_altera_senha_com_auditoria(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    recovery_redis: Any,
) -> None:
    hasher = Argon2PasswordHasher()
    old_hash = hasher.hash(_OLD_PASSWORD)
    company_id, user_id, email = _seed_user(pg, password_hash=old_hash)
    dispatcher = _Dispatcher()
    request, verify, reset, store = _components(
        session_factory, uow_factory, recovery_redis, dispatcher
    )

    with capture_logs() as logs:
        await request.execute(
            PasswordRecoveryCommand(
                email=email,
                phone_e164=None,
                turnstile_token="turnstile",
                remote_ip="203.0.113.7",
                locale="pt-BR",
            )
        )

    assert len(dispatcher.codes) == 1
    code = dispatcher.codes[0]["code"]
    assert email not in str(logs)
    assert code not in str(logs)
    raw_redis = str(await recovery_redis.hgetall(f"password_recovery:code:{user_id}"))
    assert code not in raw_redis
    assert _notification_count(pg, company_id) == 0

    verified = await verify.execute(email=email, code=code, remote_ip="203.0.113.7")
    assert await store.load_code(user_id=user_id) is None

    await reset.execute(
        reset_token=verified.reset_token,
        new_password=_NEW_PASSWORD,
        remote_ip="203.0.113.7",
    )

    new_hash = _password_hash(pg, company_id, user_id)
    assert new_hash is not None
    assert hasher.verify(_NEW_PASSWORD, new_hash)
    assert not hasher.verify(_OLD_PASSWORD, new_hash)
    assert dispatcher.changed == [{"to": email, "locale": "pt-BR"}]

    state = _credential_state(pg, company_id, user_id)
    assert state is not None
    assert state[0] == 1
    assert state[1] is not None
    assert await recovery_redis.get(f"credential_epoch:{user_id}") == "1"

    actions_and_details = _audit_actions(pg, company_id, user_id)
    actions = [item[0] for item in actions_and_details]
    assert "auth.password_reset_requested" in actions
    assert "auth.password_reset_verified" in actions
    assert "auth.password_reset_completed" in actions
    details = " ".join(item[1] for item in actions_and_details)
    assert email not in details
    assert code not in details
    assert verified.reset_token not in details
    assert _NEW_PASSWORD not in details

    # reset_token e de uso unico
    with pytest.raises(PasswordResetTokenError):
        await reset.execute(
            reset_token=verified.reset_token,
            new_password="OutraSenha@789",
            remote_ip="203.0.113.7",
        )


async def test_conta_oauth_sem_senha_consegue_definir_senha(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    recovery_redis: Any,
) -> None:
    company_id, user_id, email = _seed_user(pg, password_hash=None)
    dispatcher = _Dispatcher()
    request, verify, reset, _ = _components(
        session_factory, uow_factory, recovery_redis, dispatcher
    )

    await request.execute(
        PasswordRecoveryCommand(
            email=email,
            phone_e164=None,
            turnstile_token="turnstile",
            remote_ip="203.0.113.7",
        )
    )
    code = dispatcher.codes[0]["code"]
    verified = await verify.execute(email=email, code=code, remote_ip="203.0.113.7")
    await reset.execute(
        reset_token=verified.reset_token,
        new_password=_NEW_PASSWORD,
        remote_ip="203.0.113.7",
    )

    new_hash = _password_hash(pg, company_id, user_id)
    assert new_hash is not None
    assert Argon2PasswordHasher().verify(_NEW_PASSWORD, new_hash)


async def test_inexistente_inativo_e_cooldown_nao_enviam(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    recovery_redis: Any,
) -> None:
    dispatcher = _Dispatcher()
    request, verify, _, _ = _components(session_factory, uow_factory, recovery_redis, dispatcher)
    _company, _user_id, inactive_email = _seed_user(
        pg, status=UserStatus.SUSPENDED.value, password_hash=None
    )

    await request.execute(
        PasswordRecoveryCommand(
            email="nao-existe@teste.com",
            phone_e164=None,
            turnstile_token="turnstile",
            remote_ip="203.0.113.7",
        )
    )
    await request.execute(
        PasswordRecoveryCommand(
            email=inactive_email,
            phone_e164=None,
            turnstile_token="turnstile",
            remote_ip="203.0.113.7",
        )
    )
    assert dispatcher.codes == []
    with pytest.raises(PasswordRecoveryCodeError):
        await verify.execute(email=inactive_email, code="123456", remote_ip="203.0.113.7")

    _, _, active_email = _seed_user(pg, status=UserStatus.ACTIVE.value, password_hash=None)
    command = PasswordRecoveryCommand(
        email=active_email,
        phone_e164=None,
        turnstile_token="turnstile",
        remote_ip="203.0.113.7",
    )
    await request.execute(command)
    await request.execute(command)
    assert len(dispatcher.codes) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def _credential_state(
    pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[int, str | None] | None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        row = conn.execute(
            "SELECT credential_epoch, password_changed_at::text "
            "FROM user_credential_state WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        conn.commit()
        if row is None:
            return None
        return int(row[0]), cast(str | None, row[1])
    finally:
        conn.close()


async def test_epoca_incrementa_e_nunca_diminui(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    company_id, user_id, _email = _seed_user(pg, password_hash=None)
    repository = SqlAlchemyPasswordResetRepository(uow_factory)

    first = await repository.update_password_and_audit(
        company_id=company_id,
        user_id=user_id,
        password_hash="hash-1",
        audit_action="auth.password_reset_completed",
        audit_details={"channel": "email"},
    )
    second = await repository.update_password_and_audit(
        company_id=company_id,
        user_id=user_id,
        password_hash="hash-2",
        audit_action="auth.password_reset_completed",
        audit_details={"channel": "email"},
    )

    assert first == 1
    assert second == 2
    state = _credential_state(pg, company_id, user_id)
    assert state is not None
    assert state[0] == 2
    assert state[1] is not None


def _seed_verified_phone(
    pg: PostgresInstance, company_id: uuid.UUID, user_id: uuid.UUID, phone: str
) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        conn.execute(
            "INSERT INTO user_verified_phones "
            "(user_id, company_id, phone_e164, verified_at) VALUES (%s, %s, %s, now())",
            (user_id, company_id, phone),
        )
        conn.commit()
    finally:
        conn.close()


async def test_fluxo_completo_sms_altera_senha_e_audita_channel(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    recovery_redis: Any,
) -> None:
    company_id, user_id, email = _seed_user(pg, password_hash=None)
    _seed_verified_phone(pg, company_id, user_id, _PHONE)
    email_dispatcher = _Dispatcher()
    sms_dispatcher = _SmsDispatcher()
    phone_service = _PhoneService(approved=True)
    request, verify, reset, _store = _components(
        session_factory,
        uow_factory,
        recovery_redis,
        email_dispatcher,
        sms_dispatcher=sms_dispatcher,
        phone_service=phone_service,
    )

    await request.execute(
        PasswordRecoveryCommand(
            email=None,
            phone_e164=_PHONE,
            turnstile_token="turnstile",
            remote_ip="203.0.113.7",
            locale="pt-BR",
        )
    )
    assert sms_dispatcher.calls == [(_PHONE, "pt-BR")]

    verified = await verify.execute(phone_e164=_PHONE, code=_CODE, remote_ip="203.0.113.7")
    assert phone_service.checks == [(_PHONE, _CODE)]
    await reset.execute(
        reset_token=verified.reset_token,
        new_password=_NEW_PASSWORD,
        remote_ip="203.0.113.7",
    )

    new_hash = _password_hash(pg, company_id, user_id)
    assert new_hash is not None
    assert Argon2PasswordHasher().verify(_NEW_PASSWORD, new_hash)
    assert email_dispatcher.changed == [{"to": email, "locale": None}]
    state = _credential_state(pg, company_id, user_id)
    assert state is not None and state[0] == 1
    actions = _audit_actions(pg, company_id, user_id)
    completed = [
        details for action, details in actions if action == "auth.password_reset_completed"
    ]
    assert completed and '"channel": "sms"' in completed[0]


async def test_sms_sem_telefone_verificado_nao_envia(
    pg: PostgresInstance,
    migrated_domain_schema: None,
    session_factory: async_sessionmaker[AsyncSession],
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    recovery_redis: Any,
) -> None:
    company_id, user_id, _email = _seed_user(pg, password_hash=None)
    email_dispatcher = _Dispatcher()
    sms_dispatcher = _SmsDispatcher()
    phone_service = _PhoneService(approved=True)
    request, verify, _reset, _store = _components(
        session_factory,
        uow_factory,
        recovery_redis,
        email_dispatcher,
        sms_dispatcher=sms_dispatcher,
        phone_service=phone_service,
    )

    await request.execute(
        PasswordRecoveryCommand(
            email=None,
            phone_e164=_PHONE_2,
            turnstile_token="turnstile",
            remote_ip="203.0.113.7",
        )
    )
    assert sms_dispatcher.calls == []
    with pytest.raises(PasswordRecoveryCodeError):
        await verify.execute(phone_e164=_PHONE_2, code=_CODE, remote_ip="203.0.113.7")
    assert phone_service.checks == [(_PHONE_2, _CODE)]
    assert _verified_phone(pg, company_id, user_id) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
