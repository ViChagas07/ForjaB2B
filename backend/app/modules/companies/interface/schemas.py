"""Schemas HTTP do contexto de empresas (onboarding + consulta)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class RegisterCompanyRequest(BaseModel):
    """Entrada do onboarding: empresa + operador inicial (ADMIN)."""

    model_config = ConfigDict(extra="forbid")

    cnpj: str = Field(min_length=14, max_length=18)
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    admin_full_name: str = Field(min_length=2, max_length=200)
    admin_email: str = Field(min_length=3, max_length=320)
    admin_cpf: str = Field(min_length=11, max_length=14)
    password: str = Field(min_length=8, max_length=128)


class CompanyResponse(BaseModel):
    """Visao publica da empresa (sem dados sensiveis)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    cnpj: str
    legal_name: str
    trade_name: str | None
    status: str


class RegisterCompanyResponse(BaseModel):
    """Resultado do onboarding."""

    model_config = ConfigDict(extra="forbid")

    company: CompanyResponse
    admin_user_id: uuid.UUID
