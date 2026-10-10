"""Configuracao tipada da aplicacao via pydantic-settings.

Toda configuracao vem de variaveis de ambiente (ver .env.example).
Nenhum segredo e hardcoded: os defaults abaixo sao os valores de
desenvolvimento ja publicados em .env.example e no docker-compose.yml.

Separacao de credenciais (ver docs/RUNBOOK.md secao 4):
- `database_url`: role de runtime (forja_app, sujeita a RLS). Unica URL de
  banco injetada nos containers backend/worker.
- `database_admin_url`: role administrativa restrita (forja_admin). Pertence
  EXCLUSIVAMENTE a processos de migracao/operacao (Alembic via `make migrate`
  ou CI). Nunca e injetada no runtime normal e nunca e usada pela aplicacao.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
LogFormat = Literal["json", "console"]


class Settings(BaseSettings):
    """Configuracoes da aplicacao lidas do ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "forja-backend"
    environment: Environment = "development"
    log_level: str = "INFO"
    log_format: LogFormat = "json"

    # Banco de dados (role de runtime, sujeita a RLS).
    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+asyncpg://forja_app:forja_app_secret_dev@localhost:5432/forja_db"
        )
    )
    # Somente para ferramentas de migracao/operacao (Alembic). A aplicacao
    # nunca le este campo em runtime; ele existe para tipagem do ambiente.
    database_admin_url: PostgresDsn | None = None

    # Pool do SQLAlchemy.
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout_seconds: int = Field(default=30, ge=1)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)

    # Redis (cache, rate limit, readiness).
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    # OpenTelemetry (fundacao apenas).
    otel_enabled: bool = True
    otel_service_name: str = "forja-backend"
    otel_exporter_otlp_endpoint: str | None = None

    # Elasticsearch (busca lexical; Fase 2). Seguranca LIGADA no servidor
    # (xpack.security) com autenticacao por senha. Em desenvolvimento usa-se
    # HTTP sem TLS apenas na rede interna do Docker; TLS e obrigatorio em
    # producao (Fase 6). `elasticsearch_enabled=False` desliga a integracao e a
    # aplicacao sobe em modo degradado. O Elasticsearch NUNCA e fonte de
    # verdade: os dados comerciais (preco/estoque) permanecem no PostgreSQL.
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_username: str | None = "elastic"
    elasticsearch_password: str | None = "forja_es_dev_password"  # noqa: S105 - default de dev
    elasticsearch_api_key: str | None = None
    elasticsearch_index: str = "forja_products"
    elasticsearch_index_version: int = Field(default=1, ge=1)
    elasticsearch_index_replicas: int = Field(default=0, ge=0)
    elasticsearch_request_timeout_seconds: float = Field(default=5.0, gt=0)
    elasticsearch_bulk_batch_size: int = Field(default=500, ge=1)
    elasticsearch_enabled: bool = True
    elasticsearch_max_retries: int = Field(default=3, ge=0)

    # Sincronizacao do indice de busca (Fase 3): tentativas por evento na
    # outbox antes de descartar (dead-letter).
    search_outbox_max_attempts: int = Field(default=5, ge=1)

    # Seguranca de aplicacao (Fase 2).
    # `secret_key`: assinatura HMAC dos JWTs de acesso (HS256). Em producao
    # DEVE ser forte e injetada via secrets; em desenvolvimento usa o valor
    # publicado em .env.example. Nunca em hardcode em staging/production.
    secret_key: str = "dev_secret_key_change_in_production_min_32_bytes_long_value"  # noqa: S105 - default de dev, nunca em producao
    # `pepper`: HMAC do CPF (mesmo esquema do seed da Fase 1). Valor de dev.
    pepper: str = "dev_pepper_secret_for_cpf_hmac_2026"
    # JWT de acesso (curta duracao) e refresh (rotacao, armazenado no Redis).
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Google OAuth (fluxo tradicional de redirect). Todos opcionais: ausentes,
    # o fluxo OAuth fica indisponivel (o frontend oculta o botao). O segredo e
    # injetado apenas pelo backend (nunca exposto ao frontend).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_oauth_frontend_redirect: str | None = None

    # Pagamentos (Fase 10): desconto PIX simulado e segredo do webhook HMAC.
    # `payment_webhook_secret` autentica eventos do provedor (canal
    # sistema-a-sistema); nunca usado para autenticar usuarios. Default de dev
    # publicado em .env.example; em producao deve ser injetado via secrets.
    pix_discount_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    payment_webhook_secret: str = "dev_payment_webhook_secret_change_in_production"  # noqa: S105 - default de dev, nunca em producao

    # Celery (worker assincrono de notificacoes/outbox). Defaults de dev.
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/2"

    # E-mail (notificacoes, Fase 11): SMTP local (Mailpit), sem segredos.
    email_smtp_host: str = "localhost"
    email_smtp_port: int = Field(default=1025, ge=1)
    email_from: str = "no-reply@forja.local"

    # Admin de plataforma (aprovação de empresas). Em producao deve ser uma
    # chave forte injetada via secrets manager. Ausente, a rota admin 401.
    admin_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def google_oauth_enabled(self) -> bool:
        return all(
            value is not None
            for value in (
                self.google_client_id,
                self.google_client_secret,
                self.google_redirect_uri,
                self.google_oauth_frontend_redirect,
            )
        )


@lru_cache
def get_settings() -> Settings:
    """Settings cacheadas por processo; testes usam Settings() diretamente."""
    return Settings()
