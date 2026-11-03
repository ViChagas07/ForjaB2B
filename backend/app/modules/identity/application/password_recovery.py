"""Recuperacao de conta: request, verify e reset por e-mail (Fase 3).

Regras de seguranca aplicadas aqui:
- respostas de request sao sempre genericas (exista/esteja ativa a conta ou nao);
- codigo de 6 digitos SO existe em claro no broker Celery, nunca em
  PostgreSQL/log/auditoria; o Redis guarda apenas HMAC(PEPPER, user_id + code);
- comparacao do codigo com ``hmac.compare_digest`` e consumo atomico;
- reset_token opaco tem apenas o SHA-256 no Redis e e consumido com GETDEL;
- o UPDATE de senha roda com o tenant do token (RLS), nunca com bypass.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, NoReturn

from app.application.rate_limit import (
    DailyQuotaStore,
    RateLimitBackendError,
    RateLimitClass,
    RateLimitDecision,
    RateLimiter,
    pseudonymous_key,
)
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.core.logging import get_logger
from app.modules.identity.application.errors import (
    AntiBotVerificationError,
    InvalidPasswordRecoveryRequestError,
    PasswordRecoveryCodeError,
    PasswordRecoveryStoreError,
    PasswordResetTokenError,
    PasswordReuseError,
)
from app.modules.identity.application.ports import (
    PasswordHasher,
    PasswordRecoveryCodeState,
    PasswordRecoveryEmailDispatcher,
    PasswordRecoverySmsDispatcher,
    PasswordRecoveryStore,
    PasswordResetRepository,
    PasswordResetSessionRevoker,
    PasswordResetTokenData,
    PasswordResetUser,
    PhoneVerificationService,
    ResolvedIdentity,
    TurnstileVerifier,
    UserIdentityResolver,
    VerifiedPhoneOwner,
    VerifiedPhoneResolver,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.rules import validate_password_strength

_logger = get_logger(__name__)

IdentifierKind = Literal["email", "phone"]

_GENERIC_UNAVAILABLE = "Servico temporariamente indisponivel."
_RESET_TOKEN_BYTES = 32
_CODE_MODULUS = 1_000_000
_DUMMY_DIGEST = "0" * 64


@dataclass(frozen=True, kw_only=True)
class PasswordRecoveryCommand:
    """Pedido normalizado de recuperacao (exatamente um identificador)."""

    email: str | None
    phone_e164: str | None
    turnstile_token: str
    remote_ip: str
    locale: str | None = None


@dataclass(frozen=True, kw_only=True)
class PasswordRecoveryVerified:
    """reset_token opaco devolvido apos a verificacao do codigo."""

    reset_token: str
    expires_in: int


def generate_recovery_code() -> str:
    """Gera 6 digitos uniformes com secrets (nunca random)."""
    return f"{secrets.randbelow(_CODE_MODULUS):06d}"


def recovery_code_digest(*, pepper: str, user_id: uuid.UUID, code: str) -> str:
    """HMAC-SHA256(PEPPER, user_id + codigo); o unico formato persistido."""
    message = f"{user_id}:{code}".encode()
    return hmac.new(pepper.encode(), message, hashlib.sha256).hexdigest()


def reset_token_hash(token: str) -> str:
    """SHA-256 do reset_token para uso como chave no Redis."""
    return hashlib.sha256(token.encode()).hexdigest()


class PasswordRecoveryLimiter:
    """Baldes dedicados de recuperacao: request, verify e reset."""

    def __init__(
        self,
        *,
        limiter: RateLimiter,
        daily_store: DailyQuotaStore,
        secret: str,
        daily_limit: int,
        enabled: bool = True,
        daily_ttl_seconds: int = 86_400,
    ) -> None:
        self._limiter = limiter
        self._daily_store = daily_store
        self._secret = secret
        self._daily_limit = daily_limit
        self._enabled = enabled
        self._daily_ttl_seconds = daily_ttl_seconds

    async def check_ip(self, ip: str) -> None:
        """Limita o request por IP antes de qualquer chamada externa."""
        if not self._enabled:
            return
        await self._consume_bucket(
            rate_class=RateLimitClass.PASSWORD_RECOVERY,
            identity=f"ip:{ip}",
            scope="ip",
        )

    async def check_identifier(self, *, kind: IdentifierKind, value: str) -> None:
        """Limita o request por identificador (HMAC) e aplica o teto diario."""
        if not self._enabled:
            return
        digest = pseudonymous_key(self._secret, f"{kind}:{value}")
        await self._consume_bucket(
            rate_class=RateLimitClass.PASSWORD_RECOVERY_IDENTIFIER,
            identity=f"{kind}:{digest}",
            scope="identifier",
        )
        try:
            decision = await self._daily_store.consume(
                key=f"rl:password_recovery:daily:{kind}:{digest}",
                limit=self._daily_limit,
                ttl_seconds=self._daily_ttl_seconds,
            )
        except RateLimitBackendError as exc:
            _logger.warning(
                "password_recovery_rate_limit_unavailable",
                scope="daily",
                error_type=type(exc).__name__,
            )
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
        if not decision.allowed:
            _logger.info("password_recovery_rate_limited", scope="daily")
            raise RateLimitExceededError(
                retry_after_seconds=decision.retry_after_seconds,
                limit=decision.limit,
                remaining=decision.remaining,
                reset_after_seconds=decision.retry_after_seconds,
            )

    async def check_verify_ip(self, ip: str) -> None:
        """Limita as tentativas de verificacao por IP."""
        if not self._enabled:
            return
        await self._consume_bucket(
            rate_class=RateLimitClass.PASSWORD_RECOVERY_VERIFY_IP,
            identity=f"verify-ip:{ip}",
            scope="verify_ip",
        )

    async def check_verify_identifier(self, *, kind: IdentifierKind, value: str) -> None:
        """Limita as tentativas por identificador (HMAC)."""
        if not self._enabled:
            return
        digest = pseudonymous_key(self._secret, f"verify:{kind}:{value}")
        await self._consume_bucket(
            rate_class=RateLimitClass.PASSWORD_RECOVERY_VERIFY_IDENTIFIER,
            identity=f"verify-{kind}:{digest}",
            scope="verify_identifier",
        )

    async def check_reset_ip(self, ip: str) -> None:
        """Limita o reset por IP (mesma policy do request, chave separada)."""
        if not self._enabled:
            return
        await self._consume_bucket(
            rate_class=RateLimitClass.PASSWORD_RECOVERY,
            identity=f"reset-ip:{ip}",
            scope="reset_ip",
        )

    async def _consume_bucket(
        self,
        *,
        rate_class: RateLimitClass,
        identity: str,
        scope: str,
    ) -> None:
        try:
            decision = await self._limiter.check(
                rate_class=rate_class,
                identity=identity,
                fail_closed=True,
            )
        except RateLimitBackendError as exc:
            _logger.warning(
                "password_recovery_rate_limit_unavailable",
                scope=scope,
                error_type=type(exc).__name__,
            )
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
        self._raise_if_denied(decision=decision, scope=scope)

    def _raise_if_denied(self, *, decision: RateLimitDecision, scope: str) -> None:
        if decision.allowed:
            return
        _logger.info("password_recovery_rate_limited", scope=scope)
        raise RateLimitExceededError(
            retry_after_seconds=decision.retry_after_seconds,
            limit=decision.limit,
            remaining=decision.remaining,
            reset_after_seconds=decision.reset_after_seconds,
        )


class RequestPasswordRecovery:
    """Caso de uso: pedir codigo por e-mail ou SMS."""

    def __init__(
        self,
        *,
        verifier: TurnstileVerifier | None,
        limiter: PasswordRecoveryLimiter,
        resolver: UserIdentityResolver,
        phone_resolver: VerifiedPhoneResolver,
        store: PasswordRecoveryStore,
        email_dispatcher: PasswordRecoveryEmailDispatcher,
        sms_dispatcher: PasswordRecoverySmsDispatcher,
        audit: PasswordResetRepository,
        pepper: str,
        code_ttl_seconds: int,
        resend_cooldown_seconds: int,
    ) -> None:
        self._verifier = verifier
        self._limiter = limiter
        self._resolver = resolver
        self._phone_resolver = phone_resolver
        self._store = store
        self._email_dispatcher = email_dispatcher
        self._sms_dispatcher = sms_dispatcher
        self._audit = audit
        self._pepper = pepper
        self._code_ttl_seconds = code_ttl_seconds
        self._resend_cooldown_seconds = resend_cooldown_seconds

    async def execute(self, command: PasswordRecoveryCommand) -> None:
        has_email = command.email is not None
        has_phone = command.phone_e164 is not None
        if has_email == has_phone:
            raise InvalidPasswordRecoveryRequestError()

        kind: IdentifierKind = "email" if command.email is not None else "phone"
        identifier = command.email if command.email is not None else command.phone_e164
        if identifier is None:  # pragma: no cover - defendido pelo XOR acima
            raise InvalidPasswordRecoveryRequestError()

        # IP antes do Turnstile para conter abuso barato sem consumir a cota
        # do identificador com tokens invalidos.
        await self._limiter.check_ip(command.remote_ip)

        if self._verifier is None or not await self._verifier.verify(
            token=command.turnstile_token,
            remote_ip=command.remote_ip,
        ):
            raise AntiBotVerificationError()

        await self._limiter.check_identifier(kind=kind, value=identifier)

        if command.phone_e164 is not None:
            await self._process_phone(phone=command.phone_e164, locale=command.locale)
            return

        email = command.email
        if email is None:  # pragma: no cover - defendido pelo XOR acima
            raise InvalidPasswordRecoveryRequestError()
        await self._process_email(email=email, locale=command.locale)

    async def _process_email(self, *, email: str, locale: str | None) -> None:
        try:
            identity = await self._resolver.resolve_by_email(email)
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            await self._probe_store()
            return

        # Trabalho equivalente nos dois caminhos (codigo + HMAC) para nao
        # vazar existencia/status por timing.
        code = generate_recovery_code()
        digest = recovery_code_digest(
            pepper=self._pepper,
            user_id=identity.user_id if identity is not None else uuid.uuid4(),
            code=code,
        )

        if identity is None or identity.status is not UserStatus.ACTIVE:
            await self._probe_store()
            if identity is not None:
                await self._record_audit(
                    company_id=identity.company_id,
                    user_id=identity.user_id,
                    action="auth.password_reset_failed",
                    details={
                        "channel": "email",
                        "stage": "request",
                        "reason": "inactive",
                    },
                )
            return

        try:
            reserved = await self._store.reserve_resend(
                user_id=identity.user_id,
                ttl_seconds=self._resend_cooldown_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)
        if not reserved:
            return

        try:
            await self._store.save_code(
                user_id=identity.user_id,
                digest=digest,
                locale=locale,
                ttl_seconds=self._code_ttl_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            await self._safe_delete_cooldown(identity.user_id)
            self._unavailable(exc)

        await self._record_audit(
            company_id=identity.company_id,
            user_id=identity.user_id,
            action="auth.password_reset_requested",
            details={"channel": "email"},
        )

        try:
            await self._email_dispatcher.send_reset_code(
                to=email,
                locale=locale,
                code=code,
                expires_minutes=max(1, self._code_ttl_seconds // 60),
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning(
                "password_recovery_email_enqueue_failed",
                error_type=type(exc).__name__,
            )

    async def _process_phone(self, *, phone: str, locale: str | None) -> None:
        try:
            owner = await self._phone_resolver.resolve(phone_e164=phone)
        except Exception as exc:  # noqa: BLE001 - resolver vira resposta generica
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            await self._probe_store()
            return
        if owner is None:
            await self._probe_store()
            return

        try:
            user = await self._audit.get_user(company_id=owner.company_id, user_id=owner.user_id)
        except Exception as exc:  # noqa: BLE001 - DB vira resposta generica
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            await self._probe_store()
            return
        if user is None or user.status is not UserStatus.ACTIVE:
            await self._probe_store()
            await self._record_audit(
                company_id=owner.company_id,
                user_id=owner.user_id,
                action="auth.password_reset_failed",
                details={
                    "channel": "sms",
                    "stage": "request",
                    "reason": "inactive",
                },
            )
            return

        try:
            reserved = await self._store.reserve_resend(
                user_id=owner.user_id,
                ttl_seconds=self._resend_cooldown_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)
        if not reserved:
            return

        await self._record_audit(
            company_id=owner.company_id,
            user_id=owner.user_id,
            action="auth.password_reset_requested",
            details={"channel": "sms"},
        )
        try:
            await self._sms_dispatcher.send_reset_code(to_phone=phone, locale=locale)
        except Exception as exc:  # noqa: BLE001 - enqueue best-effort
            _logger.warning(
                "password_recovery_sms_enqueue_failed",
                error_type=type(exc).__name__,
            )

    async def _probe_store(self) -> None:
        try:
            await self._store.probe()
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

    async def _safe_delete_cooldown(self, user_id: uuid.UUID) -> None:
        try:
            await self._store.delete_cooldown(user_id=user_id)
        except PasswordRecoveryStoreError:
            return

    async def _record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        try:
            await self._audit.record_audit(
                company_id=company_id,
                user_id=user_id,
                action=action,
                details=details,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning(
                "password_recovery_audit_failed",
                action=action,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _unavailable(exc: Exception) -> NoReturn:
        raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc


class VerifyPasswordRecoveryCode:
    """Caso de uso: verificar codigo e emitir reset_token de uso unico."""

    def __init__(
        self,
        *,
        resolver: UserIdentityResolver,
        phone_resolver: VerifiedPhoneResolver,
        phone_service: PhoneVerificationService | None,
        store: PasswordRecoveryStore,
        limiter: PasswordRecoveryLimiter,
        audit: PasswordResetRepository,
        pepper: str,
        reset_token_ttl_seconds: int,
        max_attempts: int,
        code_ttl_seconds: int,
    ) -> None:
        self._resolver = resolver
        self._phone_resolver = phone_resolver
        self._phone_service = phone_service
        self._store = store
        self._limiter = limiter
        self._audit = audit
        self._pepper = pepper
        self._reset_token_ttl_seconds = reset_token_ttl_seconds
        self._max_attempts = max_attempts
        self._code_ttl_seconds = code_ttl_seconds

    async def execute(
        self,
        *,
        email: str | None = None,
        phone_e164: str | None = None,
        code: str,
        remote_ip: str,
    ) -> PasswordRecoveryVerified:
        has_email = email is not None
        has_phone = phone_e164 is not None
        if has_email == has_phone:
            raise InvalidPasswordRecoveryRequestError()

        if email is not None:
            await self._limiter.check_verify_ip(remote_ip)
            await self._limiter.check_verify_identifier(kind="email", value=email)
            return await self._verify_email(email=email, code=code)

        if phone_e164 is None:  # pragma: no cover - defendido pelo XOR acima
            raise InvalidPasswordRecoveryRequestError()
        await self._limiter.check_verify_ip(remote_ip)
        await self._limiter.check_verify_identifier(kind="phone", value=phone_e164)
        return await self._verify_phone(phone=phone_e164, code=code)

    async def _verify_email(self, *, email: str, code: str) -> PasswordRecoveryVerified:
        identity = await self._resolve(email)
        user_id = identity.user_id if identity is not None else uuid.uuid4()
        state = await self._load_code(user_id)
        expected = recovery_code_digest(pepper=self._pepper, user_id=user_id, code=code)
        state_digest = state.digest if state is not None else _DUMMY_DIGEST
        matches = hmac.compare_digest(state_digest, expected)

        if identity is None or identity.status is not UserStatus.ACTIVE:
            await self._fail_inactive(identity=identity, state=state, user_id=user_id)
        if state is None or not matches:
            await self._fail_code(identity=identity, state=state, user_id=user_id)
        return await self._issue_token(identity=identity, state=state, expected=expected)

    async def _verify_phone(self, *, phone: str, code: str) -> PasswordRecoveryVerified:
        owner = await self._resolve_phone_owner(phone)
        user = await self._load_phone_user(owner)
        active = user is not None and user.status is UserStatus.ACTIVE
        attempts = 0
        if active and user is not None:
            attempts = await self._load_sms_attempts(user.user_id)

        # Mesmo sem conta/ativa, chama o check do Twilio para equalizar tempo.
        approved = await self._check_phone_code(phone=phone, code=code)

        if not active or user is None:
            await self._fail_phone_inactive(owner)
        if self._phone_service is None:
            await self._fail_phone_provider(user)
        if attempts >= self._max_attempts:
            await self._fail_phone_attempts(user)
        if not approved:
            await self._fail_phone_code(user)
        return await self._issue_phone_token(user=user)

    async def _resolve_phone_owner(self, phone: str) -> VerifiedPhoneOwner | None:
        try:
            return await self._phone_resolver.resolve(phone_e164=phone)
        except Exception as exc:  # noqa: BLE001 - resolver vira erro generico
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            return None

    async def _load_phone_user(self, owner: VerifiedPhoneOwner | None) -> PasswordResetUser | None:
        if owner is None:
            return None
        try:
            return await self._audit.get_user(company_id=owner.company_id, user_id=owner.user_id)
        except Exception as exc:  # noqa: BLE001 - DB vira erro generico
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            return None

    async def _check_phone_code(self, *, phone: str, code: str) -> bool:
        if self._phone_service is None:
            return False
        try:
            return await self._phone_service.check(phone_e164=phone, code=code)
        except Exception as exc:  # noqa: BLE001 - provedor vira erro generico
            _logger.warning(
                "password_recovery_provider_failed",
                action="check",
                error_type=type(exc).__name__,
            )
            return False

    async def _fail_phone_inactive(self, owner: VerifiedPhoneOwner | None) -> NoReturn:
        if owner is not None:
            await self._record_audit(
                company_id=owner.company_id,
                user_id=owner.user_id,
                action="auth.password_reset_failed",
                details={
                    "channel": "sms",
                    "stage": "verify",
                    "reason": "inactive",
                },
            )
        raise PasswordRecoveryCodeError()

    async def _fail_phone_provider(self, user: PasswordResetUser | None) -> NoReturn:
        if user is not None:
            await self._record_audit(
                company_id=user.company_id,
                user_id=user.user_id,
                action="auth.password_reset_failed",
                details={
                    "channel": "sms",
                    "stage": "verify",
                    "reason": "provider",
                },
            )
        raise PasswordRecoveryCodeError()

    async def _fail_phone_attempts(self, user: PasswordResetUser | None) -> NoReturn:
        if user is not None:
            await self._record_audit(
                company_id=user.company_id,
                user_id=user.user_id,
                action="auth.password_reset_failed",
                details={
                    "channel": "sms",
                    "stage": "verify",
                    "reason": "max_attempts",
                },
            )
        raise PasswordRecoveryCodeError()

    async def _fail_phone_code(self, user: PasswordResetUser | None) -> NoReturn:
        if user is None:
            raise PasswordRecoveryCodeError()
        attempts = await self._record_sms_attempt(user.user_id)
        reason = "max_attempts" if attempts >= self._max_attempts else "wrong_code"
        await self._record_audit(
            company_id=user.company_id,
            user_id=user.user_id,
            action="auth.password_reset_failed",
            details={"channel": "sms", "stage": "verify", "reason": reason},
        )
        raise PasswordRecoveryCodeError()

    async def _resolve(self, email: str) -> ResolvedIdentity | None:
        try:
            return await self._resolver.resolve_by_email(email)
        except Exception as exc:
            _logger.warning("password_recovery_resolve_failed", error_type=type(exc).__name__)
            raise PasswordRecoveryCodeError() from exc

    async def _fail_inactive(
        self,
        *,
        identity: ResolvedIdentity | None,
        state: PasswordRecoveryCodeState | None,
        user_id: uuid.UUID,
    ) -> NoReturn:
        if state is not None:
            await self._safe_delete_code(user_id)
        if identity is not None:
            await self._record_audit(
                company_id=identity.company_id,
                user_id=identity.user_id,
                action="auth.password_reset_failed",
                details={
                    "channel": "email",
                    "stage": "verify",
                    "reason": "inactive",
                },
            )
        raise PasswordRecoveryCodeError()

    async def _fail_code(
        self,
        *,
        identity: ResolvedIdentity | None,
        state: PasswordRecoveryCodeState | None,
        user_id: uuid.UUID,
    ) -> NoReturn:
        reason = "expired"
        if state is not None:
            attempts = await self._record_failed_attempt(user_id)
            reason = "max_attempts" if attempts >= self._max_attempts else "wrong_code"
        if identity is not None:
            await self._record_audit(
                company_id=identity.company_id,
                user_id=identity.user_id,
                action="auth.password_reset_failed",
                details={"channel": "email", "stage": "verify", "reason": reason},
            )
        raise PasswordRecoveryCodeError()

    async def _issue_token(
        self,
        *,
        identity: ResolvedIdentity | None,
        state: PasswordRecoveryCodeState | None,
        expected: str,
    ) -> PasswordRecoveryVerified:
        if identity is None or state is None:  # pragma: no cover - fluxo ja validou
            raise PasswordRecoveryCodeError()
        try:
            consumed = await self._store.consume_code(user_id=identity.user_id, digest=expected)
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)
        if not consumed:
            raise PasswordRecoveryCodeError()

        token = secrets.token_urlsafe(_RESET_TOKEN_BYTES)
        try:
            await self._store.save_reset_token(
                token_hash=reset_token_hash(token),
                user_id=identity.user_id,
                company_id=identity.company_id,
                locale=state.locale,
                channel="email",
                ttl_seconds=self._reset_token_ttl_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

        with suppress(PasswordRecoveryStoreError):
            await self._store.delete_cooldown(user_id=identity.user_id)

        await self._record_audit(
            company_id=identity.company_id,
            user_id=identity.user_id,
            action="auth.password_reset_verified",
            details={"channel": "email"},
        )
        return PasswordRecoveryVerified(reset_token=token, expires_in=self._reset_token_ttl_seconds)

    async def _issue_phone_token(self, *, user: PasswordResetUser) -> PasswordRecoveryVerified:
        token = secrets.token_urlsafe(_RESET_TOKEN_BYTES)
        try:
            await self._store.save_reset_token(
                token_hash=reset_token_hash(token),
                user_id=user.user_id,
                company_id=user.company_id,
                locale=None,
                channel="sms",
                ttl_seconds=self._reset_token_ttl_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

        with suppress(PasswordRecoveryStoreError):
            await self._store.clear_sms_attempts(user_id=user.user_id)
        with suppress(PasswordRecoveryStoreError):
            await self._store.delete_cooldown(user_id=user.user_id)

        await self._record_audit(
            company_id=user.company_id,
            user_id=user.user_id,
            action="auth.password_reset_verified",
            details={"channel": "sms"},
        )
        return PasswordRecoveryVerified(reset_token=token, expires_in=self._reset_token_ttl_seconds)

    async def _load_sms_attempts(self, user_id: uuid.UUID) -> int:
        try:
            return await self._store.get_sms_attempts(user_id=user_id)
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

    async def _record_sms_attempt(self, user_id: uuid.UUID) -> int:
        try:
            return await self._store.record_sms_failed_attempt(
                user_id=user_id,
                max_attempts=self._max_attempts,
                ttl_seconds=self._code_ttl_seconds,
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

    async def _load_code(self, user_id: uuid.UUID) -> PasswordRecoveryCodeState | None:
        try:
            return await self._store.load_code(user_id=user_id)
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

    async def _record_failed_attempt(self, user_id: uuid.UUID) -> int:
        try:
            return await self._store.record_failed_attempt(
                user_id=user_id, max_attempts=self._max_attempts
            )
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)

    async def _safe_delete_code(self, user_id: uuid.UUID) -> None:
        try:
            await self._store.delete_code(user_id=user_id)
        except PasswordRecoveryStoreError:
            return

    async def _record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        try:
            await self._audit.record_audit(
                company_id=company_id,
                user_id=user_id,
                action=action,
                details=details,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning(
                "password_recovery_audit_failed",
                action=action,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _unavailable(exc: Exception) -> NoReturn:
        raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc


class ResetPassword:
    """Caso de uso: consumir reset_token e trocar a senha com RLS."""

    def __init__(
        self,
        *,
        store: PasswordRecoveryStore,
        repository: PasswordResetRepository,
        hasher: PasswordHasher,
        email_dispatcher: PasswordRecoveryEmailDispatcher,
        limiter: PasswordRecoveryLimiter,
        session_revoker: PasswordResetSessionRevoker | None = None,
    ) -> None:
        self._store = store
        self._repository = repository
        self._hasher = hasher
        self._email_dispatcher = email_dispatcher
        self._limiter = limiter
        self._session_revoker = session_revoker

    async def execute(self, *, reset_token: str, new_password: str, remote_ip: str) -> None:
        await self._limiter.check_reset_ip(remote_ip)
        validate_password_strength(new_password)
        token_hash = reset_token_hash(reset_token)

        try:
            token_data = await self._store.consume_reset_token(token_hash=token_hash)
        except PasswordRecoveryStoreError as exc:
            self._unavailable(exc)
        if token_data is None:
            raise PasswordResetTokenError()
        await self._apply_reset(token_data=token_data, new_password=new_password)

    async def _apply_reset(self, *, token_data: PasswordResetTokenData, new_password: str) -> None:
        try:
            user = await self._repository.get_user(
                company_id=token_data.company_id, user_id=token_data.user_id
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning("password_reset_get_user_failed", error_type=type(exc).__name__)
            self._unavailable(exc)
        if user is None or user.status is not UserStatus.ACTIVE:
            await self._record_audit(
                company_id=token_data.company_id,
                user_id=token_data.user_id,
                reason="missing_or_inactive",
                channel=token_data.channel,
            )
            raise PasswordResetTokenError()

        reuse = False
        if user.password_hash is not None:
            reuse = await asyncio.to_thread(self._hasher.verify, new_password, user.password_hash)
        if reuse:
            await self._record_audit(
                company_id=user.company_id,
                user_id=user.user_id,
                reason="password_reuse",
                channel=token_data.channel,
            )
            raise PasswordReuseError()

        new_hash = await asyncio.to_thread(self._hasher.hash, new_password)
        try:
            new_epoch = await self._repository.update_password_and_audit(
                company_id=user.company_id,
                user_id=user.user_id,
                password_hash=new_hash,
                audit_action="auth.password_reset_completed",
                audit_details={"channel": token_data.channel},
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning("password_reset_update_failed", error_type=type(exc).__name__)
            self._unavailable(exc)
        if new_epoch is None:
            await self._record_audit(
                company_id=user.company_id,
                user_id=user.user_id,
                reason="missing_or_inactive",
                channel=token_data.channel,
            )
            raise PasswordResetTokenError()

        await self._after_reset(user=user, token_data=token_data, credential_epoch=new_epoch)

    async def _after_reset(
        self,
        *,
        user: PasswordResetUser,
        token_data: PasswordResetTokenData,
        credential_epoch: int,
    ) -> None:
        if self._session_revoker is not None:
            # A senha/epoca ja foram commitadas; falha do cache apenas atrasa
            # a convergencia (TTL curto) e fica registrada sem PII.
            try:
                await self._session_revoker.revoke_all_for_user(
                    user_id=user.user_id,
                    company_id=user.company_id,
                    credential_epoch=credential_epoch,
                )
            except Exception as exc:  # noqa: BLE001 - best-effort/log
                _logger.warning(
                    "password_reset_session_revoke_failed",
                    error_type=type(exc).__name__,
                )

        try:
            await self._email_dispatcher.send_password_changed(
                to=user.email, locale=token_data.locale
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning(
                "password_recovery_email_enqueue_failed",
                error_type=type(exc).__name__,
            )

    async def _record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        channel: str,
    ) -> None:
        try:
            await self._repository.record_audit(
                company_id=company_id,
                user_id=user_id,
                action="auth.password_reset_failed",
                details={"channel": channel, "stage": "reset", "reason": reason},
            )
        except Exception as exc:  # noqa: BLE001 - best-effort/log
            _logger.warning(
                "password_recovery_audit_failed",
                action="auth.password_reset_failed",
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _unavailable(exc: Exception) -> NoReturn:
        raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
