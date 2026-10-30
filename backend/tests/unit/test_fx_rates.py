"""Testes unitarios do cambio de exibicao (sem rede real).

Cobrem dominio, parsing da Frankfurter, retry/timeout, cache Redis (TTL,
payload estavel, corrupcao, fail-open), lock e o caso de uso com fallback
stale/erro tipado.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import httpx
import pytest

from app.modules.fx.application.errors import FxProviderError, FxRatesUnavailableError
from app.modules.fx.application.get_rates import GetFxRates
from app.modules.fx.application.ports import FxRateCache, FxRateProvider
from app.modules.fx.domain.rates import (
    BASE_CURRENCY,
    QUOTE_CURRENCIES,
    SUPPORTED_CURRENCIES,
    FxRates,
    normalize_currency,
)
from app.modules.fx.infrastructure.cache import (
    FX_LAST_KNOWN_TTL_SECONDS,
    FX_RATES_TTL_SECONDS,
    RedisFxRateCache,
    decode_rates,
    encode_rates,
)
from app.modules.fx.infrastructure.frankfurter import FrankfurterFxRateProvider

_FIXED_NOW = datetime(2026, 10, 30, 23, 0, tzinfo=UTC)
_RATE_VALUES: dict[str, str] = {
    "BRL": "1",
    "USD": "0.18408",
    "EUR": "0.16477",
    "GBP": "0.13738",
    "CAD": "0.25713",
    "AUD": "0.26204",
    "JPY": "28.946",
    "CNY": "1.2246",
}


def _sample_rates(*, fetched_at: datetime = _FIXED_NOW) -> FxRates:
    return FxRates(
        rates={code: Decimal(value) for code, value in _RATE_VALUES.items()},
        rate_date=date(2026, 10, 30),
        fetched_at=fetched_at,
        source="Frankfurter / European Central Bank",
    )


def _row(quote: str, rate: str, *, rate_date: str = "2026-10-30", base: str = "BRL") -> dict:
    return {"date": rate_date, "base": base, "quote": quote, "rate": float(rate)}


def _payload(
    *,
    rate_date: str = "2026-10-30",
    omit: str | None = None,
    extra: list[dict] | None = None,
) -> list[dict]:
    rows = [
        _row(quote, _RATE_VALUES[quote], rate_date=rate_date)
        for quote in QUOTE_CURRENCIES
        if quote != omit
    ]
    if extra:
        rows.extend(extra)
    return rows


@asynccontextmanager
async def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AsyncIterator[FrankfurterFxRateProvider]:
    provider = FrankfurterFxRateProvider(
        transport=httpx.MockTransport(handler),
        timeout_seconds=0.1,
        max_retries=1,
        clock=lambda: _FIXED_NOW,
    )
    try:
        yield provider
    finally:
        await provider.aclose()


def test_lista_fechada_e_normalizacao_de_moeda() -> None:
    assert SUPPORTED_CURRENCIES == ("BRL", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY")
    assert QUOTE_CURRENCIES == ("USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY")
    assert normalize_currency(" usd ") == "USD"
    assert normalize_currency("JPY") == "JPY"
    assert normalize_currency("CHF") == BASE_CURRENCY
    assert normalize_currency("") == BASE_CURRENCY
    assert normalize_currency(None) == BASE_CURRENCY


def test_fx_rates_valida_lista_fechada_e_taxas_positivas() -> None:
    rates = _sample_rates()
    assert rates.rate_for("usd") == Decimal("0.18408")
    assert rates.rate_for("CHF") == Decimal("1")

    base = {code: Decimal(value) for code, value in _RATE_VALUES.items()}
    with pytest.raises(ValueError, match="exactly the supported"):
        FxRates(
            rates={**base, "CHF": Decimal("0.15")},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
        )
    with pytest.raises(ValueError, match="exactly the supported"):
        FxRates(
            rates={key: value for key, value in base.items() if key != "USD"},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
        )
    with pytest.raises(ValueError, match="BRL rate must be 1"):
        FxRates(
            rates={**base, "BRL": Decimal("2")},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
        )
    with pytest.raises(ValueError, match="positive finite"):
        FxRates(
            rates={**base, "USD": Decimal("-1")},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
        )
    with pytest.raises(ValueError, match="source"):
        FxRates(
            rates=base,
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source=" ",
        )


async def test_parsing_usa_decimal_data_de_referencia_e_fonte_do_bce() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_payload(extra=[_row("CHF", "0.15149")]))

    async with _provider(handler) as provider:
        rates = await provider.fetch_latest()

    assert len(calls) == 1
    assert calls[0].url.path == "/v2/providers/ecb/rates"
    assert calls[0].url.params["base"] == "BRL"
    assert calls[0].url.params["quotes"] == ",".join(QUOTE_CURRENCIES)
    assert rates.rate_date == date(2026, 10, 30)
    assert rates.fetched_at == _FIXED_NOW
    assert rates.source == "Frankfurter / European Central Bank"
    assert rates.rates["USD"] == Decimal("0.18408")
    assert rates.rates["JPY"] == Decimal("28.946")
    assert rates.rates["BRL"] == Decimal("1")
    assert set(rates.rates) == set(SUPPORTED_CURRENCIES)
    assert "CHF" not in rates.rates


async def test_payload_incompleto_falha_apos_um_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json=_payload(omit="USD"))

    async with _provider(handler) as provider:
        with pytest.raises(FxProviderError):
            await provider.fetch_latest()

    assert attempts == 2


async def test_datas_mistas_falham() -> None:
    rows = _payload()
    rows[0]["date"] = "2026-10-29"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rows)

    async with _provider(handler) as provider:
        with pytest.raises(FxProviderError):
            await provider.fetch_latest()


async def test_base_diferente_de_brl_falha() -> None:
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(200, json=[_row("USD", "0.18", base="EUR")])

    async with _provider(handler) as provider:
        with pytest.raises(FxProviderError):
            await provider.fetch_latest()

    assert attempt_count == 2


async def test_erro_5xx_e_repetido_uma_vez() -> None:
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(503)

    async with _provider(handler) as provider:
        with pytest.raises(FxProviderError):
            await provider.fetch_latest()

    assert attempt_count == 2


async def test_timeout_e_repetido_uma_vez() -> None:
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.ReadTimeout("timeout de teste", request=request)

    async with _provider(handler) as provider:
        with pytest.raises(FxProviderError):
            await provider.fetch_latest()

    assert attempt_count == 2


async def test_sucesso_na_primeira_tentativa_nao_repete() -> None:
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(200, json=_payload())

    async with _provider(handler) as provider:
        await provider.fetch_latest()

    assert attempt_count == 1


class _FakeRedis:
    """Redis minimo: GET/SET (com NX/EX) e DELETE, com modo de falha."""

    def __init__(self, *, fail: bool = False) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RuntimeError("redis fora do ar")
        return self.data.get(key)

    async def set(
        self, key: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if self.fail:
            raise RuntimeError("redis fora do ar")
        if nx and key in self.data:
            return None
        self.data[key] = value
        self.ttls[key] = ex if ex is not None else 0
        return True

    async def delete(self, key: str) -> int:
        if self.fail:
            raise RuntimeError("redis fora do ar")
        return 1 if self.data.pop(key, None) is not None else 0


def _redis_cache(fake: _FakeRedis) -> RedisFxRateCache:
    return RedisFxRateCache(redis_client=cast("Any", fake))


async def test_cache_round_trip_com_ttls_fresco_e_ultima_conhecida() -> None:
    fake = _FakeRedis()
    cache = _redis_cache(fake)
    rates = _sample_rates()

    await cache.save(rates)

    assert sorted(fake.ttls.values()) == sorted([FX_RATES_TTL_SECONDS, FX_LAST_KNOWN_TTL_SECONDS])
    assert await cache.load_fresh() == rates
    assert await cache.load_last_known() == rates


def test_payload_canonico_e_estavel() -> None:
    expected = (
        '{"base":"BRL","fetched_at":"2026-10-30T23:00:00+00:00",'
        '"rate_date":"2026-10-30","rates":{"AUD":"0.26204","BRL":"1",'
        '"CAD":"0.25713","CNY":"1.2246","EUR":"0.16477","GBP":"0.13738",'
        '"JPY":"28.946","USD":"0.18408"},'
        '"source":"Frankfurter / European Central Bank"}'
    )

    assert encode_rates(_sample_rates()) == expected
    assert encode_rates(_sample_rates()) == encode_rates(_sample_rates())


def test_payload_corrompido_vira_none() -> None:
    assert decode_rates("{") is None
    assert decode_rates('{"base":"BRL"}') is None
    assert (
        decode_rates(
            '{"base":"BRL","rates":{"USD":"1"},"rate_date":"2026-10-30",'
            '"fetched_at":"2026-10-30T23:00:00+00:00","source":"x"}'
        )
        is None
    )


async def test_redis_indisponivel_degrada_sem_quebrar() -> None:
    fake = _FakeRedis(fail=True)
    cache = _redis_cache(fake)

    assert await cache.load_fresh() is None
    assert await cache.load_last_known() is None
    await cache.save(_sample_rates())

    token = await cache.acquire_refresh_lock()
    assert token is not None
    await cache.release_refresh_lock(token)


async def test_lock_tem_um_dono_e_libera_pelo_token() -> None:
    fake = _FakeRedis()
    cache = _redis_cache(fake)

    token = await cache.acquire_refresh_lock()
    assert token is not None
    assert await cache.acquire_refresh_lock() is None

    await cache.release_refresh_lock("outro-token")
    assert fake.data

    await cache.release_refresh_lock(token)
    assert fake.data == {}
    assert await cache.acquire_refresh_lock() is not None


async def test_sem_redis_nao_cacheia_mas_nao_quebra() -> None:
    cache = RedisFxRateCache(redis_client=None)
    rates = _sample_rates()

    assert await cache.load_fresh() is None
    assert await cache.load_last_known() is None
    await cache.save(rates)
    token = await cache.acquire_refresh_lock()
    assert token is not None
    await cache.release_refresh_lock(token)


class _FakeProvider:
    def __init__(
        self,
        *,
        result: FxRates | None = None,
        error: Exception | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.started = started
        self.gate = gate
        self.calls = 0

    async def fetch_latest(self) -> FxRates:
        self.calls += 1
        if self.started is not None:
            self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("provider sem resultado")
        return self.result


class _FakeCache:
    def __init__(
        self,
        *,
        fresh: FxRates | None = None,
        last_known: FxRates | None = None,
        lock_busy: bool = False,
    ) -> None:
        self.fresh = fresh
        self.last_known = last_known
        self.lock_busy = lock_busy
        self.saves = 0

    async def load_fresh(self) -> FxRates | None:
        return self.fresh

    async def load_last_known(self) -> FxRates | None:
        return self.last_known

    async def save(self, rates: FxRates) -> None:
        self.saves += 1
        self.fresh = rates
        self.last_known = rates

    async def acquire_refresh_lock(self) -> str | None:
        if self.lock_busy:
            return None
        self.lock_busy = True
        return "token"

    async def release_refresh_lock(self, token: str) -> None:
        if token == "token":
            self.lock_busy = False


def _use_case(
    provider: FxRateProvider,
    cache: FxRateCache,
    *,
    wait_seconds: float = 1.0,
) -> GetFxRates:
    return GetFxRates(
        provider=provider,
        cache=cache,
        refresh_wait_seconds=wait_seconds,
        poll_interval_seconds=0.01,
    )


async def test_hit_fresco_nao_chama_o_provedor() -> None:
    rates = _sample_rates()
    provider = _FakeProvider(result=None)
    view = await _use_case(provider, _FakeCache(fresh=rates)).run()

    assert view.rates == rates
    assert view.stale is False
    assert provider.calls == 0


async def test_miss_consulta_e_grava_como_fresco() -> None:
    rates = _sample_rates()
    cache = _FakeCache()
    provider = _FakeProvider(result=rates)

    view = await _use_case(provider, cache).run()

    assert view.rates == rates
    assert view.stale is False
    assert provider.calls == 1
    assert cache.saves == 1
    assert cache.lock_busy is False


async def test_expiracao_refresca_mesmo_havendo_ultima_conhecida() -> None:
    old = _sample_rates(fetched_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC))
    new = _sample_rates()
    cache = _FakeCache(last_known=old)
    provider = _FakeProvider(result=new)

    view = await _use_case(provider, cache).run()

    assert view.rates == new
    assert view.stale is False
    assert provider.calls == 1
    assert cache.saves == 1


async def test_falha_do_provedor_serve_ultima_conhecida_stale() -> None:
    old = _sample_rates(fetched_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC))
    cache = _FakeCache(last_known=old)
    provider = _FakeProvider(error=FxProviderError("fora do ar"))

    view = await _use_case(provider, cache).run()

    assert view.rates == old
    assert view.stale is True
    assert provider.calls == 1
    assert cache.saves == 0


async def test_sem_taxa_nenhuma_devolve_erro_503_tipado() -> None:
    provider = _FakeProvider(error=FxProviderError("fora do ar"))

    with pytest.raises(FxRatesUnavailableError) as exc_info:
        await _use_case(provider, _FakeCache()).run()

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "fx_rates_unavailable"
    assert "indisponiveis" in exc_info.value.detail


async def test_lock_de_concorrencia_permite_uma_unica_chamada_ao_provedor() -> None:
    rates = _sample_rates()
    started = asyncio.Event()
    gate = asyncio.Event()
    provider = _FakeProvider(result=rates, started=started, gate=gate)
    cache = _FakeCache()
    use_case = _use_case(provider, cache, wait_seconds=1.0)

    first = asyncio.create_task(use_case.run())
    await started.wait()
    second = asyncio.create_task(use_case.run())
    await asyncio.sleep(0)
    gate.set()

    views = await asyncio.gather(first, second)

    assert provider.calls == 1
    assert cache.saves == 1
    assert all(view.rates == rates and view.stale is False for view in views)


async def test_lock_ocupado_sem_fresco_recorre_a_ultima_conhecida() -> None:
    old = _sample_rates(fetched_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC))
    provider = _FakeProvider(result=_sample_rates())
    cache = _FakeCache(last_known=old, lock_busy=True)

    view = await _use_case(provider, cache, wait_seconds=0.0).run()

    assert view.rates == old
    assert view.stale is True
    assert provider.calls == 0
