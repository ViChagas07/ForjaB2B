"""Portas do contexto de identidade (contratos de dependencias invertidas).

Os casos de uso dependem destas abstracoes; as implementacoes concretas vivem
na infraestrutura (Argon2, SECURITY DEFINER SQL, ORM/Redis). Isso permite
testar a orquestracao de login sem banco nem crypto reais.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus


@dataclass(frozen=True, kw_only=True)
class ResolvedIdentity:
    """Identidade resolvida por email ANTES do contexto de tenant (login)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    status: UserStatus
    password_hash: str | None


@dataclass(frozen=True, kw_only=True)
class Membership:
    """Vinculo usuario x empresa + perfil minimo para emissao de token."""

    role: MemberRole
    status: MemberStatus
    full_name: str
    email: str


@dataclass(frozen=True, kw_only=True)
class RefreshTokenPayload:
    """Dados persistidos associados a um refresh token (rotacao/revogacao)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str


class PasswordHasher(Protocol):
    """Hash e verificacao de senha (Argon2id na implementacao concreta)."""

    def hash(self, password: str) -> str:
        """Gera o hash irreversivel da senha em texto plano."""

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Verifica a senha contra o hash; None/`malformado` devolve False."""


class UserIdentityResolver(Protocol):
    """Resolve email -> identidade minima via funcao SECURITY DEFINER."""

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        """Devolve a identidade ou None quando o email nao existe."""


class MembershipReader(Protocol):
    """Le o vinculo (role, status) e o perfil dentro do tenant autenticado."""

    async def get_membership(self, company_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        """Devolve o vinculo ativo ou None quando inexistente."""


class RefreshTokenStore(Protocol):
    """Armazenamento temporario (Redis) de refresh tokens com rotacao."""

    async def put(
        self, refresh_token_id: str, payload: RefreshTokenPayload, ttl_seconds: int
    ) -> None:
        """Registra um refresh token com TTL."""

    async def get(self, refresh_token_id: str) -> RefreshTokenPayload | None:
        """Le o payload de um refresh token ou None (ausente/expirado)."""

    async def delete(self, refresh_token_id: str) -> None:
        """Revoga um refresh token (logout/rotacao)."""


@dataclass(frozen=True, kw_only=True)
class GoogleUserInfo:
    """Identidade devolvida pelo Google (userinfo) apos troca do code."""

    subject: str
    email: str
    email_verified: bool
    name: str


class GoogleIdentityClient(Protocol):
    """Troca authorization code por identidade verificada (OAuth 2.0).

    Nunca devolve tokens do Google para o chamador; apenas a identidade
    (subject/email/name) ja validada contra o provider.
    """

    async def exchange_authorization_code(self, code: str) -> GoogleUserInfo:
        """Troca o code e devolve a identidade do usuario Google."""


class OAuthStateStore(Protocol):
    """Armazenamento de state anti-CSRF (single-use, com TTL)."""

    async def put(self, state: str, ttl_seconds: int) -> None:
        """Registra um state para o fluxo de autorizacao."""

    async def consume(self, state: str) -> bool:
        """Valida e consome um state (True somente na primeira vez)."""


class ExternalIdentityRepository(Protocol):
    """Vinculo entre usuario e identidade externa (provider + subject)."""

    async def link(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        provider: str,
        subject: str,
        email: str,
    ) -> None:
        """Vincula a identidade externa ao usuario; idempotente; conflito -> erro."""
