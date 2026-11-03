"""Testes unitarios da configuracao tipada (sem Docker)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ConfigurationError


def test_defaults_de_desenvolvimento() -> None:
    settings = Settings(otel_enabled=False)
    assert settings.app_name == "forja-backend"
    assert settings.environment == "development"
    assert settings.is_production is False
    assert settings.database_url.hosts()[0]["host"] == "localhost"
    assert settings.database_url.path == "/forja_db"
    assert settings.database_admin_url is None
    assert settings.reconcile_interval_seconds == 0  # agendador desligado por padrao
    assert settings.search_metrics_interval_seconds == 30


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


def test_url_libpq_do_provedor_e_normalizada_para_asyncpg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render injeta `postgresql://`; o SQLAlchemy tentaria psycopg2 no boot."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://forja_app:secret@dpg-host.oregon-postgres.render.com:5432/"
        "forja_db?sslmode=require",
    )
    monkeypatch.setenv(
        "DATABASE_ADMIN_URL",
        "postgres://forja_admin:secret@dpg-host.oregon-postgres.render.com:5432/forja_db",
    )
    settings = Settings(otel_enabled=False)
    assert str(settings.database_url).startswith("postgresql+asyncpg://")
    assert "sslmode" not in str(settings.database_url)
    assert "ssl=require" in str(settings.database_url)
    assert str(settings.database_admin_url).startswith("postgresql+asyncpg://")


def test_url_ja_asyncpg_e_preservada(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://forja_app:secret@db.internal:5432/forja_db"
    monkeypatch.setenv("DATABASE_URL", url)
    assert str(Settings(otel_enabled=False).database_url) == url


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


_RECOVERY_ENV = {
    "TURNSTILE_SECRET_KEY": "test-turnstile-secret",
    "TWILIO_ACCOUNT_SID": "test-twilio-account-sid",
    "TWILIO_AUTH_TOKEN": "test-twilio-auth-token",
    "TWILIO_VERIFY_SERVICE_SID": "test-twilio-verify-service-sid",
    "RESEND_API_KEY": "test-resend-api-key",
}


def _recovery_settings(**overrides: object) -> Settings:
    values: dict[str, Any] = {
        "otel_enabled": False,
        "environment": "production",
        "password_recovery_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_recuperacao_de_conta_desligada_por_padrao() -> None:
    settings = Settings(otel_enabled=False, _env_file=None)
    assert settings.password_recovery_enabled is False
    assert settings.recovery_code_ttl_seconds == 600
    assert settings.recovery_code_max_attempts == 5
    assert settings.recovery_reset_token_ttl_seconds == 600


def test_recuperacao_em_producao_exige_todas_as_credenciais() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        _recovery_settings(
            turnstile_secret_key=None,
            twilio_account_sid=None,
            twilio_auth_token=None,
            twilio_verify_service_sid=None,
            resend_api_key=None,
        )

    message = str(excinfo.value)
    assert "TURNSTILE_SECRET_KEY" in message
    assert "TWILIO_ACCOUNT_SID" in message
    assert "TWILIO_AUTH_TOKEN" in message
    assert "TWILIO_VERIFY_SERVICE_SID" in message
    assert "RESEND_API_KEY" in message


def test_recuperacao_em_producao_lista_apenas_variaveis_ausentes() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        _recovery_settings(
            turnstile_secret_key=_RECOVERY_ENV["TURNSTILE_SECRET_KEY"],
            twilio_account_sid=_RECOVERY_ENV["TWILIO_ACCOUNT_SID"],
            twilio_auth_token=None,
            twilio_verify_service_sid=_RECOVERY_ENV["TWILIO_VERIFY_SERVICE_SID"],
            resend_api_key=_RECOVERY_ENV["RESEND_API_KEY"],
        )

    message = str(excinfo.value)
    assert "TWILIO_AUTH_TOKEN" in message
    assert "TWILIO_ACCOUNT_SID" not in message
    assert _RECOVERY_ENV["TWILIO_ACCOUNT_SID"] not in message


def test_recuperacao_em_producao_nao_expoe_segredos_em_repr() -> None:
    settings = _recovery_settings(**{key.lower(): value for key, value in _RECOVERY_ENV.items()})

    rendered = repr(settings)
    for value in (
        _RECOVERY_ENV["TURNSTILE_SECRET_KEY"],
        _RECOVERY_ENV["TWILIO_ACCOUNT_SID"],
        _RECOVERY_ENV["TWILIO_AUTH_TOKEN"],
        _RECOVERY_ENV["TWILIO_VERIFY_SERVICE_SID"],
    ):
        assert value not in rendered
    assert settings.twilio_auth_token is not None
    assert settings.twilio_auth_token.get_secret_value() == _RECOVERY_ENV["TWILIO_AUTH_TOKEN"]


def test_recuperacao_em_desenvolvimento_permite_credenciais_ausentes() -> None:
    settings = _recovery_settings(
        environment="development",
        turnstile_secret_key=None,
        twilio_account_sid=None,
        twilio_auth_token=None,
        twilio_verify_service_sid=None,
        resend_api_key=None,
    )
    assert settings.password_recovery_enabled is True
    assert settings.turnstile_secret_key is None


def test_credenciais_de_recuperacao_vazias_viram_none() -> None:
    settings = _recovery_settings(
        environment="development",
        turnstile_secret_key="   ",
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_verify_service_sid="",
    )
    assert settings.turnstile_secret_key is None
    assert settings.twilio_account_sid is None
    assert settings.twilio_auth_token is None
    assert settings.twilio_verify_service_sid is None


def test_twilio_client_sid_nao_faz_parte_das_settings() -> None:
    assert "twilio_client_sid" not in Settings.model_fields


def test_phone_verification_dry_run_proibido_em_producao() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(
            _env_file=None,
            environment="production",
            otel_enabled=False,
            phone_verification_dry_run=True,
        )
    assert "PHONE_VERIFICATION_DRY_RUN" in str(excinfo.value)
