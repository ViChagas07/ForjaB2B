"""Casos de uso do OAuth Google (Authorization Code Flow tradicional).

Fluxo:

    GET  /auth/google            -> state anti-CSRF + redirect para o Google
    GET  /auth/google/callback   -> valida state/code, resolve identidade,
                                    vincula ao usuario (ou onboarding) e devolve
                                    apenas um exchange code de uso unico
    POST /auth/oauth/exchange    -> troca o exchange code pela sessao (JSON)

Nenhum access/refresh token, authorization code, secret ou identidade e exposto
em URL de redirect. O exchange code e opaco, aleatorio, curto e consumido uma
unica vez (GETDEL). Nunca usar Google Identity Services (GIS) nem popup.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from app.application.security import AuthContext, TokenService
from app.modules.identity.application.errors import (
    OAuthCodeError,
    OAuthEmailNotVerifiedError,
    OAuthExchangeError,
    OAuthStateError,
    UserInactiveError,
)
from app.modules.identity.application.ports import (
    ExternalIdentityRepository,
    GoogleIdentityClient,
    GoogleUserInfo,
    MembershipReader,
    OAuthExchange,
    OAuthExchangeCodeStore,
    OAuthStateStore,
    RefreshTokenPayload,
    RefreshTokenStore,
    UserIdentityResolver,
)
from app.modules.identity.domain.enums import MemberStatus, UserStatus

_GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_SCOPE = "openid email profile"
_STATE_BYTES = 32
_REFRESH_TOKEN_BYTES = 32
_EXCHANGE_CODE_BYTES = 32


@dataclass(frozen=True, kw_only=True)
class GoogleOAuthResult:
    """Resultado do callback OAuth: apenas um exchange code de uso unico."""

    status: str  # "authenticated" | "onboarding"
    exchange_code: str


class BuildGoogleAuthorizationUrl:
    """Caso de uso: gera a URL de autorizacao do Google com state anti-CSRF."""

    def __init__(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state_store: OAuthStateStore,
        state_ttl_seconds: int = 600,
    ) -> None:
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._state_store = state_store
        self._state_ttl_seconds = state_ttl_seconds

    async def build(self) -> str:
        state = secrets.token_urlsafe(_STATE_BYTES)
        await self._state_store.put(state, self._state_ttl_seconds)
        params = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": _GOOGLE_SCOPE,
                "state": state,
                "access_type": "online",
                "include_granted_scopes": "true",
            }
        )
        return f"{_GOOGLE_AUTHORIZATION_ENDPOINT}?{params}"


class CompleteGoogleOAuth:
    """Caso de uso: conclui o callback e emite um exchange code de uso unico."""

    def __init__(
        self,
        *,
        google_client: GoogleIdentityClient,
        state_store: OAuthStateStore,
        exchange_code_store: OAuthExchangeCodeStore,
        resolver: UserIdentityResolver,
        external_identity_repository: ExternalIdentityRepository,
        membership_reader: MembershipReader,
        token_service: TokenService,
        refresh_store: RefreshTokenStore,
        access_token_expire_minutes: int,
        refresh_token_expire_seconds: int,
        exchange_code_ttl_seconds: int = 60,
    ) -> None:
        self._google_client = google_client
        self._state_store = state_store
        self._exchange_code_store = exchange_code_store
        self._resolver = resolver
        self._external_identity_repository = external_identity_repository
        self._membership_reader = membership_reader
        self._token_service = token_service
        self._refresh_store = refresh_store
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_seconds = refresh_token_expire_seconds
        self._exchange_code_ttl_seconds = exchange_code_ttl_seconds

    async def complete(self, *, code: str, state: str) -> GoogleOAuthResult:
        if not await self._state_store.consume(state):
            raise OAuthStateError()

        userinfo = await self._exchange(code)
        if not userinfo.email_verified:
            raise OAuthEmailNotVerifiedError()

        email = userinfo.email.strip().lower()
        identity = await self._resolver.resolve_by_email(email)
        if identity is None:
            payload = OAuthExchange(
                status="onboarding",
                email=email,
                full_name=userinfo.name,
            )
            return await self._issue(payload)

        if identity.status is not UserStatus.ACTIVE:
            raise UserInactiveError()

        membership = await self._membership_reader.get_membership(
            identity.company_id, identity.user_id
        )
        if membership is None or membership.status is not MemberStatus.ACTIVE:
            raise UserInactiveError()

        await self._external_identity_repository.link(
            company_id=identity.company_id,
            user_id=identity.user_id,
            provider="google",
            subject=userinfo.subject,
            email=email,
        )

        role = membership.role.value
        access_token = self._token_service.issue_access_token(
            AuthContext(
                user_id=identity.user_id,
                company_id=identity.company_id,
                role=role,
                token_id=secrets.token_hex(16),
            )
        )
        refresh_token = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
        await self._refresh_store.put(
            refresh_token,
            RefreshTokenPayload(
                user_id=identity.user_id, company_id=identity.company_id, role=role
            ),
            self._refresh_token_expire_seconds,
        )

        payload = OAuthExchange(
            status="authenticated",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",  # noqa: S106 - tipo OAuth2 padrao, nao segredo
            expires_in=self._access_token_expire_minutes * 60,
            user_id=str(identity.user_id),
            email=membership.email,
            full_name=membership.full_name,
            role=role,
        )
        return await self._issue(payload)

    async def _issue(self, payload: OAuthExchange) -> GoogleOAuthResult:
        exchange_code = secrets.token_urlsafe(_EXCHANGE_CODE_BYTES)
        await self._exchange_code_store.put(exchange_code, payload, self._exchange_code_ttl_seconds)
        return GoogleOAuthResult(status=payload.status, exchange_code=exchange_code)

    async def _exchange(self, code: str) -> GoogleUserInfo:
        try:
            return await self._google_client.exchange_authorization_code(code)
        except OAuthCodeError:
            raise
        except Exception as exc:
            raise OAuthCodeError() from exc


class ExchangeOAuthCode:
    """Caso de uso: troca um exchange code de uso unico pelo conteudo da sessao."""

    def __init__(self, *, store: OAuthExchangeCodeStore) -> None:
        self._store = store

    async def exchange(self, code: str) -> OAuthExchange:
        payload = await self._store.consume(code)
        if payload is None:
            raise OAuthExchangeError()
        return payload
