"""Raiz de composicao: app factory do FastAPI.

Responsabilidades:
- instanciar Settings, logging e telemetria;
- criar engine SQLAlchemy e cliente Redis (sem conectar na criacao);
- ligar probes de readiness em app.state;
- registrar middlewares, exception handlers RFC 7807 e routers;
- liberar recursos no shutdown do lifespan.

Este modulo fica fora das camadas (propositalmente): e o unico ponto que
conhece interface e infraestrutura ao mesmo tempo.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.idempotency import IdempotencyService
from app.application.ports.translation import NullTranslationProvider
from app.application.product_attributes import load_default_registry
from app.application.rate_limit import (
    InMemoryBucketStore,
    InMemoryFailureStore,
    LoginThrottle,
    RateLimitClass,
    RateLimiter,
    RateLimitPolicy,
)
from app.application.security import TokenService
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import (
    configure_telemetry,
    instrument_app,
    instrument_engine,
    shutdown_telemetry,
)
from app.infrastructure.cache.probe import ping_redis
from app.infrastructure.cache.redis import close_redis_client, create_redis_client
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.db.probe import ping_database
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.rate_limit import RedisBucketStore, RedisFailureStore
from app.interface.deprecation import register_deprecation
from app.interface.errors import register_exception_handlers
from app.interface.health import ReadinessProbe
from app.interface.health import router as health_router
from app.interface.metrics import PrometheusMiddleware
from app.interface.middleware import CorrelationIdMiddleware
from app.interface.openapi import configure_openapi
from app.interface.rate_limit import RateLimitMiddleware
from app.interface.security_headers import SecurityHeadersMiddleware
from app.interface.v1.router import api_v1_router
from app.modules.cart.application.cart import CartService
from app.modules.cart.infrastructure.repository import SqlAlchemyCartRepository
from app.modules.catalog.application.catalog import (
    GetBrand,
    GetCategory,
    GetProduct,
    ListBrands,
    ListCategories,
    ListProducts,
)
from app.modules.catalog.application.product_admin import (
    CreateProduct,
    GetAttributeDefinitionsForCategory,
    GetProductAdmin,
    ListProductsAdmin,
    ListStaticImages,
    PublishProduct,
    UnpublishProduct,
    UpdateProduct,
)
from app.modules.catalog.application.translation_admin import (
    GetProductTranslations,
    SqlAlchemyTranslationAdminRepository,
    UpdateTranslation,
)
from app.modules.catalog.infrastructure.admin_repository import (
    SqlAlchemyCatalogAdminRepository,
    SqlAlchemySearchOutboxRepository,
)
from app.modules.catalog.infrastructure.audit_repository import SqlAlchemyAuditLogRepository
from app.modules.catalog.infrastructure.repository import SqlAlchemyCatalogRepository
from app.modules.catalog.interface import admin_router as catalog_admin_router
from app.modules.catalog.interface import translation_admin_router
from app.modules.companies.application.company import (
    ApproveCompany,
    GetCurrentCompany,
    RegisterCompany,
)
from app.modules.companies.infrastructure.cpf import HmacCpfHasher
from app.modules.companies.infrastructure.repository import SqlAlchemyCompanyRepository
from app.modules.credit.application.credit import (
    GetCreditAccount,
    ListCreditEntries,
    ReleaseCredit,
    ReserveCredit,
)
from app.modules.credit.infrastructure.repository import SqlAlchemyCreditRepository
from app.modules.identity.application.auth import AuthenticateUser, Logout, RefreshSession
from app.modules.identity.application.google_oauth import (
    BuildGoogleAuthorizationUrl,
    CompleteGoogleOAuth,
    ExchangeOAuthCode,
)
from app.modules.identity.infrastructure.external_identity import (
    SqlAlchemyExternalIdentityRepository,
)
from app.modules.identity.infrastructure.google_client import GoogleIdentityClientImpl
from app.modules.identity.infrastructure.identity_resolver import SqlAlchemyUserIdentityResolver
from app.modules.identity.infrastructure.membership import SqlAlchemyMembershipReader
from app.modules.identity.infrastructure.oauth_exchange import RedisOAuthExchangeCodeStore
from app.modules.identity.infrastructure.oauth_state import RedisOAuthStateStore
from app.modules.identity.infrastructure.password import Argon2PasswordHasher
from app.modules.identity.infrastructure.tokens import RedisRefreshTokenStore
from app.modules.invoicing.application.invoice import CreateInvoice, GetInvoice, GetInvoiceByOrder
from app.modules.invoicing.infrastructure.repository import SqlAlchemyInvoicingRepository
from app.modules.notification.application.notification import (
    ListNotifications,
    ResendNotification,
    UpdateWhatsAppOptIn,
)
from app.modules.notification.infrastructure.repository import SqlAlchemyNotificationRepository
from app.modules.ordering.application.order import CancelOrder, CreateOrder, GetOrder
from app.modules.ordering.infrastructure.repository import SqlAlchemyOrderingRepository
from app.modules.payment.application.payment import (
    ConfirmPayment,
    GetPayment,
    InitiatePayment,
    ReconcileStripePayments,
    RefundPayment,
)
from app.modules.payment.infrastructure.gateway import (
    FakePaymentGateway,
    PaymentGatewayRouter,
    StripeCheckoutGateway,
)
from app.modules.payment.infrastructure.repository import SqlAlchemyPaymentRepository
from app.modules.privacy.application.privacy import (
    DeletePersonalData,
    ExportPersonalData,
    GetConsentState,
    RecordConsent,
    RectifyPersonalData,
)
from app.modules.privacy.infrastructure.repository import SqlAlchemyPrivacyRepository
from app.modules.search.application.metrics import SearchMetricsLoop
from app.modules.search.application.ports import SearchEngine
from app.modules.search.application.scheduler import ReconcileScheduler
from app.modules.search.application.search import (
    AutocompleteProducts,
    SearchProducts,
    SuggestProducts,
)
from app.modules.search.application.semantic import SemanticSearch
from app.modules.search.application.sync import RefreshSearchMetrics
from app.modules.search.infrastructure.elasticsearch import build_product_index, build_search_engine
from app.modules.search.infrastructure.embeddings import build_embedding_provider
from app.modules.search.infrastructure.outbox_repository import (
    SqlAlchemySearchOutboxRepository as SqlAlchemySearchDispatchOutboxRepository,
)
from app.modules.search.infrastructure.pgvector_store import PgVectorStore
from app.modules.search.infrastructure.postgres_search import PostgresSearchReader
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader
from app.modules.search.infrastructure.reconcile import ReconcileService
from app.modules.search.infrastructure.suggest_cache import SuggestCache

_logger = get_logger(__name__)


async def _log_search_engine_startup(search_engine: SearchEngine) -> None:
    """Verifica o motor de busca no startup sem tornar sua ausencia fatal.

    Indisponibilidade do Elasticsearch nunca impede a aplicacao de subir: o
    resultado e apenas registrado como aviso (modo degradado).
    """
    try:
        health = await search_engine.check_health()
    except Exception:  # noqa: BLE001 - indisponibilidade nunca e fatal
        _logger.warning("search_engine_health_check_failed")
        return
    if health.state.value != "ok":
        _logger.warning("search_engine_unavailable", state=health.state.value, detail=health.detail)


async def _stop_background_task(task: asyncio.Task[None] | None) -> None:
    """Cancela um loop de manutencao sem propagar o cancelamento no shutdown."""
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _start_reconcile_scheduler(app: FastAPI, settings: Settings) -> asyncio.Task[None] | None:
    """Inicia a reconciliacao periodica (desligada por padrao)."""
    if settings.reconcile_interval_seconds <= 0:
        return None
    service = ReconcileService(
        settings=settings,
        engine=app.state.db_engine,
        uow_factory=app.state.uow_factory,
    )
    return asyncio.create_task(
        ReconcileScheduler(
            run_once=service.run,
            interval_seconds=settings.reconcile_interval_seconds,
            jitter_seconds=settings.reconcile_jitter_seconds,
            timeout_seconds=settings.reconcile_timeout_seconds,
        ).run_forever()
    )


def _start_search_metrics(app: FastAPI, settings: Settings) -> asyncio.Task[None] | None:
    """Inicia o loop de gauges da outbox (sem bloquear o startup)."""
    if settings.search_metrics_interval_seconds <= 0:
        return None
    # Gauge da outbox: le o PostgreSQL em background. O worker nao expoe
    # /metrics; a API e quem responde ao scrape do Prometheus.
    return asyncio.create_task(
        SearchMetricsLoop(
            updater=RefreshSearchMetrics(
                outbox=SqlAlchemySearchDispatchOutboxRepository(app.state.uow_factory)
            ),
            interval_seconds=settings.search_metrics_interval_seconds,
        ).run_forever()
    )


def _compose_search(app: FastAPI, settings: Settings) -> None:
    """Monta a busca (Fases 4/5): ES lexical, pgvector semantico e fallback Postgres.

    Mantido fora de ``create_app`` para preservar a complexidade ciclomatica da
    raiz de composicao. Quando os embeddings estao desabilitados ou indisponiveis,
    o caminho semantico fica ``None`` e a busca opera em modo lexical/fallback.
    """
    product_reader = SqlAlchemyProductReader(app.state.uow_factory)
    postgres_search_reader = PostgresSearchReader(app.state.uow_factory)
    product_index = build_product_index(settings)
    embedding_provider = build_embedding_provider(settings)
    vector_store = PgVectorStore(app.state.uow_factory) if embedding_provider is not None else None
    semantic: SemanticSearch | None = None
    if embedding_provider is not None and vector_store is not None:
        semantic = SemanticSearch(
            provider=embedding_provider,
            store=vector_store,
            candidate_limit=settings.embedding_candidate_limit,
            timeout_seconds=settings.embedding_query_timeout_seconds,
        )
    app.state.embedding_provider = embedding_provider
    app.state.vector_store = vector_store
    app.state.search_products = SearchProducts(
        primary=product_index,
        fallback=postgres_search_reader,
        semantic=semantic,
        product_reader=product_reader,
        settings=settings,
    )
    app.state.search_autocomplete_products = AutocompleteProducts(
        primary=product_index,
        fallback=postgres_search_reader,
        settings=settings,
    )
    app.state.search_suggest_products = SuggestProducts(
        primary=product_index,
        fallback=postgres_search_reader,
        product_reader=product_reader,
        settings=settings,
    )


async def _dispose_engine(engine: AsyncEngine | None) -> None:
    """Descarta uma engine opcional (admin pode nao estar configurada)."""
    if engine is not None:
        await engine.dispose()


def _rate_limit_policies(settings: Settings) -> dict[RateLimitClass, RateLimitPolicy]:
    """Politicas por classe, configuradas por ambiente."""
    return {
        RateLimitClass.AUTH: RateLimitPolicy(
            capacity=settings.rate_limit_auth_capacity,
            refill_per_minute=settings.rate_limit_auth_refill_per_minute,
        ),
        RateLimitClass.REGISTRATION: RateLimitPolicy(
            capacity=settings.rate_limit_registration_capacity,
            refill_per_minute=settings.rate_limit_registration_refill_per_minute,
        ),
        RateLimitClass.SEARCH: RateLimitPolicy(
            capacity=settings.rate_limit_search_capacity,
            refill_per_minute=settings.rate_limit_search_refill_per_minute,
        ),
        RateLimitClass.SUGGEST: RateLimitPolicy(
            capacity=settings.rate_limit_suggest_capacity,
            refill_per_minute=settings.rate_limit_suggest_refill_per_minute,
        ),
        RateLimitClass.ADMIN_WRITE: RateLimitPolicy(
            capacity=settings.rate_limit_admin_write_capacity,
            refill_per_minute=settings.rate_limit_admin_write_refill_per_minute,
        ),
        RateLimitClass.AUTHENTICATED: RateLimitPolicy(
            capacity=settings.rate_limit_authenticated_capacity,
            refill_per_minute=settings.rate_limit_authenticated_refill_per_minute,
        ),
        RateLimitClass.PUBLIC_READ: RateLimitPolicy(
            capacity=settings.rate_limit_public_read_capacity,
            refill_per_minute=settings.rate_limit_public_read_refill_per_minute,
        ),
        RateLimitClass.WEBHOOK: RateLimitPolicy(
            capacity=settings.rate_limit_webhook_capacity,
            refill_per_minute=settings.rate_limit_webhook_refill_per_minute,
        ),
        RateLimitClass.LOGIN_ACCOUNT: RateLimitPolicy(
            capacity=settings.rate_limit_auth_capacity,
            refill_per_minute=settings.rate_limit_auth_refill_per_minute,
        ),
        RateLimitClass.AI: RateLimitPolicy(
            capacity=settings.rate_limit_ai_capacity,
            refill_per_minute=settings.rate_limit_ai_refill_per_minute,
        ),
    }


def _build_rate_limiter(settings: Settings, redis_client: Redis[str]) -> RateLimiter:
    """Limiter distribuido com fallback local (fail-open)."""
    return RateLimiter(
        store=RedisBucketStore(redis_client),
        policies=_rate_limit_policies(settings),
        fallback_store=InMemoryBucketStore(),
    )


def _build_login_throttle(settings: Settings, redis_client: Redis[str]) -> LoginThrottle:
    """Bloqueio progressivo de login (Redis + fallback local)."""
    return LoginThrottle(
        store=RedisFailureStore(redis_client),
        fallback_store=InMemoryFailureStore(),
        secret=settings.secret_key,
        ttl_seconds=settings.login_failure_window_seconds,
        threshold=settings.login_failure_threshold,
        base_backoff_seconds=settings.login_failure_base_backoff_seconds,
        max_backoff_seconds=settings.login_failure_max_backoff_seconds,
    )


def _build_admin_factories(
    settings: Settings,
) -> tuple[
    AsyncEngine | None, async_sessionmaker[AsyncSession] | None, SqlAlchemyUnitOfWorkFactory | None
]:
    """Cria engine/sessao/UoW administrativos (role forja_admin, bypass de RLS).

    Retorna ``(None, None, None)`` quando ``DATABASE_ADMIN_URL`` nao esta
    configurada. Nesse caso a API administrativa de catalogo nao funciona:
    a variavel e obrigatoria em qualquer ambiente que use o backoffice.
    """
    if not settings.database_admin_url:
        return None, None, None
    admin_engine = create_engine(settings, admin=True)
    session_factory = create_session_factory(admin_engine)
    return admin_engine, session_factory, SqlAlchemyUnitOfWorkFactory(session_factory)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    configure_telemetry(settings)

    engine = create_engine(settings)
    admin_engine, admin_session_factory, admin_uow_factory = _build_admin_factories(settings)
    redis_client = create_redis_client(settings)

    if settings.otel_enabled:
        instrument_engine(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _logger.info("application_starting", environment=settings.environment)
        search_engine: SearchEngine | None = app.state.search_engine
        if search_engine is not None:
            await _log_search_engine_startup(search_engine)
        metrics_task = _start_search_metrics(app, settings)
        reconcile_task = _start_reconcile_scheduler(app, settings)
        yield
        _logger.info("application_stopping")
        await _stop_background_task(reconcile_task)
        await _stop_background_task(metrics_task)
        if search_engine is not None:
            await search_engine.close()
        await engine.dispose()
        await _dispose_engine(admin_engine)
        await close_redis_client(redis_client)
        shutdown_telemetry()

    app = FastAPI(
        title="Forja B2B API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.db_engine = engine
    app.state.redis_client = redis_client
    app.state.rate_limiter = _build_rate_limiter(settings, redis_client)
    app.state.login_throttle = _build_login_throttle(settings, redis_client)
    app.state.search_suggest_cache = SuggestCache(
        redis_client=redis_client,
        index_version=settings.elasticsearch_index_version,
    )
    app.state.session_factory = create_session_factory(engine)
    app.state.uow_factory = SqlAlchemyUnitOfWorkFactory(app.state.session_factory)
    app.state.idempotency_service = IdempotencyService(
        repository=SqlAlchemyIdempotencyRepository(app.state.uow_factory),
        ttl_seconds=settings.idempotency_ttl_seconds,
        in_progress_ttl_seconds=settings.idempotency_in_progress_ttl_seconds,
    )
    # Admin factories (forja_admin role, bypasses RLS on catalog tables)
    app.state.admin_session_factory = admin_session_factory
    app.state.admin_uow_factory = admin_uow_factory
    # Motor de busca (Elasticsearch). Construido aqui (nao apenas no lifespan)
    # para que o health check funcione sob ASGITransport nos testes. A
    # construcao nao abre conexao; indisponibilidade nao impede o startup.
    app.state.search_engine = build_search_engine(settings)

    # Composicao da busca (Fases 4/5): ES lexical, pgvector semantico e fallback.
    _compose_search(app, settings)

    # Composicao do contexto de identidade (autenticacao). A raiz de composicao
    # liga casos de uso as implementacoes de infraestrutura; os routers apenas
    # consomem os casos de uso prontos via app.state.
    token_service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    refresh_store = RedisRefreshTokenStore(redis_client)
    app.state.identity_authenticate = AuthenticateUser(
        resolver=SqlAlchemyUserIdentityResolver(app.state.session_factory),
        hasher=Argon2PasswordHasher(),
        membership_reader=SqlAlchemyMembershipReader(app.state.uow_factory),
        token_service=token_service,
        refresh_store=refresh_store,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_seconds=settings.refresh_token_expire_days * 24 * 3600,
    )
    app.state.identity_refresh = RefreshSession(
        refresh_store=refresh_store,
        token_service=token_service,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_seconds=settings.refresh_token_expire_days * 24 * 3600,
    )
    app.state.identity_logout = Logout(refresh_store=refresh_store)

    # Composicao do OAuth Google (redirect tradicional). So e montado quando a
    # configuracao esta completa; ausente, os endpoints retornam 503 e o
    # frontend (que ja esconde o botao) nao tem fluxo utilizavel.
    if settings.google_oauth_enabled:
        client_id = settings.google_client_id
        client_secret = settings.google_client_secret
        redirect_uri = settings.google_redirect_uri
        frontend_redirect = settings.google_oauth_frontend_redirect
        if (
            client_id is None
            or client_secret is None
            or redirect_uri is None
            or frontend_redirect is None
        ):  # pragma: no cover - guarda defensiva de tipos
            raise ConfigurationError("Google OAuth configuracao incompleta")
        oauth_state_store = RedisOAuthStateStore(redis_client)
        oauth_exchange_store = RedisOAuthExchangeCodeStore(redis_client)
        app.state.oauth_google_start = BuildGoogleAuthorizationUrl(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state_store=oauth_state_store,
        )
        app.state.oauth_google_callback = CompleteGoogleOAuth(
            google_client=GoogleIdentityClientImpl(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
            ),
            state_store=oauth_state_store,
            exchange_code_store=oauth_exchange_store,
            resolver=SqlAlchemyUserIdentityResolver(app.state.session_factory),
            external_identity_repository=SqlAlchemyExternalIdentityRepository(
                app.state.uow_factory
            ),
            membership_reader=SqlAlchemyMembershipReader(app.state.uow_factory),
            token_service=token_service,
            refresh_store=refresh_store,
            access_token_expire_minutes=settings.access_token_expire_minutes,
            refresh_token_expire_seconds=settings.refresh_token_expire_days * 24 * 3600,
        )
        app.state.oauth_google_exchange = ExchangeOAuthCode(store=oauth_exchange_store)
    else:
        app.state.oauth_google_start = None
        app.state.oauth_google_callback = None
        app.state.oauth_google_exchange = None

    # Composicao do contexto de empresas (onboarding + consulta). O hasher de
    # senha e a MESMA instancia Argon2 usada pelo identity; o hasher de CPF usa
    # o pepper de Settings (mesmo esquema do seed).
    company_repository = SqlAlchemyCompanyRepository(app.state.uow_factory)
    app.state.companies_register = RegisterCompany(
        repository=company_repository,
        password_hasher=Argon2PasswordHasher(),
        cpf_hasher=HmacCpfHasher(settings.pepper),
    )
    app.state.companies_get = GetCurrentCompany(repository=company_repository)
    app.state.companies_approve = ApproveCompany(repository=company_repository)

    # Composicao do contexto de catalogo (somente leitura, global).
    catalog_repository = SqlAlchemyCatalogRepository(app.state.uow_factory)
    app.state.catalog_list_categories = ListCategories(repository=catalog_repository)
    app.state.catalog_get_category = GetCategory(repository=catalog_repository)
    app.state.catalog_list_brands = ListBrands(repository=catalog_repository)
    app.state.catalog_get_brand = GetBrand(repository=catalog_repository)
    app.state.catalog_list_products = ListProducts(repository=catalog_repository)
    app.state.catalog_get_product = GetProduct(repository=catalog_repository)

    # Composicao do contexto de catalogo - ADMIN (escrita, role forja_admin via UoW sem tenant).
    admin_repository = SqlAlchemyCatalogAdminRepository(app.state.admin_uow_factory)
    search_outbox = SqlAlchemySearchOutboxRepository(app.state.admin_uow_factory)
    audit_log = SqlAlchemyAuditLogRepository(app.state.uow_factory)
    attribute_registry = load_default_registry()
    app.state.catalog_admin_create_product = CreateProduct(
        repository=admin_repository,
        outbox=search_outbox,
        audit=audit_log,
        registry=attribute_registry,
    )
    app.state.catalog_admin_get_product = GetProductAdmin(repository=admin_repository)
    app.state.catalog_admin_list_products = ListProductsAdmin(repository=admin_repository)
    app.state.catalog_admin_update_product = UpdateProduct(
        repository=admin_repository,
        outbox=search_outbox,
        audit=audit_log,
        registry=attribute_registry,
    )
    app.state.catalog_admin_publish_product = PublishProduct(
        repository=admin_repository, outbox=search_outbox, audit=audit_log
    )
    app.state.catalog_admin_unpublish_product = UnpublishProduct(
        repository=admin_repository, outbox=search_outbox, audit=audit_log
    )
    app.state.catalog_admin_get_attribute_definitions = GetAttributeDefinitionsForCategory(
        registry=attribute_registry
    )
    app.state.catalog_admin_list_static_images = ListStaticImages()

    # Composicao do contexto de catalogo - ADMIN (traduções).
    translation_repository = SqlAlchemyTranslationAdminRepository(app.state.admin_uow_factory)
    translation_provider = NullTranslationProvider()
    app.state.catalog_admin_get_translations = GetProductTranslations(
        repository=translation_repository,
        catalog_repository=admin_repository,
    )
    app.state.catalog_admin_update_translation = UpdateTranslation(
        repository=translation_repository,
        catalog_repository=admin_repository,
        translation_provider=translation_provider,
        settings=settings,
    )

    # Composicao do contexto de credito (consulta + operacoes transacionais).
    credit_repository = SqlAlchemyCreditRepository(app.state.uow_factory)
    app.state.credit_get_account = GetCreditAccount(repository=credit_repository)
    app.state.credit_list_entries = ListCreditEntries(repository=credit_repository)
    app.state.credit_reserve = ReserveCredit(repository=credit_repository)
    app.state.credit_release = ReleaseCredit(repository=credit_repository)

    # Composicao do contexto de carrinho.
    app.state.cart_service = CartService(repository=SqlAlchemyCartRepository(app.state.uow_factory))

    # Composicao do contexto de pedidos.
    ordering_repository = SqlAlchemyOrderingRepository(app.state.uow_factory)
    app.state.ordering_create = CreateOrder(repository=ordering_repository)
    app.state.ordering_get = GetOrder(repository=ordering_repository)
    app.state.ordering_cancel = CancelOrder(repository=ordering_repository)

    # Composicao do contexto de faturamento (boleto + captura de credito).
    invoicing_repository = SqlAlchemyInvoicingRepository(app.state.uow_factory)
    app.state.invoicing_create = CreateInvoice(repository=invoicing_repository)
    app.state.invoicing_get = GetInvoice(repository=invoicing_repository)
    app.state.invoicing_get_by_order = GetInvoiceByOrder(repository=invoicing_repository)

    # Composicao do contexto de pagamento (checkout PIX/cartao + webhook).
    payment_repository = SqlAlchemyPaymentRepository(app.state.uow_factory)
    stripe_api_key = settings.effective_stripe_secret_key
    stripe_gateway = (
        StripeCheckoutGateway(
            api_key=stripe_api_key,
            frontend_base_url=settings.frontend_base_url,
            success_path=settings.stripe_checkout_success_path,
            cancel_path=settings.stripe_checkout_cancel_path,
        )
        if stripe_api_key is not None
        else None
    )
    payment_gateway = PaymentGatewayRouter(fake=FakePaymentGateway(), stripe=stripe_gateway)
    app.state.payment_initiate = InitiatePayment(
        repository=payment_repository,
        gateway=payment_gateway,
        pix_discount_rate=settings.pix_discount_rate,
    )
    app.state.payment_confirm = ConfirmPayment(repository=payment_repository)
    app.state.payment_get = GetPayment(repository=payment_repository)
    app.state.payment_refund = RefundPayment(repository=payment_repository, gateway=payment_gateway)
    app.state.payment_reconcile = ReconcileStripePayments(
        repository=payment_repository, gateway=payment_gateway
    )

    # Composicao do contexto de notificacao (administracao: consulta/reenvio).
    notification_repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    app.state.notification_list = ListNotifications(repository=notification_repository)
    app.state.notification_resend = ResendNotification(repository=notification_repository)
    app.state.notification_whatsapp = UpdateWhatsAppOptIn(repository=notification_repository)

    # Composicao do contexto de privacidade (LGPD, self-service do titular).
    privacy_repository = SqlAlchemyPrivacyRepository(app.state.uow_factory)
    app.state.privacy_export = ExportPersonalData(repository=privacy_repository)
    app.state.privacy_rectify = RectifyPersonalData(repository=privacy_repository)
    app.state.privacy_delete = DeletePersonalData(repository=privacy_repository)
    app.state.privacy_record_consent = RecordConsent(repository=privacy_repository)
    app.state.privacy_get_consent = GetConsentState(repository=privacy_repository)

    readiness_probes: dict[str, ReadinessProbe] = {
        "database": lambda: ping_database(engine),
        "redis": lambda: ping_redis(redis_client),
    }
    app.state.readiness_probes = readiness_probes

    # Ordem de execucao (de fora para dentro): CORS -> SecurityHeaders ->
    # Prometheus -> Correlation -> RateLimit -> app. O 429 atravessa os
    # headers de seguranca e o request id.
    app.add_middleware(
        RateLimitMiddleware,
        limiter=app.state.rate_limiter,
        settings=settings,
        token_service=token_service,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    # CORS por ultimo = camada mais externa, garantindo cabecalhos tambem em
    # respostas de erro produzidas pelos middlewares internos.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept-Language",
            "X-Request-ID",
            "X-Admin-Key",
        ],
        expose_headers=["X-Request-ID", "RateLimit-Limit", "RateLimit-Remaining", "Retry-After"],
        max_age=settings.cors_max_age_seconds,
    )
    register_exception_handlers(app)

    # Ilustracoes originais do catalogo (SVG), versionadas em app/static e
    # servidas pela propria API (cacheaveis via ETag/Last-Modified). Nenhum
    # arquivo e gravado em disco em runtime.
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )

    app.include_router(health_router)
    app.include_router(api_v1_router)
    app.include_router(catalog_admin_router, prefix="/api/v1")
    app.include_router(translation_admin_router, prefix="/api/v1")

    register_deprecation(app)
    configure_openapi(app)

    if settings.otel_enabled:
        instrument_app(app)

    return app


app = create_app()
