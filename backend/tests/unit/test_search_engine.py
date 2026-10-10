"""Testes unitarios do motor de busca (sem Docker e sem Elasticsearch real)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import SearchEngineState
from app.modules.search.infrastructure.elasticsearch import (
    ElasticsearchSearchEngine,
    build_search_engine,
    classify_cluster_status,
    translate_elasticsearch_error,
)


@pytest.mark.parametrize(
    ("cluster_status", "expected"),
    [
        ("green", SearchEngineState.OK),
        ("yellow", SearchEngineState.OK),
        ("red", SearchEngineState.DEGRADED),
    ],
)
def test_classify_cluster_status(cluster_status: str, expected: SearchEngineState) -> None:
    assert classify_cluster_status(cluster_status) is expected


def test_factory_retorna_none_quando_desabilitado() -> None:
    settings = Settings(otel_enabled=False, elasticsearch_enabled=False)
    assert build_search_engine(settings) is None


def test_factory_monta_engine_com_indice_configurado() -> None:
    settings = Settings(otel_enabled=False, elasticsearch_enabled=True, elasticsearch_index="idx-x")
    engine = build_search_engine(settings)
    assert isinstance(engine, ElasticsearchSearchEngine)
    assert engine.index == "idx-x"


def test_traducao_de_erro_para_search_unavailable() -> None:
    error = translate_elasticsearch_error(ValueError("boom"))
    assert isinstance(error, SearchUnavailableError)
    assert error.status_code == 503
    assert error.code == "search_unavailable"


async def test_check_health_indisponivel_sem_servidor() -> None:
    engine = ElasticsearchSearchEngine(
        url="http://127.0.0.1:9",
        username="elastic",
        password="x",  # noqa: S106 - credencial descartavel de teste (sem valor real)
        api_key=None,
        index="forja-products",
        request_timeout_seconds=1.0,
        max_retries=0,
    )
    try:
        health = await engine.check_health()
    finally:
        await engine.close()
    assert health.state is SearchEngineState.UNAVAILABLE


def test_settings_leem_variaveis_elasticsearch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://es.internal:9200")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "idx-env")
    monkeypatch.setenv("ELASTICSEARCH_ENABLED", "false")
    monkeypatch.setenv("ELASTICSEARCH_REQUEST_TIMEOUT_SECONDS", "2.5")
    settings = Settings(otel_enabled=False)
    assert settings.elasticsearch_url == "http://es.internal:9200"
    assert settings.elasticsearch_index == "idx-env"
    assert settings.elasticsearch_enabled is False
    assert settings.elasticsearch_request_timeout_seconds == 2.5
