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
