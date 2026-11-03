"""Schemas HTTP do contexto de identidade (login/refresh/logout)."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.consumer import Gender
from app.modules.identity.application.phone import normalize_phone_e164

DisplayCurrency = Literal["BRL", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY"]
PasswordRecoveryLocale = Literal[
    "pt-BR",
    "en",
    "zh-CN",
    "ja",
    "ko",
    "ru",
    "es",
    "de",
    "fr",
    "it",
    "ar",
]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if len(normalized) > 320 or not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("E-mail invalido.")
    return normalized


class LoginRequest(BaseModel):
    """Credenciais de login. Nunca aceitar senha via query string (so no body)."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    account_type: Literal["PERSON", "COMPANY"] | None = None


class RefreshRequest(BaseModel):
    """Refresh token opaco para rotacao."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=16, max_length=256)


class UserProfile(BaseModel):
    """Perfil minimo devolvido apos o login (sem hash/senha/token interno)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    account_type: str = "COMPANY"
    avatar_url: str | None = None


class LoginResponse(BaseModel):
    """Par de tokens + perfil minimo."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserProfile


class RefreshResponse(BaseModel):
    """Novo par de tokens apos rotacao (sem perfil: nao ha nova consulta)."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class OAuthExchangeRequest(BaseModel):
    """Exchange code de uso unico recebido do callback OAuth."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=16, max_length=256)


class OAuthExchangeResponse(BaseModel):
    """Resultado da troca: sessao (authenticated) OU onboarding."""

    model_config = ConfigDict(extra="forbid")

    status: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    user: UserProfile | None = None
    email: str | None = None
    full_name: str | None = None


class AccountProfileResponse(BaseModel):
    """Perfil da conta autenticada (e-mail somente leitura)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    birth_date: date | None
    gender: Gender | None
    postal_code: str | None
    display_currency: DisplayCurrency
    avatar_url: str | None = None
    account_type: str
    role: str
    hide_spending: bool


class UpdateAccountRequest(BaseModel):
    """Dados editaveis do perfil; e-mail/CPF/CNPJ nao entram aqui."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    gender: Gender | None = None
    postal_code: str | None = Field(default=None, max_length=9)


class AccountPreferencesRequest(BaseModel):
    """Preferencias visuais persistidas no perfil (sem dados financeiros).

    O valor e normalizado pela lista fechada no caso de uso; qualquer string
    desconhecida vira BRL, sem persistir um codigo invalido.
    """

    model_config = ConfigDict(extra="forbid")

    display_currency: str


class AccountSpendingVisibilityRequest(BaseModel):
    """Preferencia de privacidade do painel (mascarar gastos)."""

    model_config = ConfigDict(extra="forbid")

    hide_spending: bool


class AccountPreferencesResponse(BaseModel):
    """Confirmacao da preferencia persistida."""

    model_config = ConfigDict(extra="forbid")

    display_currency: DisplayCurrency
    hide_spending: bool


class AccountAvatarResponse(BaseModel):
    """URL publica do avatar e instante da ultima alteracao."""

    model_config = ConfigDict(extra="forbid")

    avatar_url: str | None
    updated_at: datetime | None


class PasswordRecoveryRequest(BaseModel):
    """Pedido de codigo: exatamente um entre email e phone, mais Turnstile."""

    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    turnstile_token: str = Field(min_length=1, max_length=4096)
    locale: PasswordRecoveryLocale | None = None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str | None) -> str | None:
        return _normalize_email_value(value)

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        return normalize_phone_e164(raw)

    @field_validator("turnstile_token")
    @classmethod
    def _strip_turnstile_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Token anti-bot obrigatorio.")
        return token

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> PasswordRecoveryRequest:
        provided = int(self.email is not None) + int(self.phone is not None)
        if provided != 1:
            raise ValueError("Informe exatamente um entre email e phone.")
        return self


class PasswordRecoveryAcceptedResponse(BaseModel):
    """Resposta generica e fixa do pedido de recuperacao."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted"] = "accepted"


class PasswordRecoveryVerifyRequest(BaseModel):
    """Verificacao do codigo com exatamente um entre email e phone."""

    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    code: str = Field(min_length=1, max_length=32)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str | None) -> str | None:
        return _normalize_email_value(value)

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return _normalize_phone_value(value)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        code = value.strip()
        if not code:
            raise ValueError("Codigo obrigatorio.")
        return code

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> PasswordRecoveryVerifyRequest:
        provided = int(self.email is not None) + int(self.phone is not None)
        if provided != 1:
            raise ValueError("Informe exatamente um entre email e phone.")
        return self


class PasswordRecoveryVerifiedResponse(BaseModel):
    """reset_token opaco e TTL para a etapa de definicao da senha."""

    model_config = ConfigDict(extra="forbid")

    reset_token: str
    expires_in: int


class PasswordRecoveryResetRequest(BaseModel):
    """Definicao da nova senha com o reset_token de uso unico."""

    model_config = ConfigDict(extra="forbid")

    reset_token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=1024)

    @field_validator("reset_token")
    @classmethod
    def _strip_reset_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Token de redefinicao obrigatorio.")
        return token


def _normalize_phone_value(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    return normalize_phone_e164(raw)


class PhoneVerificationStartRequest(BaseModel):
    """Inicio da verificacao do proprio telefone por SMS."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=1, max_length=40)
    locale: PasswordRecoveryLocale | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        normalized = _normalize_phone_value(value)
        if normalized is None:
            raise ValueError("Telefone obrigatorio.")
        return normalized


class PhoneVerificationCheckRequest(BaseModel):
    """Codigo recebido por SMS para confirmar o telefone."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=32)

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        normalized = _normalize_phone_value(value)
        if normalized is None:
            raise ValueError("Telefone obrigatorio.")
        return normalized

    @field_validator("code")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        code = value.strip()
        if not code:
            raise ValueError("Codigo obrigatorio.")
        return code


class PhoneVerificationAcceptedResponse(BaseModel):
    """Resposta generica do inicio da verificacao."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted"] = "accepted"


class PhoneVerificationCheckResponse(BaseModel):
    """Confirmacao do telefone."""

    model_config = ConfigDict(extra="forbid")

    verified: Literal[True] = True


class PhoneVerificationStatusResponse(BaseModel):
    """Status mascarado para a tela de conta."""

    model_config = ConfigDict(extra="forbid")

    verified: bool
    phone_masked: str | None = None
