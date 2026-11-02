"""Leitura do tipo de conta da empresa (tenant-scoped).

O tipo de conta (``COMPANY`` = CNPJ, ``PERSON`` = CPF) e sempre lido do banco
no servidor. Nenhum valor enviado pelo cliente participa da decisao de preco.
Em ambientes legados sem a coluna ``companies.account_type`` o fallback e
``COMPANY``, o mesmo usado pelo restante da aplicacao.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pricing import CNPJ_ACCOUNT_TYPE
from app.infrastructure.db.schema import has_account_type

_SELECT_ACCOUNT_TYPE = text("SELECT account_type FROM companies WHERE id = :company_id")


async def load_company_account_type(session: AsyncSession, company_id: uuid.UUID) -> str:
    """Devolve o ``account_type`` da empresa, com fallback seguro para COMPANY."""
    if not await has_account_type(session):
        return CNPJ_ACCOUNT_TYPE
    row = (await session.execute(_SELECT_ACCOUNT_TYPE, {"company_id": company_id})).first()
    if row is None or not row[0]:
        return CNPJ_ACCOUNT_TYPE
    return str(row[0])
