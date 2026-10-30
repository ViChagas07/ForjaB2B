"""Endpoints de autenticacao do contexto de identidade.

Rotas finas: apenas traduzem HTTP <-> caso de uso. Os casos de uso sao
construidos pela raiz de composicao (app.main) e expostos em ``app.state``;
este modulo NAO importa infraestrutura (contrato Clean Architecture: interface
e infraestrutura sao irmaos independentes).
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse

from app.application.rate_limit import (
    LoginThrottle,
    RateLimitClass,
    RateLimiter,
    pseudonymous_key,
)
from app.core.errors import RateLimitExceededError
from app.core.request_context import client_ip
from app.modules.identity.application.auth import AuthenticateUser, Logout, RefreshSession
from app.modules.identity.application.errors import (
    InvalidCredentialsError,
    OAuthCodeError,
    OAuthCompanyAccountError,
    OAuthConfigurationError,
    OAuthEmailNotVerifiedError,
    OAuthStateError,
    UserInactiveError,
)
from app.modules.identity.application.google_oauth import (
    BuildGoogleAuthorizationUrl,
    CompleteGoogleOAuth,
    ExchangeOAuthCode,
    GoogleOAuthResult,
)
from app.modules.identity.application.ports import OAuthExchange
from app.modules.identity.interface.schemas import (
    LoginRequest,
    LoginResponse,
    OAuthExchangeRequest,
    OAuthExchangeResponse,
    RefreshRequest,
    RefreshResponse,
    UserProfile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate_usecase(request: Request) -> AuthenticateUser:
    return cast(AuthenticateUser, request.app.state.identity_authenticate)


def _rate_limiter(request: Request) -> RateLimiter:
    return cast(RateLimiter, request.app.state.rate_limiter)


def _login_throttle(request: Request) -> LoginThrottle:
    return cast(LoginThrottle, request.app.state.login_throttle)


def _refresh_usecase(request: Request) -> RefreshSession:
    return cast(RefreshSession, request.app.state.identity_refresh)


def _logout_usecase(request: Request) -> Logout:
    return cast(Logout, request.app.state.identity_logout)


def _oauth_start_usecase(request: Request) -> BuildGoogleAuthorizationUrl | None:
    return cast(BuildGoogleAuthorizationUrl | None, request.app.state.oauth_google_start)


def _oauth_callback_usecase(request: Request) -> CompleteGoogleOAuth | None:
    return cast(CompleteGoogleOAuth | None, request.app.state.oauth_google_callback)


def _oauth_exchange_usecase(request: Request) -> ExchangeOAuthCode | None:
    return cast(ExchangeOAuthCode | None, request.app.state.oauth_google_exchange)


def _normalize_frontend_redirect(
    configured: str | None, backend_redirect_uri: str | None
) -> str:
    """Impede loop de redirect quando a env aponta para o callback da API.

    A pagina do frontend e ``/[locale]/auth/google/callback``. Se a variavel
    foi configurada por engano como ``/api/v1/auth/google/callback``, o
    backend redirecionaria para si mesmo em loop. Nesse caso usamos o caminho
    de pagina no mesmo host; o middleware do Next acrescenta o locale e
    preserva ``?code``/``?error``. Se o host configurado for o proprio backend
    (sem uma pagina de frontend), falhamos explicitamente em vez de criar loop.
    """
    if not configured:
        raise OAuthConfigurationError("GOOGLE_OAUTH_FRONTEND_REDIRECT ausente.")
    parsed = urlparse(configured)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OAuthConfigurationError("GOOGLE_OAUTH_FRONTEND_REDIRECT invalido.")

    backend_host = urlparse(backend_redirect_uri).hostname if backend_redirect_uri else None
    if backend_host and parsed.hostname == backend_host:
        raise OAuthConfigurationError(
            "GOOGLE_OAUTH_FRONTEND_REDIRECT deve apontar para a pagina do "
            "frontend (/[locale]/auth/google/callback), nao para a API."
        )

    if parsed.path.startswith("/api/"):
        return urlunparse(
            parsed._replace(path="/auth/google/callback", params="", query="", fragment="")
        )
    return configured


def _frontend_redirect(request: Request) -> str:
    settings = request.app.state.settings
    return _normalize_frontend_redirect(
        settings.google_oauth_frontend_redirect, settings.google_redirect_uri
    )


def _code_redirect(base_url: str, result: GoogleOAuthResult) -> RedirectResponse:
    """Redirect final para o frontend carregando APENAS o exchange code."""
    separator = "&" if "?" in base_url else "?"
    return RedirectResponse(
        f"{base_url}{separator}{urlencode({'code': result.exchange_code})}",
        status_code=status.HTTP_302_FOUND,
    )


def _error_redirect(base_url: str, code: str) -> RedirectResponse:
    """Redirect de erro esperado do OAuth para a tela de callback do frontend.

    O codigo e estavel e nao contem detalhes sensiveis; a UI traduz a mensagem.
    """
    separator = "&" if "?" in base_url else "?"
    return RedirectResponse(
        f"{base_url}{separator}{urlencode({'error': code})}",
        status_code=status.HTTP_302_FOUND,
    )


def _callback_error_code(exc: Exception) -> str:
    """Traduz a excecao esperada do callback para um codigo curto e publico."""
    if isinstance(exc, OAuthCompanyAccountError):
        return "oauth_company_account"
    if isinstance(exc, OAuthEmailNotVerifiedError):
        return "oauth_email_not_verified"
    if isinstance(exc, UserInactiveError):
        return "user_inactive"
    if isinstance(exc, OAuthStateError):
        return "oauth_state_invalid"
    if isinstance(exc, OAuthCodeError) and exc.reason in {
        "invalid_client",
        "unauthorized_client",
        "redirect_uri_mismatch",
    }:
        return "oauth_client_invalid"
    return "oauth_code_invalid"


def _to_exchange_response(exchange: OAuthExchange) -> OAuthExchangeResponse:
    """Traduz o payload trocado para o contrato HTTP (sessao OU cadastro)."""
    if exchange.status == "authenticated" and exchange.user_id is not None:
        return OAuthExchangeResponse(
            status="authenticated",
            access_token=exchange.access_token,
            refresh_token=exchange.refresh_token,
            token_type=exchange.token_type,
            expires_in=exchange.expires_in,
            user=UserProfile(
                id=uuid.UUID(exchange.user_id),
                email=exchange.email or "",
                full_name=exchange.full_name or "",
                role=exchange.role or "",
                account_type=exchange.account_type or "COMPANY",
            ),
        )
    return OAuthExchangeResponse(
        status="registration_required",
        email=exchange.email,
        full_name=exchange.full_name,
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    use_case: Annotated[AuthenticateUser, Depends(_authenticate_usecase)],
    limiter: Annotated[RateLimiter, Depends(_rate_limiter)],
    throttle: Annotated[LoginThrottle, Depends(_login_throttle)],
) -> LoginResponse:
    settings = request.app.state.settings
    ip = client_ip(request.scope, settings.trusted_proxy_count)

    # Limite por conta (independente do IP) contra brute force distribuido.
    account_identity = pseudonymous_key(settings.secret_key, payload.email)
    account_decision = await limiter.check(
        rate_class=RateLimitClass.LOGIN_ACCOUNT,
        identity=f"account:{account_identity}",
    )
    if not account_decision.allowed:
        raise RateLimitExceededError(
            retry_after_seconds=account_decision.retry_after_seconds,
            limit=account_decision.limit,
            remaining=account_decision.remaining,
            reset_after_seconds=account_decision.reset_after_seconds,
        )

    # Bloqueio progressivo por conta+IP apos falhas repetidas.
    blocked = await throttle.blocked_for(email=payload.email, client_ip=ip)
    if blocked > 0:
        raise RateLimitExceededError(
            retry_after_seconds=blocked,
            limit=settings.rate_limit_auth_capacity,
            reset_after_seconds=blocked,
        )

    try:
        result = await use_case.login(
            payload.email,
            payload.password,
            expected_account_type=payload.account_type,
        )
    except (InvalidCredentialsError, UserInactiveError):
        blocked = await throttle.record_failure(email=payload.email, client_ip=ip)
        if blocked > 0:
            raise RateLimitExceededError(
                retry_after_seconds=blocked,
                limit=settings.rate_limit_auth_capacity,
                reset_after_seconds=blocked,
            ) from None
        raise

    await throttle.clear(email=payload.email, client_ip=ip)
    return LoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
        user=UserProfile(
            id=result.user_id,
            email=result.email,
            full_name=result.full_name,
            role=result.role,
            account_type=result.account_type,
        ),
    )


@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(
    payload: RefreshRequest,
    use_case: Annotated[RefreshSession, Depends(_refresh_usecase)],
) -> RefreshResponse:
    result = await use_case.refresh(payload.refresh_token)
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    use_case: Annotated[Logout, Depends(_logout_usecase)],
) -> None:
    await use_case.logout(payload.refresh_token)


@router.get("/google", status_code=status.HTTP_302_FOUND)
async def google_start(request: Request) -> RedirectResponse:
    """Inicia o OAuth Google (redirect para o provider com state anti-CSRF)."""
    use_case = _oauth_start_usecase(request)
    if use_case is None:
        return _error_redirect(_frontend_redirect(request), "oauth_unavailable")
    return RedirectResponse(await use_case.build(), status_code=status.HTTP_302_FOUND)


@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
async def google_callback(
    request: Request,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Callback OAuth: valida state/code e redireciona com um exchange code."""
    use_case = _oauth_callback_usecase(request)
    if use_case is None:
        return _error_redirect(_frontend_redirect(request), "oauth_unavailable")
    base_url = _frontend_redirect(request)
    if error == "access_denied":
        return _error_redirect(base_url, "oauth_access_denied")
    if not code:
        return _error_redirect(base_url, "oauth_code_invalid")
    if not state:
        return _error_redirect(base_url, "oauth_state_invalid")
    try:
        result = await use_case.complete(code=code, state=state)
    except (
        OAuthCompanyAccountError,
        OAuthEmailNotVerifiedError,
        OAuthStateError,
        OAuthCodeError,
        UserInactiveError,
    ) as exc:
        return _error_redirect(base_url, _callback_error_code(exc))
    return _code_redirect(base_url, result)


@router.post(
    "/oauth/exchange",
    response_model=OAuthExchangeResponse,
    status_code=status.HTTP_200_OK,
)
async def oauth_exchange(
    payload: OAuthExchangeRequest,
    request: Request,
) -> OAuthExchangeResponse:
    """Troca um exchange code de uso unico pela sessao (ou onboarding)."""
    use_case = _oauth_exchange_usecase(request)
    if use_case is None:
        raise OAuthConfigurationError()
    exchange = await use_case.exchange(payload.code)
    return _to_exchange_response(exchange)
