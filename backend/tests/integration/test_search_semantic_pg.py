"""Integracao da busca semantica com pgvector real (Testcontainers).

Requer a imagem `pgvector/pgvector` (migration 0013) e o daemon Docker. Usa um
provedor de embeddings FAKE deterministico: o objetivo e validar o armazenamento,
a ordenacao por cosseno, a idempotencia e o backfill no PostgreSQL real, sem
depender do modelo (cujo teste real fica fora da execucao padrao).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Sequence

import pytest

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.embeddings_backfill import BackfillEmbeddings
from app.modules.search.application.ports import EmbeddingEntry, SearchQuery
from app.modules.search.infrastructure.pgvector_store import PgVectorStore
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader

from .conftest import PostgresInstance
from .test_catalog_api import _P_EPI_VALIDO, _P_INATIVO, _P_NAO_EPI, _seed_catalog

_DIM = 384
_NEAR = [1.0] * _DIM
_FAR = [-1.0] * _DIM


class _FakeProvider:
    @property
    def model(self) -> str:
        return "test-model"

    @property
    def dimension(self) -> int:
        return _DIM

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [_NEAR for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return _NEAR


@pytest.fixture()
def semantic_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed_catalog(pg, migrated_domain_schema)
    conn = pg.connect_admin()
    try:
        conn.execute("DELETE FROM product_embeddings")
    finally:
        conn.close()


def _entry(product_id: uuid.UUID, vector: list[float], *, digest: str) -> EmbeddingEntry:
    return EmbeddingEntry(
        product_id=product_id,
        model="test-model",
        dimension=_DIM,
        embedding=vector,
        content_hash=digest,
    )


def _filters() -> SearchQuery:
    return SearchQuery(q="x", category_id=None, brand_id=None, is_epi=None, page=1, page_size=10)


async def test_pgvector_ordena_por_cosseno_e_exclui_nao_vendaveis(
    uow_factory: SqlAlchemyUnitOfWorkFactory, semantic_seed: None
) -> None:
    store = PgVectorStore(uow_factory)
    await store.upsert_many(
        [
            _entry(_P_EPI_VALIDO, _NEAR, digest="a"),
            _entry(_P_NAO_EPI, _FAR, digest="b"),
            _entry(_P_INATIVO, _NEAR, digest="c"),
        ]
    )
    hits = await store.search_similar(embedding=_NEAR, filters=_filters(), limit=10)
    ids = [hit.product_id for hit in hits]
    assert ids[0] == _P_EPI_VALIDO
    assert _P_INATIVO not in ids
    assert _P_NAO_EPI in ids


async def test_upsert_e_idempotente(
    uow_factory: SqlAlchemyUnitOfWorkFactory, semantic_seed: None
) -> None:
    store = PgVectorStore(uow_factory)
    await store.upsert_many([_entry(_P_EPI_VALIDO, _NEAR, digest="v1")])
    await store.upsert_many([_entry(_P_EPI_VALIDO, _NEAR, digest="v2")])
    assert await store.get_hash(_P_EPI_VALIDO) == "v2"


async def test_delete_remove_vetor(
    uow_factory: SqlAlchemyUnitOfWorkFactory, semantic_seed: None
) -> None:
    store = PgVectorStore(uow_factory)
    await store.upsert_many([_entry(_P_NAO_EPI, _NEAR, digest="x")])
    assert await store.get_hash(_P_NAO_EPI) == "x"
    await store.delete([_P_NAO_EPI])
    assert await store.get_hash(_P_NAO_EPI) is None


async def test_backfill_vetorial_idempotente_no_postgres(
    uow_factory: SqlAlchemyUnitOfWorkFactory, semantic_seed: None
) -> None:
    store = PgVectorStore(uow_factory)
    reader = SqlAlchemyProductReader(uow_factory)
    await store.upsert_many([_entry(_P_INATIVO, _NEAR, digest="orfa")])
    use_case = BackfillEmbeddings(
        provider=_FakeProvider(), store=store, reader=reader, batch_size=2
    )
    first = await use_case.run()
    assert first.embedded >= 2
    assert first.removed >= 1  # vetor do produto inativo e removido
    assert await store.get_hash(_P_EPI_VALIDO) is not None
    assert await store.get_hash(_P_INATIVO) is None
    second = await use_case.run()
    assert second.embedded == 0  # reexecucao nao duplica nem recalcula


@pytest.mark.skipif(
    os.environ.get("RUN_EMBEDDING_MODEL_TESTS") != "1",
    reason="teste lento com o modelo ONNX real; fora da execucao padrao",
)
def test_modelo_real_disponivel_para_embeddings() -> None:
    from app.core.config import Settings
    from app.modules.search.infrastructure.embeddings import build_embedding_provider

    provider = build_embedding_provider(Settings(embeddings_enabled=True, embedding_dimension=384))
    assert provider is not None
