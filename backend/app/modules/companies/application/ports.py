"""Portas do contexto de empresas (contratos de dependencias invertidas).

O onboarding cria, alem da empresa, o operador inicial (usuario + vinculo), que
sao entidades do contexto identity. Para NAO acoplar os bounded contexts
(independencia exigida pelo import-linter), o contexto companies trabalha com
registros de dados neutros (``CompanyRecord`` / ``OperatorRecord``) e a
infraestrutura persiste via SQL bruto sobre o schema compartilhado, sem
importar os modelos ORM do contexto identity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class CompanyRecord:
    """Dados da empresa a persistir/ler."""

    id: uuid.UUID
    cnpj: str
    legal_name: str
    trade_name: str | None
    status: str


@dataclass(frozen=True, kw_only=True)
class OperatorRecord:
    """Operador inicial (usuario + vinculo ADMIN) criado no onboarding."""

    user_id: uuid.UUID
    member_id: uuid.UUID
    full_name: str
    email: str
    cpf_hash: str
    password_hash: str
    user_status: str
    role: str
    member_status: str


class PasswordHasher(Protocol):
    """Hash de senha (Argon2id)."""

    def hash(self, password: str) -> str: ...


class CpfHasher(Protocol):
    """Hash irreversivel de CPF (HMAC-SHA256 com pepper)."""

    def hash(self, cpf: str) -> str: ...


class CompanyRepository(Protocol):
    """Persistencia do agregado empresa + operador inicial (onboarding)."""

    async def add(self, company: CompanyRecord, operator: OperatorRecord) -> None:
        """Registra empresa + operador inicial + vinculo ADMIN atomicamente."""

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRecord | None:
        """Le a empresa do tenant (RLS limita ao proprio tenant)."""
