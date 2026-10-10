"""Testes dos arquivos de schema do indice (mapping/settings versionados)."""

from __future__ import annotations

from app.modules.search.infrastructure.index_files import (
    load_index_mappings,
    load_index_settings,
    versioned_index_name,
)


def test_mapping_e_explicito_e_estrito() -> None:
    mappings = load_index_mappings()
    assert mappings["dynamic"] == "strict"
    properties = mappings["properties"]
    for field in ("id", "sku", "name", "description", "status", "is_epi", "version"):
        assert field in properties


def test_mapping_nao_indexa_preco() -> None:
    mappings = load_index_mappings()
    for name in mappings["properties"]:
        assert "price" not in name
        assert "preco" not in name


def test_settings_tem_analisadores_de_portugues_e_autocomplete() -> None:
    settings = load_index_settings()
    filters = settings["analysis"]["filter"]
    analyzers = settings["analysis"]["analyzer"]
    assert filters["pt_stemmer"]["language"] == "portuguese"
    assert filters["ascii_folding"]["type"] == "asciifolding"
    assert filters["edge_ngram_2_15"]["type"] == "edge_ngram"
    assert analyzers["pt_text"]["type"] == "custom"
    assert "ascii_folding" in analyzers["pt_text"]["filter"]
    assert "edge_ngram_2_15" in analyzers["autocomplete_index"]["filter"]
    assert "lowercase_normalizer" in settings["analysis"]["normalizer"]


def test_replicas_configuraveis_partem_de_zero() -> None:
    assert load_index_settings()["number_of_replicas"] == 0


def test_nome_do_indice_e_versionado_sob_o_alias() -> None:
    assert versioned_index_name(alias="forja_products", version=1) == "forja_products_v1"
    assert versioned_index_name(alias="forja_products", version=2) == "forja_products_v2"
