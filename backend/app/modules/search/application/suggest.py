"""Montagem pura dos termos do dropdown de sugestoes (ordem e deduplica).

Usada pelos adaptadores ES e PostgreSQL para produzir a MESMA lista de termos:
marcas que comecam com o digitado (kind ``brand``), nomes dos produtos
encontrados (kind ``product``) e SKUs que casem por prefixo (kind ``sku``),
sem duplicatas (case-insensitive) e limitado a ``term_limit``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.search.application.ports import SuggestTerm


def _append_unique(terms: list[SuggestTerm], seen: set[str], text: str, kind: str) -> None:
    """Acrescenta o termo apenas se for novo (case-insensitive) e nao vazio."""
    candidate = text.strip()
    if not candidate:
        return
    key = candidate.lower()
    if key in seen:
        return
    seen.add(key)
    terms.append(SuggestTerm(text=candidate, kind=kind))


def collect_suggest_terms(
    *,
    query: str,
    brands: Sequence[str],
    product_names: Sequence[str],
    skus: Sequence[str],
    term_limit: int,
) -> list[SuggestTerm]:
    """Ordena e deduplica termos: brand (prefixo) > product > sku (prefixo)."""
    normalized = query.strip().lower()
    terms: list[SuggestTerm] = []
    seen: set[str] = set()
    for brand in brands:
        if brand.strip().lower().startswith(normalized):
            _append_unique(terms, seen, brand, "brand")
    for name in product_names:
        _append_unique(terms, seen, name, "product")
    for sku in skus:
        if sku.strip().lower().startswith(normalized):
            _append_unique(terms, seen, sku, "sku")
    return terms[:term_limit]
