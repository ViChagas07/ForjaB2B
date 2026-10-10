"""Testes dos casos de uso de sincronizacao (fakes em memoria, sem Docker)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime

from app.modules.search.application.documents import build_product_document, is_row_sellable
from app.modules.search.application.errors import SearchUnavailableError
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
