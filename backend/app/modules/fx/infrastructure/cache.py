"""Cache Redis das taxas de cambio (fresco + ultima conhecida + lock).

Os valores sao gravados como strings decimais dentro de um JSON estavel, para
nao perder precisao nem depender do parser de float. O TTL fresco e de 12h; a
copia de ultima conhecida fica por 7 dias para o fallback quando o provedor
falha. Falha do Redis degrada para "sem cache" e nunca derruba a rota.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.modules.fx.domain.rates import FxRates

_logger = get_logger(__name__)

FX_RATES_TTL_SECONDS = 12 * 60 * 60
FX_LAST_KNOWN_TTL_SECONDS = 7 * 24 * 60 * 60
FX_REFRESH_LOCK_TTL_SECONDS = 15

_FRESH_KEY = "fx:rates:brl:v1:fresh"
_LAST_KNOWN_KEY = "fx:rates:brl:v1:last-known"
_REFRESH_LOCK_KEY = "fx:rates:brl:v1:refresh-lock"


def encode_rates(rates: FxRates) -> str:
    """Serializa o payload canonico (chaves ordenadas, sem espacos extras)."""
    payload = {
        "base": rates.base,
        "rates": {code: str(value) for code, value in rates.rates.items()},
        "rate_date": rates.rate_date.isoformat(),
        "fetched_at": rates.fetched_at.isoformat(),
        "source": rates.source,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_rates(raw: str) -> FxRates | None:
    """Le o payload canonico; `None` quando o cache esta corrompido."""
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        raw_rates = payload["rates"]
        if not isinstance(raw_rates, dict):
            return None
        rates = {str(code): Decimal(str(value)) for code, value in raw_rates.items()}
        return FxRates(
            rates=rates,
            rate_date=date.fromisoformat(str(payload["rate_date"])),
            fetched_at=datetime.fromisoformat(str(payload["fetched_at"])),
            source=str(payload["source"]),
            base=str(payload["base"]),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


class RedisFxRateCache:
    """Implementacao best-effort do cache com lock distribuido curto."""

    def __init__(
        self,
        *,
        redis_client: Redis[str] | None,
        fresh_ttl_seconds: int = FX_RATES_TTL_SECONDS,
        last_known_ttl_seconds: int = FX_LAST_KNOWN_TTL_SECONDS,
        lock_ttl_seconds: int = FX_REFRESH_LOCK_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._fresh_ttl = fresh_ttl_seconds
        self._last_known_ttl = last_known_ttl_seconds
        self._lock_ttl = lock_ttl_seconds

    async def load_fresh(self) -> FxRates | None:
        raw = await self._get(_FRESH_KEY)
        return decode_rates(raw) if raw is not None else None

    async def load_last_known(self) -> FxRates | None:
        raw = await self._get(_LAST_KNOWN_KEY)
        return decode_rates(raw) if raw is not None else None

    async def save(self, rates: FxRates) -> None:
        payload = encode_rates(rates)
        await self._set(_FRESH_KEY, payload, self._fresh_ttl)
        await self._set(_LAST_KNOWN_KEY, payload, self._last_known_ttl)

    async def acquire_refresh_lock(self) -> str | None:
        token = secrets.token_urlsafe(16)
        if self._redis is None:
            return token
        try:
            acquired = await self._redis.set(_REFRESH_LOCK_KEY, token, nx=True, ex=self._lock_ttl)
        except Exception as exc:  # noqa: BLE001 - Redis fora do ar: fail-open
            _logger.warning("fx_refresh_lock_failed", error=str(exc))
            return token
        return token if acquired else None

    async def release_refresh_lock(self, token: str) -> None:
        if self._redis is None:
            return
        try:
            current = await self._redis.get(_REFRESH_LOCK_KEY)
            if current == token:
                await self._redis.delete(_REFRESH_LOCK_KEY)
        except Exception as exc:  # noqa: BLE001 - liberacao best-effort
            _logger.warning("fx_refresh_unlock_failed", error=str(exc))

    async def _get(self, key: str) -> str | None:
        if self._redis is None:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001 - cache indisponivel degrada
            _logger.warning("fx_cache_read_failed", error=str(exc))
            return None

    async def _set(self, key: str, payload: str, ttl_seconds: int) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(key, payload, ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001 - cache indisponivel degrada
            _logger.warning("fx_cache_write_failed", error=str(exc))
