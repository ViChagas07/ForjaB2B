"""Testes do request de recuperacao por e-mail (Fase 3)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from structlog.testing import capture_logs

from app.core.errors import ServiceUnavailableError
from app.modules.identity.application.errors import (
    AntiBotVerificationError,
    InvalidPasswordRecoveryRequestError,
    PasswordRecoveryStoreError,
)
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryCommand,
    RequestPasswordRecovery,
)
from app.modules.identity.application.ports import (
    PasswordResetUser,
    ResolvedIdentity,
    VerifiedPhoneOwner,
)
from app.modules.identity.domain.enums import UserStatus

_IP = "203.0.113.7"
_TOKEN = "turnstile-token"
_EMAIL = "user@example.com"
_USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_COMPANY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
_PEPPER = "pepper-de-teste"


class _Verifier:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.calls: list[tuple[str, str | None]] = []

    async def verify(self, *, token: str, remote_ip: str | None) -> bool:
        self.calls.append((token, remote_ip))
        return self.result


class _Limiter:
    def __init__(
        self,
        *,
        ip_error: Exception | None = None,
        identifier_error: Exception | None = None,
    ) -> None:
        self.ip_error = ip_error
        self.identifier_error = identifier_error
        self.calls: list[tuple[Any, ...]] = []

    async def check_ip(self, ip: str) -> None:
        self.calls.append(("ip", ip))
        if self.ip_error is not None:
            raise self.ip_error

    async def check_identifier(self, *, kind: str, value: str) -> None:
        self.calls.append(("identifier", kind, value))
        if self.identifier_error is not None:
            raise self.identifier_error


class _Resolver:
    def __init__(
        self, identity: ResolvedIdentity | None, *, error: Exception | None = None
    ) -> None:
        self.identity = identity
        self.error = error
        self.calls: list[str] = []

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        self.calls.append(email)
        if self.error is not None:
            raise self.error
        return self.identity


class _Store:
    def __init__(
        self,
        *,
        reserved: bool = True,
        probe_error: Exception | None = None,
    ) -> None:
        self.reserved = reserved
        self.probe_error = probe_error
        self.probes = 0
        self.reserve_calls: list[tuple[uuid.UUID, int]] = []
        self.codes: dict[uuid.UUID, tuple[str, str | None]] = {}
        self.deleted_cooldowns: list[uuid.UUID] = []

    async def reserve_resend(self, *, user_id: uuid.UUID, ttl_seconds: int) -> bool:
        self.reserve_calls.append((user_id, ttl_seconds))
        return self.reserved

    async def save_code(
        self, *, user_id: uuid.UUID, digest: str, locale: str | None, ttl_seconds: int
    ) -> None:
        _ = ttl_seconds
        self.codes[user_id] = (digest, locale)

    async def delete_cooldown(self, *, user_id: uuid.UUID) -> None:
        self.deleted_cooldowns.append(user_id)

    async def probe(self) -> None:
        self.probes += 1
        if self.probe_error is not None:
            raise self.probe_error


class _Dispatcher:
    def __init__(self) -> None:
        self.reset_code_calls: list[dict[str, Any]] = []
        self.changed_calls: list[dict[str, Any]] = []

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        self.reset_code_calls.append(
            {
                "to": to,
                "locale": locale,
                "code": code,
                "expires_minutes": expires_minutes,
            }
        )

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        self.changed_calls.append({"to": to, "locale": locale})


class _Audit:
    def __init__(self, *, user: PasswordResetUser | None = None) -> None:
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


def _identity(status: UserStatus = UserStatus.ACTIVE) -> ResolvedIdentity:
    return ResolvedIdentity(
        user_id=_USER_ID,
        company_id=_COMPANY_ID,
        status=status,
        password_hash=None,
    )


def _command(**overrides: Any) -> PasswordRecoveryCommand:
    values: dict[str, Any] = {
        "email": _EMAIL,
        "phone_e164": None,
        "turnstile_token": _TOKEN,
        "remote_ip": _IP,
        "locale": "pt-BR",
    }
    values.update(overrides)
    return PasswordRecoveryCommand(**values)


class _PhoneResolver:
    def __init__(self, owner: VerifiedPhoneOwner | None) -> None:
        self.owner = owner
        self.calls: list[str] = []

    async def resolve(self, *, phone_e164: str) -> VerifiedPhoneOwner | None:
        self.calls.append(phone_e164)
        return self.owner


class _SmsDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        self.calls.append((to_phone, locale))


def _usecase(
    *,
    verifier: _Verifier | None,
    limiter: _Limiter,
    resolver: _Resolver | None = None,
    phone_resolver: _PhoneResolver | None = None,
    store: _Store | None = None,
    dispatcher: _Dispatcher | None = None,
    sms_dispatcher: _SmsDispatcher | None = None,
    audit: _Audit | None = None,
) -> tuple[RequestPasswordRecovery, _Store, _Dispatcher, _Audit, _Resolver]:
    store = store or _Store()
    dispatcher = dispatcher or _Dispatcher()
    audit = audit or _Audit()
    resolver = resolver or _Resolver(_identity())
    usecase = RequestPasswordRecovery(
        verifier=cast(Any, verifier),
        limiter=cast(Any, limiter),
        resolver=cast(Any, resolver),
        phone_resolver=cast(Any, phone_resolver or _PhoneResolver(None)),
        store=cast(Any, store),
        email_dispatcher=cast(Any, dispatcher),
        sms_dispatcher=cast(Any, sms_dispatcher or _SmsDispatcher()),
        audit=cast(Any, audit),
        pepper=_PEPPER,
        code_ttl_seconds=600,
        resend_cooldown_seconds=60,
    )
    return usecase, store, dispatcher, audit, resolver


async def test_conta_ativa_gera_codigo_e_enfileira_email() -> None:
    verifier = _Verifier(True)
    limiter = _Limiter()
    usecase, store, dispatcher, audit, resolver = _usecase(verifier=verifier, limiter=limiter)

    await usecase.execute(_command())

    assert limiter.calls == [
        ("ip", _IP),
        ("identifier", "email", _EMAIL),
    ]
    assert verifier.calls == [(_TOKEN, _IP)]
    assert resolver.calls == [_EMAIL]
    assert store.reserve_calls == [(_USER_ID, 60)]
    digest, locale = store.codes[_USER_ID]
    assert len(digest) == 64
    assert _EMAIL not in digest
    assert locale == "pt-BR"
    assert len(dispatcher.reset_code_calls) == 1
    call = dispatcher.reset_code_calls[0]
    assert call["to"] == _EMAIL
    assert call["locale"] == "pt-BR"
    assert call["expires_minutes"] == 10
    assert len(call["code"]) == 6
    assert call["code"].isdigit()
    assert call["code"] not in digest
    assert audit.events == [("auth.password_reset_requested", {"channel": "email"})]


async def test_turnstile_falso_impede_identificador_e_envio() -> None:
    verifier = _Verifier(False)
    limiter = _Limiter()
    usecase, store, dispatcher, _, resolver = _usecase(verifier=verifier, limiter=limiter)

    with pytest.raises(AntiBotVerificationError):
        await usecase.execute(_command())

    assert limiter.calls == [("ip", _IP)]
    assert verifier.calls == [(_TOKEN, _IP)]
    assert resolver.calls == []
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []


async def test_verificador_ausente_falha_fechado() -> None:
    limiter = _Limiter()
    usecase, store, dispatcher, _, resolver = _usecase(verifier=None, limiter=limiter)

    with pytest.raises(AntiBotVerificationError):
        await usecase.execute(_command())

    assert limiter.calls == [("ip", _IP)]
    assert resolver.calls == []
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []


async def test_falha_do_ip_nao_chama_turnstile() -> None:
    error = RuntimeError("rate limit indisponivel")
    verifier = _Verifier(True)
    limiter = _Limiter(ip_error=error)
    usecase, _, _, _, resolver = _usecase(verifier=verifier, limiter=limiter)

    with pytest.raises(RuntimeError, match="rate limit indisponivel"):
        await usecase.execute(_command())

    assert verifier.calls == []
    assert resolver.calls == []
    assert limiter.calls == [("ip", _IP)]


async def test_falha_do_identificador_impede_resolucao() -> None:
    error = RuntimeError("limite por identificador")
    verifier = _Verifier(True)
    limiter = _Limiter(identifier_error=error)
    usecase, _, _, _, resolver = _usecase(verifier=verifier, limiter=limiter)

    with pytest.raises(RuntimeError, match="limite por identificador"):
        await usecase.execute(_command())

    assert verifier.calls == [(_TOKEN, _IP)]
    assert resolver.calls == []
    assert limiter.calls == [
        ("ip", _IP),
        ("identifier", "email", _EMAIL),
    ]


@pytest.mark.parametrize(
    "command",
    [
        _command(email=None, phone_e164=None),
        _command(email=_EMAIL, phone_e164="+5511999999999"),
    ],
)
async def test_xor_defensivo_no_caso_de_uso(command: PasswordRecoveryCommand) -> None:
    verifier = _Verifier(True)
    limiter = _Limiter()
    usecase, store, dispatcher, _, resolver = _usecase(verifier=verifier, limiter=limiter)

    with pytest.raises(InvalidPasswordRecoveryRequestError):
        await usecase.execute(command)

    assert verifier.calls == []
    assert limiter.calls == []
    assert resolver.calls == []
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []


async def test_conta_inexistente_responde_generico_sem_envio() -> None:
    resolver = _Resolver(None)
    store = _Store()
    usecase, _, dispatcher, audit, _ = _usecase(
        verifier=_Verifier(True), limiter=_Limiter(), resolver=resolver, store=store
    )

    await usecase.execute(_command())

    assert store.probes == 1
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []
    assert audit.events == []


async def test_conta_inativa_responde_generico_e_audita_sem_pii() -> None:
    resolver = _Resolver(_identity(UserStatus.SUSPENDED))
    store = _Store()
    usecase, _, dispatcher, audit, _ = _usecase(
        verifier=_Verifier(True), limiter=_Limiter(), resolver=resolver, store=store
    )

    await usecase.execute(_command())

    assert store.probes == 1
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []
    assert audit.events == [
        (
            "auth.password_reset_failed",
            {"channel": "email", "stage": "request", "reason": "inactive"},
        )
    ]
    assert _EMAIL not in str(audit.events)


async def test_cooldown_ativo_nao_gera_novo_codigo() -> None:
    store = _Store(reserved=False)
    usecase, _, dispatcher, _, _ = _usecase(
        verifier=_Verifier(True), limiter=_Limiter(), store=store
    )

    await usecase.execute(_command())

    assert store.reserve_calls == [(_USER_ID, 60)]
    assert store.codes == {}
    assert dispatcher.reset_code_calls == []


async def test_novo_pedido_sobrescreve_codigo_anterior() -> None:
    store = _Store()
    usecase, _, dispatcher, _, _ = _usecase(
        verifier=_Verifier(True), limiter=_Limiter(), store=store
    )

    await usecase.execute(_command())
    first_digest = store.codes[_USER_ID][0]
    await usecase.execute(_command())

    assert store.codes[_USER_ID][0] != first_digest
    assert len(dispatcher.reset_code_calls) == 2


async def test_telefone_nao_aciona_canal_email() -> None:
    resolver = _Resolver(_identity())
    dispatcher = _Dispatcher()
    usecase, _, _, _, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        resolver=resolver,
        dispatcher=dispatcher,
    )

    await usecase.execute(_command(email=None, phone_e164="+5511999999999"))

    assert resolver.calls == []
    assert dispatcher.reset_code_calls == []


async def test_redis_indisponivel_vira_503_generico() -> None:
    store = _Store(probe_error=PasswordRecoveryStoreError("fora"))
    usecase, _, _, _, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        resolver=_Resolver(None),
        store=store,
    )

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await usecase.execute(_command())
    assert "redis" not in str(excinfo.value).lower()


async def test_erro_do_resolver_nao_vaza_e_responde_generico() -> None:
    resolver = _Resolver(None, error=RuntimeError("db fora"))
    store = _Store()
    usecase, _, dispatcher, _, _ = _usecase(
        verifier=_Verifier(True), limiter=_Limiter(), resolver=resolver, store=store
    )

    await usecase.execute(_command())

    assert store.probes == 1
    assert dispatcher.reset_code_calls == []


async def test_logs_nao_contem_pii_no_request() -> None:
    usecase, _, _, _, _ = _usecase(
        verifier=_Verifier(False), limiter=_Limiter(), resolver=_Resolver(_identity())
    )

    with capture_logs() as logs, pytest.raises(AntiBotVerificationError):
        await usecase.execute(_command())

    rendered = str(logs)
    assert _EMAIL not in rendered
    assert _TOKEN not in rendered
    assert _IP not in rendered


def _reset_user(status: UserStatus = UserStatus.ACTIVE) -> PasswordResetUser:
    return PasswordResetUser(
        user_id=_USER_ID,
        company_id=_COMPANY_ID,
        email=_EMAIL,
        password_hash=None,
        status=status,
    )


async def test_request_sms_ativo_enfileira_e_audita() -> None:
    sms = _SmsDispatcher()
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, store, _email, audit, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        phone_resolver=_PhoneResolver(owner),
        sms_dispatcher=sms,
        audit=_Audit(user=_reset_user()),
    )

    await usecase.execute(_command(email=None, phone_e164="+5511999991234"))

    assert sms.calls == [("+5511999991234", "pt-BR")]
    assert store.reserve_calls == [(_USER_ID, 60)]
    assert audit.events == [("auth.password_reset_requested", {"channel": "sms"})]


async def test_request_sms_sem_vinculo_nao_envia() -> None:
    sms = _SmsDispatcher()
    usecase, store, _, _, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        phone_resolver=_PhoneResolver(None),
        sms_dispatcher=sms,
    )

    await usecase.execute(_command(email=None, phone_e164="+5511999991234"))

    assert sms.calls == []
    assert store.probes == 1


async def test_request_sms_inativo_nao_envia_e_audita() -> None:
    sms = _SmsDispatcher()
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, _, _, audit, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        phone_resolver=_PhoneResolver(owner),
        sms_dispatcher=sms,
        audit=_Audit(user=_reset_user(UserStatus.SUSPENDED)),
    )

    await usecase.execute(_command(email=None, phone_e164="+5511999991234"))

    assert sms.calls == []
    assert audit.events[0][0] == "auth.password_reset_failed"
    assert audit.events[0][1]["channel"] == "sms"


async def test_request_sms_cooldown_nao_envia() -> None:
    sms = _SmsDispatcher()
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, _, _, _, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        phone_resolver=_PhoneResolver(owner),
        sms_dispatcher=sms,
        store=_Store(reserved=False),
        audit=_Audit(user=_reset_user()),
    )

    await usecase.execute(_command(email=None, phone_e164="+5511999991234"))

    assert sms.calls == []


async def test_request_sms_logs_sem_telefone() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, _, _, _, _ = _usecase(
        verifier=_Verifier(True),
        limiter=_Limiter(),
        phone_resolver=_PhoneResolver(owner),
        audit=_Audit(user=_reset_user(UserStatus.SUSPENDED)),
    )

    with capture_logs() as logs:
        await usecase.execute(_command(email=None, phone_e164="+5511999991234"))

    assert "+5511999991234" not in str(logs)
