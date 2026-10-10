"""Testes unitarios da configuracao tipada (sem Docker)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_de_desenvolvimento() -> None:
    settings = Settings(otel_enabled=False)
    assert settings.app_name == "forja-backend"
    assert settings.environment == "development"
    assert settings.is_production is False
    assert settings.database_url.hosts()[0]["host"] == "localhost"
    assert settings.database_url.path == "/forja_db"
    assert settings.database_admin_url is None


def test_leitura_de_variaveis_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://forja_app:secret@db.internal:5432/forja_db"
    )
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379/0")
    settings = Settings(otel_enabled=False)
    assert settings.environment == "production"
    assert settings.is_production is True
    assert settings.database_url.hosts()[0]["host"] == "db.internal"
    assert settings.redis_url.host == "redis.internal"


def test_url_de_banco_invalida_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "nao-e-uma-url")
    with pytest.raises(ValidationError):
        Settings()


def test_pool_com_limites_validados() -> None:
    with pytest.raises(ValidationError):
        Settings(db_pool_size=0)


_BLANK = "   "
_ES_SECRET = "segredo-de-teste"  # valor efemero de teste, nunca real
_ES_KEY = "chave-de-teste"


def test_credenciais_vazias_do_es_sao_tratadas_como_ausentes() -> None:
    settings = Settings(
        otel_enabled=False,
        elasticsearch_api_key="",
        elasticsearch_username="",
        elasticsearch_password=_BLANK,
        elasticsearch_ca_certs="",
    )
    assert settings.elasticsearch_api_key is None
    assert settings.elasticsearch_username is None
    assert settings.elasticsearch_password is None
    assert settings.elasticsearch_ca_certs is None


def test_sem_api_key_usa_basic_auth_mesmo_com_valor_vazio() -> None:
    from app.modules.search.infrastructure.elasticsearch import _basic_auth

    settings = Settings(
        otel_enabled=False,
        elasticsearch_api_key="",
        elasticsearch_username="elastic",
        elasticsearch_password=_ES_SECRET,
    )
    assert _basic_auth(settings) == ("elastic", _ES_SECRET)


def test_api_key_preenchida_desliga_basic_auth() -> None:
    from app.modules.search.infrastructure.elasticsearch import _basic_auth

    settings = Settings(
        otel_enabled=False,
        elasticsearch_api_key=_ES_KEY,
        elasticsearch_username="elastic",
        elasticsearch_password=_ES_SECRET,
    )
    assert _basic_auth(settings) is None
