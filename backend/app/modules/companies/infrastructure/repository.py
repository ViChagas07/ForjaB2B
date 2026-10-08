"""Repositorio SQLAlchemy do contexto de empresas (onboarding + consulta).

Usa SQL bruto (padrao ja usado em seeds.py) para persistir empresa + operador
inicial dentro da UoW com ``TenantContext`` do NOVO tenant. Isso mantem o
bounded context companies independente do modulo identity (nao importa os
modelos ORM de identity, evitando acoplamento transitivo via enums). A
unicidade de CNPJ/CPF e garantida pelas constraints e traduzida para 409.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.companies.application.errors import (
    CompanyAlreadyExistsError,
    CpfAlreadyExistsError,
)
from app.modules.companies.application.ports import CompanyRecord, OperatorRecord

_CNPJ_UNIQUE = "uq_companies_cnpj"
_CPF_UNIQUE = "uq_users_cpf_hash"

_INSERT_COMPANY = text(
    "INSERT INTO companies (id, cnpj, legal_name, trade_name, status) "
    "VALUES (:id, :cnpj, :legal_name, :trade_name, :status)"
)
_INSERT_USER = text(
    "INSERT INTO users (id, company_id, email, full_name, cpf_hash, password_hash, status) "
    "VALUES (:id, :company_id, :email, :full_name, :cpf_hash, :password_hash, :status)"
)
_INSERT_MEMBER = text(
    "INSERT INTO company_members (id, company_id, user_id, role, status) "
    "VALUES (:id, :company_id, :user_id, :role, :status)"
)
_SELECT_COMPANY = text(
    "SELECT id, cnpj, legal_name, trade_name, status FROM companies WHERE id = :company_id"
)


def _constraint_name(exc: BaseException) -> str:
    """Extrai o nome da constraint de violacao percorrendo a cadeia de causas.

    O dialect asyncpg embrulha o UniqueViolationError do driver em uma excecao
    propria (que nao herda de sqlalchemy.exc.IntegrityError) e expoe o erro
    original apenas como ``__cause__``. A constraint_name fica no objeto asyncpg
    original, entao percorremos a cadeia ate encontra-lo.
    """
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


class SqlAlchemyCompanyRepository:
    """Implementacao da porta CompanyRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def add(self, company: CompanyRecord, operator: OperatorRecord) -> None:
        tenant = TenantContext(company_id=company.id, user_id=operator.user_id)
        try:
            async with self._uow_factory.begin(tenant) as uow:
                await uow.session.execute(
                    _INSERT_COMPANY,
                    {
                        "id": company.id,
                        "cnpj": company.cnpj,
                        "legal_name": company.legal_name,
                        "trade_name": company.trade_name,
                        "status": company.status,
                    },
                )
                await uow.session.execute(
                    _INSERT_USER,
                    {
                        "id": operator.user_id,
                        "company_id": company.id,
                        "email": operator.email,
                        "full_name": operator.full_name,
                        "cpf_hash": operator.cpf_hash,
                        "password_hash": operator.password_hash,
                        "status": operator.user_status,
                    },
                )
                await uow.session.execute(
                    _INSERT_MEMBER,
                    {
                        "id": operator.member_id,
                        "company_id": company.id,
                        "user_id": operator.user_id,
                        "role": operator.role,
                        "status": operator.member_status,
                    },
                )
                await uow.commit()
        except Exception as exc:
            constraint = _constraint_name(exc)
            if constraint == _CNPJ_UNIQUE:
                raise CompanyAlreadyExistsError() from exc
            if constraint == _CPF_UNIQUE:
                raise CpfAlreadyExistsError() from exc
            raise

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRecord | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (await uow.session.execute(_SELECT_COMPANY, {"company_id": company_id})).first()
            await uow.commit()
            if row is None:
                return None
            return CompanyRecord(
                id=row.id,
                cnpj=row.cnpj,
                legal_name=row.legal_name,
                trade_name=row.trade_name,
                status=row.status,
            )
