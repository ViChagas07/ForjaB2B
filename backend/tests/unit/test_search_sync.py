"""Testes dos casos de uso de sincronizacao (fakes em memoria, sem Docker)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from app.domain.pricing import CompanyPriceRule
from app.modules.search.application.documents import build_product_document, is_row_sellable
from app.modules.search.application.errors import SearchIndexError, SearchUnavailableError
from app.modules.search.application.ports import (
    IndexBulkResult,
    ProductDocument,
    ProductRow,
    SearchEventType,
    SearchOutboxEvent,
)
from app.modules.search.application.sync import (
    DispatchSearchOutbox,
    ReconcileSearchIndex,
    ReindexProducts,
)
from app.modules.search.infrastructure import elasticsearch as es_mod

_TODAY = date.today()
_V1 = datetime(2026, 1, 1, tzinfo=UTC)
_V2 = datetime(2026, 2, 1, tzinfo=UTC)


def _row(
    *,
    key: str,
    status: str = "ACTIVE",
    updated_at: datetime = _V1,
) -> ProductRow:
    return ProductRow(
        id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        sku=key,
        name=f"Produto {key}",
        description=None,
        slug=key.lower(),
        status=status,
        is_epi=False,
        ca_number=None,
        ca_valid_until=None,
        category_id=uuid.uuid5(uuid.NAMESPACE_URL, "cat"),
        category_name="Categoria",
        category_slug="categoria",
        brand_id=None,
        brand_name=None,
        brand_slug=None,
        attributes=None,
        base_unit_price=Decimal("10.00"),
        currency="BRL",
        min_order_qty=1,
        created_at=updated_at,
        updated_at=updated_at,
    )


class _FakeIndex:
    """Indice em memoria com semantica de versao externa (maior vence)."""

    def __init__(self, alias: str = "forja_products") -> None:
        self._alias = alias
        self.docs: dict[str, dict[str, tuple[int, dict[str, object]]]] = {}
        self.created: list[str] = []
        self.swapped: list[str] = []

    @property
    def alias(self) -> str:
        return self._alias

    async def create_versioned_index(self, *, version: int, replicas: int) -> str:
        name = f"{self._alias}_v{version}"
        self.created.append(name)
        self.docs.setdefault(name, {})
        return name

    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        bucket = self.docs.setdefault(target, {})
        indexed = 0
        for document in documents:
            current = bucket.get(document.id)
            if current is not None and current[0] >= document.version:
                continue
            bucket[document.id] = (document.version, document.to_source())
            indexed += 1
        return IndexBulkResult(indexed=indexed)

    async def delete_documents(self, *, target: str, ids: Sequence[str]) -> IndexBulkResult:
        bucket = self.docs.setdefault(target, {})
        deleted = 0
        for doc_id in ids:
            if bucket.pop(doc_id, None) is not None:
                deleted += 1
        return IndexBulkResult(deleted=deleted)

    async def fetch_versions(self, *, target: str) -> dict[str, int]:
        return {doc_id: version for doc_id, (version, _src) in self.docs.get(target, {}).items()}

    async def count(self, *, target: str) -> int:
        return len(self.docs.get(target, {}))

    async def refresh(self, *, target: str) -> None:
        return None

    async def swap_alias(self, *, index_name: str) -> None:
        self.swapped.append(index_name)


class _FailingIndex(_FakeIndex):
    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        raise SearchUnavailableError("elasticsearch down")


class _RejectingIndex(_FakeIndex):
    """Rejeita documentos (como o mapping faria) e reporta o motivo, sem indexar."""

    def __init__(self, *, reject: set[str]) -> None:
        super().__init__()
        self._reject = reject

    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        accepted = [doc for doc in documents if doc.id not in self._reject]
        result = await super().index_documents(target=target, documents=accepted)
        rejected = len(documents) - len(accepted)
        if rejected:
            return IndexBulkResult(
                indexed=result.indexed,
                errors=rejected,
                sample_errors=("index:document_parsing_exception",),
            )
        return result


class _DroppingIndex(_FakeIndex):
    """Omite documentos SEM reportar erro (divergencia de contagem)."""

    def __init__(self, *, drop: set[str]) -> None:
        super().__init__()
        self._drop = drop

    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        kept = [doc for doc in documents if doc.id not in self._drop]
        return await super().index_documents(target=target, documents=kept)


class _FakeReader:
    def __init__(self, rows: list[ProductRow]) -> None:
        self._rows = rows

    def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        async def _gen() -> AsyncIterator[list[ProductRow]]:
            for start in range(0, len(self._rows), batch_size):
                yield self._rows[start : start + batch_size]

        return _gen()

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        return next((row for row in self._rows if row.id == product_id), None)

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        return {row.id: row for row in self._rows if row.id in product_ids}

    async def get_company_price_rules(
        self, *, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        return {}


class _FakeOutbox:
    def __init__(self, events: list[SearchOutboxEvent]) -> None:
        self.events = events
        self.processed: list[uuid.UUID] = []
        self.failed: list[tuple[uuid.UUID, str]] = []

    async def list_due(self, *, limit: int, max_attempts: int) -> list[SearchOutboxEvent]:
        return list(self.events[:limit])

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self.processed.append(event_id)

    async def mark_failed(self, event_id: uuid.UUID, *, error: str) -> None:
        self.failed.append((event_id, error))


def _event(
    row: ProductRow, event_type: SearchEventType = SearchEventType.UPSERT
) -> SearchOutboxEvent:
    return SearchOutboxEvent(
        id=uuid.uuid4(),
        aggregate_id=row.id,
        event_type=event_type.value,
        version=row.version,
        attempts=0,
    )


async def test_reindex_indexa_so_vendaveis_e_troca_alias() -> None:
    rows = [_row(key="A"), _row(key="B"), _row(key="C", status="INACTIVE")]
    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader(rows), replicas=0).run(
        version=1, batch_size=2
    )
    assert report.expected == 2
    assert report.swapped is True
    assert report.index_name == "forja_products_v1"
    assert await index.count(target="forja_products_v1") == 2
    assert index.swapped == ["forja_products_v1"]


async def test_reindex_reexecutado_nao_duplica_e_remove_orfaos() -> None:
    rows = [_row(key="A"), _row(key="B")]
    index = _FakeIndex()
    index.docs["forja_products_v1"] = {"orfao": (1, {"version": 1})}
    use_case = ReindexProducts(index=index, reader=_FakeReader(rows), replicas=0)
    first = await use_case.run(version=1, batch_size=50)
    second = await use_case.run(version=1, batch_size=50)
    assert first.orphans_removed == 1
    assert second.expected == 2
    assert await index.count(target="forja_products_v1") == 2  # sem duplicatas


async def test_reindex_dry_run_nao_toca_no_indice() -> None:
    rows = [_row(key="A"), _row(key="B"), _row(key="C", status="INACTIVE")]
    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader(rows), replicas=0).run(
        version=1, batch_size=2, dry_run=True
    )
    assert report.dry_run is True
    assert report.expected == 2
    assert index.created == []
    assert index.swapped == []


async def test_reconcile_corrige_faltantes_e_orfaos() -> None:
    a = _row(key="A", updated_at=_V1)
    b = _row(key="B", updated_at=_V2)
    index = _FakeIndex()
    index.docs[index.alias] = {
        str(a.id): (a.version, {"version": a.version}),  # atualizado: nao muda
        str(b.id): (b.version - 1, {"version": b.version - 1}),  # desatualizado: reindexa
        "orfao": (1, {"version": 1}),  # nao existe no Postgres: remove
    }
    report = await ReconcileSearchIndex(
        index=index, reader=_FakeReader([a, b, _row(key="C", status="INACTIVE")]), batch_size=50
    ).run()
    assert report.upserted == 1
    assert report.deleted == 1
    assert "orfao" not in index.docs[index.alias]


async def test_dispatch_aplica_upsert_e_delete() -> None:
    a = _row(key="A")
    c = _row(key="C", status="INACTIVE")
    b = _row(key="B")
    outbox = _FakeOutbox([_event(a), _event(c), _event(b, SearchEventType.DELETE)])
    index = _FakeIndex()
    report = await DispatchSearchOutbox(
        index=index, reader=_FakeReader([a, b, c]), outbox=outbox, max_attempts=5
    ).run()
    assert report.processed == 3
    assert report.failed == 0
    assert await index.count(target=index.alias) == 1  # apenas A (vendavel)
    assert len(outbox.processed) == 3


async def test_dispatch_registra_falha_sem_perder_evento() -> None:
    a = _row(key="A")
    outbox = _FakeOutbox([_event(a)])
    report = await DispatchSearchOutbox(
        index=_FailingIndex(), reader=_FakeReader([a]), outbox=outbox, max_attempts=5
    ).run()
    assert report.processed == 0
    assert report.failed == 1
    assert len(outbox.failed) == 1
    assert outbox.events  # evento permanece para reprocessamento


def test_documento_de_linha_vendavel_tem_versao() -> None:
    row = _row(key="A")
    assert is_row_sellable(row, today=_TODAY)
    assert build_product_document(row, today=_TODAY).version == row.version


async def test_reindex_rejeicao_impede_troca_de_alias() -> None:
    a = _row(key="A")
    b = _row(key="B")
    index = _RejectingIndex(reject={str(a.id)})
    with pytest.raises(SearchIndexError):
        await ReindexProducts(index=index, reader=_FakeReader([a, b]), replicas=0).run(
            version=1, batch_size=50
        )
    assert index.swapped == []  # alias anterior preservado
    assert await index.count(target="forja_products_v1") == 1


async def test_reindex_divergencia_acima_da_tolerancia_impede_troca() -> None:
    a = _row(key="A")
    b = _row(key="B")
    index = _DroppingIndex(drop={str(a.id)})
    with pytest.raises(SearchIndexError):
        await ReindexProducts(index=index, reader=_FakeReader([a, b]), replicas=0).run(
            version=1, batch_size=50
        )
    assert index.swapped == []


async def test_reindex_divergencia_dentro_da_tolerancia_permite_troca() -> None:
    a = _row(key="A")
    b = _row(key="B")
    index = _DroppingIndex(drop={str(a.id)})
    report = await ReindexProducts(
        index=index, reader=_FakeReader([a, b]), replicas=0, count_tolerance=1
    ).run(version=1, batch_size=50)
    assert report.swapped is True
    assert report.count == 1
    assert report.expected == 2
    assert index.swapped == ["forja_products_v1"]


async def test_reindex_sem_rejeicao_troca_alias_normalmente() -> None:
    a = _row(key="A")
    b = _row(key="B")
    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader([a, b]), replicas=0).run(
        version=1, batch_size=50
    )
    assert report.swapped is True
    assert report.rejected == 0
    assert report.count == 2
    assert index.swapped == ["forja_products_v1"]


async def test_dispatch_rejeicao_marca_evento_como_falho() -> None:
    a = _row(key="A")
    outbox = _FakeOutbox([_event(a)])
    index = _RejectingIndex(reject={str(a.id)})
    report = await DispatchSearchOutbox(
        index=index, reader=_FakeReader([a]), outbox=outbox, max_attempts=5
    ).run()
    assert report.processed == 0
    assert report.failed == 1
    assert [event_id for event_id, _error in outbox.failed] == [outbox.events[0].id]
    assert await index.count(target=index.alias) == 0


async def test_reconcile_reporta_rejeicao_sem_engolir() -> None:
    a = _row(key="A", updated_at=_V2)
    index = _RejectingIndex(reject={str(a.id)})
    index.docs[index.alias] = {str(a.id): (a.version - 1, {"version": a.version - 1})}
    report = await ReconcileSearchIndex(index=index, reader=_FakeReader([a]), batch_size=50).run()
    assert report.rejected == 1
    assert report.upserted == 0


async def test_bulk_guarda_motivo_resumido_da_rejeicao(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_bulk(*args: object, **kwargs: object) -> tuple[bool, list[dict[str, object]]]:
        return True, [{"index": {"error": {"type": "document_parsing_exception"}}}]

    monkeypatch.setattr(es_mod, "async_bulk", _fake_bulk)
    index = es_mod.ElasticsearchProductIndex(client=cast(Any, object()), alias="forja_products")
    document = build_product_document(_row(key="A"), today=_TODAY)
    result = await index.index_documents(target="forja_products_v1", documents=[document])
    assert result.errors == 1
    assert result.sample_errors == ("index:document_parsing_exception",)
