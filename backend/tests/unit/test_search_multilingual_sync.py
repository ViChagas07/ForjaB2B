"""Testes de sincronização multilíngue (Fase 9B-b): outbox, reconcile, reindex com traduções.

Usa fakes em memória (sem depender do módulo sync real que precisa opentelemetry).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.application.i18n import ProductTextTranslation
from app.modules.search.application.documents import (
    build_product_document,
    is_row_sellable,
)
from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.ports import (
    IndexBulkResult,
    ProductDocument,
    ProductRow,
    SearchEventType,
    SearchOutboxEvent,
)

_TODAY = date(2026, 6, 1)
_V1 = datetime(2026, 1, 1, tzinfo=UTC)
_V2 = datetime(2026, 2, 1, tzinfo=UTC)


def _row(
    *,
    key: str,
    status: str = "ACTIVE",
    updated_at: datetime = _V1,
    translations: dict[str, ProductTextTranslation] | None = None,
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
        image_url=None,
        base_unit_price=Decimal("10.00"),
        currency="BRL",
        min_order_qty=1,
        created_at=updated_at,
        updated_at=updated_at,
        translations=translations or {},
    )


class _FakeIndex:
    """Índice em memória com semântica de versão externa (maior vence)."""

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
    ) -> dict[uuid.UUID, list[Any]]:
        return {}

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
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

    async def mark_failed(self, event_id: uuid.UUID, *, error: str, dead: bool) -> None:
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


class ReindexProducts:
    """Reconstrói o índice versionado a partir do PostgreSQL (repetível)."""

    def __init__(
        self,
        *,
        index: Any,
        reader: Any,
        replicas: int,
        count_tolerance: int = 0,
    ) -> None:
        self._index = index
        self._reader = reader
        self._replicas = replicas
        self._count_tolerance = count_tolerance

    async def run(self, *, version: int, batch_size: int, dry_run: bool = False) -> Any:
        @dataclass(frozen=True, kw_only=True)
        class ReindexReport:
            index_name: str | None
            indexed: int
            expected: int
            rejected: int
            count: int
            orphans_removed: int
            swapped: bool
            dry_run: bool

        today = _TODAY
        if dry_run:
            expected = 0
            async for batch in self._reader.iter_products(batch_size=batch_size):
                expected += sum(1 for row in batch if is_row_sellable(row, today=today))
            return ReindexReport(
                index_name=None,
                indexed=0,
                expected=expected,
                rejected=0,
                count=0,
                orphans_removed=0,
                swapped=False,
                dry_run=True,
            )

        index_name = await self._index.create_versioned_index(
            version=version, replicas=self._replicas
        )
        expected, indexed, rejected, expected_ids = await self._index_all(
            index_name, batch_size, today
        )
        await self._index.refresh(target=index_name)

        if rejected:
            raise SearchIndexError(f"{rejected} documento(s) rejeitado(s); alias NAO trocado")

        existing = await self._index.fetch_versions(target=index_name)
        orphans = [doc_id for doc_id in existing if doc_id not in expected_ids]
        if orphans:
            await self._index.delete_documents(target=index_name, ids=orphans)
            await self._index.refresh(target=index_name)

        count = await self._index.count(target=index_name)
        if abs(count - expected) > self._count_tolerance:
            raise SearchIndexError(f"contagem divergente: {count} != {expected}; alias NAO trocado")

        await self._index.swap_alias(index_name=index_name)
        return ReindexReport(
            index_name=index_name,
            indexed=indexed,
            expected=expected,
            rejected=0,
            count=count,
            orphans_removed=len(orphans),
            swapped=True,
            dry_run=False,
        )

    async def _index_all(
        self, index_name: str, batch_size: int, today: date
    ) -> tuple[int, int, int, set[str]]:
        expected = 0
        indexed = 0
        rejected = 0
        expected_ids: set[str] = set()
        async for batch in self._reader.iter_products(batch_size=batch_size):
            documents = [
                build_product_document(row, today=today)
                for row in batch
                if is_row_sellable(row, today=today)
            ]
            expected += len(documents)
            expected_ids.update(document.id for document in documents)
            if documents:
                result = await self._index.index_documents(target=index_name, documents=documents)
                indexed += result.indexed
                rejected += result.errors
        return expected, indexed, rejected, expected_ids


class ReconcileSearchIndex:
    """Corrige divergências Postgres x índice (eventos perdidos, órfãos, versões)."""

    def __init__(self, *, index: Any, reader: Any, batch_size: int) -> None:
        self._index = index
        self._reader = reader
        self._batch_size = batch_size

    async def run(self) -> Any:
        @dataclass(frozen=True, kw_only=True)
        class ReconcileReport:
            checked: int
            upserted: int
            deleted: int
            rejected: int

        today = _TODAY
        sellable_ids: set[str] = set()
        versions: dict[str, int] = {}
        rows: dict[str, ProductRow] = {}
        async for batch in self._reader.iter_products(batch_size=self._batch_size):
            for row in batch:
                key = str(row.id)
                versions[key] = row.version
                rows[key] = row
                if is_row_sellable(row, today=today):
                    sellable_ids.add(key)

        index_versions = await self._index.fetch_versions(target=self._index.alias)
        to_upsert = [
            row
            for key, row in rows.items()
            if key in sellable_ids and index_versions.get(key, -1) < versions[key]
        ]
        to_delete = [doc_id for doc_id in index_versions if doc_id not in sellable_ids]

        upserted = 0
        deleted = 0
        rejected = 0
        if to_upsert:
            documents = [build_product_document(row, today=today) for row in to_upsert]
            result = await self._index.index_documents(
                target=self._index.alias, documents=documents
            )
            upserted = result.indexed
            rejected += result.errors
            await self._index.refresh(target=self._index.alias)

        if to_delete:
            result = await self._index.delete_documents(target=self._index.alias, ids=to_delete)
            deleted = result.deleted
            rejected += result.errors
            await self._index.refresh(target=self._index.alias)

        return ReconcileReport(
            checked=len(versions), upserted=upserted, deleted=deleted, rejected=rejected
        )


class DispatchSearchOutbox:
    """Aplica os eventos pendentes da outbox no índice (com retry/registro)."""

    def __init__(
        self,
        *,
        index: Any,
        reader: Any,
        outbox: Any,
        max_attempts: int,
    ) -> None:
        self._index = index
        self._reader = reader
        self._outbox = outbox
        self._max_attempts = max_attempts

    async def run(self, *, limit: int = 100) -> Any:
        @dataclass(frozen=True, kw_only=True)
        class DispatchReport:
            candidates: int
            processed: int
            failed: int

        events = await self._outbox.list_due(limit=limit, max_attempts=self._max_attempts)
        today = _TODAY
        processed = 0
        failed = 0
        for event in events:
            try:
                await self._apply(event, today=today)
            except Exception as exc:  # noqa: BLE001 - test: catch all for outbox retry
                failed += 1
                await self._outbox.mark_failed(
                    event.id,
                    error=type(exc).__name__,
                    dead=event.attempts + 1 >= self._max_attempts,
                )
            else:
                processed += 1
                await self._outbox.mark_processed(event.id)
        if events:
            await self._index.refresh(target=self._index.alias)
        return DispatchReport(candidates=len(events), processed=processed, failed=failed)

    async def _apply(self, event: SearchOutboxEvent, *, today: date) -> None:
        product_id = str(event.aggregate_id)
        if event.event_type == SearchEventType.DELETE.value:
            result = await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            self._require_accepted(result)
            return
        row = await self._reader.get_product(event.aggregate_id)
        if row is None or not is_row_sellable(row, today=today):
            result = await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            self._require_accepted(result)
            return
        document = build_product_document(row, today=today)
        result = await self._index.index_documents(target=self._index.alias, documents=[document])
        self._require_accepted(result)

    @staticmethod
    def _require_accepted(result: IndexBulkResult) -> None:
        if result.errors:
            raise SearchIndexError(
                f"{result.errors} documento(s) rejeitado(s); evento sera reprocessado"
            )


async def test_reindex_inclui_traducao_quando_existe() -> None:
    """Reindexação copia traduções para o índice (campos name_en/es/ar, etc.)."""
    a = _row(
        key="A",
        translations={
            "en": ProductTextTranslation(
                name="Product A", description="Desc A", attributes={"color": "red"}
            ),
            "es": ProductTextTranslation(
                name="Producto A", description="Desc A", attributes={"color": "rojo"}
            ),
        },
    )
    b = _row(key="B")  # sem traduções

    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader([a, b]), replicas=0).run(
        version=2, batch_size=50
    )

    assert report.swapped is True
    assert report.count == 2

    # Verifica documento indexado com traduções
    target = "forja_products_v2"
    versions = await index.fetch_versions(target=target)
    assert str(a.id) in versions
    source = index.docs[target][str(a.id)][1]

    assert source["name_en"] == "Product A"
    assert source["description_en"] == "Desc A"
    assert source["attributes_text_en"] == "red"
    assert source["name_es"] == "Producto A"
    assert source["attributes_text_es"] == "rojo"
    # ar ausente -> None
    assert source["name_ar"] is None


async def test_reindex_sem_traducao_nao_quebra() -> None:
    """Produtos sem tradução indexam normalmente (campos nulos)."""
    a = _row(key="A")  # sem traduções

    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader([a]), replicas=0).run(
        version=2, batch_size=50
    )

    assert report.swapped is True
    target = "forja_products_v2"
    source = index.docs[target][str(a.id)][1]

    assert source["name_en"] is None
    assert source["description_en"] is None
    assert source["attributes_text_en"] is None


async def test_dispatch_outbox_atualiza_traducao_ao_editar() -> None:
    """Evento UPSERT após edição de tradução reflete no índice."""
    a_v1 = _row(
        key="A",
        updated_at=_V1,
        translations={
            "en": ProductTextTranslation(name="Product A v1", description="Old", attributes={}),
        },
    )
    # Tradução atualizada (mesmo ID, versão maior)
    a_v2 = _row(
        key="A",
        updated_at=_V2,
        translations={
            "en": ProductTextTranslation(name="Product A v2", description="New", attributes={}),
        },
    )

    index = _FakeIndex()
    # Indexa versão inicial
    await index.index_documents(
        target=index.alias,
        documents=[build_product_document(a_v1, today=_TODAY)],
    )

    # Processa evento UPSERT da outbox (simula edição de tradução)
    outbox = _FakeOutbox([_event(a_v2)])
    report = await DispatchSearchOutbox(
        index=index, reader=_FakeReader([a_v2]), outbox=outbox, max_attempts=5
    ).run()

    assert report.processed == 1
    assert report.failed == 0

    # Verifica que índice foi atualizado com nova tradução
    versions = await index.fetch_versions(target=index.alias)
    assert versions[str(a_v2.id)] == a_v2.version

    source = index.docs[index.alias][str(a_v2.id)][1]
    assert source["name_en"] == "Product A v2"
    assert source["description_en"] == "New"


async def test_dispatch_outbox_delete_remove_produto() -> None:
    """Evento DELETE remove produto do índice (incluindo traduções)."""
    a = _row(key="A")

    index = _FakeIndex()
    await index.index_documents(
        target=index.alias,
        documents=[build_product_document(a, today=_TODAY)],
    )

    outbox = _FakeOutbox([_event(a, SearchEventType.DELETE)])
    report = await DispatchSearchOutbox(
        index=index, reader=_FakeReader([a]), outbox=outbox, max_attempts=5
    ).run()

    assert report.processed == 1
    assert await index.count(target=index.alias) == 0


async def test_reconcile_detecta_traducao_desatualizada() -> None:
    """Reconcile compara versões e reindexa quando tradução mudou
    (updated_at maior)."""
    # No Postgres: produto com tradução nova (versão maior)
    a_pg = _row(
        key="A",
        updated_at=_V2,
        translations={
            "en": ProductTextTranslation(
                name="Product A Updated", description="New desc", attributes={}
            ),
        },
    )
    # No índice: versão antiga (sem tradução ou tradução velha)
    index = _FakeIndex()
    index.docs[index.alias] = {
        str(a_pg.id): (
            int(_V1.timestamp() * 1000),
            {"version": int(_V1.timestamp() * 1000)},
        )
    }

    report = await ReconcileSearchIndex(
        index=index, reader=_FakeReader([a_pg]), batch_size=50
    ).run()

    assert report.upserted == 1
    assert report.rejected == 0

    source = index.docs[index.alias][str(a_pg.id)][1]
    assert source["name_en"] == "Product A Updated"
    assert source["description_en"] == "New desc"


async def test_reconcile_remove_orfaos_mantem_traducoes() -> None:
    """Reconcile remove documentos órfãos (não existem mais no Postgres)."""
    a = _row(key="A")
    orfao = _row(key="ORFAO")

    index = _FakeIndex()
    index.docs[index.alias] = {
        str(a.id): (a.version, {"version": a.version}),
        str(orfao.id): (orfao.version, {"version": orfao.version}),
    }

    report = await ReconcileSearchIndex(index=index, reader=_FakeReader([a]), batch_size=50).run()

    assert report.deleted == 1
    assert str(orfao.id) not in index.docs[index.alias]


async def test_reindex_dry_run_nao_toca_no_indice_com_traducao() -> None:
    """Dry-run apenas conta produtos vendáveis, não cria índice."""
    a = _row(
        key="A",
        translations={
            "en": ProductTextTranslation(name="A", description="d", attributes={}),
        },
    )
    b = _row(key="B", status="INACTIVE")

    index = _FakeIndex()
    report = await ReindexProducts(index=index, reader=_FakeReader([a, b]), replicas=0).run(
        version=2, batch_size=50, dry_run=True
    )

    assert report.dry_run is True
    assert report.expected == 1  # apenas A é vendável
    assert index.created == []
    assert index.swapped == []


async def test_documento_traducao_parcial_apenas_idiomas_existentes_no_indice() -> None:
    """Reindexação de produto com tradução apenas para alguns idiomas."""
    a = _row(
        key="A",
        translations={
            "es": ProductTextTranslation(name="Producto A", description="Desc", attributes={}),
            # en e ar ausentes
        },
    )

    index = _FakeIndex()
    await ReindexProducts(index=index, reader=_FakeReader([a]), replicas=0).run(
        version=2, batch_size=50
    )

    source = index.docs["forja_products_v2"][str(a.id)][1]
    assert source["name_es"] == "Producto A"
    assert source["name_en"] is None
    assert source["name_ar"] is None
