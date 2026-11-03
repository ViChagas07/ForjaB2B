"""Testes de seguranca da recuperacao de conta (Fase 8)."""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from app.application.rate_limit import (
    InMemoryBucketStore,
    InMemoryDailyQuotaStore,
    RateLimitBackendError,
    RateLimitClass,
    RateLimiter,
    RateLimitPolicy,
)
from app.core.config import Settings
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.infrastructure.cache.redis import close_redis_client
from app.interface.errors import register_exception_handlers
from app.main import create_app
from app.modules.identity.application.errors import (
    PasswordRecoveryCodeError,
    PasswordResetTokenError,
)
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryLimiter,
    RequestPasswordRecovery,
    ResetPassword,
    VerifyPasswordRecoveryCode,
    recovery_code_digest,
)
from app.modules.identity.application.ports import (
    PasswordRecoveryCodeState,
    PasswordResetTokenData,
    PasswordResetUser,
    ResolvedIdentity,
    VerifiedPhoneOwner,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.infrastructure.turnstile import CloudflareTurnstileVerifier
from app.modules.identity.interface.password_recovery_router import (
    router as password_recovery_router,
)
from app.modules.identity.interface.schemas import (
    PasswordRecoveryRequest,
    PasswordRecoveryVerifyRequest,
)
from app.tasks.celery_app import celery_app
from app.tasks.password_recovery import (
    send_password_reset_code,
    send_password_reset_sms,
)

_USER = uuid.uuid4()
_COMPANY = uuid.uuid4()
_EMAIL = "security@example.com"
_PHONE = "+5511999991234"
_CODE = "123456"
_PEPPER = "security-pepper"
_IP = "203.0.113.7"


class _Verifier:
    def __init__(self, result: bool = True) -> None:
        self.result = result

    async def verify(self, *, token: str, remote_ip: str | None) -> bool:
        _ = (token, remote_ip)
        return self.result


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


class _Store:
    def __init__(
        self,
        *,
        state: PasswordRecoveryCodeState | None = None,
        sms_attempts: int = 0,
        token_data: PasswordResetTokenData | None = None,
        probe_error: Exception | None = None,
    ) -> None:
        self.state = state
        self.sms_attempts = sms_attempts
        self.token_data = token_data
        self.probe_error = probe_error
        self.probes = 0
        self.audit_codes: list[str] = []
        self.reset_tokens: list[dict[str, Any]] = []

    async def reserve_resend(self, *, user_id: uuid.UUID, ttl_seconds: int) -> bool:
        _ = (user_id, ttl_seconds)
        return True

    async def save_code(
        self, *, user_id: uuid.UUID, digest: str, locale: str | None, ttl_seconds: int
    ) -> None:
        _ = (user_id, locale, ttl_seconds)
        self.audit_codes.append(digest)

    async def load_code(self, *, user_id: uuid.UUID) -> PasswordRecoveryCodeState | None:
        _ = user_id
        return self.state

    async def record_failed_attempt(self, *, user_id: uuid.UUID, max_attempts: int) -> int:
        _ = (user_id, max_attempts)
        return max_attempts

    async def consume_code(self, *, user_id: uuid.UUID, digest: str) -> bool:
        _ = (user_id, digest)
        return True

    async def delete_code(self, *, user_id: uuid.UUID) -> None:
        _ = user_id

    async def delete_cooldown(self, *, user_id: uuid.UUID) -> None:
        _ = user_id

    async def save_reset_token(
        self,
        *,
        token_hash: str,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str | None,
        channel: str,
        ttl_seconds: int,
    ) -> None:
        self.reset_tokens.append(
            {
                "hash": token_hash,
                "user_id": user_id,
                "company_id": company_id,
                "locale": locale,
                "channel": channel,
                "ttl": ttl_seconds,
            }
        )

    async def consume_reset_token(self, *, token_hash: str) -> PasswordResetTokenData | None:
        _ = token_hash
        current = self.token_data
        self.token_data = None
        return current

    async def probe(self) -> None:
        self.probes += 1
        if self.probe_error is not None:
            raise self.probe_error

    async def get_sms_attempts(self, *, user_id: uuid.UUID) -> int:
        _ = user_id
        return self.sms_attempts

    async def record_sms_failed_attempt(
        self, *, user_id: uuid.UUID, max_attempts: int, ttl_seconds: int
    ) -> int:
        _ = (user_id, max_attempts, ttl_seconds)
        self.sms_attempts += 1
        return self.sms_attempts

    async def clear_sms_attempts(self, *, user_id: uuid.UUID) -> None:
        _ = user_id
        self.sms_attempts = 0


class _EmailDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        self.calls.append({"to": to, "locale": locale, "code": code, "expires": expires_minutes})

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        _ = (to, locale)


class _SmsDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        self.calls.append((to_phone, locale))


class _Resolver:
    def __init__(self, identity: ResolvedIdentity | None) -> None:
        self.identity = identity

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        _ = email
        return self.identity


class _PhoneResolver:
    def __init__(self, owner: VerifiedPhoneOwner | None) -> None:
        self.owner = owner

    async def resolve(self, *, phone_e164: str) -> VerifiedPhoneOwner | None:
        _ = phone_e164
        return self.owner


class _PhoneService:
    def __init__(self, result: bool = False) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        _ = (phone_e164, locale)
        return self.result

    async def check(self, *, phone_e164: str, code: str) -> bool:
        self.calls.append((phone_e164, code))
        return self.result


class _Audit:
    def __init__(self, user: PasswordResetUser | None) -> None:
        self.user = user
        self.events: list[tuple[str, dict[str, str]]] = []

    async def get_user(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PasswordResetUser | None:
        _ = (company_id, user_id)
        return self.user

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        _ = (company_id, user_id)
        self.events.append((action, details))


class _ResetRepository:
    def __init__(self, user: PasswordResetUser | None) -> None:
        self.user = user
        self.updated = 0
        self.events: list[tuple[str, dict[str, str]]] = []

    async def get_user(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PasswordResetUser | None:
        _ = (company_id, user_id)
        return self.user

    async def update_password_and_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        password_hash: str,
        audit_action: str,
        audit_details: dict[str, str],
    ) -> int | None:
        _ = (company_id, user_id, password_hash, audit_action, audit_details)
        self.updated += 1
        return 1

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        _ = (company_id, user_id)
        self.events.append((action, details))


class _Hasher:
    def verify(self, password: str, password_hash: str) -> bool:
        _ = (password, password_hash)
        return False

    def hash(self, password: str) -> str:
        return f"hash:{password}"


class _Revoker:
    def __init__(self) -> None:
        self.calls = 0

    async def revoke_all_for_user(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, credential_epoch: int
    ) -> None:
        _ = (user_id, company_id, credential_epoch)
        self.calls += 1


def _identity(status: UserStatus = UserStatus.ACTIVE) -> ResolvedIdentity:
    return ResolvedIdentity(user_id=_USER, company_id=_COMPANY, status=status, password_hash=None)


def _user(status: UserStatus = UserStatus.ACTIVE) -> PasswordResetUser:
    return PasswordResetUser(
        user_id=_USER,
        company_id=_COMPANY,
        email=_EMAIL,
        password_hash=None,
        status=status,
    )


def _request_usecase(
    *,
    identity: ResolvedIdentity | None,
    phone_owner: VerifiedPhoneOwner | None = None,
    user: PasswordResetUser | None = None,
    store: _Store | None = None,
) -> RequestPasswordRecovery:
    return RequestPasswordRecovery(
        verifier=cast(Any, _Verifier(True)),
        limiter=cast(Any, _Limiter()),
        resolver=cast(Any, _Resolver(identity)),
        phone_resolver=cast(Any, _PhoneResolver(phone_owner)),
        store=cast(Any, store or _Store()),
        email_dispatcher=cast(Any, _EmailDispatcher()),
        sms_dispatcher=cast(Any, _SmsDispatcher()),
        audit=cast(Any, _Audit(user)),
        pepper=_PEPPER,
        code_ttl_seconds=600,
        resend_cooldown_seconds=60,
    )


def _verify_usecase(
    *,
    identity: ResolvedIdentity | None = None,
    phone_owner: VerifiedPhoneOwner | None = None,
    user: PasswordResetUser | None = None,
    store: _Store | None = None,
    phone_service: _PhoneService | None = None,
) -> VerifyPasswordRecoveryCode:
    return VerifyPasswordRecoveryCode(
        resolver=cast(Any, _Resolver(identity)),
        phone_resolver=cast(Any, _PhoneResolver(phone_owner)),
        phone_service=cast(Any, phone_service or _PhoneService(False)),
        store=cast(Any, store or _Store()),
        limiter=cast(Any, _Limiter()),
        audit=cast(Any, _Audit(user)),
        pepper=_PEPPER,
        reset_token_ttl_seconds=600,
        max_attempts=5,
        code_ttl_seconds=600,
    )


def _minimal_app(
    request_usecase: RequestPasswordRecovery,
    verify_usecase: VerifyPasswordRecoveryCode,
) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(password_recovery_router, prefix="/api/v1")
    app.state.settings = Settings(
        _env_file=None,
        environment="test",
        otel_enabled=False,
        password_recovery_enabled=True,
        rate_limit_enabled=False,
        trusted_proxy_count=0,
    )
    app.state.password_recovery_request = request_usecase
    app.state.password_recovery_verify = verify_usecase
    app.state.password_recovery_reset = cast(Any, None)
    return app


async def _post(app: FastAPI, path: str, payload: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(path, json=payload)


def _comparable_headers(response: httpx.Response) -> dict[str, str]:
    return {
        "content-type": response.headers.get("content-type", ""),
        "cache-control": response.headers.get("cache-control", ""),
        "pragma": response.headers.get("pragma", ""),
    }


async def test_request_generico_para_existente_inexistente_inativo_e_telefone() -> None:
    cases = [
        ("existing", _request_usecase(identity=_identity(), user=_user())),
        ("missing", _request_usecase(identity=None)),
        (
            "inactive",
            _request_usecase(
                identity=_identity(UserStatus.SUSPENDED), user=_user(UserStatus.SUSPENDED)
            ),
        ),
        (
            "verified_phone",
            _request_usecase(
                identity=None,
                phone_owner=VerifiedPhoneOwner(user_id=_USER, company_id=_COMPANY),
                user=_user(),
            ),
        ),
        ("unverified_phone", _request_usecase(identity=None)),
    ]
    responses: list[httpx.Response] = []
    durations: list[float] = []
    for _name, usecase in cases:
        app = _minimal_app(usecase, _verify_usecase(store=_Store(state=None)))
        payload = (
            {"phone": _PHONE, "turnstile_token": "token", "locale": "pt-BR"}
            if "phone" in _name
            else {"email": _EMAIL, "turnstile_token": "token", "locale": "pt-BR"}
        )
        start = time.perf_counter()
        response = await _post(app, "/api/v1/auth/password-recovery/request", payload)
        durations.append(time.perf_counter() - start)
        responses.append(response)

    assert {response.status_code for response in responses} == {202}
    assert {response.content for response in responses} == {b'{"status":"accepted"}'}
    assert {tuple(_comparable_headers(response).items()) for response in responses} == {
        tuple(_comparable_headers(responses[0]).items())
    }
    assert "user_id" not in responses[0].text
    assert statistics.median(durations) < 0.5


async def test_verify_falhas_sao_identicas_e_sem_pii() -> None:
    cases = [
        (
            _verify_usecase(identity=_identity(), user=_user(), store=_Store(state=None)),
            {"email": _EMAIL, "code": "000000"},
        ),
        (
            _verify_usecase(identity=None, store=_Store(state=None)),
            {"email": _EMAIL, "code": "000000"},
        ),
        (
            _verify_usecase(
                identity=_identity(UserStatus.SUSPENDED),
                user=_user(UserStatus.SUSPENDED),
                store=_Store(state=None),
            ),
            {"email": _EMAIL, "code": "000000"},
        ),
        (
            _verify_usecase(
                identity=None,
                phone_owner=VerifiedPhoneOwner(user_id=_USER, company_id=_COMPANY),
                user=_user(),
                store=_Store(sms_attempts=5),
                phone_service=_PhoneService(False),
            ),
            {"phone": _PHONE, "code": "000000"},
        ),
        (
            _verify_usecase(
                identity=None,
                phone_owner=None,
                store=_Store(sms_attempts=0),
                phone_service=_PhoneService(False),
            ),
            {"phone": _PHONE, "code": "000000"},
        ),
    ]
    responses: list[httpx.Response] = []
    for usecase, payload in cases:
        app = _minimal_app(_request_usecase(identity=None), usecase)
        responses.append(await _post(app, "/api/v1/auth/password-recovery/verify", payload))

    assert {response.status_code for response in responses} == {400}
    bodies = []
    for response in responses:
        body = response.json()
        bodies.append((body.get("type"), body.get("title"), body.get("status"), body.get("detail")))
        assert "user_id" not in response.text
        assert "company_id" not in response.text
        assert "password_hash" not in response.text
        assert "twilio" not in response.text.lower()
    assert len(set(bodies)) == 1


async def test_xor_rejeita_ambos_e_nenhum() -> None:
    with pytest.raises(ValueError):
        PasswordRecoveryRequest.model_validate(
            {"email": _EMAIL, "phone": _PHONE, "turnstile_token": "token"}
        )
    with pytest.raises(ValueError):
        PasswordRecoveryRequest.model_validate({"turnstile_token": "token"})
    with pytest.raises(ValueError):
        PasswordRecoveryVerifyRequest.model_validate(
            {"email": _EMAIL, "phone": _PHONE, "code": _CODE}
        )
    with pytest.raises(ValueError):
        PasswordRecoveryVerifyRequest.model_validate({"code": _CODE})


async def test_brute_force_email_e_sms_e_replay_de_token() -> None:
    state = PasswordRecoveryCodeState(
        digest=recovery_code_digest(pepper=_PEPPER, user_id=_USER, code="999999"),
        attempts=4,
    )
    email = _verify_usecase(identity=_identity(), user=_user(), store=_Store(state=state))
    with pytest.raises(PasswordRecoveryCodeError):
        await email.execute(email=_EMAIL, code="000000", remote_ip=_IP)

    sms = _verify_usecase(
        identity=None,
        phone_owner=VerifiedPhoneOwner(user_id=_USER, company_id=_COMPANY),
        user=_user(),
        store=_Store(sms_attempts=5),
        phone_service=_PhoneService(False),
    )
    with pytest.raises(PasswordRecoveryCodeError):
        await sms.execute(phone_e164=_PHONE, code="000000", remote_ip=_IP)

    token_data = PasswordResetTokenData(user_id=_USER, company_id=_COMPANY)
    reset = ResetPassword(
        store=cast(Any, _Store(token_data=token_data)),
        repository=cast(Any, _ResetRepository(_user())),
        hasher=cast(Any, _Hasher()),
        email_dispatcher=cast(Any, _EmailDispatcher()),
        limiter=cast(Any, _Limiter()),
        session_revoker=cast(Any, _Revoker()),
    )
    await reset.execute(reset_token="token", new_password="SenhaNova123", remote_ip=_IP)
    with pytest.raises(PasswordResetTokenError):
        await reset.execute(reset_token="token", new_password="SenhaNova123", remote_ip=_IP)


async def test_reset_concorrente_so_um_vence_e_token_adulterado_falha() -> None:
    store = _Store(token_data=PasswordResetTokenData(user_id=_USER, company_id=_COMPANY))
    reset = ResetPassword(
        store=cast(Any, store),
        repository=cast(Any, _ResetRepository(_user())),
        hasher=cast(Any, _Hasher()),
        email_dispatcher=cast(Any, _EmailDispatcher()),
        limiter=cast(Any, _Limiter()),
        session_revoker=cast(Any, _Revoker()),
    )
    results = await asyncio.gather(
        reset.execute(reset_token="token", new_password="SenhaNova123", remote_ip=_IP),
        reset.execute(reset_token="token", new_password="SenhaNova123", remote_ip=_IP),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, PasswordResetTokenError) for result in results) == 1

    tampered = ResetPassword(
        store=cast(Any, _Store(token_data=None)),
        repository=cast(Any, _ResetRepository(_user())),
        hasher=cast(Any, _Hasher()),
        email_dispatcher=cast(Any, _EmailDispatcher()),
        limiter=cast(Any, _Limiter()),
        session_revoker=cast(Any, _Revoker()),
    )
    with pytest.raises(PasswordResetTokenError):
        await tampered.execute(reset_token="adulterado", new_password="SenhaNova123", remote_ip=_IP)


async def test_turnstile_fail_closed_e_redis_fail_closed() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    verifier = CloudflareTurnstileVerifier(
        secret_key="secret",
        transport=httpx.MockTransport(timeout),
    )
    with capture_logs() as logs:
        assert not await verifier.verify(token="token-secreto", remote_ip=_IP)
    assert "token-secreto" not in str(logs)

    class _FailingStore:
        async def consume(self, **kwargs: Any) -> tuple[bool, float, float]:
            _ = kwargs
            raise RateLimitBackendError("redis fora")

    policies = {
        rate_class: RateLimitPolicy(capacity=2, refill_per_minute=60)
        for rate_class in RateLimitClass
    }
    limiter = RateLimiter(
        store=_FailingStore(),
        policies=policies,
        fallback_store=InMemoryBucketStore(),
    )
    guard = PasswordRecoveryLimiter(
        limiter=limiter,
        daily_store=InMemoryDailyQuotaStore(),
        secret="secret",
        daily_limit=5,
    )
    with pytest.raises(ServiceUnavailableError):
        await guard.check_ip(_IP)


async def test_rate_limit_diario_e_teto() -> None:
    policies = {
        rate_class: RateLimitPolicy(capacity=10, refill_per_minute=60)
        for rate_class in RateLimitClass
    }
    limiter = RateLimiter(store=InMemoryBucketStore(), policies=policies)
    guard = PasswordRecoveryLimiter(
        limiter=limiter,
        daily_store=InMemoryDailyQuotaStore(),
        secret="secret",
        daily_limit=1,
    )
    await guard.check_identifier(kind="email", value=_EMAIL)
    with pytest.raises(RateLimitExceededError):
        await guard.check_identifier(kind="email", value=_EMAIL)


async def test_headers_no_store_em_recuperacao_e_telefone() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            otel_enabled=False,
            password_recovery_enabled=True,
            rate_limit_enabled=False,
            trusted_proxy_count=0,
        )
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            recovery = await client.post("/api/v1/auth/password-recovery/request", json={})
            phone = await client.get("/api/v1/account/phone/verification")
        for response in (recovery, phone):
            assert response.headers.get("cache-control") == "no-store"
            assert response.headers.get("pragma") == "no-cache"
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


def test_celery_nao_emite_eventos_com_args_e_tasks_ignoram_resultado() -> None:
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile.worker"
    content = dockerfile.read_text(encoding="utf-8")
    assert '"-E"' not in content
    assert celery_app.conf.worker_send_task_events is False
    assert celery_app.conf.task_send_sent_event is False
    assert send_password_reset_code.ignore_result is True
    assert send_password_reset_sms.ignore_result is True
