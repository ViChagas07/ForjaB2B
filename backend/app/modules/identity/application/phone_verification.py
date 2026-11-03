"""Verificacao do proprio telefone na conta (start/check/status).

O SMS e gerado/checado pelo Twilio Verify. O vinculo aprovado e gravado em
`user_verified_phones` por uma funcao SECURITY DEFINER atomica (migration
0044); a politica e "quem provou controle por ultimo vence", removendo o
vinculo anterior e avisando o dono antigo por e-mail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.rate_limit import (
    CooldownStore,
    DailyQuotaStore,
    RateLimitBackendError,
    RateLimitClass,
    RateLimitDecision,
    RateLimiter,
)
from app.application.security import AuthContext
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.core.logging import get_logger
from app.modules.identity.application.errors import (
    PhoneVerificationConflictError,
    PhoneVerificationFailedError,
)
from app.modules.identity.application.phone import mask_phone_e164
from app.modules.identity.application.ports import (
    AccountEmailDispatcher,
    PhoneVerificationRepository,
    PhoneVerificationService,
    PreviousPhoneOwner,
)

_logger = get_logger(__name__)

_GENERIC_UNAVAILABLE = "Servico temporariamente indisponivel."
_DAILY_TTL_SECONDS = 86_400


class PhoneVerificationLimiter:
    """Rate limits e cooldown proprios da verificacao de telefone."""

    def __init__(
        self,
        *,
        limiter: RateLimiter,
        daily_store: DailyQuotaStore,
        cooldown_store: CooldownStore,
        daily_user_limit: int,
        daily_ip_limit: int,
        cooldown_seconds: int,
        enabled: bool = True,
    ) -> None:
        self._limiter = limiter
        self._daily_store = daily_store
        self._cooldown_store = cooldown_store
        self._daily_user_limit = daily_user_limit
        self._daily_ip_limit = daily_ip_limit
        self._cooldown_seconds = cooldown_seconds
        self._enabled = enabled

    async def check_start(self, *, ip: str, user_id: uuid.UUID) -> None:
        if not self._enabled:
            return
        await self._consume_bucket(
            RateLimitClass.PHONE_VERIFICATION_IP, f"ip:{ip}", scope="start_ip"
        )
        await self._consume_bucket(
            RateLimitClass.PHONE_VERIFICATION_USER,
            f"user:{user_id}",
            scope="start_user",
        )
        await self._consume_daily(
            key=f"rl:phone_verification:daily:user:{user_id}",
            limit=self._daily_user_limit,
            scope="start_daily_user",
        )
        await self._consume_daily(
            key=f"rl:phone_verification:daily:ip:{ip}",
            limit=self._daily_ip_limit,
            scope="start_daily_ip",
        )

    async def reserve_cooldown(self, user_id: uuid.UUID) -> bool:
        if not self._enabled:
            return True
        try:
            return await self._cooldown_store.reserve(
                key=f"phone_verification:cooldown:{user_id}",
                ttl_seconds=self._cooldown_seconds,
            )
        except RateLimitBackendError as exc:
            _logger.warning(
                "phone_verification_rate_limit_unavailable",
                scope="cooldown",
                error_type=type(exc).__name__,
            )
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc

    async def release_cooldown(self, user_id: uuid.UUID) -> None:
        if not self._enabled:
            return
        try:
            await self._cooldown_store.release(key=f"phone_verification:cooldown:{user_id}")
        except RateLimitBackendError:
            return

    async def check_check(self, *, ip: str, user_id: uuid.UUID) -> None:
        if not self._enabled:
            return
        await self._consume_bucket(
            RateLimitClass.PHONE_VERIFICATION_CHECK_IP,
            f"ip:{ip}",
            scope="check_ip",
        )
        await self._consume_bucket(
            RateLimitClass.PHONE_VERIFICATION_CHECK_USER,
            f"user:{user_id}",
            scope="check_user",
        )

    async def _consume_bucket(
        self, rate_class: RateLimitClass, identity: str, *, scope: str
    ) -> None:
        try:
            decision = await self._limiter.check(
                rate_class=rate_class,
                identity=identity,
                fail_closed=True,
            )
        except RateLimitBackendError as exc:
            _logger.warning(
                "phone_verification_rate_limit_unavailable",
                scope=scope,
                error_type=type(exc).__name__,
            )
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
        self._raise_if_denied(decision=decision, scope=scope)

    async def _consume_daily(self, *, key: str, limit: int, scope: str) -> None:
        try:
            decision = await self._daily_store.consume(
                key=key, limit=limit, ttl_seconds=_DAILY_TTL_SECONDS
            )
        except RateLimitBackendError as exc:
            _logger.warning(
                "phone_verification_rate_limit_unavailable",
                scope=scope,
                error_type=type(exc).__name__,
            )
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
        if not decision.allowed:
            _logger.info("phone_verification_rate_limited", scope=scope)
            raise RateLimitExceededError(
                retry_after_seconds=decision.retry_after_seconds,
                limit=decision.limit,
                remaining=decision.remaining,
                reset_after_seconds=decision.retry_after_seconds,
            )

    def _raise_if_denied(self, *, decision: RateLimitDecision, scope: str) -> None:
        if decision.allowed:
            return
        _logger.info("phone_verification_rate_limited", scope=scope)
        raise RateLimitExceededError(
            retry_after_seconds=decision.retry_after_seconds,
            limit=decision.limit,
            remaining=decision.remaining,
            reset_after_seconds=decision.reset_after_seconds,
        )


@dataclass(frozen=True, kw_only=True)
class PhoneVerificationStatus:
    verified: bool
    phone_masked: str | None


class StartPhoneVerification:
    """Inicia o envio do SMS de verificacao."""

    def __init__(
        self,
        *,
        service: PhoneVerificationService | None,
        limiter: PhoneVerificationLimiter,
        repository: PhoneVerificationRepository,
        cooldown_seconds: int,
    ) -> None:
        self._service = service
        self._limiter = limiter
        self._repository = repository
        self._cooldown_seconds = cooldown_seconds

    async def execute(
        self,
        auth: AuthContext,
        *,
        phone_e164: str,
        locale: str | None,
        remote_ip: str,
    ) -> None:
        if self._service is None:
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE)

        await self._limiter.check_start(ip=remote_ip, user_id=auth.user_id)
        if not await self._limiter.reserve_cooldown(auth.user_id):
            raise RateLimitExceededError(
                retry_after_seconds=self._cooldown_seconds,
                limit=1,
                remaining=0,
                reset_after_seconds=self._cooldown_seconds,
            )

        try:
            started = await self._service.start(phone_e164=phone_e164, locale=locale)
        except Exception as exc:  # noqa: BLE001 - provedor externo, falha generica
            _logger.warning(
                "phone_verification_provider_failed",
                action="start",
                error_type=type(exc).__name__,
            )
            started = False
        if not started:
            await self._limiter.release_cooldown(auth.user_id)
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE)

        await self._audit(
            auth,
            action="auth.phone_verification_started",
            details={"channel": "sms"},
        )

    async def _audit(self, auth: AuthContext, *, action: str, details: dict[str, str]) -> None:
        try:
            await self._repository.record_audit(
                company_id=auth.company_id,
                user_id=auth.user_id,
                action=action,
                details=details,
            )
        except Exception as exc:  # noqa: BLE001 - auditoria best-effort
            _logger.warning(
                "phone_verification_audit_failed",
                action=action,
                error_type=type(exc).__name__,
            )


class CheckPhoneVerification:
    """Confere o codigo SMS e grava o telefone verificado."""

    def __init__(
        self,
        *,
        service: PhoneVerificationService | None,
        limiter: PhoneVerificationLimiter,
        repository: PhoneVerificationRepository,
        email_dispatcher: AccountEmailDispatcher,
    ) -> None:
        self._service = service
        self._limiter = limiter
        self._repository = repository
        self._email_dispatcher = email_dispatcher

    async def execute(
        self,
        auth: AuthContext,
        *,
        phone_e164: str,
        code: str,
        remote_ip: str,
    ) -> None:
        if self._service is None:
            raise ServiceUnavailableError(_GENERIC_UNAVAILABLE)

        await self._limiter.check_check(ip=remote_ip, user_id=auth.user_id)
        try:
            approved = await self._service.check(phone_e164=phone_e164, code=code)
        except Exception as exc:  # noqa: BLE001 - provedor externo, falha generica
            _logger.warning(
                "phone_verification_provider_failed",
                action="check",
                error_type=type(exc).__name__,
            )
            approved = False
        if not approved:
            await self._audit(
                auth,
                action="auth.phone_verification_failed",
                details={"channel": "sms", "reason": "code_or_provider"},
            )
            raise PhoneVerificationFailedError()

        previous = await self._claim(auth=auth, phone_e164=phone_e164)
        await self._audit(
            auth,
            action="auth.phone_verified",
            details={"channel": "sms"},
        )
        if previous is not None:
            await self._notify_previous_owner(
                previous_user=previous.user_id, previous_company=previous.company_id
            )

    async def _claim(self, *, auth: AuthContext, phone_e164: str) -> PreviousPhoneOwner | None:
        for attempt in range(2):
            try:
                return await self._repository.claim_verified_phone(
                    phone_e164=phone_e164,
                    user_id=auth.user_id,
                    company_id=auth.company_id,
                )
            except PhoneVerificationConflictError:
                if attempt == 0:
                    continue
                raise PhoneVerificationFailedError() from None
            except Exception as exc:
                _logger.warning(
                    "phone_verification_claim_failed",
                    error_type=type(exc).__name__,
                )
                raise ServiceUnavailableError(_GENERIC_UNAVAILABLE) from exc
        raise PhoneVerificationFailedError()

    async def _notify_previous_owner(
        self, *, previous_user: uuid.UUID, previous_company: uuid.UUID
    ) -> None:
        try:
            await self._repository.record_audit(
                company_id=previous_company,
                user_id=previous_user,
                action="auth.phone_unlinked",
                details={"channel": "sms", "reason": "reclaimed"},
            )
        except Exception as exc:  # noqa: BLE001 - auditoria best-effort
            _logger.warning(
                "phone_verification_audit_failed",
                action="auth.phone_unlinked",
                error_type=type(exc).__name__,
            )
        try:
            email = await self._repository.get_user_email(
                company_id=previous_company, user_id=previous_user
            )
        except Exception as exc:  # noqa: BLE001 - aviso best-effort
            _logger.warning("phone_unlink_email_lookup_failed", error_type=type(exc).__name__)
            return
        if email is None:
            return
        try:
            await self._email_dispatcher.send_phone_unlinked(to=email, locale=None)
        except Exception as exc:  # noqa: BLE001 - enqueue best-effort
            _logger.warning(
                "phone_unlink_email_enqueue_failed",
                error_type=type(exc).__name__,
            )

    async def _audit(self, auth: AuthContext, *, action: str, details: dict[str, str]) -> None:
        try:
            await self._repository.record_audit(
                company_id=auth.company_id,
                user_id=auth.user_id,
                action=action,
                details=details,
            )
        except Exception as exc:  # noqa: BLE001 - auditoria best-effort
            _logger.warning(
                "phone_verification_audit_failed",
                action=action,
                error_type=type(exc).__name__,
            )


class GetPhoneVerificationStatus:
    """Status mascarado para a tela de conta."""

    def __init__(self, *, repository: PhoneVerificationRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext) -> PhoneVerificationStatus:
        phone = await self._repository.get_verified_phone(
            company_id=auth.company_id, user_id=auth.user_id
        )
        if phone is None:
            return PhoneVerificationStatus(verified=False, phone_masked=None)
        return PhoneVerificationStatus(verified=True, phone_masked=mask_phone_e164(phone))
