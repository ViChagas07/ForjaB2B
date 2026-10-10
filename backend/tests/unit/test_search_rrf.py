"""Testes unitarios da fusao RRF e da heuristica de SKU (Fase 5)."""

from __future__ import annotations

import pytest

from app.modules.search.application.rrf import looks_like_sku, reciprocal_rank_fusion


def test_documento_presente_nas_duas_listas_vence() -> None:
    lexical = ["a", "b", "c"]
    semantic = ["c", "d"]
    assert reciprocal_rank_fusion([lexical, semantic], k=60)[0] == "c"


def test_empate_resolvido_por_melhor_rank_e_primeira_aparicao() -> None:
    fused = reciprocal_rank_fusion([["a"], ["b"]], k=60)
    assert fused == ["a", "b"]  # mesmo score; primeira aparicao decide


def test_ids_duplicados_nao_se_repetem() -> None:
    fused = reciprocal_rank_fusion([["a", "a", "b"]], k=60)
    assert fused.count("a") == 1


def test_k_invalido_rejeitado() -> None:
    with pytest.raises(ValueError, match="k must be"):
        reciprocal_rank_fusion([["a"]], k=0)


def test_looks_like_sku() -> None:
    assert looks_like_sku("CAP-001") is True
    assert looks_like_sku("sku123") is True
    assert looks_like_sku("capacete de seguranca") is False
    assert looks_like_sku("luva") is False  # sem digito
    assert looks_like_sku("") is False
