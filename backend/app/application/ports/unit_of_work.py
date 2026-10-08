"""Porta de Unit of Work.

Contrato de transacao por caso de uso:

    async with uow_factory.begin(tenant) as uow:
        ... trabalho ...
        await uow.commit()   # sem commit explicito, faz rollback

Regra de RLS: o contexto de tenant (quando presente) e estabelecido DENTRO
da mesma transacao que executara as consultas protegidas, garantindo que o
contexto jamais sobreviva ao fim da transacao (sem vazamento entre requests
que reutilizam conexoes do pool).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Protocol, Self

from app.application.ports.tenant import TenantContext


class UnitOfWork(ABC):
    """Unidade de trabalho transacional (context manager assincrono)."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Inicia a transacao e, se houver tenant, aplica o contexto RLS."""
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Encerra a transacao; sem commit explicito, faz rollback."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Confirma a transacao corrente."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Desfaz a transacao corrente."""
        ...


class UnitOfWorkFactory(Protocol):
    """Fabrica de unidades de trabalho, opcionalmente com contexto de tenant."""

    def begin(self, tenant: TenantContext | None = None) -> UnitOfWork:
        """Nova unidade de trabalho; o tenant e aplicado dentro da transacao."""
        ...
