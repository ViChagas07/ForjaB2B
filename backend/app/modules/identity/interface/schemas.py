"""Schemas HTTP do contexto de identidade (login/refresh/logout)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credenciais de login. Nunca aceitar senha via query string (so no body)."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


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
