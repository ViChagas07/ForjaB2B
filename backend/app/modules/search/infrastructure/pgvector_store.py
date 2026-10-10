"""Armazenamento vetorial em pgvector (Fase 5).

SQL parametrizado sobre ``product_embeddings`` (global, sem RLS). A ordenacao
usa a distancia de cosseno (``<=>``) e a busca restringe-se a produtos vendaveis,
aplicando os mesmos filtros da busca lexical. Nenhum preco passa por aqui.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.ports import EmbeddingEntry, SearchQuery, VectorHit

_UPSERT = text(
    "INSERT INTO product_embeddings "
    "(product_id, model, dimension, embedding, content_hash, updated_at) "
    "VALUES (:product_id, :model, :dimension, CAST(:embedding AS vector), "
    ":content_hash, now()) "
    "ON CONFLICT (product_id) DO UPDATE SET "
    "model = EXCLUDED.model, dimension = EXCLUDED.dimension, "
    "embedding = EXCLUDED.embedding, content_hash = EXCLUDED.content_hash, "
    "updated_at = now()"
)

_SELECT_HASHES = text("SELECT product_id, content_hash FROM product_embeddings")

_SELECT_HASH = text(
    "SELECT content_hash FROM product_embeddings WHERE product_id = CAST(:product_id AS uuid)"
)

_DELETE = text(
    "DELETE FROM product_embeddings WHERE product_id = ANY(CAST(:product_ids AS uuid[]))"
)

_SEARCH_SIMILAR = text(
    "SELECT e.product_id, 1 - (e.embedding <=> CAST(:embedding AS vector)) AS score "
    "FROM product_embeddings AS e "
    "JOIN products AS p ON p.id = e.product_id "
    "WHERE p.status = 'ACTIVE' "
    "  AND (p.is_epi = false OR (p.ca_valid_until IS NOT NULL "
    "       AND p.ca_valid_until >= CURRENT_DATE)) "
    "  AND (CAST(:category_id AS uuid) IS NULL "
    "       OR p.category_id = CAST(:category_id AS uuid)) "
    "  AND (CAST(:brand_id AS uuid) IS NULL OR p.brand_id = CAST(:brand_id AS uuid)) "
    "  AND (CAST(:is_epi AS boolean) IS NULL OR p.is_epi = CAST(:is_epi AS boolean)) "
    "ORDER BY e.embedding <=> CAST(:embedding AS vector) "
    "LIMIT CAST(:limit AS integer)"
)


def to_vector_literal(values: Sequence[float]) -> str:
    """Formata um vetor como literal aceito pelo pgvector."""
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"


class PgVectorStore:
    """Implementacao da porta VectorStore sobre pgvector."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def upsert_many(self, entries: Sequence[EmbeddingEntry]) -> int:
        if not entries:
            return 0
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(
                _UPSERT,
                [
                    {
                        "product_id": str(entry.product_id),
                        "model": entry.model,
                        "dimension": entry.dimension,
                        "embedding": to_vector_literal(entry.embedding),
                        "content_hash": entry.content_hash,
                    }
                    for entry in entries
                ],
            )
            await uow.commit()
        return len(entries)

    async def get_hashes(self) -> dict[uuid.UUID, str]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_SELECT_HASHES)).all()
            await uow.commit()
        return {row[0]: str(row[1]) for row in rows}

    async def get_hash(self, product_id: uuid.UUID) -> str | None:
        async with self._uow_factory.begin() as uow:
            row = (await uow.session.execute(_SELECT_HASH, {"product_id": str(product_id)})).first()
            await uow.commit()
        return None if row is None else str(row[0])

    async def search_similar(
        self, *, embedding: Sequence[float], filters: SearchQuery, limit: int
    ) -> list[VectorHit]:
        params: dict[str, Any] = {
            "embedding": to_vector_literal(embedding),
            "category_id": str(filters.category_id) if filters.category_id is not None else None,
            "brand_id": str(filters.brand_id) if filters.brand_id is not None else None,
            "is_epi": filters.is_epi,
            "limit": limit,
        }
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_SEARCH_SIMILAR, params)).all()
            await uow.commit()
        return [VectorHit(product_id=row[0], score=float(row[1])) for row in rows]

    async def delete(self, product_ids: Sequence[uuid.UUID]) -> int:
        if not product_ids:
            return 0
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(_DELETE, {"product_ids": [str(pid) for pid in product_ids]})
            await uow.commit()
        return len(product_ids)
