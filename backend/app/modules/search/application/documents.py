"""Construcao do documento indexavel de produto (puro, sem frameworks).

O documento NAO inclui preco (individualizado/consultivo) nem dados pessoais
ou de pagamento. Somente campos publicos do catalogo. A disponibilidade e
derivada no momento da indexacao (``is_sellable``), nunca armazenada no banco.
"""

from __future__ import annotations

from datetime import date

from app.domain.product_availability import is_sellable
from app.modules.search.application.ports import ProductDocument, ProductRow

# Idiomas com campos proprios no indice (o idioma de origem pt-BR usa name/description).
SEARCH_TRANSLATION_LOCALES: tuple[str, ...] = ("en", "es", "ar")


def _attributes_text(attributes: dict[str, object] | None) -> str | None:
    """Concatena os valores de texto dos atributos (para busca). Sem preco."""
    if not attributes:
        return None
    parts = [
        str(value) for value in attributes.values() if isinstance(value, str) and value.strip()
    ]
    return " ".join(parts) if parts else None


def _translated_name(row: ProductRow, locale: str) -> str | None:
    translation = row.translations.get(locale)
    return translation.name if translation else None


def _translated_description(row: ProductRow, locale: str) -> str | None:
    translation = row.translations.get(locale)
    return translation.description if translation else None


def _translated_attributes_text(row: ProductRow, locale: str) -> str | None:
    translation = row.translations.get(locale)
    return _attributes_text(translation.attributes) if translation else None


def is_row_sellable(row: ProductRow, *, today: date) -> bool:
    """Produto vendavel (status ACTIVE + CA de EPI valido) => deve estar no indice."""
    return is_sellable(
        status=row.status, is_epi=row.is_epi, ca_valid_until=row.ca_valid_until, today=today
    )


def build_product_document(row: ProductRow, *, today: date) -> ProductDocument:
    """Monta o documento indexavel a partir da linha do catalogo."""
    return ProductDocument(
        id=str(row.id),
        sku=row.sku,
        name=row.name,
        description=row.description,
        slug=row.slug,
        status=row.status,
        is_epi=row.is_epi,
        is_available=is_row_sellable(row, today=today),
        ca_number=row.ca_number,
        ca_valid_until=row.ca_valid_until.isoformat() if row.ca_valid_until is not None else None,
        category_id=str(row.category_id),
        category=row.category_name,
        category_slug=row.category_slug,
        brand_id=str(row.brand_id) if row.brand_id is not None else None,
        brand=row.brand_name,
        brand_slug=row.brand_slug,
        attributes=row.attributes or {},
        name_en=_translated_name(row, "en"),
        name_es=_translated_name(row, "es"),
        name_ar=_translated_name(row, "ar"),
        description_en=_translated_description(row, "en"),
        description_es=_translated_description(row, "es"),
        description_ar=_translated_description(row, "ar"),
        attributes_text_en=_translated_attributes_text(row, "en"),
        attributes_text_es=_translated_attributes_text(row, "es"),
        attributes_text_ar=_translated_attributes_text(row, "ar"),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        version=row.version,
    )
