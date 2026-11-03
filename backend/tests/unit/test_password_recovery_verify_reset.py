"""Testes de verify/reset da recuperacao de conta por e-mail (Fase 3)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from structlog.testing import capture_logs

from app.core.errors import ServiceUnavailableError
from app.modules.identity.application.errors import (
    PasswordRecoveryCodeError,
    PasswordRecoveryStoreError,
    PasswordResetTokenError,
    PasswordReuseError,
)
from app.modules.identity.application.password_recovery import (
    ResetPassword,
    VerifyPasswordRecoveryCode,
    recovery_code_digest,
    reset_token_hash,
)
from app.modules.identity.application.ports import (
    PasswordRecoveryCodeState,
    PasswordResetTokenData,
    PasswordResetUser,
    ResolvedIdentity,
    VerifiedPhoneOwner,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.errors import WeakPasswordError

_EMAIL = "user@example.com"
_CODE = "123456"
_PEPPER = "pepper-de-teste"
_USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_COMPANY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
_IP = "203.0.113.7"
_NEW_PASSWORD = "NovaSenha@123"


class _Limiter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Any, ...]] = []

    async def check_verify_ip(self, ip: str) -> None:
        self.calls.append(("verify_ip", ip))
        if self.error is not None:
            raise self.error

    async def check_verify_identifier(self, *, kind: str, value: str) -> None:
        self.calls.append(("verify_identifier", kind, value))
        if self.error is not None:
            raise self.error

    async def check_reset_ip(self, ip: str) -> None:
        self.calls.append(("reset_ip", ip))
        if self.error is not None:
            raise self.error


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
        state: PasswordRecoveryCodeState | None = None,
        consume_code_result: bool = True,
        failed_attempts: int = 1,
        token_data: PasswordResetTokenData | None = None,
        load_error: Exception | None = None,
        sms_attempts: int = 0,
        sms_record_result: int = 1,
    ) -> None:
        self.state = state
        self.consume_code_result = consume_code_result
        self.failed_attempts = failed_attempts
        self.token_data = token_data
        self.load_error = load_error
        self.sms_attempts = sms_attempts
        self.sms_record_result = sms_record_result
        self.consume_reset_calls = 0
        self.loaded_user_ids: list[uuid.UUID] = []
        self.consume_code_calls: list[tuple[uuid.UUID, str]] = []
        self.failed_attempt_calls: list[tuple[uuid.UUID, int]] = []
        self.sms_attempt_calls: list[uuid.UUID] = []
        self.saved_tokens: list[dict[str, Any]] = []
        self.deleted_codes: list[uuid.UUID] = []
        self.deleted_cooldowns: list[uuid.UUID] = []

    async def load_code(self, *, user_id: uuid.UUID) -> PasswordRecoveryCodeState | None:
        self.loaded_user_ids.append(user_id)
        if self.load_error is not None:
            raise self.load_error
        return self.state

    async def consume_code(self, *, user_id: uuid.UUID, digest: str) -> bool:
        self.consume_code_calls.append((user_id, digest))
        return self.consume_code_result

    async def record_failed_attempt(self, *, user_id: uuid.UUID, max_attempts: int) -> int:
        self.failed_attempt_calls.append((user_id, max_attempts))
        return self.failed_attempts

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
        self.saved_tokens.append(
            {
                "token_hash": token_hash,
                "user_id": user_id,
                "company_id": company_id,
                "locale": locale,
                "channel": channel,
                "ttl_seconds": ttl_seconds,
            }
        )

    async def get_sms_attempts(self, *, user_id: uuid.UUID) -> int:
        self.sms_attempt_calls.append(user_id)
        return self.sms_attempts

    async def record_sms_failed_attempt(
        self, *, user_id: uuid.UUID, max_attempts: int, ttl_seconds: int
    ) -> int:
        _ = (max_attempts, ttl_seconds)
        self.sms_attempt_calls.append(user_id)
        self.sms_attempts = self.sms_record_result
        return self.sms_record_result

    async def clear_sms_attempts(self, *, user_id: uuid.UUID) -> None:
        _ = user_id
        self.sms_attempts = 0

    async def consume_reset_token(self, *, token_hash: str) -> PasswordResetTokenData | None:
        _ = token_hash
        self.consume_reset_calls += 1
        current = self.token_data
        self.token_data = None
        return current

    async def delete_code(self, *, user_id: uuid.UUID) -> None:
        self.deleted_codes.append(user_id)

    async def delete_cooldown(self, *, user_id: uuid.UUID) -> None:
        self.deleted_cooldowns.append(user_id)

    async def probe(self) -> None:
        return None


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


class _Repository:
    def __init__(
        self,
        user: PasswordResetUser | None,
        *,
        updated: bool = True,
        credential_epoch: int = 7,
        update_error: Exception | None = None,
    ) -> None:
        self.user = user
        self.updated = updated
        self.credential_epoch = credential_epoch
        self.update_error = update_error
        self.get_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.events: list[tuple[str, dict[str, str]]] = []

    async def get_user(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PasswordResetUser | None:
        self.get_calls.append((company_id, user_id))
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
        self.update_calls.append(
            {
                "company_id": company_id,
                "user_id": user_id,
                "password_hash": password_hash,
                "audit_action": audit_action,
                "audit_details": audit_details,
            }
        )
        if self.update_error is not None:
            raise self.update_error
        return self.credential_epoch if self.updated else None

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
    def __init__(self, *, reuse: bool = False) -> None:
        self.reuse = reuse
        self.verify_calls: list[tuple[str, str]] = []
        self.hash_calls: list[str] = []

    def verify(self, password: str, password_hash: str) -> bool:
        self.verify_calls.append((password, password_hash))
        return self.reuse

    def hash(self, password: str) -> str:
        self.hash_calls.append(password)
        return f"argon2id:{password}"


class _Dispatcher:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.changed_calls: list[dict[str, Any]] = []

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        _ = (to, locale, code, expires_minutes)

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        if self.error is not None:
            raise self.error
        self.changed_calls.append({"to": to, "locale": locale})


class _Revoker:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[uuid.UUID, uuid.UUID, int]] = []

    async def revoke_all_for_user(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, credential_epoch: int
    ) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append((user_id, company_id, credential_epoch))


def _identity(status: UserStatus = UserStatus.ACTIVE) -> ResolvedIdentity:
    return ResolvedIdentity(
        user_id=_USER_ID,
        company_id=_COMPANY_ID,
        status=status,
        password_hash="hash-antigo",
    )


def _state(*, attempts: int = 0) -> PasswordRecoveryCodeState:
    return PasswordRecoveryCodeState(
        digest=recovery_code_digest(pepper=_PEPPER, user_id=_USER_ID, code=_CODE),
        attempts=attempts,
        locale="pt-BR",
    )


def _token_data() -> PasswordResetTokenData:
    return PasswordResetTokenData(user_id=_USER_ID, company_id=_COMPANY_ID, locale="pt-BR")


def _user(status: UserStatus = UserStatus.ACTIVE) -> PasswordResetUser:
    return PasswordResetUser(
        user_id=_USER_ID,
        company_id=_COMPANY_ID,
        email=_EMAIL,
        password_hash="hash-antigo",
        status=status,
    )


class _PhoneResolver:
    def __init__(self, owner: VerifiedPhoneOwner | None) -> None:
        self.owner = owner
        self.calls: list[str] = []

    async def resolve(self, *, phone_e164: str) -> VerifiedPhoneOwner | None:
        self.calls.append(phone_e164)
        return self.owner


class _PhoneService:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.calls: list[tuple[str, str]] = []

    async def check(self, *, phone_e164: str, code: str) -> bool:
        self.calls.append((phone_e164, code))
        return self.approved

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        _ = (phone_e164, locale)
        return True


def _verify_usecase(
    *,
    resolver: _Resolver | None = None,
    phone_resolver: _PhoneResolver | None = None,
    phone_service: _PhoneService | None = None,
    store: _Store | None = None,
    limiter: _Limiter | None = None,
    audit: _Audit | None = None,
) -> tuple[VerifyPasswordRecoveryCode, _Store, _Audit]:
    store = store or _Store(state=_state())
    audit = audit or _Audit()
    usecase = VerifyPasswordRecoveryCode(
        resolver=cast(Any, resolver or _Resolver(_identity())),
        phone_resolver=cast(Any, phone_resolver or _PhoneResolver(None)),
        phone_service=cast(Any, phone_service),
        store=cast(Any, store),
        limiter=cast(Any, limiter or _Limiter()),
        audit=cast(Any, audit),
        pepper=_PEPPER,
        reset_token_ttl_seconds=600,
        max_attempts=5,
        code_ttl_seconds=600,
    )
    return usecase, store, audit


def _reset_usecase(
    *,
    store: _Store,
    repository: _Repository,
    hasher: _Hasher | None = None,
    dispatcher: _Dispatcher | None = None,
    revoker: _Revoker | None = None,
    limiter: _Limiter | None = None,
) -> ResetPassword:
    return ResetPassword(
        store=cast(Any, store),
        repository=cast(Any, repository),
        hasher=cast(Any, hasher or _Hasher()),
        email_dispatcher=cast(Any, dispatcher or _Dispatcher()),
        limiter=cast(Any, limiter or _Limiter()),
        session_revoker=cast(Any, revoker) if revoker is not None else None,
    )


async def test_verify_feliz_emite_token_e_consome_codigo() -> None:
    usecase, store, audit = _verify_usecase()

    result = await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)

    assert result.reset_token
    assert result.expires_in == 600
    assert store.consume_code_calls == [
        (_USER_ID, recovery_code_digest(pepper=_PEPPER, user_id=_USER_ID, code=_CODE))
    ]
    assert len(store.saved_tokens) == 1
    saved = store.saved_tokens[0]
    assert saved["token_hash"] == reset_token_hash(result.reset_token)
    assert result.reset_token not in str(saved)
    assert saved["locale"] == "pt-BR"
    assert audit.events == [("auth.password_reset_verified", {"channel": "email"})]


async def test_verify_codigo_errado_incrementa_tentativas() -> None:
    usecase, store, audit = _verify_usecase(store=_Store(state=_state(), failed_attempts=2))

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email=_EMAIL, code="000000", remote_ip=_IP)

    assert store.failed_attempt_calls == [(_USER_ID, 5)]
    assert store.consume_code_calls == []
    assert audit.events == [
        (
            "auth.password_reset_failed",
            {"channel": "email", "stage": "verify", "reason": "wrong_code"},
        )
    ]


async def test_verify_tentativas_esgotadas_audita_max_attempts() -> None:
    usecase, store, audit = _verify_usecase(
        store=_Store(state=_state(attempts=4), failed_attempts=5)
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email=_EMAIL, code="000000", remote_ip=_IP)

    assert store.failed_attempt_calls == [(_USER_ID, 5)]
    assert audit.events[0][1]["reason"] == "max_attempts"


async def test_verify_codigo_expirado_sem_envio() -> None:
    usecase, store, audit = _verify_usecase(store=_Store(state=None))

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)

    assert store.failed_attempt_calls == []
    assert store.consume_code_calls == []
    assert audit.events[0][1]["reason"] == "expired"


async def test_verify_conta_inativa_invalida_codigo() -> None:
    usecase, store, audit = _verify_usecase(resolver=_Resolver(_identity(UserStatus.SUSPENDED)))

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)

    assert store.deleted_codes == [_USER_ID]
    assert store.saved_tokens == []
    assert audit.events[0][1]["reason"] == "inactive"


async def test_verify_email_inexistente_e_generico() -> None:
    usecase, store, audit = _verify_usecase(resolver=_Resolver(None), store=_Store(state=None))

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email="naoexiste@example.com", code=_CODE, remote_ip=_IP)

    assert store.saved_tokens == []
    assert audit.events == []


async def test_verify_reuso_concorrente_do_codigo_falha() -> None:
    usecase, store, _ = _verify_usecase(store=_Store(state=_state(), consume_code_result=False))

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)

    assert store.saved_tokens == []


async def test_verify_redis_fora_vira_503_generico() -> None:
    usecase, _, _ = _verify_usecase(
        store=_Store(state=_state(), load_error=PasswordRecoveryStoreError("fora"))
    )

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)
    assert "redis" not in str(excinfo.value).lower()


async def test_verify_rate_limit_falho_propaga() -> None:
    usecase, store, _ = _verify_usecase(limiter=_Limiter(RuntimeError("limite")))
    with pytest.raises(RuntimeError, match="limite"):
        await usecase.execute(email=_EMAIL, code=_CODE, remote_ip=_IP)
    assert store.consume_code_calls == []


async def test_reset_feliz_atualiza_hash_auditoria_e_avisa() -> None:
    store = _Store(token_data=_token_data())
    repository = _Repository(_user())
    hasher = _Hasher()
    dispatcher = _Dispatcher()
    revoker = _Revoker()
    usecase = _reset_usecase(
        store=store,
        repository=repository,
        hasher=hasher,
        dispatcher=dispatcher,
        revoker=revoker,
    )

    await usecase.execute(reset_token="token-opaco", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert hasher.verify_calls == [(_NEW_PASSWORD, "hash-antigo")]
    assert hasher.hash_calls == [_NEW_PASSWORD]
    assert repository.update_calls[0]["password_hash"] == f"argon2id:{_NEW_PASSWORD}"
    assert repository.update_calls[0]["audit_action"] == "auth.password_reset_completed"
    assert revoker.calls == [(_USER_ID, _COMPANY_ID, 7)]
    assert dispatcher.changed_calls == [{"to": _EMAIL, "locale": "pt-BR"}]


async def test_reset_senha_fraca_nao_consome_token() -> None:
    store = _Store(token_data=_token_data())
    usecase = _reset_usecase(store=store, repository=_Repository(_user()))

    with pytest.raises(WeakPasswordError):
        await usecase.execute(reset_token="token", new_password="curta", remote_ip=_IP)
    assert store.consume_reset_calls == 0


async def test_reset_reuso_de_senha_e_rejeitado() -> None:
    repository = _Repository(_user())
    usecase = _reset_usecase(
        store=_Store(token_data=_token_data()),
        repository=repository,
        hasher=_Hasher(reuse=True),
    )

    with pytest.raises(PasswordReuseError):
        await usecase.execute(reset_token="token", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert repository.update_calls == []
    assert repository.events[0][1]["reason"] == "password_reuse"


async def test_reset_token_invalido_e_generico() -> None:
    repository = _Repository(_user())
    usecase = _reset_usecase(store=_Store(token_data=None), repository=repository)

    with pytest.raises(PasswordResetTokenError):
        await usecase.execute(reset_token="invalido", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert repository.update_calls == []


async def test_reset_token_reutilizado_so_um_vence() -> None:
    store = _Store(token_data=_token_data())
    repository = _Repository(_user())
    usecase = _reset_usecase(store=store, repository=repository)

    await usecase.execute(reset_token="mesmo-token", new_password=_NEW_PASSWORD, remote_ip=_IP)
    with pytest.raises(PasswordResetTokenError):
        await usecase.execute(reset_token="mesmo-token", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert len(repository.update_calls) == 1


async def test_reset_conta_inativa_falha_sem_update() -> None:
    repository = _Repository(_user(UserStatus.SUSPENDED))
    usecase = _reset_usecase(store=_Store(token_data=_token_data()), repository=repository)

    with pytest.raises(PasswordResetTokenError):
        await usecase.execute(reset_token="token", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert repository.update_calls == []
    assert repository.events[0][1]["reason"] == "missing_or_inactive"


async def test_reset_falha_de_update_vira_503() -> None:
    repository = _Repository(_user(), update_error=RuntimeError("db fora"))
    usecase = _reset_usecase(store=_Store(token_data=_token_data()), repository=repository)

    with pytest.raises(ServiceUnavailableError):
        await usecase.execute(reset_token="token", new_password=_NEW_PASSWORD, remote_ip=_IP)


async def test_reset_falha_de_revogador_nao_desfaz_senha() -> None:
    repository = _Repository(_user())
    usecase = _reset_usecase(
        store=_Store(token_data=_token_data()),
        repository=repository,
        revoker=_Revoker(error=RuntimeError("redis fora")),
    )

    await usecase.execute(reset_token="token", new_password=_NEW_PASSWORD, remote_ip=_IP)

    assert len(repository.update_calls) == 1


async def test_reset_logs_nao_contem_pii_nem_senha() -> None:
    repository = _Repository(_user())
    usecase = _reset_usecase(
        store=_Store(token_data=_token_data()),
        repository=repository,
        dispatcher=_Dispatcher(error=RuntimeError("broker fora")),
    )

    with capture_logs() as logs:
        await usecase.execute(
            reset_token="token-secreto", new_password=_NEW_PASSWORD, remote_ip=_IP
        )

    rendered = str(logs)
    assert _EMAIL not in rendered
    assert _NEW_PASSWORD not in rendered
    assert "token-secreto" not in rendered


async def test_reset_senha_acima_de_128_nao_consome_token() -> None:
    store = _Store(token_data=_token_data())
    usecase = _reset_usecase(store=store, repository=_Repository(_user()))

    with pytest.raises(WeakPasswordError):
        await usecase.execute(reset_token="token", new_password="a" * 129, remote_ip=_IP)
    assert store.consume_reset_calls == 0


_PHONE = "+5511999991234"


async def test_verify_sms_feliz_emite_token_channel_sms() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    service = _PhoneService(approved=True)
    store = _Store(state=None)
    usecase, _, audit = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=service,
        store=store,
        audit=_Audit(user=_user()),
    )

    result = await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert result.reset_token
    assert service.calls == [(_PHONE, _CODE)]
    assert store.saved_tokens[0]["channel"] == "sms"
    assert store.saved_tokens[0]["locale"] is None
    assert audit.events[-1] == ("auth.password_reset_verified", {"channel": "sms"})


async def test_verify_sms_sem_conta_chama_twilio_e_falha_generico() -> None:
    service = _PhoneService(approved=True)
    store = _Store(state=None)
    usecase, _, _ = _verify_usecase(
        phone_resolver=_PhoneResolver(None),
        phone_service=service,
        store=store,
        audit=_Audit(user=None),
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert service.calls == [(_PHONE, _CODE)]
    assert store.saved_tokens == []


async def test_verify_sms_inativo_nao_emite_token() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, store, _ = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=_PhoneService(approved=True),
        store=_Store(state=None),
        audit=_Audit(user=_user(UserStatus.SUSPENDED)),
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert store.saved_tokens == []


async def test_verify_sms_codigo_errado_incrementa_tentativas() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    store = _Store(state=None, sms_record_result=2)
    usecase, _, audit = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=_PhoneService(approved=False),
        store=store,
        audit=_Audit(user=_user()),
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code="000000", remote_ip=_IP)

    assert store.sms_attempt_calls == [_USER_ID, _USER_ID]
    assert audit.events[-1][1]["reason"] == "wrong_code"


async def test_verify_sms_tentativas_esgotadas_nao_chama_token() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, store, audit = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=_PhoneService(approved=True),
        store=_Store(state=None, sms_attempts=5),
        audit=_Audit(user=_user()),
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert store.saved_tokens == []
    assert audit.events[-1][1]["reason"] == "max_attempts"


async def test_verify_sms_twilio_ausente_falha_generico() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, store, _ = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=None,
        store=_Store(state=None),
        audit=_Audit(user=_user()),
    )

    with pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    assert store.saved_tokens == []


async def test_verify_sms_logs_sem_telefone_ou_codigo() -> None:
    owner = VerifiedPhoneOwner(user_id=_USER_ID, company_id=_COMPANY_ID)
    usecase, _, _ = _verify_usecase(
        phone_resolver=_PhoneResolver(owner),
        phone_service=_PhoneService(approved=False),
        store=_Store(state=None),
        audit=_Audit(user=_user()),
    )

    with capture_logs() as logs, pytest.raises(PasswordRecoveryCodeError):
        await usecase.execute(phone_e164=_PHONE, code=_CODE, remote_ip=_IP)

    rendered = str(logs)
    assert _PHONE not in rendered
    assert _CODE not in rendered


async def test_reset_token_de_sms_revoga_e_audita_channel_sms() -> None:
    token_data = PasswordResetTokenData(
        user_id=_USER_ID,
        company_id=_COMPANY_ID,
        locale=None,
        channel="sms",
    )
    repository = _Repository(_user())
    revoker = _Revoker()
    usecase = _reset_usecase(
        store=_Store(token_data=token_data),
        repository=repository,
        revoker=revoker,
    )

    await usecase.execute(reset_token="token-sms", new_password="NovaSenha@123", remote_ip=_IP)

    assert revoker.calls == [(_USER_ID, _COMPANY_ID, 7)]
    assert repository.update_calls[0]["audit_details"] == {"channel": "sms"}
