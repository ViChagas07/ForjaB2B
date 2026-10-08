"""Casos de uso de autenticacao do contexto de identidade.

Orquestram o fluxo de login/resolucao de identidade sem conhecer detalhes de
persistencia ou crypto (portas). Nenhuma senha, hash ou token e logado aqui.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from app.application.security import AuthContext, TokenService
from app.modules.identity.application.errors import (
    InvalidCredentialsError,
    RefreshTokenRejectedError,
    UserInactiveError,
)
from app.modules.identity.application.ports import (
    MembershipReader,
    PasswordHasher,
    RefreshTokenPayload,
    RefreshTokenStore,
    UserIdentityResolver,
)
from app.modules.identity.domain.enums import MemberStatus, UserStatus

_REFRESH_TOKEN_BYTES = 32


@dataclass(frozen=True, kw_only=True)
class AuthenticationResult:
    """Resultado de um login/refresh bem-sucedido (dados minimos para o cliente)."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str
    email: str
    full_name: str


class AuthenticateUser:
    """Caso de uso: login por email/senha com resolucao de tenant segura."""

    def __init__(
        self,
        *,
        resolver: UserIdentityResolver,
        hasher: PasswordHasher,
        membership_reader: MembershipReader,
        token_service: TokenService,
        refresh_store: RefreshTokenStore,
        access_token_expire_minutes: int,
        refresh_token_expire_seconds: int,
    ) -> None:
        self._resolver = resolver
        self._hasher = hasher
        self._membership_reader = membership_reader
        self._token_service = token_service
        self._refresh_store = refresh_store
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_seconds = refresh_token_expire_seconds

    async def login(self, email: str, password: str) -> AuthenticationResult:
        identity = await self._resolver.resolve_by_email(email)

        # Verificar SEMPRE (mesmo sem usuario) mitiga enumeracao por timing.
        hash_candidate = identity.password_hash if identity is not None else None
        if not self._hasher.verify(password, hash_candidate):
            raise InvalidCredentialsError()

        if identity is None or identity.status is not UserStatus.ACTIVE:
            raise UserInactiveError()

        membership = await self._membership_reader.get_membership(
            identity.company_id, identity.user_id
        )
        if membership is None or membership.status is not MemberStatus.ACTIVE:
            raise UserInactiveError()

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
        return AuthenticationResult(
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


class RefreshSession:
    """Caso de uso: rotaciona o refresh token e emite novo par de tokens."""

    def __init__(
        self,
        *,
        refresh_store: RefreshTokenStore,
        token_service: TokenService,
        access_token_expire_minutes: int,
        refresh_token_expire_seconds: int,
    ) -> None:
        self._refresh_store = refresh_store
        self._token_service = token_service
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_seconds = refresh_token_expire_seconds

    async def refresh(self, refresh_token: str) -> AuthenticationResult:
        payload = await self._refresh_store.get(refresh_token)
        if payload is None:
            raise RefreshTokenRejectedError()

        # Rotacao: o token antigo e consumido e nao pode ser reutilizado.
        await self._refresh_store.delete(refresh_token)

        access_token = self._token_service.issue_access_token(
            AuthContext(
                user_id=payload.user_id,
                company_id=payload.company_id,
                role=payload.role,
                token_id=secrets.token_hex(16),
            )
        )
        new_refresh_token = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
        await self._refresh_store.put(
            new_refresh_token, payload, self._refresh_token_expire_seconds
        )
        return AuthenticationResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",  # noqa: S106 - tipo OAuth2 padrao, nao segredo
            expires_in=self._access_token_expire_minutes * 60,
            user_id=payload.user_id,
            company_id=payload.company_id,
            role=payload.role,
            email="",
            full_name="",
        )


class Logout:
    """Caso de uso: revoga um refresh token (logout)."""

    def __init__(self, *, refresh_store: RefreshTokenStore) -> None:
        self._refresh_store = refresh_store

    async def logout(self, refresh_token: str) -> None:
        await self._refresh_store.delete(refresh_token)
