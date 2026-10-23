"""Testes da limpeza de versoes antigas do indice (sem Elasticsearch)."""

from __future__ import annotations

import pytest

from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.prune import PruneSearchIndices


class _PrunableIndex:
    alias = "forja_products"

    def __init__(self, *, indices: list[str], targets: set[str]) -> None:
        self.indices = indices
        self.targets = targets
        self.deleted: list[str] = []

    async def list_versioned_indices(self) -> list[str]:
        return list(self.indices)

    async def alias_targets(self) -> set[str]:
        return set(self.targets)

    async def delete_index(self, *, index_name: str) -> None:
        self.deleted.append(index_name)


async def test_keep_respeita_n_e_preserva_alias() -> None:
    index = _PrunableIndex(
        indices=[
            "forja_products_v1",
            "forja_products_v2",
            "forja_products_v3",
            "forja_products_v4",
        ],
        targets={"forja_products_v4"},
    )
    report = await PruneSearchIndices(index=index, keep=2).run(dry_run=False)
    assert report.deleted == ["forja_products_v1", "forja_products_v2"]
    assert report.kept == ["forja_products_v3", "forja_products_v4"]
    assert index.deleted == ["forja_products_v1", "forja_products_v2"]


async def test_alias_antigo_nunca_e_removido_mesmo_fora_dos_n_mais_novos() -> None:
    index = _PrunableIndex(
        indices=[
            "forja_products_v1",
            "forja_products_v2",
            "forja_products_v3",
            "forja_products_v4",
        ],
        targets={"forja_products_v2"},
    )
    report = await PruneSearchIndices(index=index, keep=1).run(dry_run=False)
    assert "forja_products_v2" not in report.deleted
    assert "forja_products_v4" in report.kept
    assert set(report.deleted) == {"forja_products_v1", "forja_products_v3"}


async def test_dry_run_nao_remove_nada() -> None:
    index = _PrunableIndex(
        indices=["forja_products_v1", "forja_products_v2", "forja_products_v3"],
        targets={"forja_products_v3"},
    )
    report = await PruneSearchIndices(index=index, keep=2).run(dry_run=True)
    assert report.dry_run is True
    assert report.deleted == ["forja_products_v1"]
    assert index.deleted == []


async def test_ordena_por_versao_numerica_nao_lexicografica() -> None:
    index = _PrunableIndex(
        indices=[
            "forja_products_v2",
            "forja_products_v8",
            "forja_products_v9",
            "forja_products_v10",
        ],
        targets={"forja_products_v10"},
    )
    report = await PruneSearchIndices(index=index, keep=2).run(dry_run=True)
    assert report.deleted == ["forja_products_v2", "forja_products_v8"]


async def test_alias_sem_alvo_recusa_limpeza() -> None:
    index = _PrunableIndex(indices=["forja_products_v1"], targets=set())
    with pytest.raises(SearchIndexError):
        await PruneSearchIndices(index=index, keep=2).run(dry_run=True)


def test_keep_zero_e_invalido() -> None:
    with pytest.raises(ValueError):
        PruneSearchIndices(index=_PrunableIndex(indices=[], targets=set()), keep=0)
