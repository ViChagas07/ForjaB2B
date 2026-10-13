"""Testes da busca multilíngue (Fase 9B-b): mapping, documento e consulta."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.modules.search.application.documents import (
    SEARCH_TRANSLATION_LOCALES,
    build_product_document,
    is_row_sellable,
)
from app.modules.search.application.ports import ProductRow
from app.modules.search.infrastructure.index_files import load_index_mappings, load_index_settings


def _base_row(**overrides: object) -> ProductRow:
    defaults = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000301"),
        "sku": "CAP-002",
        "name": "Capacete de Segurança Classe A",
        "description": "Capacete de segurança classe A com suspensão ajustável",
        "slug": "capacete-de-seguranca-classe-a",
        "status": "ACTIVE",
        "is_epi": True,
        "ca_number": "DEMO-CA-0001",
        "ca_valid_until": date(2029, 12, 31),
        "category_id": uuid.UUID("00000000-0000-0000-0000-000000000401"),
        "category_name": "Proteção da Cabeça",
        "category_slug": "protecao-cabeca",
        "brand_id": uuid.UUID("00000000-0000-0000-0000-000000000501"),
        "brand_name": "PROTEC",
        "brand_slug": "protec",
        "attributes": {"cor": "branco", "material": "ABS"},
        "image_url": None,
        "base_unit_price": Decimal("99.90"),
        "currency": "BRL",
        "min_order_qty": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
        "translations": {},
    }
    defaults.update(overrides)
    return ProductRow(**defaults)


def test_mapping_tem_campos_por_idioma_com_analisadores_nativos() -> None:
    """Mapping inclui name/description/attributes_text para en, es, ar
    com analisadores corretos."""
    mappings = load_index_mappings()
    props = mappings["properties"]

    # Campos base (pt-BR)
    assert "name" in props
    assert props["name"]["analyzer"] == "pt_text"
    assert "description" in props
    assert props["description"]["analyzer"] == "pt_text"

    # Inglês
    for field in ("name_en", "description_en", "attributes_text_en"):
        assert field in props, f"campo {field} ausente no mapping"
        assert props[field]["analyzer"] == "en_text", f"{field} deve usar en_text"

    # Espanhol (com normalização de acentos via ascii_folding no analisador)
    for field in ("name_es", "description_es", "attributes_text_es"):
        assert field in props, f"campo {field} ausente no mapping"
        assert props[field]["analyzer"] == "es_text", f"{field} deve usar es_text"

    # Árabe
    for field in ("name_ar", "description_ar", "attributes_text_ar"):
        assert field in props, f"campo {field} ausente no mapping"
        assert props[field]["analyzer"] == "ar_text", f"{field} deve usar ar_text"


def test_settings_analisadores_por_idioma() -> None:
    """Settings definem analisadores nativos para cada idioma suportado."""
    settings = load_index_settings()
    analyzers = settings["analysis"]["analyzer"]

    assert "pt_text" in analyzers
    assert "en_text" in analyzers
    assert "es_text" in analyzers
    assert "ar_text" in analyzers

    # Espanhol inclui ascii_folding para normalização de acentos
    es_filters = analyzers["es_text"]["filter"]
    assert "ascii_folding" in es_filters, "es_text deve ter ascii_folding"

    # Árabe usa arabic_normalization
    ar_filters = analyzers["ar_text"]["filter"]
    assert "arabic_normalization" in ar_filters, "ar_text deve ter arabic_normalization"


def test_documento_inclui_campos_traduzidos_quando_existem() -> None:
    """Documento indexado contém name/description/attributes_text para
    en, es, ar quando há tradução."""
    from app.application.i18n import ProductTextTranslation

    row = _base_row(
        translations={
            "en": ProductTextTranslation(
                name="Safety Helmet Class A",
                description="Class A safety helmet with adjustable suspension",
                attributes={"color": "white", "material": "ABS"},
            ),
            "es": ProductTextTranslation(
                name="Casco de Seguridad Clase A",
                description="Casco de seguridad clase A con suspensión ajustable",
                attributes={"color": "blanco", "material": "ABS"},
            ),
            "ar": ProductTextTranslation(
                name="خوذة أمان الفئة أ",
                description="خوذة أمان من الفئة أ مع تعليق قابل للتعديل",
                attributes={"color": "أبيض", "material": "ABS"},
            ),
        }
    )

    doc = build_product_document(row, today=date(2026, 6, 1))
    source = doc.to_source()

    # pt-BR (origem)
    assert source["name"] == "Capacete de Segurança Classe A"
    assert source["description"] == "Capacete de segurança classe A com suspensão ajustável"

    # en
    assert source["name_en"] == "Safety Helmet Class A"
    assert source["description_en"] == "Class A safety helmet with adjustable suspension"
    assert source["attributes_text_en"] == "white ABS"

    # es
    assert source["name_es"] == "Casco de Seguridad Clase A"
    assert source["description_es"] == "Casco de seguridad clase A con suspensión ajustable"
    assert source["attributes_text_es"] == "blanco ABS"

    # ar
    assert source["name_ar"] == "خوذة أمان الفئة أ"
    assert source["description_ar"] == "خوذة أمان من الفئة أ مع تعليق قابل للتعديل"
    assert source["attributes_text_ar"] == "أبيض ABS"


def test_documento_sem_traducao_nao_quebra_indexacao() -> None:
    """Produto sem tradução para algum/qualquer idioma indexa sem erro
    (campos nulos)."""
    row = _base_row(translations={})  # sem traduções

    doc = build_product_document(row, today=date(2026, 6, 1))
    source = doc.to_source()

    # Campos de tradução são None (não quebram o mapping dynamic:strict
    # porque são explícitos)
    for locale in SEARCH_TRANSLATION_LOCALES:
        assert source[f"name_{locale}"] is None
        assert source[f"description_{locale}"] is None
        assert source[f"attributes_text_{locale}"] is None

    # Campos base (pt-BR) continuam presentes
    assert source["name"] == "Capacete de Segurança Classe A"
    assert source["description"] == "Capacete de segurança classe A com suspensão ajustável"


def test_documento_traducao_parcial_apenas_idiomas_existentes() -> None:
    """Produto com tradução apenas para alguns idiomas indexa apenas
    esses."""
    from app.application.i18n import ProductTextTranslation

    row = _base_row(
        translations={
            "en": ProductTextTranslation(
                name="Safety Helmet",
                description="A safety helmet",
                attributes={},
            ),
            # es e ar ausentes
        }
    )

    doc = build_product_document(row, today=date(2026, 6, 1))
    source = doc.to_source()

    assert source["name_en"] == "Safety Helmet"
    assert source["description_en"] == "A safety helmet"
    assert source["attributes_text_en"] is None  # empty attributes -> None

    assert source["name_es"] is None
    assert source["description_es"] is None
    assert source["attributes_text_es"] is None

    assert source["name_ar"] is None
    assert source["description_ar"] is None
    assert source["attributes_text_ar"] is None


def test_documento_nao_contem_preco_nem_dados_sensiveis() -> None:
    """Documento indexado nunca contém preço, estoque, dados de cliente
    ou pagamento."""
    row = _base_row()
    doc = build_product_document(row, today=date(2026, 6, 1))
    source = doc.to_source()

    forbidden_keywords = (
        "price",
        "preco",
        "stock",
        "estoque",
        "credit",
        "credito",
        "cpf",
        "cnpj",
        "password",
        "senha",
    )
    source_str = " ".join(str(v) for v in source.values()).lower()
    for kw in forbidden_keywords:
        assert kw not in source_str, f"campo sensível '{kw}' encontrado no documento"


def test_disponibilidade_derivada_no_momento_da_indexacao() -> None:
    """is_available reflete status ACTIVE + CA válido (para EPI); não
    armazenado no banco."""
    today = date(2026, 6, 1)

    # EPI com CA válido (futuro) -> disponível
    row_ok = _base_row(ca_valid_until=date(2029, 12, 31))
    assert is_row_sellable(row_ok, today=today) is True
    assert build_product_document(row_ok, today=today).is_available is True

    # EPI com CA vencido (passado) -> não disponível
    row_ca_vencido = _base_row(ca_valid_until=date(2020, 1, 1))
    assert is_row_sellable(row_ca_vencido, today=today) is False
    assert build_product_document(row_ca_vencido, today=today).is_available is False

    # EPI sem CA -> não disponível
    row_sem_ca = _base_row(ca_valid_until=None)
    assert is_row_sellable(row_sem_ca, today=today) is False
    assert build_product_document(row_sem_ca, today=today).is_available is False

    # Não-EPI sem CA -> disponível (se ACTIVE)
    row_nao_epi = _base_row(is_epi=False, ca_valid_until=None)
    assert is_row_sellable(row_nao_epi, today=today) is True
    assert build_product_document(row_nao_epi, today=today).is_available is True

    # INACTIVE -> não disponível
    row_inactive = _base_row(status="INACTIVE")
    assert is_row_sellable(row_inactive, today=today) is False
    assert build_product_document(row_inactive, today=today).is_available is False


def test_versao_deriva_de_updated_at_epoch_ms() -> None:
    """Versão do documento = epoch ms de updated_at (concorrência
    otimista)."""
    updated_at = datetime(2026, 5, 15, 10, 30, 45, tzinfo=UTC)
    expected = int(updated_at.timestamp() * 1000)
    row = _base_row(updated_at=updated_at)

    assert row.version == expected
    assert build_product_document(row, today=date(2026, 6, 1)).version == expected
