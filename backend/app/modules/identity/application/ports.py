"""Portas do contexto de identidade (contratos de dependencias invertidas).

Os casos de uso dependem destas abstracoes; as implementacoes concretas vivem
na infraestrutura (Argon2, SECURITY DEFINER SQL, ORM/Redis). Isso permite
testar a orquestracao de login sem banco nem crypto reais.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

from app.domain.consumer import Gender
from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus


@dataclass(frozen=True, kw_only=True)
class UserPreferences:
    """Preferencias do usuario (moeda, privacidade, avatar, whatsapp)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    display_currency: str
    hide_spending: bool
    avatar_key: uuid.UUID | None = None
    avatar_content_type: str | None = None
    avatar_data: bytes | None = None
    avatar_updated_at: datetime | None = None
    whatsapp_phone: str | None = None
    whatsapp_opt_in: bool = False
    whatsapp_opt_in_at: datetime | None = None


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
    credential_epoch: int = 0


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
    hide_spending: bool = False


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
        birth_date: date | None = None,
        gender: Gender | None = None,
        postal_code: str | None = None,
        unlink_verified_phone: bool = False,
    ) -> AccountRecord | None:
        """Atualiza nome/telefone; remove o telefone verificado se solicitado."""

    async def update_display_currency(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        display_currency: str,
    ) -> AccountRecord | None:
        """Atualiza somente a moeda de exibicao; None se o usuario sumiu."""

    async def update_hide_spending(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        hide_spending: bool,
    ) -> AccountRecord | None:
        """Atualiza somente a privacidade dos gastos; None se o usuario sumiu."""

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

    async def get_preferences(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserPreferences | None:
        """Le as preferencias do usuario (moeda, privacidade, avatar, whatsapp)."""


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


class TurnstileVerifier(Protocol):
    """Verifica um token Cloudflare Turnstile no servidor (fail-closed)."""

    async def verify(self, *, token: str, remote_ip: str | None) -> bool:
        """True somente quando a Cloudflare confirma o token; qualquer falha e False."""


@dataclass(frozen=True, kw_only=True)
class PasswordRecoveryCodeState:
    """Estado do codigo de recuperacao guardado no Redis (sem texto puro)."""

    digest: str
    attempts: int
    locale: str | None = None


@dataclass(frozen=True, kw_only=True)
class PasswordResetTokenData:
    """Dados associados ao reset_token (o token em claro nunca e persistido)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    locale: str | None = None
    channel: Literal["email", "sms"] = "email"


@dataclass(frozen=True, kw_only=True)
class PasswordResetUser:
    """Usuario resolvido no tenant para o reset de senha."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    email: str
    password_hash: str | None
    status: UserStatus


class PasswordRecoveryStore(Protocol):
    """Temporarios do fluxo de recuperacao no Redis (fail-closed)."""

    async def reserve_resend(self, *, user_id: uuid.UUID, ttl_seconds: int) -> bool:
        """Reserva o cooldown de reenvio; False quando ainda ativo."""

    async def save_code(
        self,
        *,
        user_id: uuid.UUID,
        digest: str,
        locale: str | None,
        ttl_seconds: int,
    ) -> None:
        """Grava/sobrescreve o codigo (apenas HMAC) e zera tentativas."""

    async def load_code(self, *, user_id: uuid.UUID) -> PasswordRecoveryCodeState | None:
        """Le o estado do codigo ou None (ausente/expirado)."""

    async def record_failed_attempt(self, *, user_id: uuid.UUID, max_attempts: int) -> int:
        """Incrementa tentativas e invalida o codigo ao atingir o maximo."""

    async def consume_code(self, *, user_id: uuid.UUID, digest: str) -> bool:
        """Consome o codigo atomicamente; True somente se o HMAC confere."""

    async def delete_code(self, *, user_id: uuid.UUID) -> None:
        """Invalida o codigo (sucesso/limpeza)."""

    async def delete_cooldown(self, *, user_id: uuid.UUID) -> None:
        """Libera o reenvio apos sucesso."""

    async def save_reset_token(
        self,
        *,
        token_hash: str,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str | None,
        channel: Literal["email", "sms"],
        ttl_seconds: int,
    ) -> None:
        """Grava somente o hash do reset_token com TTL."""

    async def consume_reset_token(self, *, token_hash: str) -> PasswordResetTokenData | None:
        """Consome o reset_token atomicamente; None se ausente/expirado/reutilizado."""

    async def probe(self) -> None:
        """Garante que o Redis responde (usado no caminho sem conta)."""

    async def get_sms_attempts(self, *, user_id: uuid.UUID) -> int:
        """Tentativas SMS consumidas na janela atual (0 se ausente)."""

    async def record_sms_failed_attempt(
        self, *, user_id: uuid.UUID, max_attempts: int, ttl_seconds: int
    ) -> int:
        """Incrementa tentativas SMS e devolve o total atual."""

    async def clear_sms_attempts(self, *, user_id: uuid.UUID) -> None:
        """Zera tentativas SMS apos sucesso."""


@dataclass(frozen=True, kw_only=True)
class VerifiedPhoneOwner:
    """Usuario/tenant resolvido por telefone verificado (sem status)."""

    user_id: uuid.UUID
    company_id: uuid.UUID


class VerifiedPhoneResolver(Protocol):
    """Resolve user/company por telefone verificado sem tenant autenticado."""

    async def resolve(self, *, phone_e164: str) -> VerifiedPhoneOwner | None:
        """Dono verificado ou None; nunca revela status."""


class PasswordRecoverySmsDispatcher(Protocol):
    """Enfileira o SMS de recuperacao (Twilio gera o codigo)."""

    async def send_reset_code(self, *, to_phone: str, locale: str | None) -> None:
        """Enfileira o envio do SMS; nao bloqueia a request."""


class PasswordRecoveryEmailDispatcher(Protocol):
    """Enfileira o envio de e-mail da recuperacao (nunca envia na request)."""

    async def send_reset_code(
        self, *, to: str, locale: str | None, code: str, expires_minutes: int
    ) -> None:
        """Enfileira o e-mail com o codigo (trafega apenas no broker)."""

    async def send_password_changed(self, *, to: str, locale: str | None) -> None:
        """Enfileira o aviso de senha alterada (sem codigo)."""


class PasswordResetRepository(Protocol):
    """Leitura/atualizacao de senha e auditoria no tenant resolvido."""

    async def get_user(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PasswordResetUser | None:
        """Usuario do tenant ou None (RLS aplicada)."""

    async def update_password_and_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        password_hash: str,
        audit_action: str,
        audit_details: dict[str, str],
    ) -> int | None:
        """Troca o hash, incrementa a epoca e audita na mesma transacao.

        Retorna a nova epoca de credencial, ou None se o usuario sumiu/nao
        estiver ACTIVE. A epoca nunca diminui.
        """

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        """Grava um evento de auditoria sem PII."""


class PasswordResetSessionRevoker(Protocol):
    """Atualiza o cache da epoca para revogar sessoes antigas apos o reset."""

    async def revoke_all_for_user(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, credential_epoch: int
    ) -> None:
        """Propaga a nova epoca para o cache (o banco ja foi atualizado)."""


class PhoneVerificationService(Protocol):
    """Envio/checagem de codigo SMS via provedor (Twilio Verify)."""

    async def start(self, *, phone_e164: str, locale: str | None) -> bool:
        """Inicia a verificacao; False em qualquer falha do provedor."""

    async def check(self, *, phone_e164: str, code: str) -> bool:
        """True somente quando o provedor aprova o codigo."""


@dataclass(frozen=True, kw_only=True)
class PreviousPhoneOwner:
    """Dono anterior de um telefone vinculado que acabou de ser reivindicado."""

    user_id: uuid.UUID
    company_id: uuid.UUID


class PhoneVerificationRepository(Protocol):
    """Persistencia/auditoria da verificacao de telefone."""

    async def get_verified_phone(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        """Telefone verificado do usuario no tenant, se houver."""

    async def claim_verified_phone(
        self, *, phone_e164: str, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> PreviousPhoneOwner | None:
        """Grava o vinculo atomicamente e devolve o dono anterior, se diferente."""

    async def get_user_email(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        """E-mail de um usuario no tenant informado (para aviso de desvinculo)."""

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        """Grava auditoria sem PII."""


class AccountEmailDispatcher(Protocol):
    """Enfileira e-mails de seguranca da conta."""

    async def send_phone_unlinked(self, *, to: str, locale: str | None) -> None:
        """Enfileira o aviso de telefone desvinculado."""
