"""Portas do contexto de identidade (contratos de dependencias invertidas).

Os casos de uso dependem destas abstracoes; as implementacoes concretas vivem
na infraestrutura (Argon2, SECURITY DEFINER SQL, ORM/Redis). Isso permite
testar a orquestracao de login sem banco nem crypto reais.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.domain.consumer import Gender
from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus


@dataclass(frozen=True, kw_only=True)
class ResolvedIdentity:
    """Identidade resolvida por email ANTES do contexto de tenant (login)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    status: UserStatus
    password_hash: str | None
    account_type: str = "COMPANY"


@dataclass(frozen=True, kw_only=True)
class Membership:
    """Vinculo usuario x empresa + perfil minimo para emissao de token."""

    role: MemberRole
    status: MemberStatus
    full_name: str
    email: str
    avatar_url: str | None = None


@dataclass(frozen=True, kw_only=True)
class RefreshTokenPayload:
    """Dados persistidos associados a um refresh token (rotacao/revogacao)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str
    account_type: str = "COMPANY"


@dataclass(frozen=True, kw_only=True)
class AccountRecord:
    """Perfil persistido do usuario (users + fallback consumer_profiles)."""

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    birth_date: date | None
    gender: Gender | None
    postal_code: str | None
    display_currency: str
    avatar_url: str | None
    account_type: str


class AccountRepository(Protocol):
    """Leitura/atualizacao do perfil da propria conta no tenant."""

    async def get(self, company_id: uuid.UUID, user_id: uuid.UUID) -> AccountRecord | None:
        """Perfil do usuario ou None quando nao pertence ao tenant."""

    async def update(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
        birth_date: date | None,
        gender: Gender | None,
        postal_code: str | None,
    ) -> AccountRecord | None:
        """Atualiza nome/telefone/perfil pessoal; None se o usuario sumiu."""

    async def update_display_currency(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        display_currency: str,
    ) -> AccountRecord | None:
        """Atualiza somente a moeda de exibicao; None se o usuario sumiu."""

    async def set_avatar(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        avatar_key: uuid.UUID,
        content_type: str,
        data: bytes,
        updated_at: datetime,
    ) -> bool:
        """Grava o avatar; False se o usuario nao existe no tenant."""

    async def clear_avatar(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Remove o avatar; False se o usuario nao existe no tenant."""

    async def get_avatar(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        avatar_key: uuid.UUID,
    ) -> AvatarBlob | None:
        """Le o avatar publico pela chave aleatoria, dentro do tenant."""


@dataclass(frozen=True, kw_only=True)
class AvatarBlob:
    """Bytes e metadados de um avatar armazenado."""

    content_type: str
    data: bytes
    updated_at: datetime


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
    picture: str | None = None


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


@dataclass(frozen=True, kw_only=True)
class OAuthExchange:
    """Conteudo de um exchange code de uso unico (sessao OU onboarding).

    Nunca vai em URL: fica no servidor (Redis) e e consumido uma unica vez pelo
    endpoint de troca. Para ``status == "authenticated"`` os campos de token e
    perfil estao preenchidos; para ``status == "registration_required"`` apenas
    ``email``/``full_name`` (identidade Google) estao disponiveis.
    """

    status: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    user_id: str | None = None
    email: str | None = None
    full_name: str | None = None
    role: str | None = None
    account_type: str | None = None
    avatar_url: str | None = None


class OAuthExchangeCodeStore(Protocol):
    """Armazenamento de exchange codes de uso unico (curta duracao, atomico)."""

    async def put(self, code: str, payload: OAuthExchange, ttl_seconds: int) -> None:
        """Registra um exchange code associado ao payload."""

    async def consume(self, code: str) -> OAuthExchange | None:
        """Consome um exchange code (devolve None se ausente/expirado/reutilizado)."""
