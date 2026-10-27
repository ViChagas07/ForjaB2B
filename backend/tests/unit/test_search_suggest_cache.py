"""Testes do cache Redis do suggest (hit, miss, fail-open, chave)."""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.modules.search.infrastructure.suggest_cache import SUGGEST_CACHE_TTL_SECONDS, SuggestCache


class _FakeRedis:
    """Redis minimo de teste (sem TTL real; grava e le strings)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.data: dict[str, str] = {}
        self.fail = fail
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RuntimeError("redis fora do ar")
        return self.data.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        if self.fail:
            raise RuntimeError("redis fora do ar")
        self.data[key] = value
        self.ttls[key] = ex if ex is not None else 0


def _cache(fake: _FakeRedis, *, index_version: int = 2) -> SuggestCache:
    return SuggestCache(
        redis_client=cast("Any", fake),
        index_version=index_version,
        ttl_seconds=SUGGEST_CACHE_TTL_SECONDS,
    )


async def test_set_e_get_fazem_round_trip_com_ttl_configurado() -> None:
    fake = _FakeRedis()
    cache = _cache(fake)
    key = cache.key_for(q="cap", locale="pt-BR")

    await cache.set(key=key, payload='{"terms":[]}')
    assert await cache.get(key=key) == '{"terms":[]}'
    assert fake.ttls[key] == SUGGEST_CACHE_TTL_SECONDS


def test_chave_normaliza_termo_e_inclui_locale_e_versao_do_indice() -> None:
    cache = _cache(_FakeRedis(), index_version=3)
    assert cache.key_for(q="  CAP ", locale="en") == "search:suggest:v3:en:cap"
    assert cache.key_for(q="cap", locale="pt-BR") == cache.key_for(q="CAP", locale="pt-BR")


async def test_redis_indisponivel_degrada_sem_erro() -> None:
    fake = _FakeRedis(fail=True)
    cache = _cache(fake)
    key = cache.key_for(q="cap", locale="pt-BR")

    assert await cache.get(key=key) is None
    await cache.set(key=key, payload='{"terms":[]}')  # nao levanta
    assert fake.data == {}


async def test_sem_redis_client_nao_cacheia_e_nao_quebra() -> None:
    cache = SuggestCache(redis_client=None, index_version=2)
    key = cache.key_for(q="cap", locale="pt-BR")
    assert await cache.get(key=key) is None
    await cache.set(key=key, payload='{"terms":[]}')
    assert await cache.get(key=key) is None


def test_ttl_default_e_30_segundos() -> None:
    assert SUGGEST_CACHE_TTL_SECONDS == 30


@pytest.mark.parametrize(
    ("q", "locale", "index_version", "esperado"),
    [
        ("  Capacete  ", "pt-BR", 2, "search:suggest:v2:pt-BR:capacete"),
        ("CAP", "en", 5, "search:suggest:v5:en:cap"),
    ],
)
def test_chave_com_variacoes(q: str, locale: str, index_version: int, esperado: str) -> None:
    cache = SuggestCache(redis_client=None, index_version=index_version)
    assert cache.key_for(q=q, locale=locale) == esperado
