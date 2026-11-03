"""Temporarios Redis da recuperacao de conta (codigo, cooldown e reset_token).

O codigo de e-mail NUNCA e persistido em claro: apenas o HMAC (PEPPER) no
hash. O reset_token tambem so existe como hash (SHA-256) na chave. TTLs e
contadores sao atomicos em Lua para impedir reuso concorrente. Qualquer falha
do Redis vira ``PasswordRecoveryStoreError`` (o caso de uso responde 503).
"""

from __future__ import annotations

import json
import uuid
from typing import Protocol, cast

import redis.asyncio as redis

from app.modules.identity.application.errors import PasswordRecoveryStoreError
from app.modules.identity.application.ports import (
    PasswordRecoveryCodeState,
    PasswordResetTokenData,
)

_CODE_PREFIX = "password_recovery:code:"
_COOLDOWN_PREFIX = "password_recovery:cooldown:"
_RESET_PREFIX = "password_recovery:reset:"
_SMS_ATTEMPTS_PREFIX = "password_recovery:sms_attempts:"

_SAVE_CODE_SCRIPT = """
local key = KEYS[1]
redis.call('HSET', key, 'digest', ARGV[1], 'attempts', '0')
if ARGV[2] ~= '' then
  redis.call('HSET', key, 'locale', ARGV[2])
else
  redis.call('HDEL', key, 'locale')
end
redis.call('EXPIRE', key, ARGV[3])
return 1
"""

_FAILED_ATTEMPT_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
  return 0
end
local attempts = redis.call('HINCRBY', KEYS[1], 'attempts', 1)
if attempts >= tonumber(ARGV[1]) then
  redis.call('DEL', KEYS[1])
end
return attempts
"""

_CONSUME_CODE_SCRIPT = """
if redis.call('HGET', KEYS[1], 'digest') == ARGV[1] then
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

_SMS_ATTEMPT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class _EvalCapable(Protocol):
    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


def _code_key(user_id: uuid.UUID) -> str:
    return f"{_CODE_PREFIX}{user_id}"


def _cooldown_key(user_id: uuid.UUID) -> str:
    return f"{_COOLDOWN_PREFIX}{user_id}"


def _reset_key(token_hash: str) -> str:
    return f"{_RESET_PREFIX}{token_hash}"


def _sms_attempts_key(user_id: uuid.UUID) -> str:
    return f"{_SMS_ATTEMPTS_PREFIX}{user_id}"


class RedisPasswordRecoveryStore:
    """Implementacao da porta PasswordRecoveryStore sobre Redis."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def reserve_resend(self, *, user_id: uuid.UUID, ttl_seconds: int) -> bool:
        try:
            result = await self._client.set(_cooldown_key(user_id), "1", nx=True, ex=ttl_seconds)
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        return bool(result)

    async def save_code(
        self,
        *,
        user_id: uuid.UUID,
        digest: str,
        locale: str | None,
        ttl_seconds: int,
    ) -> None:
        try:
            await cast(_EvalCapable, self._client).eval(
                _SAVE_CODE_SCRIPT,
                1,
                _code_key(user_id),
                digest,
                locale or "",
                ttl_seconds,
            )
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc

    async def load_code(self, *, user_id: uuid.UUID) -> PasswordRecoveryCodeState | None:
        try:
            raw = await self._client.hgetall(_code_key(user_id))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        digest_raw = raw.get("digest")
        if digest_raw is None:
            return None
        attempts_raw = raw.get("attempts", "0")
        try:
            attempts = int(attempts_raw)
        except (TypeError, ValueError):
            attempts = 0
        locale_raw = raw.get("locale")
        if isinstance(locale_raw, bytes):
            locale: str | None = locale_raw.decode("utf-8") or None
        else:
            locale = locale_raw or None
        digest = digest_raw.decode("utf-8") if isinstance(digest_raw, bytes) else digest_raw
        return PasswordRecoveryCodeState(digest=str(digest), attempts=attempts, locale=locale)

    async def record_failed_attempt(self, *, user_id: uuid.UUID, max_attempts: int) -> int:
        try:
            result = await cast(_EvalCapable, self._client).eval(
                _FAILED_ATTEMPT_SCRIPT,
                1,
                _code_key(user_id),
                max_attempts,
            )
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        try:
            return int(cast(int, result))
        except (TypeError, ValueError):
            return max_attempts

    async def consume_code(self, *, user_id: uuid.UUID, digest: str) -> bool:
        try:
            result = await cast(_EvalCapable, self._client).eval(
                _CONSUME_CODE_SCRIPT,
                1,
                _code_key(user_id),
                digest,
            )
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        return bool(int(cast(int, result)))

    async def delete_code(self, *, user_id: uuid.UUID) -> None:
        try:
            await self._client.delete(_code_key(user_id))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc

    async def delete_cooldown(self, *, user_id: uuid.UUID) -> None:
        try:
            await self._client.delete(_cooldown_key(user_id))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc

    async def get_sms_attempts(self, *, user_id: uuid.UUID) -> int:
        try:
            raw = await self._client.get(_sms_attempts_key(user_id))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        if raw is None:
            return 0
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    async def record_sms_failed_attempt(
        self, *, user_id: uuid.UUID, max_attempts: int, ttl_seconds: int
    ) -> int:
        try:
            result = await cast(_EvalCapable, self._client).eval(
                _SMS_ATTEMPT_SCRIPT,
                1,
                _sms_attempts_key(user_id),
                ttl_seconds,
            )
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        return int(cast(int, result))

    async def clear_sms_attempts(self, *, user_id: uuid.UUID) -> None:
        try:
            await self._client.delete(_sms_attempts_key(user_id))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc

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
        payload = json.dumps(
            {
                "user_id": str(user_id),
                "company_id": str(company_id),
                "locale": locale,
                "channel": channel,
            }
        )
        try:
            await self._client.set(_reset_key(token_hash), payload, ex=ttl_seconds)
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc

    async def consume_reset_token(self, *, token_hash: str) -> PasswordResetTokenData | None:
        try:
            raw = await self._client.getdel(_reset_key(token_hash))
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return PasswordResetTokenData(
                user_id=uuid.UUID(data["user_id"]),
                company_id=uuid.UUID(data["company_id"]),
                locale=data.get("locale"),
                channel=(
                    data.get("channel") if data.get("channel") in {"email", "sms"} else "email"
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def probe(self) -> None:
        try:
            await self._client.ping()
        except Exception as exc:
            raise PasswordRecoveryStoreError("password recovery store unavailable") from exc
