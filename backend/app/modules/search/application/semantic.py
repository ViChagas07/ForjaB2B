"""Busca semantica: embedding da consulta + top-N no pgvector (Fase 5)."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.modules.search.application.errors import EmbeddingUnavailableError
from app.modules.search.application.ports import EmbeddingProvider, SearchQuery, VectorStore

_logger = get_logger(__name__)


class SemanticSearch:
    """Gera o vetor da consulta e busca os vizinhos mais proximos (cosseno)."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        store: VectorStore,
        candidate_limit: int,
        timeout_seconds: float,
    ) -> None:
        self._provider = provider
        self._store = store
        self._candidate_limit = candidate_limit
        self._timeout_seconds = timeout_seconds

    async def search_ids(self, *, query: SearchQuery) -> list[str]:
        """Ids ordenados por similaridade; lista vazia quando nao ha texto."""
        text = (query.q or "").strip()
        if not text:
            return []
        try:
            embedding = await asyncio.wait_for(
                self._provider.embed_query(text), timeout=self._timeout_seconds
            )
        except TimeoutError as exc:
            raise EmbeddingUnavailableError("embedding query timeout") from exc
        except EmbeddingUnavailableError:
            raise
        except Exception as exc:
            _logger.warning("embedding_query_failed", error=type(exc).__name__)
            raise EmbeddingUnavailableError(f"embedding failed: {type(exc).__name__}") from exc
        hits = await self._store.search_similar(
            embedding=embedding, filters=query, limit=self._candidate_limit
        )
        return [str(hit.product_id) for hit in hits]
