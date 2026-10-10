"""Testes das metricas Prometheus da busca (Fase 6, observabilidade)."""

from __future__ import annotations

from prometheus_client import generate_latest

from app.core import metrics


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
