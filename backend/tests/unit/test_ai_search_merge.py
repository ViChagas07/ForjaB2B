"""Busca multi-consulta: original + pt/en, dedupe e ordenacao por preco."""

from __future__ import annotations

from decimal import Decimal

from app.modules.ai.application.tools import ProductSearchResult, ToolProduct
from app.wiring.ai_tools import _merge_search_results, _normalized_queries


def product(product_id: str, price: str) -> ToolProduct:
    return ToolProduct(
        product_id=product_id,
        name=f"Produto {product_id}",
        sku=f"SKU-{product_id}",
        price=Decimal(price),
    )


def test_queries_normalizadas_sem_duplicatas() -> None:
    assert _normalized_queries("gants", "luvas", "gloves") == [
        "gants",
        "luvas",
        "gloves",
    ]
    assert _normalized_queries("luvas", "", "luvas") == ["luvas"]


def test_merge_deduplica_e_ordena_por_preco() -> None:
    first = ProductSearchResult(products=(product("b", "20"), product("a", "10")), capped=False)
    second = ProductSearchResult(products=(product("c", "30"), product("b", "20")), capped=True)
    ascending = _merge_search_results([first, second], offset=0, limit=10, price_sort="asc")
    assert [item.product_id for item in ascending.products] == ["a", "b", "c"]
    assert ascending.capped is True
    descending = _merge_search_results([first, second], offset=0, limit=10, price_sort="desc")
    assert [item.product_id for item in descending.products] == ["c", "b", "a"]
