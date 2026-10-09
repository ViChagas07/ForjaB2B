"""Endpoints de autenticacao do contexto de identidade.

Rotas finas: apenas traduzem HTTP <-> caso de uso. Os casos de uso sao
construidos pela raiz de composicao (app.main) e expostos em ``app.state``;
este modulo NAO importa infraestrutura (contrato Clean Architecture: interface
e infraestrutura sao irmaos independentes).
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse

from app.modules.identity.application.auth import AuthenticateUser, Logout, RefreshSession
from app.modules.identity.application.errors import (
    OAuthCodeError,
    OAuthConfigurationError,
    OAuthStateError,
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


def _frontend_redirect(request: Request) -> str:
    return cast(str, request.app.state.settings.google_oauth_frontend_redirect)


def _code_redirect(base_url: str, result: GoogleOAuthResult) -> RedirectResponse:
    """Redirect final para o frontend carregando APENAS o exchange code."""
    separator = "&" if "?" in base_url else "?"
    return RedirectResponse(
        f"{base_url}{separator}{urlencode({'code': result.exchange_code})}",
        status_code=status.HTTP_302_FOUND,
    )


def _to_exchange_response(exchange: OAuthExchange) -> OAuthExchangeResponse:
    """Traduz o payload trocado para o contrato HTTP (sessao OU onboarding)."""
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
            ),
        )
    return OAuthExchangeResponse(
        status="onboarding",
        email=exchange.email,
        full_name=exchange.full_name,
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    use_case: Annotated[AuthenticateUser, Depends(_authenticate_usecase)],
) -> LoginResponse:
    result = await use_case.login(payload.email, payload.password)
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
        raise OAuthConfigurationError()
    return RedirectResponse(await use_case.build(), status_code=status.HTTP_302_FOUND)


@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
async def google_callback(
    request: Request,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Callback OAuth: valida state/code e redireciona com um exchange code."""
    use_case = _oauth_callback_usecase(request)
    if use_case is None:
        raise OAuthConfigurationError()
    if not code:
        raise OAuthCodeError()
    if not state:
        raise OAuthStateError()
    result = await use_case.complete(code=code, state=state)
    return _code_redirect(_frontend_redirect(request), result)


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
