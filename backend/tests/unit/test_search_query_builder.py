"""Testes unitarios do construtor de consultas Elasticsearch (Fase 4).

Nao e necessario um servidor ES: verificamos a estrutura do DSL gerada pela
infraestrutura, garantindo prioridades de ranking e filtros obrigatorios.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from app.modules.search.application.ports import SearchQuery
from app.modules.search.infrastructure.elasticsearch import ElasticsearchProductIndex


class _FakeClient:
    """Cliente ES falso: apenas satisfaz a assinatura do construtor."""

    async def close(self) -> None:
        return None


def _index() -> ElasticsearchProductIndex:
    return ElasticsearchProductIndex(client=cast(Any, _FakeClient()), alias="forja_products")


def test_sku_exato_tem_maior_boost() -> None:
    query = _index()._build_text_query("CAP-001")
    first = query["bool"]["should"][0]
    assert first == {"term": {"sku": {"value": "cap-001", "boost": 10}}}


def test_prefixo_sku_e_segundo_mais_relevante() -> None:
    query = _index()._build_text_query("CAP")
    should = query["bool"]["should"]
    assert should[1] == {"prefix": {"sku.prefix": {"value": "cap", "boost": 8}}}


def test_frase_no_nome_vem_antes_de_termos_fuzzy() -> None:
    query = _index()._build_text_query("capacete branco")
    should = query["bool"]["should"]
    assert should[2] == {"match_phrase": {"name": {"query": "capacete branco", "boost": 6}}}
    expected_match = {
        "match": {"name": {"query": "capacete branco", "fuzziness": "AUTO", "boost": 4}}
    }
    assert should[3] == expected_match


def test_fuzziness_apenas_no_nome_nao_no_sku() -> None:
    query = _index()._build_text_query("CAP-001")
    should = query["bool"]["should"]
    sku_clauses = [c for c in should if "sku" in c]
    assert all("fuzziness" not in str(c) for c in sku_clauses)
    name_clause = next(c for c in should if "match" in c and "name" in c["match"])
    assert name_clause["match"]["name"]["fuzziness"] == "AUTO"


def test_filtros_sempre_aplicam_status_e_disponibilidade() -> None:
    filters = _index()._base_filters(
        SearchQuery(q=None, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20)
    )
    assert {"term": {"status": "ACTIVE"}} in filters
    assert {"term": {"is_available": True}} in filters


def test_filtros_incluem_facets_opcionais() -> None:
    category_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    filters = _index()._base_filters(
        SearchQuery(
            q=None,
            category_id=category_id,
            brand_id=brand_id,
            is_epi=True,
            page=1,
            page_size=20,
        )
    )
    assert {"term": {"category_id": str(category_id)}} in filters
    assert {"term": {"brand_id": str(brand_id)}} in filters
    assert {"term": {"is_epi": True}} in filters
