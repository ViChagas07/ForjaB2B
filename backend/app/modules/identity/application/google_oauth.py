"""Casos de uso do OAuth Google (Authorization Code Flow tradicional).

Fluxo:

    GET /auth/google          -> state anti-CSRF + redirect para o Google
    GET /auth/google/callback -> valida state, troca code, resolve identidade,
                                 vincula ao usuario existente (ou onboarding) e
                                 estabelece a sessao (mesmo access/refresh token).

Nunca usar Google Identity Services (GIS) nem popup. O client_secret vive
somente no backend. Nenhum token do Google e exposto ao frontend.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt

from app.application.security import AuthContext, TokenService
from app.modules.identity.application.auth import AuthenticationResult
from app.modules.identity.application.errors import (
    OAuthCodeError,
    OAuthEmailNotVerifiedError,
    OAuthStateError,
    UserInactiveError,
)
from app.modules.identity.application.ports import (
    ExternalIdentityRepository,
    GoogleIdentityClient,
    GoogleUserInfo,
    MembershipReader,
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
_ONBOARDING_TOKEN_TYPE = "onboarding"  # noqa: S105 - tipo de claim, nao segredo


@dataclass(frozen=True, kw_only=True)
class GoogleOAuthResult:
    """Resultado do fluxo OAuth (sessao estabelecida OU onboarding)."""

    status: str  # "authenticated" | "onboarding"
    session: AuthenticationResult | None = None
    onboarding_token: str | None = None


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
    """Caso de uso: conclui o fluxo OAuth (callback)."""

    def __init__(
        self,
        *,
        google_client: GoogleIdentityClient,
        state_store: OAuthStateStore,
        resolver: UserIdentityResolver,
        external_identity_repository: ExternalIdentityRepository,
        membership_reader: MembershipReader,
        token_service: TokenService,
        refresh_store: RefreshTokenStore,
        access_token_expire_minutes: int,
        refresh_token_expire_seconds: int,
        secret_key: str,
        jwt_algorithm: str,
        onboarding_token_ttl_seconds: int = 600,
    ) -> None:
        self._google_client = google_client
        self._state_store = state_store
        self._resolver = resolver
        self._external_identity_repository = external_identity_repository
        self._membership_reader = membership_reader
        self._token_service = token_service
        self._refresh_store = refresh_store
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_seconds = refresh_token_expire_seconds
        self._secret_key = secret_key
        self._jwt_algorithm = jwt_algorithm
        self._onboarding_token_ttl_seconds = onboarding_token_ttl_seconds

    async def complete(self, *, code: str, state: str) -> GoogleOAuthResult:
        if not await self._state_store.consume(state):
            raise OAuthStateError()

        userinfo = await self._exchange(code)
        if not userinfo.email_verified:
            raise OAuthEmailNotVerifiedError()

        email = userinfo.email.strip().lower()
        identity = await self._resolver.resolve_by_email(email)
        if identity is None:
            return GoogleOAuthResult(
                status="onboarding", onboarding_token=self._issue_onboarding_token(userinfo)
            )
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
        session = AuthenticationResult(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",  # noqa: S106 - tipo OAuth2 padrao, nao segredo
            expires_in=self._access_token_expire_minutes * 60,
            user_id=identity.user_id,
            company_id=identity.company_id,
            role=role,
            email=membership.email,
            full_name=membership.full_name,
        )
        return GoogleOAuthResult(status="authenticated", session=session)

    async def _exchange(self, code: str) -> GoogleUserInfo:
        try:
            return await self._google_client.exchange_authorization_code(code)
        except OAuthCodeError:
            raise
        except Exception as exc:
            raise OAuthCodeError() from exc

    def _issue_onboarding_token(self, userinfo: GoogleUserInfo) -> str:
        now = datetime.now(UTC)
        payload = {
            "type": _ONBOARDING_TOKEN_TYPE,
            "provider": "google",
            "sub": userinfo.subject,
            "email": userinfo.email,
            "name": userinfo.name,
            "iat": now,
            "exp": now + timedelta(seconds=self._onboarding_token_ttl_seconds),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._jwt_algorithm)
