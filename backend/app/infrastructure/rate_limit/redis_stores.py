"""Implementacoes Redis dos stores de rate limiting e falhas de login.

As operacoes sao atomicas via scripts Lua. Qualquer erro de rede/protocolo e
convertido em ``RateLimitBackendError`` para o chamador aplicar fail-open com
o store local (nunca derrubar a API por causa do limitador).
"""

from __future__ import annotations

from typing import cast

import redis.asyncio as redis

from app.application.rate_limit import RateLimitBackendError

_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(data[1])
local updated = tonumber(data[2])
if tokens == nil then tokens = capacity end
if updated == nil then updated = now end
if now < updated then updated = now end

local elapsed = now - updated
if elapsed > 0 then
  tokens = math.min(capacity, tokens + elapsed * refill)
end

local allowed = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
end

redis.call('HSET', key, 'tokens', tokens, 'updated', now)
local ttl = math.ceil(capacity / refill) + 60
redis.call('EXPIRE', key, ttl)

local retry = 0
if allowed == 0 then
  retry = (1 - tokens) / refill
end
return {allowed, tokens, retry}
"""

_FAILURE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local threshold = tonumber(ARGV[3])
local base_backoff = tonumber(ARGV[4])
local max_backoff = tonumber(ARGV[5])

local blocked_until = tonumber(redis.call('HGET', key, 'blocked_until') or '0')
if blocked_until > now then
  return {blocked_until, tonumber(redis.call('HGET', key, 'count') or '0')}
end

local count = redis.call('HINCRBY', key, 'count', 1)
redis.call('EXPIRE', key, ttl)

if count >= threshold then
  local exponent = count - threshold
  local backoff = base_backoff * (2 ^ exponent)
  if backoff > max_backoff then backoff = max_backoff end
  blocked_until = now + backoff
  redis.call('HSET', key, 'blocked_until', blocked_until)
end
return {blocked_until, count}
"""


def _numbers(result: object) -> list[float]:
    if not isinstance(result, list):
        raise RateLimitBackendError("resposta Lua inesperada")
    return [float(cast(int | str, item)) for item in result]


class RedisBucketStore:
    """Token bucket atomico no Redis."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._client = client

    async def consume(
        self,
        *,
        key: str,
        capacity: int,
        refill_per_second: float,
        now: float,
    ) -> tuple[bool, float, float]:
        try:
            result = await self._client.eval(  # type: ignore[no-untyped-call]
                _BUCKET_SCRIPT,
                1,
                key,
                capacity,
                refill_per_second,
                now,
            )
            allowed, remaining, retry = _numbers(result)
        except Exception as exc:
            raise RateLimitBackendError(str(exc)) from exc
        return bool(allowed), remaining, retry


class RedisFailureStore:
    """Contador atomico de falhas de login no Redis."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._client = client

    async def blocked_for(self, *, key: str, now: float) -> float:
        try:
            raw = await self._client.hget(key, "blocked_until")
        except Exception as exc:
            raise RateLimitBackendError(str(exc)) from exc
        if raw is None:
            return 0.0
        try:
            return max(0.0, float(raw) - now)
        except (TypeError, ValueError):
            return 0.0

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
        try:
            result = await self._client.eval(  # type: ignore[no-untyped-call]
                _FAILURE_SCRIPT,
                1,
                key,
                now,
                ttl_seconds,
                threshold,
                base_backoff_seconds,
                max_backoff_seconds,
            )
            blocked_until, _count = _numbers(result)
        except Exception as exc:
            raise RateLimitBackendError(str(exc)) from exc
        return max(0.0, blocked_until - now)

    async def clear(self, *, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as exc:
            raise RateLimitBackendError(str(exc)) from exc
