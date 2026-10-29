"""Schemas HTTP do contexto de empresas (onboarding + consulta)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.consumer import Gender


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
    """Visao publica da empresa/conta (sem dados sensiveis)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    cnpj: str | None
    legal_name: str
    trade_name: str | None
    status: str
    account_type: str


class RegisterCompanyResponse(BaseModel):
    """Resultado do onboarding."""

    model_config = ConfigDict(extra="forbid")

    company: CompanyResponse
    admin_user_id: uuid.UUID


class RegisterConsumerRequest(BaseModel):
    """Entrada do cadastro de cliente consumidor (CPF)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    cpf: str = Field(min_length=11, max_length=14)
    birth_date: date
    postal_code: str = Field(min_length=8, max_length=9, pattern=r"^\d{8}$")
    gender: Gender
    consent: bool


class RegisterConsumerResponse(BaseModel):
    """Resultado do cadastro de consumidor."""

    model_config = ConfigDict(extra="forbid")

    company_id: uuid.UUID
    user_id: uuid.UUID
