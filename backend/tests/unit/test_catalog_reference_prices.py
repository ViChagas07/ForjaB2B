"""Testes dos precos de referencia do catalogo de demonstracao.

Valida o mapa publicado no seed (41 SKUs vendaveis), a aplicacao idempotente
sobre os dados do seed, a preservacao dos nove produtos bloqueados e o
alinhamento das faixas de preco ao preco base.
"""

from __future__ import annotations

from decimal import Decimal

from app.infrastructure.db.seeds import (
    _ALL_PRODUCTS,
    _ALL_TIERS,
    BLOCKED_CATALOG_SKUS,
    CATALOG_REFERENCE_PRICES,
    _apply_reference_prices,
)

_EXPECTED_REFERENCE_PRICES: dict[str, Decimal] = {
    "AUD-001": Decimal("4.90"),
    "AUD-002": Decimal("39.90"),
    "AUD-003": Decimal("79.90"),
    "AUD-004": Decimal("2.90"),
    "CAP-002": Decimal("29.90"),
    "CAP-003": Decimal("59.90"),
    "CAP-004": Decimal("119.90"),
    "QUE-001": Decimal("189.90"),
    "QUE-003": Decimal("89.90"),
    "QUE-004": Decimal("149.90"),
    "LUV-003": Decimal("19.90"),
    "LUV-004": Decimal("29.90"),
    "LUV-005": Decimal("3.90"),
    "LUV-006": Decimal("34.90"),
    "LUV-007": Decimal("49.90"),
    "BOT-001": Decimal("89.90"),
    "BOT-002": Decimal("149.90"),
    "BOT-003": Decimal("69.90"),
    "BOT-005": Decimal("99.90"),
    "RES-004": Decimal("2.90"),
    "RES-005": Decimal("5.90"),
    "RES-006": Decimal("79.90"),
    "RES-007": Decimal("2.50"),
    "OCV-001": Decimal("7.90"),
    "OCV-002": Decimal("9.90"),
    "OCV-003": Decimal("24.90"),
    "OCV-004": Decimal("19.90"),
    "OCV-005": Decimal("14.90"),
    "EPI-CAP-001": Decimal("39.90"),
    "EPI-LUV-002": Decimal("29.90"),
    "FUR-001": Decimal("249.90"),
    "FUR-002": Decimal("599.90"),
    "FUR-003": Decimal("199.90"),
    "FUR-004": Decimal("399.90"),
    "FUR-005": Decimal("229.90"),
    "MAQ-PAR-004": Decimal("499.90"),
    "MAQ-005": Decimal("2499.90"),
    "MAQ-006": Decimal("3499.90"),
    "MAQ-007": Decimal("899.90"),
    "MAQ-008": Decimal("1499.90"),
    "MAQ-009": Decimal("349.90"),
}


def _products_by_sku() -> dict[str, dict[str, object]]:
    return {str(product["sku"]): product for product in _ALL_PRODUCTS}


def test_mapa_de_referencia_tem_exatamente_41_precos_positivos() -> None:
    assert CATALOG_REFERENCE_PRICES == _EXPECTED_REFERENCE_PRICES
    assert len(CATALOG_REFERENCE_PRICES) == 41
    for price in CATALOG_REFERENCE_PRICES.values():
        assert price > 0
        assert price == price.quantize(Decimal("0.01"))


def test_seed_aplica_os_precos_de_referencia_por_sku() -> None:
    products = _products_by_sku()
    assert len(products) == 50
    for sku, expected in CATALOG_REFERENCE_PRICES.items():
        assert sku in products
        assert products[sku]["base_unit_price"] == expected


def test_produtos_bloqueados_ficam_fora_do_mapa_e_preservados() -> None:
    assert len(BLOCKED_CATALOG_SKUS) == 9
    assert BLOCKED_CATALOG_SKUS.isdisjoint(CATALOG_REFERENCE_PRICES)
    products = _products_by_sku()
    assert set(products) >= BLOCKED_CATALOG_SKUS
    blocked_prices = {sku: products[sku]["base_unit_price"] for sku in BLOCKED_CATALOG_SKUS}
    _apply_reference_prices()
    assert {sku: products[sku]["base_unit_price"] for sku in BLOCKED_CATALOG_SKUS} == blocked_prices


def test_reaplicacao_dos_precos_e_idempotente() -> None:
    products_before = {str(p["sku"]): p["base_unit_price"] for p in _ALL_PRODUCTS}
    tiers_before = {str(t["id"]): t["unit_price"] for t in _ALL_TIERS}
    _apply_reference_prices()
    assert {str(p["sku"]): p["base_unit_price"] for p in _ALL_PRODUCTS} == products_before
    assert {str(t["id"]): t["unit_price"] for t in _ALL_TIERS} == tiers_before


def test_tiers_dos_skus_precificados_usam_o_preco_base() -> None:
    products_by_id = {p["id"]: p for p in _ALL_PRODUCTS}
    checked = 0
    for tier in _ALL_TIERS:
        product = products_by_id[tier["product_id"]]
        sku = str(product["sku"])
        expected = CATALOG_REFERENCE_PRICES.get(sku)
        if expected is not None:
            assert tier["unit_price"] == expected, f"{sku}: tier divergente"
            checked += 1
    assert checked == 14
