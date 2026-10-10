"""Testes dos dados de demonstracao do catalogo (seed da busca)."""

from __future__ import annotations

from app.infrastructure.db.seeds import (
    _ALL_PRODUCTS,
    _BRAND_IDS,
    _CATEGORY_IDS,
    _DEMO_PRODUCTS,
    _PRODUCTS,
    _build_demo_products,
)


def test_demo_tem_entre_40_e_60_produtos() -> None:
    assert 40 <= len(_DEMO_PRODUCTS) <= 60


def test_skus_e_slugs_sao_unicos() -> None:
    skus = [str(row["sku"]) for row in _ALL_PRODUCTS]
    slugs = [str(row["slug"]) for row in _ALL_PRODUCTS]
    assert len(skus) == len(set(skus))
    assert len(slugs) == len(set(slugs))


def test_ids_sao_deterministicos() -> None:
    first = _build_demo_products()
    second = _build_demo_products()
    assert [row["id"] for row in first] == [row["id"] for row in second]
    assert [row["slug"] for row in first] == [row["slug"] for row in second]


def test_ca_ficticio_e_ausente_em_nao_epi() -> None:
    for row in _DEMO_PRODUCTS:
        if row["is_epi"]:
            assert str(row["ca_number"]).startswith("DEMO-CA-")
        else:
            assert "ca_number" not in row
            assert "ca_valid_until" not in row


def test_inclui_inativos_e_indisponiveis() -> None:
    statuses = {str(row["status"]) for row in _DEMO_PRODUCTS}
    assert "INACTIVE" in statuses
    epi_com_data = [
        row for row in _DEMO_PRODUCTS if row["is_epi"] and row.get("ca_valid_until") is not None
    ]
    epi_sem_data = [row for row in _DEMO_PRODUCTS if row["is_epi"] and "ca_valid_until" not in row]
    assert epi_com_data and epi_sem_data


def test_categorias_e_marcas_resolvem() -> None:
    for row in _DEMO_PRODUCTS:
        assert str(row["category_id"]) in {str(value) for value in _CATEGORY_IDS.values()}
        assert str(row["brand_id"]) in {str(value) for value in _BRAND_IDS.values()}


def test_lista_final_inclui_a_base_original() -> None:
    assert len(_ALL_PRODUCTS) == len(_PRODUCTS) + len(_DEMO_PRODUCTS)
