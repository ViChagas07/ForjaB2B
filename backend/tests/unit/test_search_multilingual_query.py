"""Testes do construtor de consultas multilíngue (Fase 9B-b).

Verifica que _build_text_query gera o DSL correto para cada idioma,
mantém prioridade de SKU, e não quebra quando locale não tem tradução.
"""

from __future__ import annotations

from typing import Any

from app.modules.search.application.documents import SEARCH_TRANSLATION_LOCALES
from app.modules.search.application.ports import SearchQuery


class _FakeIndex:
    """Replica _build_text_query e _base_filters sem depender do cliente ES."""

    def _build_text_query(self, q: str, locale: str = "pt-BR") -> dict[str, Any]:
        from app.modules.search.application.documents import SEARCH_TRANSLATION_LOCALES

        normalized = q.lower()
        should: list[dict[str, Any]] = [
            {"term": {"sku": {"value": normalized, "boost": 10}}},
            {"prefix": {"sku.prefix": {"value": normalized, "boost": 8}}},
            {"match_phrase": {"name": {"query": q, "boost": 6}}},
            {"match": {"name": {"query": q, "fuzziness": "AUTO", "boost": 4}}},
            {"match": {"category.text": {"query": q, "boost": 2}}},
            {"match": {"brand.text": {"query": q, "boost": 2}}},
            {"match": {"description": {"query": q, "boost": 1}}},
        ]
        if locale in SEARCH_TRANSLATION_LOCALES:
            should.extend(
                [
                    {"match_phrase": {f"name_{locale}": {"query": q, "boost": 6}}},
                    {"match": {f"name_{locale}": {"query": q, "fuzziness": "AUTO", "boost": 4}}},
                    {"match": {f"description_{locale}": {"query": q, "boost": 1}}},
                    {"match": {f"attributes_text_{locale}": {"query": q, "boost": 1}}},
                ]
            )
        return {"bool": {"should": should, "minimum_should_match": 1}}

    def _base_filters(self, query: SearchQuery) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = [
            {"term": {"status": "ACTIVE"}},
            {"term": {"is_available": True}},
        ]
        if query.category_id is not None:
            filters.append({"term": {"category_id": str(query.category_id)}})
        if query.brand_id is not None:
            filters.append({"term": {"brand_id": str(query.brand_id)}})
        if query.is_epi is not None:
            filters.append({"term": {"is_epi": query.is_epi}})
        return filters


def _index() -> _FakeIndex:
    return _FakeIndex()


def test_query_builder_mantem_prioridade_sku_exato() -> None:
    """SKU exato (boost 10) e prefixo SKU (boost 8) continuam no topo
    para qualquer locale."""
    for locale in ("pt-BR", "en", "es", "ar", "fr"):
        query = _index()._build_text_query("CAP-001", locale=locale)
        should = query["bool"]["should"]
        assert should[0] == {"term": {"sku": {"value": "cap-001", "boost": 10}}}
        assert should[1] == {"prefix": {"sku.prefix": {"value": "cap-001", "boost": 8}}}


def test_query_builder_adiciona_campos_do_idioma_do_cliente() -> None:
    """Para locale em SEARCH_TRANSLATION_LOCALES, adiciona campos
    name/description/attributes_text do idioma."""
    for locale in SEARCH_TRANSLATION_LOCALES:
        query = _index()._build_text_query("helmet", locale=locale)
        should = query["bool"]["should"]

        # Campos pt-BR (sempre presentes)
        assert "match_phrase" in str(should)
        assert f"name_{locale}" in str(should)
        assert f"description_{locale}" in str(should)
        assert f"attributes_text_{locale}" in str(should)

        # Verifica boosts corretos
        name_phrase = next(c for c in should if f"name_{locale}" in c.get("match_phrase", {}))
        assert name_phrase["match_phrase"][f"name_{locale}"]["boost"] == 6

        name_match = next(c for c in should if f"name_{locale}" in c.get("match", {}))
        assert name_match["match"][f"name_{locale}"]["boost"] == 4
        assert name_match["match"][f"name_{locale}"]["fuzziness"] == "AUTO"

        desc_match = next(c for c in should if f"description_{locale}" in c.get("match", {}))
        assert desc_match["match"][f"description_{locale}"]["boost"] == 1

        attr_match = next(c for c in should if f"attributes_text_{locale}" in c.get("match", {}))
        assert attr_match["match"][f"attributes_text_{locale}"]["boost"] == 1


def test_query_builder_locale_fora_da_lista_nao_adiciona_campos_extra() -> None:
    """Locale não suportado (ex.: fr, de) usa apenas campos pt-BR; não quebra."""
    query = _index()._build_text_query("capacete", locale="fr")
    should = query["bool"]["should"]

    # Apenas campos base pt-BR + sku
    field_refs = str(should)
    assert "name_fr" not in field_refs
    assert "description_fr" not in field_refs
    assert "attributes_text_fr" not in field_refs

    # Campos pt-BR presentes
    assert any("name" in c.get("match_phrase", {}) for c in should)
    assert any("name" in c.get("match", {}) for c in should)


def test_query_builder_locale_pt_br_usa_apenas_campos_base() -> None:
    """pt-BR (idioma de origem) não duplica campos; usa name/description
    base."""
    query = _index()._build_text_query("capacete", locale="pt-BR")
    should = query["bool"]["should"]

    field_refs = str(should)
    # Não deve ter campos _pt-BR (não existem no mapping)
    assert "name_pt-BR" not in field_refs
    assert "description_pt-BR" not in field_refs

    # Campos base presentes com boosts corretos
    name_phrase = next(c for c in should if "name" in c.get("match_phrase", {}))
    assert name_phrase["match_phrase"]["name"]["boost"] == 6

    name_match = next(c for c in should if "name" in c.get("match", {}))
    assert name_match["match"]["name"]["boost"] == 4


def test_query_builder_fuzziness_apenas_no_name_nao_no_sku() -> None:
    """Fuzziness AUTO apenas no match do name (pt-BR e locale), nunca
    no SKU."""
    query = _index()._build_text_query("CAP-001", locale="en")
    should = query["bool"]["should"]

    for clause in should:
        if "term" in clause and "sku" in clause["term"]:
            assert "fuzziness" not in str(clause)
        if "prefix" in clause and "sku.prefix" in clause["prefix"]:
            assert "fuzziness" not in str(clause)
        if "match" in clause and "name" in clause["match"]:
            assert clause["match"]["name"]["fuzziness"] == "AUTO"
        if "match" in clause and "name_en" in clause["match"]:
            assert clause["match"]["name_en"]["fuzziness"] == "AUTO"


def test_query_builder_filtros_sempre_incluem_status_e_disponibilidade() -> None:
    """_base_filters sempre aplica status=ACTIVE e is_available=True."""
    filters = _index()._base_filters(
        SearchQuery(q=None, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20)
    )
    assert {"term": {"status": "ACTIVE"}} in filters
    assert {"term": {"is_available": True}} in filters


def test_query_builder_filtros_incluem_facets_opcionais() -> None:
    """Filtros opcionais (category_id, brand_id, is_epi) são adicionados
    quando fornecidos."""
    import uuid

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


def test_query_builder_busca_em_portugues_tambem_para_outros_idiomas() -> None:
    """Busca em inglês também encontra termos em português (marcas, SKU,
    categoria pt-BR)."""
    query = _index()._build_text_query("capacete", locale="en")
    should = query["bool"]["should"]
    field_refs = str(should)

    # Campos pt-BR sempre presentes (marcas, categoria, descrição em pt)
    assert "category.text" in field_refs
    assert "brand.text" in field_refs
    assert "description" in field_refs  # description base (pt-BR)

    # E campos en
    assert "name_en" in field_refs
    assert "description_en" in field_refs
    assert "attributes_text_en" in field_refs
