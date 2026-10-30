"""Schemas HTTP do contexto de identidade (login/refresh/logout)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.consumer import Gender

DisplayCurrency = Literal["BRL", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY"]


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
    account_type: str
    role: str


class UpdateAccountRequest(BaseModel):
    """Dados editaveis do perfil; e-mail/CPF/CNPJ nao entram aqui."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    gender: Gender | None = None
    postal_code: str | None = Field(default=None, max_length=9)


class AccountPreferencesRequest(BaseModel):
    """Preferencias visuais persistidas no perfil (sem dados financeiros)."""

    model_config = ConfigDict(extra="forbid")

    display_currency: DisplayCurrency


class AccountPreferencesResponse(BaseModel):
    """Confirmacao da preferencia persistida."""

    model_config = ConfigDict(extra="forbid")

    display_currency: DisplayCurrency
