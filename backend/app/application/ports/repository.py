"""Porta de repositorio generica.

Contrato minimo de persistencia por agregado. Repositorios concretos de
dominio (Product, Order, ...) NAO existem na Fase 0: serao declarados nos
respectivos modulos quando os dominios forem implementados.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

EntityT = TypeVar("EntityT")
IdT = TypeVar("IdT", contravariant=True)


class Repository(Protocol[EntityT, IdT]):
    """Contrato minimo de um repositorio de agregado."""

    async def get_by_id(self, entity_id: IdT) -> EntityT | None:
        """Devolve o agregado ou None quando nao encontrado."""
        ...

    async def add(self, entity: EntityT) -> None:
        """Registra um novo agregado na unidade de trabalho corrente."""
        ...
