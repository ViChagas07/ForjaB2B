"""Leitura compartilhada das traducoes de produto (tabela global).

Usada pelo catalogo, pela busca, pelo carrinho e pelo admin. A tabela e global
(sem RLS), entao a leitura ocorre em qualquer UoW. Somente leitura no caminho do
cliente: a traducao NUNCA e gerada em tempo de requisicao.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, kw_only=True)
class TranslationRow:
    """Traducao armazenada de um produto em um idioma."""

    product_id: uuid.UUID
    locale: str
    name: str | None
    description: str | None
    attributes: dict[str, object] | None
    status: str
    source_hash: str


_LOAD = text(
    "SELECT product_id, locale, name, description, attributes, status, source_hash "
    "FROM product_translations "
    "WHERE product_id = ANY(CAST(:product_ids AS uuid[])) "
    "  AND locale = ANY(CAST(:locales AS varchar[]))"
)


async def load_product_translations(
    session: AsyncSession,
    *,
    product_ids: Sequence[uuid.UUID],
    locales: Sequence[str],
) -> dict[tuple[uuid.UUID, str], TranslationRow]:
    """Mapa ``(product_id, locale) -> TranslationRow`` (vazio sem dados)."""
    if not product_ids or not locales:
        return {}
    rows = (
        await session.execute(
            _LOAD,
            {
                "product_ids": [str(pid) for pid in product_ids],
                "locales": list(locales),
            },
        )
    ).all()
    return {
        (row.product_id, row.locale): TranslationRow(
            product_id=row.product_id,
            locale=row.locale,
            name=row.name,
            description=row.description,
            attributes=row.attributes,
            status=row.status,
            source_hash=row.source_hash,
        )
        for row in rows
    }
