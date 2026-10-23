"""Limpeza de versoes antigas do indice versionado (substitui ILM).

O indice de produtos e um unico indice versionado por vez, apontado por um alias
estavel. O anterior fica para rollback; esta limpeza remove apenas versoes que
nao sao o alvo do alias nem uma das N mais recentes. Sem ILM: o indice nao e
append-only, e reconstruivel a partir do PostgreSQL, e a troca de alias e o
mecanismo de retencao.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.ports import PrunableProductIndex


@dataclass(frozen=True, kw_only=True)
class PruneReport:
    """Relatorio da limpeza (dry-run mostra o que seria removido)."""

    dry_run: bool
    keep: int
    alias_targets: list[str]
    kept: list[str]
    deleted: list[str]


class PruneSearchIndices:
    """Remove versoes antigas preservando o alias e as N mais recentes."""

    def __init__(self, *, index: PrunableProductIndex, keep: int = 2) -> None:
        if keep < 1:
            raise ValueError("keep deve ser >= 1")
        self._index = index
        self._keep = keep

    def _versioned(self, names: list[str]) -> list[tuple[int, str]]:
        pattern = re.compile(rf"^{re.escape(self._index.alias)}_v(\d+)$")
        versioned: list[tuple[int, str]] = []
        for name in names:
            match = pattern.match(name)
            if match:
                versioned.append((int(match.group(1)), name))
        return sorted(versioned, reverse=True)

    async def run(self, *, dry_run: bool = False) -> PruneReport:
        alias_targets = await self._index.alias_targets()
        if not alias_targets:
            raise SearchIndexError(
                "alias sem indice alvo: limpeza recusada para nao remover versoes validas"
            )
        versioned = self._versioned(await self._index.list_versioned_indices())
        if not versioned:
            raise SearchIndexError("nenhum indice versionado encontrado para o alias")
        protected = set(alias_targets) | {name for _version, name in versioned[: self._keep]}
        # Ordem crescente (mais antigo primeiro) para o relatorio ser estavel.
        ordered = sorted(versioned)
        to_delete = [name for _version, name in ordered if name not in protected]
        if not dry_run:
            for name in to_delete:
                await self._index.delete_index(index_name=name)
        return PruneReport(
            dry_run=dry_run,
            keep=self._keep,
            alias_targets=sorted(alias_targets),
            kept=[name for _version, name in ordered if name in protected],
            deleted=to_delete,
        )
