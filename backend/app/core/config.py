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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
LogFormat = Literal["json", "console"]

_ASYNC_POSTGRES_SCHEME = "postgresql+asyncpg"
_LIBPQ_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql"})


def normalize_async_database_url(url: str) -> str:
    """Normaliza uma URL PostgreSQL para o driver asyncpg.

    Provedores gerenciados (Render, Heroku, etc.) costumam injetar a URL no
    formato libpq (``postgresql://``), que o SQLAlchemy resolve para o driver
    sincrono psycopg2. Como a aplicacao usa ``create_async_engine``, o boot
    falharia com ``ModuleNotFoundError: No module named 'psycopg2'``. A URL e
    reescrita para ``postgresql+asyncpg://``.

    O parametro libpq ``sslmode`` tambem e traduzido para ``ssl``, que e o
    nome aceito pelo asyncpg (o SQLAlchemy repassa os query params ao driver).
    URLs com outro driver (ou nao PostgreSQL) sao devolvidas sem alteracao.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme in _LIBPQ_POSTGRES_SCHEMES:
        scheme = _ASYNC_POSTGRES_SCHEME
    if scheme != _ASYNC_POSTGRES_SCHEME:
        return url

    query = [
        ("ssl" if key == "sslmode" else key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


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
    elasticsearch_index_version: int = Field(default=2, ge=1)
    elasticsearch_index_replicas: int = Field(default=0, ge=0)
    # Timeouts/retries SEPARADOS por uso (Fase 8A):
    # - busca interativa (consulta/autocomplete): curto e SEM retries, para cair
    #   no fallback rapido quando o ES nao responde;
    # - indexacao/reindex/reconcile/bootstrap: mais longo, com retries proprios.
    elasticsearch_search_timeout_seconds: float = Field(default=2.0, gt=0)
    elasticsearch_search_max_retries: int = Field(default=0, ge=0)
    elasticsearch_index_timeout_seconds: float = Field(default=30.0, gt=0)
    elasticsearch_index_max_retries: int = Field(default=3, ge=0)
    elasticsearch_bulk_batch_size: int = Field(default=500, ge=1)
    elasticsearch_enabled: bool = True
    # TLS (Fase 6): a verificacao de certificado e SEMPRE ativa (nunca desabilitar
    # em producao). `ca_certs` aponta para a CA do cluster (Elastic Cloud ou VPS).
    elasticsearch_verify_certs: bool = True
    elasticsearch_ca_certs: str | None = None

    # Sincronizacao do indice de busca (Fase 3): tentativas por evento na
    # outbox antes de descartar (dead-letter).
    search_outbox_max_attempts: int = Field(default=5, ge=1)
    # Intervalo do atualizador de gauges da outbox no processo da API (0 = off).
    search_metrics_interval_seconds: int = Field(default=30, ge=0, le=3600)
    # Reconciliacao dentro do processo (0 = desligada; use o CLI/Cron).
    reconcile_interval_seconds: int = Field(default=0, ge=0)
    reconcile_jitter_seconds: int = Field(default=20, ge=0, le=300)
    reconcile_timeout_seconds: int = Field(default=300, ge=1, le=3600)

    # Busca lexical (Fase 4): paginacao, limites e autocomplete.
    search_default_page_size: int = Field(default=20, ge=1, le=100)
    search_max_page_size: int = Field(default=100, ge=1)
    search_max_query_length: int = Field(default=100, ge=1)
    search_max_deep_pagination: int = Field(default=5000, ge=0)
    search_autocomplete_min_chars: int = Field(default=2, ge=1)
    search_autocomplete_max_suggestions: int = Field(default=10, ge=1)
    # Circuit breaker simples do caminho lexical (Fase 8A): apos N falhas
    # consecutivas, pula o Elasticsearch por T segundos (vai direto ao fallback)
    # e retoma automaticamente (meia-abertura) apos o cooldown.
    search_circuit_breaker_failures: int = Field(default=3, ge=1)
    search_circuit_breaker_cooldown_seconds: float = Field(default=15.0, gt=0)
    # Tolerancia de divergencia de contagem na reindexacao (Fase 8A). Zero por
    # padrao: a troca de alias so ocorre se o novo indice bater com o Postgres.
    search_reindex_count_tolerance: int = Field(default=0, ge=0)

    # Busca semantica (Fase 5): pgvector + embeddings locais (ONNX).
    # Desabilitada por padrao: sem a dependencia de runtime e o modelo baixado,
    # a aplicacao sobe em modo lexical e o `search_mode` reflete isso. O modelo
    # e baixado no build da imagem (nunca em tempo de requisicao).
    embeddings_enabled: bool = False
    embedding_provider: str = "onnx"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimension: int = Field(default=384, ge=1)
    embedding_model_path: str = "/models/multilingual-e5-small"
    embedding_onnx_filename: str = "model_O4.onnx"
    embedding_tokenizer_filename: str = "tokenizer.json"
    embedding_batch_size: int = Field(default=64, ge=1)
    embedding_candidate_limit: int = Field(default=50, ge=1)
    embedding_rrf_k: int = Field(default=60, ge=1)
    embedding_query_timeout_seconds: float = Field(default=2.0, gt=0)

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
    # Rotacao sem janela de falha: o segredo anterior continua aceito ate a
    # publicacao do novo em todos os produtores. Pode ficar vazio.
    payment_webhook_secret_previous: str | None = None
    # Limite do corpo de webhooks e tolerancia de timestamp (anti-replay).
    webhook_max_body_bytes: int = Field(default=1024 * 1024, ge=1024)
    webhook_timestamp_tolerance_seconds: int = Field(default=300, ge=30, le=3600)

    # Stripe Checkout (cartao). `stripe_secret_key` cria a Checkout Session;
    # `stripe_webhook_secret` (whsec_...) valida a assinatura Stripe-Signature.
    # Compatibilidade: se apenas `stripe_webhook_secret` estiver preenchido com
    # uma chave `sk_...`, ela e usada como chave secreta (ver propriedades).
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_webhook_secret_previous: str | None = None
    stripe_checkout_success_path: str = "/checkout/success"
    stripe_checkout_cancel_path: str = "/checkout/cancel"

    # Idempotencia de mutacoes criticas (header Idempotency-Key).
    idempotency_ttl_seconds: int = Field(default=24 * 60 * 60, ge=60)
    idempotency_in_progress_ttl_seconds: int = Field(default=60, ge=5, le=600)
    # URL publica do frontend (sem barra final), usada nos redirects do Stripe.
    frontend_base_url: str = "http://localhost:3000"

    # CORS: origens do frontend autorizadas a chamar a API pelo navegador.
    # Em producao, defina CORS_ORIGINS com o dominio real do site. A lista e
    # SEMPRE explicita: `*` e rejeitado (com ou sem credenciais), porque o
    # projeto usa Bearer token e nao precisa de origem curinga.
    cors_origins: str = "http://localhost:3000,http://localhost:3010,https://forja-b2b.vercel.app"
    cors_allow_credentials: bool = False
    cors_max_age_seconds: int = Field(default=600, ge=1)

    # Rate limiting (Redis + fallback local). Limites de token bucket por
    # classe: capacidade (burst) e taxa de reposicao por minuto.
    rate_limit_enabled: bool = True
    rate_limit_auth_capacity: int = Field(default=5, ge=1)
    rate_limit_auth_refill_per_minute: float = Field(default=10.0, gt=0)
    rate_limit_registration_capacity: int = Field(default=3, ge=1)
    rate_limit_registration_refill_per_minute: float = Field(default=5.0, gt=0)
    rate_limit_search_capacity: int = Field(default=30, ge=1)
    rate_limit_search_refill_per_minute: float = Field(default=120.0, gt=0)
    # Dropdown de sugestoes (/search/suggest): balde proprio e mais folgado que
    # o da busca da pagina de resultados (digitação gera rajadas curtas).
    rate_limit_suggest_capacity: int = Field(default=40, ge=1)
    rate_limit_suggest_refill_per_minute: float = Field(default=180.0, gt=0)
    rate_limit_admin_write_capacity: int = Field(default=20, ge=1)
    rate_limit_admin_write_refill_per_minute: float = Field(default=60.0, gt=0)
    rate_limit_authenticated_capacity: int = Field(default=60, ge=1)
    rate_limit_authenticated_refill_per_minute: float = Field(default=240.0, gt=0)
    rate_limit_public_read_capacity: int = Field(default=120, ge=1)
    rate_limit_public_read_refill_per_minute: float = Field(default=600.0, gt=0)
    # Webhooks de terceiros: limite proprio, por IP (sem JWT).
    rate_limit_webhook_capacity: int = Field(default=120, ge=1)
    rate_limit_webhook_refill_per_minute: float = Field(default=300.0, gt=0)
    # Endpoints de IA (chat): classe propria, por IP ou por usuario; somada ao
    # orcamento diario de tokens (AI_DAILY_TOKEN_BUDGET). Sem rota mapeada
    # ainda (FASE 3) — a classe e a politica ja ficam definidas.
    rate_limit_ai_capacity: int = Field(default=20, ge=1)
    rate_limit_ai_refill_per_minute: float = Field(default=60.0, gt=0)
    # Quantidade de proxies confiaveis entre a internet e a aplicacao. Render
    # usa 1. Com 0 (default local), X-Forwarded-For e ignorado.
    trusted_proxy_count: int = Field(default=0, ge=0, le=10)
    # Bloqueio progressivo de login por conta+IP (sem revelar se a conta existe).
    login_failure_threshold: int = Field(default=3, ge=1)
    login_failure_window_seconds: int = Field(default=900, ge=1)
    login_failure_base_backoff_seconds: int = Field(default=30, ge=1)
    login_failure_max_backoff_seconds: int = Field(default=900, ge=1)

    # Cabecalhos de seguranca.
    security_hsts_enabled: bool = True
    security_hsts_max_age_seconds: int = Field(default=31536000, ge=0)
    security_hsts_include_subdomains: bool = True

    # Celery (worker assincrono de notificacoes/outbox). Defaults de dev.
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/2"

    # E-mail (notificacoes, Fase 11): SMTP local (Mailpit), sem segredos.
    email_smtp_host: str = "localhost"
    email_smtp_port: int = Field(default=1025, ge=1)
    email_from: str = "no-reply@forja.local"

    # Admin de plataforma (aprovacao de empresas e administracao de traducoes).
    # Em producao deve ser uma chave forte injetada via secrets. Ausente, 401.
    admin_api_key: str | None = None

    # Internacionalizacao do catalogo (Fase 9B).
    # UI_LOCALES: 11 idiomas da interface (frontend/next-intl).
    # CONTENT_LOCALES: 4 idiomas de conteudo de produto (pt-BR, en, es, ar).
    # Fallback de conteudo: idioma pedido -> en -> pt-BR (campo a campo).
    ui_locales: str = "pt-BR,en,zh-CN,ja,ko,ru,es,de,fr,it,ar"
    supported_locales: str = "pt-BR,en,es,ar"
    default_locale: str = "pt-BR"
    # Provedor de traducao automatica: "null" (padrao) = nenhum. Nenhum provedor
    # externo e adotado nesta fase; a porta existe para decisao futura.
    translation_provider: str = "null"
    translation_max_text_length: int = Field(default=4000, ge=1)

    # Agentes de IA (Fase 12): chat no app e recuperacao de carrinho abandonado.
    # `ai_agents_enabled` e o KILL SWITCH geral: false (default) desliga todos os
    # endpoints e jobs de IA (endpoints respondem 503, jobs nao fazem nada) e
    # nenhum caminho de requisicao importa pacotes de LLM. Falha de IA nunca
    # bloqueia catalogo, carrinho, checkout ou pedido.
    ai_agents_enabled: bool = False
    # LLM via API compativel com OpenAI (qualquer endpoint: OpenAI, Azure,
    # gateways, modelos locais). `llm_api_key` fica SOMENTE no backend, nunca
    # vai para logs, respostas ou o frontend; string vazia conta como ausente.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = Field(default=30.0, gt=0)
    llm_max_tokens: int = Field(default=512, ge=1)
    # Orcamento diario de tokens estimados por processo (contabilidade
    # conservadora, reset diario); 0 = sem orcamento (so o kill switch limita).
    ai_daily_token_budget: int = Field(default=200_000, ge=0)
    # Limites do chat: mensagem do usuario (texto simples, sem HTML) e quantas
    # rodadas (pergunta+resposta) de historico sao enviadas ao LLM. O historico
    # NUNCA inclui precos, CNPJ, e-mail, telefone ou dados de contrato.
    ai_chat_max_message_chars: int = Field(default=500, ge=1)
    ai_chat_history_turns: int = Field(default=10, ge=1)
    # Retencao da conversa do chat (agent_conversations) para auditoria/TTL.
    ai_conversation_ttl_days: int = Field(default=30, ge=1)

    @property
    def supported_locale_list(self) -> list[str]:
        """Idiomas de conteudo suportados (CONTENT_LOCALES), na ordem configurada."""
        return [code.strip() for code in self.supported_locales.split(",") if code.strip()]

    @property
    def ui_locale_list(self) -> list[str]:
        """Idiomas da interface suportados (UI_LOCALES), na ordem configurada."""
        return [code.strip() for code in self.ui_locales.split(",") if code.strip()]

    @property
    def effective_stripe_secret_key(self) -> str | None:
        """Chave secreta do Stripe (aceita o alias historico ``STRIPE_WEBHOOK_SECRET``)."""
        if self.stripe_secret_key:
            return self.stripe_secret_key
        legacy = self.stripe_webhook_secret
        if legacy is not None and legacy.strip().startswith("sk_"):
            return legacy.strip()
        return None

    @property
    def effective_stripe_webhook_secret(self) -> str | None:
        """Segredo de assinatura do webhook (somente valores ``whsec_...``)."""
        value = self.stripe_webhook_secret
        if value is not None and value.strip().startswith("whsec_"):
            return value.strip()
        return None

    @property
    def stripe_webhook_secrets(self) -> list[str]:
        """Segredos ativos do webhook Stripe (atual + anterior, sem duplicatas)."""
        candidates = [
            self.effective_stripe_webhook_secret,
            (self.stripe_webhook_secret_previous or "").strip() or None,
        ]
        return [value for value in dict.fromkeys(candidates) if value]

    @property
    def payment_webhook_secrets(self) -> list[str]:
        """Segredos ativos do webhook HMAC legado (atual + anterior)."""
        candidates = [self.payment_webhook_secret, self.payment_webhook_secret_previous]
        return [value.strip() for value in dict.fromkeys(candidates) if value and value.strip()]

    @property
    def stripe_enabled(self) -> bool:
        return self.effective_stripe_secret_key is not None

    @property
    def llm_ready(self) -> bool:
        """LLM utilizavel: endpoint compativel com OpenAI totalmente configurado."""
        return self.llm_base_url is not None and self.llm_api_key is not None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, value: str) -> str:
        """Rejeita curinga e origens malformadas (lista sempre explicita)."""
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS deve conter ao menos uma origem explicita")
        for origin in origins:
            if origin == "*":
                raise ValueError("CORS_ORIGINS nao aceita '*'; liste as origens explicitas")
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(f"Origem CORS invalida (sem esquema http/https): {origin}")
            if origin.endswith("/") or "/" in origin.split("://", 1)[1]:
                raise ValueError(f"Origem CORS invalida (nao deve conter caminho): {origin}")
        return value

    @field_validator(
        "elasticsearch_api_key",
        "elasticsearch_username",
        "elasticsearch_password",
        "elasticsearch_ca_certs",
        "stripe_secret_key",
        "stripe_webhook_secret",
        "stripe_webhook_secret_previous",
        "payment_webhook_secret_previous",
        "llm_base_url",
        "llm_api_key",
        mode="before",
    )
    @classmethod
    def _blank_credentials_to_none(cls, value: object) -> object:
        """Trata string vazia (ou so espacos) como ausente.

        Credenciais opcionais do Elasticsearch: um valor vazio em `.env`
        (ex.: ``ELASTICSEARCH_API_KEY=``) NAO deve contar como credencial
        definida, sob pena de o cliente ignorar usuario/senha e receber 401.
        """
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("database_url", "database_admin_url", mode="after")
    @classmethod
    def _normalize_database_urls(cls, value: PostgresDsn | None) -> PostgresDsn | None:
        """Garante o driver asyncpg mesmo quando o provedor usa URL libpq.

        Render injeta ``postgresql://...``; sem esta normalizacao o
        ``create_async_engine`` tentaria importar psycopg2 e o processo
        morreria no boot.
        """
        if value is None:
            return None
        return PostgresDsn(normalize_async_database_url(str(value)))

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
