"""Rate limiting e bloqueio de login (casos transversais, sem framework).

O algoritmo e token bucket: cada chave tem uma capacidade (burst) e uma taxa de
reposicao por segundo. A implementacao distribuida usa Redis com script Lua
(atomico); se o Redis falhar, o limitador cai para um store local por processo
(fail-open conservador) e registra metrica/aviso. Nenhuma chave contem PII:
identidades sao IPs ou IDs internos e e-mails passam por HMAC antes de virar
chave.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.core.logging import get_logger
from app.core.metrics import increment_rate_limit_backend_failure, increment_rate_limit_rejection

_logger = get_logger(__name__)


class RateLimitClass(StrEnum):
    """Classes de rota com limites independentes."""

    AUTH = "auth"
    REGISTRATION = "registration"
    SEARCH = "search"
    ADMIN_WRITE = "admin_write"
    AUTHENTICATED = "authenticated"
    PUBLIC_READ = "public_read"
    LOGIN_ACCOUNT = "login_account"
    WEBHOOK = "webhook"


@dataclass(frozen=True, kw_only=True)
class RateLimitPolicy:
    """Configuracao de um token bucket."""

    capacity: int
    refill_per_minute: float

    @property
    def refill_per_second(self) -> float:
        return self.refill_per_minute / 60.0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity deve ser >= 1")
        if self.refill_per_minute <= 0:
            raise ValueError("refill_per_minute deve ser > 0")


@dataclass(frozen=True, kw_only=True)
class RateLimitDecision:
    """Resultado de uma tentativa de consumo."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    reset_after_seconds: int


class RateLimitBackendError(RuntimeError):
    """Falha do backend distribuido (Redis); o chamador faz fail-open."""


class BucketStore(Protocol):
    """Store de token bucket atomico."""

    async def consume(
        self,
        *,
        key: str,
        capacity: int,
        refill_per_second: float,
        now: float,
    ) -> tuple[bool, float, float]:
        """Consome 1 token.

        Retorna ``(allowed, tokens_restantes, segundos_ate_1_token)``. Deve ser
        atomico em relacao a chamadas concorrentes para a mesma chave.
        """


class FailureStore(Protocol):
    """Store de falhas de login por conta+IP (janela deslizante)."""

    async def blocked_for(self, *, key: str, now: float) -> float:
        """Segundos restantes de bloqueio (0 = livre)."""

    async def record_failure(
        self,
        *,
        key: str,
        now: float,
        ttl_seconds: int,
        threshold: int,
        base_backoff_seconds: int,
        max_backoff_seconds: int,
    ) -> float:
        """Incrementa a falha e devolve segundos de bloqueio (0 = ainda livre)."""

    async def clear(self, *, key: str) -> None:
        """Zera o contador apos login bem-sucedido."""


class InMemoryBucketStore:
    """Token bucket local (fallback e testes). Seguro por processo."""

    def __init__(self) -> None:
        self._state: dict[str, tuple[float, float]] = {}

    async def consume(
        self,
        *,
        key: str,
        capacity: int,
        refill_per_second: float,
        now: float,
    ) -> tuple[bool, float, float]:
        tokens, updated = self._state.get(key, (float(capacity), now))
        elapsed = max(0.0, now - updated)
        tokens = min(float(capacity), tokens + elapsed * refill_per_second)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
        retry = 0.0 if allowed else max(0.0, (1.0 - tokens) / refill_per_second)
        self._state[key] = (tokens, now)
        # Limpeza barata: remove chaves paradas ha mais de 1h.
        if len(self._state) > 10_000:
            cutoff = now - 3600
            self._state = {
                item_key: state for item_key, state in self._state.items() if state[1] >= cutoff
            }
        return allowed, tokens, retry


class InMemoryFailureStore:
    """Contador de falhas local, com a mesma semantica do store Redis."""

    def __init__(self) -> None:
        self._state: dict[str, tuple[int, float, float]] = {}

    async def blocked_for(self, *, key: str, now: float) -> float:
        _count, expires_at, blocked_until = self._state.get(key, (0, 0.0, 0.0))
        if expires_at <= now:
            self._state.pop(key, None)
            return 0.0
        return max(0.0, blocked_until - now)

    async def record_failure(
        self,
        *,
        key: str,
        now: float,
        ttl_seconds: int,
        threshold: int,
        base_backoff_seconds: int,
        max_backoff_seconds: int,
    ) -> float:
        count, expires_at, blocked_until = self._state.get(key, (0, now + ttl_seconds, 0.0))
        if expires_at <= now:
            count, expires_at, blocked_until = 0, now + ttl_seconds, 0.0
        count += 1
        if count >= threshold and blocked_until <= now:
            exponent = max(0, count - threshold)
            backoff = min(max_backoff_seconds, base_backoff_seconds * (2**exponent))
            blocked_until = now + backoff
        self._state[key] = (count, expires_at, blocked_until)
        return max(0.0, blocked_until - now)

    async def clear(self, *, key: str) -> None:
        self._state.pop(key, None)


def pseudonymous_key(secret: str, value: str) -> str:
    """HMAC-SHA256 para identificadores (e-mail/CPF) em chaves de rate limit."""
    return hmac.new(
        secret.encode("utf-8"), value.strip().lower().encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _decision(
    *, policy: RateLimitPolicy, allowed: bool, remaining: float, retry: float
) -> RateLimitDecision:
    return RateLimitDecision(
        allowed=allowed,
        limit=policy.capacity,
        remaining=max(0, math.floor(remaining)),
        retry_after_seconds=max(1, math.ceil(retry)) if not allowed else 0,
        reset_after_seconds=max(1, math.ceil(capacity_seconds(policy, remaining))),
    )


def capacity_seconds(policy: RateLimitPolicy, remaining: float) -> float:
    """Tempo ate o bucket voltar a ficar cheio (aproximacao para RateLimit-Reset)."""
    missing = max(0.0, policy.capacity - remaining)
    return missing / policy.refill_per_second if policy.refill_per_second > 0 else 0.0


class RateLimiter:
    """Orquestra token buckets distribuidos com fallback local fail-open."""

    def __init__(
        self,
        *,
        store: BucketStore,
        policies: dict[RateLimitClass, RateLimitPolicy],
        fallback_store: BucketStore | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._store = store
        self._fallback = fallback_store or InMemoryBucketStore()
        self._policies = policies
        self._clock = clock or time.time
        self._redis_failed = False
        self._backend_retry_at = 0.0

    async def check(self, *, rate_class: RateLimitClass, identity: str) -> RateLimitDecision:
        policy = self._policies[rate_class]
        key = f"rl:{rate_class.value}:{identity}"
        now = self._clock()
        if now < self._backend_retry_at:
            # Circuit breaker curto: nao paga o timeout do Redis a cada request
            # enquanto ele esta fora; o fallback local assume o controle.
            allowed, remaining, retry = await self._fallback.consume(
                key=key,
                capacity=policy.capacity,
                refill_per_second=policy.refill_per_second,
                now=now,
            )
        else:
            try:
                allowed, remaining, retry = await self._store.consume(
                    key=key,
                    capacity=policy.capacity,
                    refill_per_second=policy.refill_per_second,
                    now=now,
                )
                if self._redis_failed:
                    self._redis_failed = False
                    _logger.info("rate_limit_backend_recovered")
            except Exception as exc:  # noqa: BLE001 - fail-open deliberado
                if not self._redis_failed:
                    _logger.warning("rate_limit_backend_unavailable", error=str(exc))
                self._redis_failed = True
                self._backend_retry_at = now + 30
                increment_rate_limit_backend_failure(rate_class=rate_class.value)
                allowed, remaining, retry = await self._fallback.consume(
                    key=key,
                    capacity=policy.capacity,
                    refill_per_second=policy.refill_per_second,
                    now=now,
                )
        decision = _decision(policy=policy, allowed=allowed, remaining=remaining, retry=retry)
        if not decision.allowed:
            increment_rate_limit_rejection(rate_class=rate_class.value)
        return decision


class LoginThrottle:
    """Atraso progressivo/bloqueio temporario de login por conta+IP.

    A chave e HMAC-SHA256(secret, "email_normalizado|ip"), entao o e-mail e o
    IP nao aparecem no Redis nem em logs. A resposta e identica para conta
    existente ou nao (nao revela cadastro).
    """

    def __init__(
        self,
        *,
        store: FailureStore,
        fallback_store: FailureStore | None = None,
        secret: str,
        ttl_seconds: int,
        threshold: int,
        base_backoff_seconds: int,
        max_backoff_seconds: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._store = store
        self._fallback = fallback_store or InMemoryFailureStore()
        self._secret = secret
        self._ttl = ttl_seconds
        self._threshold = threshold
        self._base_backoff = base_backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._clock = clock or time.time

    def key_for(self, *, email: str, client_ip: str) -> str:
        normalized = email.strip().lower()
        return hmac.new(
            self._secret.encode("utf-8"),
            f"{normalized}|{client_ip}".encode(),
            hashlib.sha256,
        ).hexdigest()

    async def blocked_for(self, *, email: str, client_ip: str) -> int:
        key = self.key_for(email=email, client_ip=client_ip)
        try:
            return math.ceil(await self._store.blocked_for(key=key, now=self._clock()))
        except Exception as exc:  # noqa: BLE001 - fail-open deliberado
            _logger.warning("login_throttle_backend_unavailable", error=str(exc))
            increment_rate_limit_backend_failure(rate_class="login_account")
            blocked = await self._fallback.blocked_for(key=key, now=self._clock())
            return math.ceil(blocked)

    async def record_failure(self, *, email: str, client_ip: str) -> int:
        key = self.key_for(email=email, client_ip=client_ip)
        try:
            blocked = await self._store.record_failure(
                key=key,
                now=self._clock(),
                ttl_seconds=self._ttl,
                threshold=self._threshold,
                base_backoff_seconds=self._base_backoff,
                max_backoff_seconds=self._max_backoff,
            )
        except Exception as exc:  # noqa: BLE001 - fail-open deliberado
            _logger.warning("login_throttle_backend_unavailable", error=str(exc))
            increment_rate_limit_backend_failure(rate_class="login_account")
            blocked = await self._fallback.record_failure(
                key=key,
                now=self._clock(),
                ttl_seconds=self._ttl,
                threshold=self._threshold,
                base_backoff_seconds=self._base_backoff,
                max_backoff_seconds=self._max_backoff,
            )
        return math.ceil(blocked)

    async def clear(self, *, email: str, client_ip: str) -> None:
        key = self.key_for(email=email, client_ip=client_ip)
        try:
            await self._store.clear(key=key)
        except Exception:  # noqa: BLE001 - limpeza e best-effort
            await self._fallback.clear(key=key)
