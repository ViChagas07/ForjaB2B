"""Testes da verificacao de telefone: use cases, limites, mascara e hook."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from structlog.testing import capture_logs

from app.application.rate_limit import (
    InMemoryBucketStore,
    InMemoryCooldownStore,
    InMemoryDailyQuotaStore,
    RateLimitClass,
    RateLimiter,
    RateLimitPolicy,
)
from app.application.security import AuthContext
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.modules.identity.application.errors import (
    PhoneVerificationConflictError,
    PhoneVerificationFailedError,
)
from app.modules.identity.application.phone import mask_phone_e164, normalize_phone_e164
from app.modules.identity.application.phone_verification import (
    CheckPhoneVerification,
    GetPhoneVerificationStatus,
    PhoneVerificationLimiter,
    StartPhoneVerification,
)
from app.modules.identity.application.ports import PreviousPhoneOwner

_COMPANY = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_AUTH = AuthContext(user_id=_USER, company_id=_COMPANY, role="BUYER", token_id="phone-test")
_PHONE = "+5511999991234"
_CODE = "123456"
_IP = "203.0.113.7"


class _Service:
    def __init__(self, *, start: bool = True, check: bool = True) -> None:
        self.start_result = start
        self.check_result = check
        self.starts: list[tuple[str, str | None]] = []
        self.checks: list[tuple[str, str]] = []

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        self.starts.append((phone_e164, locale))
        return self.start_result

    async def check(self, *, phone_e164: str, code: str) -> bool:
        self.checks.append((phone_e164, code))
        return self.check_result


class _Limiter:
    def __init__(self, *, cooldown: bool = True, error: Exception | None = None) -> None:
        self.cooldown = cooldown
        self.error = error
        self.calls: list[tuple[Any, ...]] = []
        self.released = False

    async def check_start(self, *, ip: str, user_id: uuid.UUID) -> None:
        self.calls.append(("start", ip, user_id))
        if self.error is not None:
            raise self.error

    async def reserve_cooldown(self, user_id: uuid.UUID) -> bool:
        self.calls.append(("cooldown", user_id))
        return self.cooldown

    async def release_cooldown(self, user_id: uuid.UUID) -> None:
        self.released = True

    async def check_check(self, *, ip: str, user_id: uuid.UUID) -> None:
        self.calls.append(("check", ip, user_id))
        if self.error is not None:
            raise self.error


class _Repository:
    def __init__(
        self,
        *,
        previous: PreviousPhoneOwner | None = None,
        email: str | None = None,
        conflict_times: int = 0,
        claim_error: Exception | None = None,
    ) -> None:
        self.previous = previous
        self.email = email
        self.conflict_times = conflict_times
        self.claim_error = claim_error
        self.claims: list[tuple[str, uuid.UUID, uuid.UUID]] = []
        self.audits: list[tuple[uuid.UUID, uuid.UUID, str, dict[str, str]]] = []
        self.email_lookups: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.verified_phone: str | None = None

    async def get_verified_phone(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        return self.verified_phone

    async def claim_verified_phone(
        self, *, phone_e164: str, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> PreviousPhoneOwner | None:
        self.claims.append((phone_e164, user_id, company_id))
        if self.claim_error is not None:
            raise self.claim_error
        if self.conflict_times > 0:
            self.conflict_times -= 1
            raise PhoneVerificationConflictError()
        return self.previous

    async def get_user_email(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        self.email_lookups.append((company_id, user_id))
        return self.email

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        self.audits.append((company_id, user_id, action, details))


class _Email:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_phone_unlinked(self, *, to: str, locale: str | None) -> None:
        self.calls.append((to, locale))


def _start(
    *, service: _Service | None, limiter: _Limiter, repository: _Repository
) -> StartPhoneVerification:
    return StartPhoneVerification(
        service=cast(Any, service),
        limiter=cast(Any, limiter),
        repository=cast(Any, repository),
        cooldown_seconds=60,
    )


def _check(
    *,
    service: _Service | None,
    limiter: _Limiter,
    repository: _Repository,
    email: _Email | None = None,
) -> CheckPhoneVerification:
    return CheckPhoneVerification(
        service=cast(Any, service),
        limiter=cast(Any, limiter),
        repository=cast(Any, repository),
        email_dispatcher=cast(Any, email or _Email()),
    )


async def test_start_feliz_envia_e_audita() -> None:
    service = _Service()
    limiter = _Limiter()
    repository = _Repository()
    usecase = _start(service=service, limiter=limiter, repository=repository)

    await usecase.execute(_AUTH, phone_e164=_PHONE, locale="pt-BR", remote_ip=_IP)

    assert service.starts == [(_PHONE, "pt-BR")]
    assert limiter.calls == [("start", _IP, _USER), ("cooldown", _USER)]
    assert repository.audits == [
        (_COMPANY, _USER, "auth.phone_verification_started", {"channel": "sms"})
    ]


async def test_start_sem_twilio_retorna_503() -> None:
    usecase = _start(service=None, limiter=_Limiter(), repository=_Repository())
    with pytest.raises(ServiceUnavailableError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, locale=None, remote_ip=_IP)


async def test_start_provider_falha_libera_cooldown() -> None:
    limiter = _Limiter()
    usecase = _start(service=_Service(start=False), limiter=limiter, repository=_Repository())
    with pytest.raises(ServiceUnavailableError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, locale=None, remote_ip=_IP)
    assert limiter.released is True


async def test_start_cooldown_ativo_nao_envia() -> None:
    service = _Service()
    limiter = _Limiter(cooldown=False)
    usecase = _start(service=service, limiter=limiter, repository=_Repository())
    with pytest.raises(RateLimitExceededError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, locale=None, remote_ip=_IP)
    assert service.starts == []


async def test_check_aprovado_grava_vinculo_e_audita() -> None:
    repository = _Repository()
    usecase = _check(service=_Service(check=True), limiter=_Limiter(), repository=repository)

    await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert repository.claims == [(_PHONE, _USER, _COMPANY)]
    assert [event[2] for event in repository.audits] == ["auth.phone_verified"]


async def test_check_reprovado_nao_grava_e_audita_falha() -> None:
    repository = _Repository()
    usecase = _check(service=_Service(check=False), limiter=_Limiter(), repository=repository)

    with pytest.raises(PhoneVerificationFailedError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert repository.claims == []
    assert repository.audits[0][2] == "auth.phone_verification_failed"


async def test_check_numero_de_outra_conta_desvincula_e_avisa() -> None:
    previous = PreviousPhoneOwner(user_id=uuid.uuid4(), company_id=uuid.uuid4())
    repository = _Repository(previous=previous, email="old@example.com")
    email = _Email()
    usecase = _check(
        service=_Service(check=True),
        limiter=_Limiter(),
        repository=repository,
        email=email,
    )

    await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert repository.email_lookups == [(previous.company_id, previous.user_id)]
    assert email.calls == [("old@example.com", None)]
    actions = [event[2] for event in repository.audits]
    assert actions == ["auth.phone_verified", "auth.phone_unlinked"]
    assert repository.audits[1][0:2] == (previous.company_id, previous.user_id)


async def test_check_corrida_de_unicidade_tenta_novamente() -> None:
    repository = _Repository(conflict_times=1)
    usecase = _check(service=_Service(check=True), limiter=_Limiter(), repository=repository)

    await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert len(repository.claims) == 2


async def test_check_corrida_persistente_nao_vira_500() -> None:
    repository = _Repository(conflict_times=2)
    usecase = _check(service=_Service(check=True), limiter=_Limiter(), repository=repository)

    with pytest.raises(PhoneVerificationFailedError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)


async def test_check_falha_de_persistencia_vira_503() -> None:
    repository = _Repository(claim_error=RuntimeError("db fora"))
    usecase = _check(service=_Service(check=True), limiter=_Limiter(), repository=repository)

    with pytest.raises(ServiceUnavailableError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)


async def test_logs_nao_contem_telefone_nem_codigo() -> None:
    repository = _Repository()
    usecase = _check(service=_Service(check=False), limiter=_Limiter(), repository=repository)

    with capture_logs() as logs, pytest.raises(PhoneVerificationFailedError):
        await usecase.execute(_AUTH, phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    rendered = str(logs)
    assert _PHONE not in rendered
    assert _CODE not in rendered


async def test_status_mascara_telefone() -> None:
    repository = _Repository()
    repository.verified_phone = _PHONE
    status = await GetPhoneVerificationStatus(repository=cast(Any, repository)).execute(_AUTH)
    assert status.verified is True
    assert status.phone_masked == "+55 ** *****-1234"

    repository.verified_phone = None
    empty = await GetPhoneVerificationStatus(repository=cast(Any, repository)).execute(_AUTH)
    assert empty.verified is False
    assert empty.phone_masked is None


def test_normalizacao_e_mascara() -> None:
    assert normalize_phone_e164("+55 (11) 99999-1234") == "+5511999991234"
    assert normalize_phone_e164("+1 (415) 555-2671") == "+14155552671"
    assert mask_phone_e164("+5511999991234") == "+55 ** *****-1234"
    for invalid in ("11999991234", "+55 10 99999-1234", "+55 11 9999"):
        with pytest.raises(ValueError):
            normalize_phone_e164(invalid)


_POLICIES = {
    rate_class: RateLimitPolicy(capacity=2, refill_per_minute=60) for rate_class in RateLimitClass
}


class _FailingBucketStore:
    async def consume(self, **kwargs: Any) -> tuple[bool, float, float]:
        _ = kwargs
        raise RuntimeError("redis fora")


async def test_limiter_start_aplica_buckets_diarios_e_cooldown() -> None:
    limiter = PhoneVerificationLimiter(
        limiter=RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=lambda: 1000.0),
        daily_store=InMemoryDailyQuotaStore(clock=lambda: 1000.0),
        cooldown_store=InMemoryCooldownStore(clock=lambda: 1000.0),
        daily_user_limit=1,
        daily_ip_limit=5,
        cooldown_seconds=60,
    )

    await limiter.check_start(ip=_IP, user_id=_USER)
    assert await limiter.reserve_cooldown(_USER) is True
    assert await limiter.reserve_cooldown(_USER) is False
    await limiter.release_cooldown(_USER)
    assert await limiter.reserve_cooldown(_USER) is True

    with pytest.raises(RateLimitExceededError):
        await limiter.check_start(ip=_IP, user_id=_USER)


async def test_limiter_fail_closed_quando_redis_fora() -> None:
    limiter = PhoneVerificationLimiter(
        limiter=RateLimiter(
            store=_FailingBucketStore(),
            policies=_POLICIES,
            fallback_store=InMemoryBucketStore(),
            clock=lambda: 1000.0,
        ),
        daily_store=InMemoryDailyQuotaStore(clock=lambda: 1000.0),
        cooldown_store=InMemoryCooldownStore(clock=lambda: 1000.0),
        daily_user_limit=5,
        daily_ip_limit=5,
        cooldown_seconds=60,
    )

    with pytest.raises(ServiceUnavailableError):
        await limiter.check_start(ip=_IP, user_id=_USER)


async def test_limiter_desabilitado_nao_consome() -> None:
    limiter = PhoneVerificationLimiter(
        limiter=RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=lambda: 1000.0),
        daily_store=InMemoryDailyQuotaStore(clock=lambda: 1000.0),
        cooldown_store=InMemoryCooldownStore(clock=lambda: 1000.0),
        daily_user_limit=1,
        daily_ip_limit=1,
        cooldown_seconds=60,
        enabled=False,
    )
    await limiter.check_start(ip=_IP, user_id=_USER)
    assert await limiter.reserve_cooldown(_USER) is True
    await limiter.check_check(ip=_IP, user_id=_USER)
