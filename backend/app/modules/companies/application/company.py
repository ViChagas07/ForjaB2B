"""Casos de uso do contexto de empresas (onboarding e consulta).

Nenhuma senha/CPF em texto plano e logada ou persistida: senha vai para
Argon2id e CPF para HMAC-SHA256(pepper). O tenant do operador inicial e
derivado do proprio onboarding (o novo company_id e gerado aqui e usado como
contexto RLS da transacao), nunca de um company_id vindo do cliente.

Os papeis/estados do operador inicial sao valores do vocabulario identity,
referenciados como constantes locais para manter os bounded contexts
independentes (sem importar o modulo identity).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.modules.companies.application.errors import CompanyNotFoundError
from app.modules.companies.application.ports import (
    CompanyRecord,
    CompanyRepository,
    CpfHasher,
    OperatorRecord,
    PasswordHasher,
)
from app.modules.companies.domain.cnpj import validate_cnpj
from app.modules.companies.domain.enums import CompanyStatus

_NON_DIGITS = re.compile(r"\D")

# Valores do vocabulario identity (MemberRole/MemberStatus/UserStatus), mantidos
# como constantes locais para nao importar o modulo identity (bounded contexts
# independentes).
_ADMIN_ROLE = "ADMIN"
_MEMBER_ACTIVE = "ACTIVE"
_USER_PENDING_APPROVAL = "PENDING_APPROVAL"


@dataclass(frozen=True, kw_only=True)
class RegisterCompanyCommand:
    """Entrada do onboarding de empresa + operador inicial (ADMIN)."""

    cnpj: str
    legal_name: str
    trade_name: str | None
    admin_full_name: str
    admin_email: str
    admin_cpf: str
    password: str


@dataclass(frozen=True, kw_only=True)
class CompanyRegistered:
    """Resultado do onboarding bem-sucedido."""

    company_id: uuid.UUID
    cnpj: str
    legal_name: str
    status: str
    admin_user_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class CompanyView:
    """Visao de leitura da empresa (sem dados sensiveis)."""

    id: uuid.UUID
    cnpj: str
    legal_name: str
    trade_name: str | None
    status: str


def normalize_cpf(raw: str) -> str:
    """Remove mascara do CPF (mantem apenas digitos)."""
    return _NON_DIGITS.sub("", raw)


class RegisterCompany:
    """Caso de uso: onboarding cria empresa PENDING + operador inicial ADMIN."""

    def __init__(
        self,
        *,
        repository: CompanyRepository,
        password_hasher: PasswordHasher,
        cpf_hasher: CpfHasher,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._cpf_hasher = cpf_hasher

    async def register(self, command: RegisterCompanyCommand) -> CompanyRegistered:
        cnpj = validate_cnpj(command.cnpj)

        company_id = uuid.uuid4()
        admin_user_id = uuid.uuid4()

        company = CompanyRecord(
            id=company_id,
            cnpj=cnpj,
            legal_name=command.legal_name,
            trade_name=command.trade_name,
            status=CompanyStatus.PENDING.value,
        )
        operator = OperatorRecord(
            user_id=admin_user_id,
            member_id=uuid.uuid4(),
            full_name=command.admin_full_name,
            email=command.admin_email.strip().lower(),
            cpf_hash=self._cpf_hasher.hash(normalize_cpf(command.admin_cpf)),
            password_hash=self._password_hasher.hash(command.password),
            user_status=_USER_PENDING_APPROVAL,
            role=_ADMIN_ROLE,
            member_status=_MEMBER_ACTIVE,
        )

        await self._repository.add(company, operator)

        return CompanyRegistered(
            company_id=company_id,
            cnpj=cnpj,
            legal_name=command.legal_name,
            status=company.status,
            admin_user_id=admin_user_id,
        )


class GetCurrentCompany:
    """Caso de uso: consulta a empresa do tenant autenticado."""

    def __init__(self, *, repository: CompanyRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID) -> CompanyView:
        company = await self._repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()
        return CompanyView(
            id=company.id,
            cnpj=company.cnpj,
            legal_name=company.legal_name,
            trade_name=company.trade_name,
            status=company.status,
        )


class ApproveCompany:
    """Caso de uso (admin de plataforma): ativa uma empresa PENDING."""

    def __init__(self, *, repository: CompanyRepository) -> None:
        self._repository = repository

    async def approve(self, company_id: uuid.UUID) -> bool:
        return await self._repository.approve(company_id)
