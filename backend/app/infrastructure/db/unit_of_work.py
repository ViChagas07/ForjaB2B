"""Unit of Work SQLAlchemy com contexto de tenant RLS transacional.

Estrategia de ciclo de vida (por caso de uso / request):

    factory.begin(tenant)
      -> abre AsyncSession do pool
      -> BEGIN
      -> SELECT app.set_tenant_context(company_id, user_id)  (mesma transacao)
      -> consultas protegidas por RLS
      -> commit() explicito OU rollback automatico no __aexit__
      -> sessao fechada, conexao devolvida ao pool sem estado de tenant

As GUCs `forja.current_company_id` / `forja.current_user_id` sao definidas
pela funcao `app.set_tenant_context` com escopo de transacao
(set_config(..., is_local = true)): commit ou rollback as apaga. Isso
garante que request A (company A) nunca contamina request B (company B),
mesmo reutilizando a mesma conexao fisica do pool.

A funcao `app.set_tenant_context` NAO autentica nem autoriza: o tenant e
recebido ja autenticado via TenantContext (porta da camada de aplicacao).
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.tenant import TenantContext
from app.application.ports.unit_of_work import UnitOfWork

_SET_TENANT_CONTEXT = text(
    "SELECT app.set_tenant_context(CAST(:company_id AS uuid), CAST(:user_id AS uuid))"
)


class UnitOfWorkNotStartedError(RuntimeError):
    """Acesso a sessao antes de __aenter__."""


class SqlAlchemyUnitOfWork(UnitOfWork):
    """UoW sobre AsyncSession com tenant context aplicado na transacao."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant: TenantContext | None,
    ) -> None:
        self._session_factory = session_factory
        self._tenant = tenant
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """Sessao ativa da transacao (uso interno da infraestrutura)."""
        if self._session is None:
            raise UnitOfWorkNotStartedError("Unit of Work nao iniciada: use 'async with'")
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        await self._session.begin()
        if self._tenant is not None:
            await self._apply_tenant_context(self._session, self._tenant)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if session.in_transaction():
                # Sem commit explicito (ou com excecao): rollback. Defensivo e
                # deterministico; o sucesso exige commit() antes do __aexit__.
                await session.rollback()
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def _apply_tenant_context(self, session: AsyncSession, tenant: TenantContext) -> None:
        await session.execute(
            _SET_TENANT_CONTEXT,
            {
                "company_id": str(tenant.company_id),
                "user_id": str(tenant.user_id) if tenant.user_id is not None else None,
            },
        )


class SqlAlchemyUnitOfWorkFactory:
    """Fabrica de UoW SQLAlchemy; implementa app.application.ports.UnitOfWorkFactory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def begin(self, tenant: TenantContext | None = None) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory, tenant)
