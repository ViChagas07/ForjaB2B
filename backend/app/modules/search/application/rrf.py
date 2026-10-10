"""Fusao Reciprocal Rank Fusion (RRF) e heuristicas de consulta (puro).

RRF combina varias listas ordenadas somando ``1 / (k + rank)`` por documento.
Empates sao resolvidos de forma deterministica: melhor rank e, por fim, a
primeira aparicao. Consultas que parecem SKU dispensam o caminho vetorial,
preservando o SKU exato no topo (rank alto no lexical).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,31}$")


def looks_like_sku(text: str) -> bool:
    """Heuristica: token unico, curto, com digito (ex.: ``CAP-001``)."""
    candidate = text.strip()
    if not candidate or " " in candidate or len(candidate) > 32:
        return False
    return bool(_SKU_RE.match(candidate)) and any(char.isdigit() for char in candidate)


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], *, k: int) -> list[str]:
    """Funde listas de ids por RRF; devolve ids ordenados por score decrescente."""
    if k < 1:
        raise ValueError("k must be >= 1")
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            previous = best_rank.get(doc_id)
            if previous is None or rank < previous:
                best_rank[doc_id] = rank
            if doc_id not in first_seen:
                first_seen[doc_id] = order
                order += 1
    return sorted(
        scores,
        key=lambda doc_id: (-scores[doc_id], best_rank[doc_id], first_seen[doc_id]),
    )
