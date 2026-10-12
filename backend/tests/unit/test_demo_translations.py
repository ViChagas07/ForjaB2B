"""Testes da traducao offline do catalogo de demonstracao (sem banco).

Validam, sobre o arquivo versionado ``seed_data/demo_translations.json``, as
regras da Fase 9B: preservacao EXATA de numeros/unidades/codigos (medidas como
20V/850W/100L/7 1/4) e que marcas/SKU/CA nao aparecem como se tivessem sido
traduzidos.
"""

from __future__ import annotations

import json
import re

import pytest

from app.infrastructure.db.seeds import _ALL_PRODUCTS, _DEMO_TRANSLATIONS

# Captura numeros, fracoes mistas e unidades anexas (ex.: 20V, 850W, 100L, 7 1/4,
# 15T, 2cv, 100l). Case-sensitive: 100L (nome) e 100l (atributo) sao tokens
# distintos, como exige "preserve exatamente como na origem".
_NUMERIC_UNIT_RE = re.compile(r"\d+(?:\s*\d+/\d+)?(?:[A-Za-zª°]+)?")


def _tokens(text: str | None) -> set[str]:
    return set(_NUMERIC_UNIT_RE.findall(text or ""))


def _product_tokens(product: dict[str, object]) -> set[str]:
    """Tokens de numeros/unidades da origem pt-BR (nome + descricao + atributos)."""
    tokens = _tokens(str(product["name"]))
    tokens |= _tokens(product.get("description"))
    attrs = product.get("attributes")
    if attrs:
        tokens |= _tokens(" ".join(f"{k}={v}" for k, v in json.loads(attrs).items()))
    return tokens


@pytest.mark.parametrize(
    "locale",
    ["en", "es", "ar"],
    ids=["english", "spanish", "arabic"],
)
def test_todas_as_traducoes_estao_presentes(locale: str) -> None:
    by_sku = {p["sku"]: p for p in _ALL_PRODUCTS}
    products = _DEMO_TRANSLATIONS["products"]
    assert len(products) == len(by_sku) == 50
    for sku, product in by_sku.items():
        entry = products[sku][locale]
        assert isinstance(entry["name"], str) and entry["name"], f"nome vazio {sku}/{locale}"
        # Produtos base sem descricao original ficam nulos; o restante tem descricao.
        if product.get("description") is None:
            assert entry["description"] is None, f"descricao inesperada {sku}/{locale}"
        else:
            assert isinstance(entry["description"], str) and entry["description"], (
                f"descricao vazia {sku}/{locale}"
            )


@pytest.mark.parametrize("locale", ["en", "es", "ar"])
def test_preservacao_de_numeros_unidades_e_codigos(locale: str) -> None:
    by_sku = {p["sku"]: p for p in _ALL_PRODUCTS}
    for sku, product in by_sku.items():
        source_tokens = _product_tokens(product)
        entry = _DEMO_TRANSLATIONS["products"][sku][locale]
        translation_text = entry["name"]
        if entry.get("description") is not None:
            translation_text += " " + entry["description"]
        if entry.get("attributes"):
            translation_text += " " + " ".join(f"{k}={v}" for k, v in entry["attributes"].items())
        translation_tokens = _tokens(translation_text)
        assert source_tokens == translation_tokens, (
            f"numeros/unidades divergem para {sku}/{locale}: "
            f"origem={source_tokens} traducao={translation_tokens}"
        )


def test_traducoes_nao_incluem_sku_como_texto() -> None:
    """SKUs sao codigos: nao aparecem traduzidos nos textos de produto."""
    for sku, entry in _DEMO_TRANSLATIONS["products"].items():
        for locale, t in entry.items():
            assert sku not in t["name"], f"SKU {sku} vazado no nome {locale}"
            desc = t.get("description") or ""
            assert sku not in desc, f"SKU {sku} vazado na descricao {locale}"


def test_descricao_demo_segue_formato_da_origem() -> None:
    """Demo: 'nome (item de demonstracao)' -> 'nome (demo item)' por locale."""
    suffixes = {
        "en": "(demo item).",
        "es": "(artículo de demostración).",
        "ar": "(عنصر تجريبي).",
    }
    by_sku = {p["sku"]: p for p in _ALL_PRODUCTS}
    for sku, product in by_sku.items():
        desc = product.get("description")
        if desc is None or not desc.endswith("(item de demonstracao)."):
            continue  # base com descricao propria ou sem descricao
        entry = _DEMO_TRANSLATIONS["products"][sku]
        for locale, t in entry.items():
            name = t["name"]
            assert t["description"] == f"{name} {suffixes[locale]}", (
                f"formato de descricao invalido {sku}/{locale}"
            )


def test_arquivo_de_traducoes_usa_codificacao_utf8() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "seed_data" / "demo_translations.json"
    # Mesmo caminho usado por seeds.py: garante o arquivo versionado existe e e
    # parseavel, com as locales esperadas.
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["locales"] == ["en", "es", "ar"]
