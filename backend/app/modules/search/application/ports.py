"""Portas do contexto de busca (contratos de dependencias invertidas).

A camada de aplicacao (e a interface) nunca fala o DSL do Elasticsearch: ela
depende desta porta. O adaptador concreto vive na infraestrutura.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SearchEngineState(StrEnum):
    """Estado de saude do motor de busca."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, kw_only=True)
class SearchEngineHealth:
    """Resultado de uma verificacao de saude do motor de busca.

    `detail` nunca contem credenciais nem dados sensiveis.
    """

    state: SearchEngineState
    detail: str | None = None


class SearchEngine(Protocol):
    """Porta do motor de busca lexical (implementada pelo Elasticsearch)."""

    async def check_health(self) -> SearchEngineHealth:
        """Verifica a disponibilidade do motor; nunca levanta excecao."""
        ...

    async def close(self) -> None:
        """Libera os recursos do cliente."""
        ...
