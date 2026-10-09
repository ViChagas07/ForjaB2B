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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
from app.infrastructure.db.probe import ping_database
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.interface.errors import register_exception_handlers
from app.interface.health import ReadinessProbe
from app.interface.health import router as health_router
from app.interface.metrics import PrometheusMiddleware
from app.interface.middleware import CorrelationIdMiddleware
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
from app.modules.catalog.infrastructure.repository import SqlAlchemyCatalogRepository
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
from app.modules.notification.application.notification import ListNotifications, ResendNotification
from app.modules.notification.infrastructure.repository import SqlAlchemyNotificationRepository
from app.modules.ordering.application.order import CancelOrder, CreateOrder, GetOrder
from app.modules.ordering.infrastructure.repository import SqlAlchemyOrderingRepository
from app.modules.payment.application.payment import ConfirmPayment, GetPayment, InitiatePayment
from app.modules.payment.infrastructure.gateway import FakePaymentGateway
from app.modules.payment.infrastructure.repository import SqlAlchemyPaymentRepository
from app.modules.privacy.application.privacy import (
    DeletePersonalData,
    ExportPersonalData,
    GetConsentState,
    RecordConsent,
    RectifyPersonalData,
)
from app.modules.privacy.infrastructure.repository import SqlAlchemyPrivacyRepository

_logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    configure_telemetry(settings)

    engine = create_engine(settings)
    redis_client = create_redis_client(settings)

    if settings.otel_enabled:
        instrument_engine(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _logger.info("application_starting", environment=settings.environment)
        yield
        _logger.info("application_stopping")
        await engine.dispose()
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
    app.state.session_factory = create_session_factory(engine)
    app.state.uow_factory = SqlAlchemyUnitOfWorkFactory(app.state.session_factory)

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
    app.state.payment_initiate = InitiatePayment(
        repository=payment_repository,
        gateway=FakePaymentGateway(),
        pix_discount_rate=settings.pix_discount_rate,
    )
    app.state.payment_confirm = ConfirmPayment(repository=payment_repository)
    app.state.payment_get = GetPayment(repository=payment_repository)

    # Composicao do contexto de notificacao (administracao: consulta/reenvio).
    notification_repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    app.state.notification_list = ListNotifications(repository=notification_repository)
    app.state.notification_resend = ResendNotification(repository=notification_repository)

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

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(PrometheusMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router)

    if settings.otel_enabled:
        instrument_app(app)

    return app


app = create_app()
