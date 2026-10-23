"""Testes das metricas Prometheus da busca (Fase 6, observabilidade)."""

from __future__ import annotations

from prometheus_client import REGISTRY, generate_latest

from app.core import metrics
from app.modules.search.application.ports import SearchOutboxStats
from app.modules.search.application.sync import RefreshSearchMetrics


class _StatsReader:
    async def stats(self) -> SearchOutboxStats:
        return SearchOutboxStats(pending=5, dead=1, oldest_pending_age_seconds=12.0)


def _exposition() -> str:
    return generate_latest().decode()


def test_observe_search_expoe_requisicoes_por_modo() -> None:
    metrics.observe_search(mode="lexical", duration=0.01)
    metrics.observe_search(mode="hybrid", duration=0.02)
    text = _exposition()
    assert 'forja_search_requests_total{mode="lexical"}' in text
    assert 'forja_search_requests_total{mode="hybrid"}' in text
    assert "forja_search_duration_seconds" in text


def test_modo_degradado_conta_fallback_e_hibrido_nao() -> None:
    metrics.observe_search(mode="postgres_fallback", duration=0.01)
    metrics.observe_search(mode="hybrid", duration=0.01)
    text = _exposition()
    assert 'forja_search_fallback_total{mode="postgres_fallback"}' in text
    assert 'forja_search_fallback_total{mode="hybrid"}' not in text


def test_gauges_da_outbox_refletem_o_instantaneo() -> None:
    metrics.observe_outbox_snapshot(pending=7, dead=2, oldest_pending_age_seconds=42.5)
    assert REGISTRY.get_sample_value("forja_outbox_pending") == 7
    assert REGISTRY.get_sample_value("forja_outbox_dead_total") == 2
    assert REGISTRY.get_sample_value("forja_outbox_oldest_pending_age_seconds") == 42.5


def test_reconcile_registra_sucesso_duracao_e_drift() -> None:
    before = REGISTRY.get_sample_value("forja_reconcile_drift_total", {"kind": "upserted"}) or 0.0
    metrics.observe_reconcile_success(duration=0.25, upserted=3, deleted=1)
    after = REGISTRY.get_sample_value("forja_reconcile_drift_total", {"kind": "upserted"}) or 0.0
    assert after == before + 3
    assert (REGISTRY.get_sample_value("forja_reconcile_last_success_timestamp_seconds") or 0) > 0


async def test_refresh_search_metrics_le_a_outbox_e_atualiza_gauges() -> None:
    stats = await RefreshSearchMetrics(outbox=_StatsReader()).run()
    assert stats.pending == 5
    assert REGISTRY.get_sample_value("forja_outbox_pending") == 5
    assert REGISTRY.get_sample_value("forja_outbox_dead_total") == 1
    assert REGISTRY.get_sample_value("forja_outbox_oldest_pending_age_seconds") == 12.0


def test_reconcile_falha_nao_atualiza_timestamp_de_sucesso() -> None:
    metrics.observe_reconcile_success(duration=0.1, upserted=0, deleted=0)
    success_before = REGISTRY.get_sample_value("forja_reconcile_last_success_timestamp_seconds")
    failures_before = REGISTRY.get_sample_value("forja_reconcile_failures_total") or 0.0
    metrics.observe_reconcile_failure(duration=0.2)
    assert (
        REGISTRY.get_sample_value("forja_reconcile_last_success_timestamp_seconds")
        == success_before
    )
    failures_after = REGISTRY.get_sample_value("forja_reconcile_failures_total") or 0.0
    assert failures_after == failures_before + 1
