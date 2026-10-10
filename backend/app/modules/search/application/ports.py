"""Portas do contexto de busca (contratos de dependencias invertidas).

A camada de aplicacao (e a interface) nunca fala o DSL do Elasticsearch nem SQL:
ela depende destas portas. Os adaptadores concretos vivem na infraestrutura.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.domain.pricing import CompanyPriceRule


class SearchEngineState(StrEnum):
    """Estado de saude do motor de busca."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, kw_only=True)
class SearchEngineHealth:
    """Resultado de uma verificacao de saude do motor de busca."""

    state: SearchEngineState
    detail: str | None = None


class SearchEngine(Protocol):
    """Porta do motor de busca lexical (health + ciclo de vida)."""

    async def check_health(self) -> SearchEngineHealth:
        """Verifica a disponibilidade do motor; nunca levanta excecao."""
        ...

    async def close(self) -> None:
        """Libera os recursos do cliente."""
        ...


class SearchEventType(StrEnum):
    """Tipo de evento de sincronizacao do indice."""

    UPSERT = "UPSERT"
    DELETE = "DELETE"


@dataclass(frozen=True, kw_only=True)
class ProductRow:
    """Linha do catalogo (PostgreSQL) usada para sincronizacao e hidratacao.

    NAO indexa preco: os campos ``base_unit_price``/``currency``/``min_order_qty``
    existem na linha para hidratacao da resposta de busca (Fase 4), mas o
    documento enviado ao Elasticsearch os omite de proposito.
    """

    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    slug: str
    status: str
    is_epi: bool
    ca_number: str | None
    ca_valid_until: date | None
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    brand_slug: str | None
    attributes: dict[str, object] | None
    base_unit_price: Decimal
    currency: str
    min_order_qty: int
    created_at: datetime
    updated_at: datetime

    @property
    def version(self) -> int:
        """Versao externa para o Elasticsearch (epoch ms de ``updated_at``)."""
        return int(self.updated_at.timestamp() * 1000)


@dataclass(frozen=True, kw_only=True)
class ProductDocument:
    """Documento indexavel. NAO contem preco nem qualquer dado sensivel."""

    id: str
    sku: str
    name: str
    description: str | None
    slug: str
    status: str
    is_epi: bool
    is_available: bool
    ca_number: str | None
    ca_valid_until: str | None
    category_id: str
    category: str
    category_slug: str
    brand_id: str | None
    brand: str | None
    brand_slug: str | None
    attributes: dict[str, object]
    created_at: str
    updated_at: str
    version: int

    def to_source(self) -> dict[str, object]:
        """Representacao indexada (``_source``), alinhada ao mapping explicito."""
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "slug": self.slug,
            "status": self.status,
            "is_epi": self.is_epi,
            "is_available": self.is_available,
            "ca_number": self.ca_number,
            "ca_valid_until": self.ca_valid_until,
            "category_id": self.category_id,
            "category": self.category,
            "category_slug": self.category_slug,
            "brand_id": self.brand_id,
            "brand": self.brand,
            "brand_slug": self.brand_slug,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }


@dataclass(frozen=True, kw_only=True)
class IndexBulkResult:
    """Resultado de um lote de operacoes no indice."""

    indexed: int = 0
    deleted: int = 0
    errors: int = 0
    # Motivos resumidos (sem dados sensiveis) das rejeicoes por documento.
    sample_errors: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class SearchOutboxEvent:
    """Evento pendente da outbox de busca."""

    id: uuid.UUID
    aggregate_id: uuid.UUID
    event_type: str
    version: int
    attempts: int


@dataclass(frozen=True, kw_only=True)
class SearchQuery:
    """Parametros de uma busca lexical (validados pela interface)."""

    q: str | None
    category_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    is_epi: bool | None
    page: int
    page_size: int


@dataclass(frozen=True, kw_only=True)
class SearchResult:
    """Resultado bruto de um motor de busca: ids ordenados + total."""

    ids: list[str]
    total: int
    mode: str


@dataclass(frozen=True, kw_only=True)
class SearchSuggestion:
    """Sugestao de autocomplete (sem preco nem dado sensivel)."""

    id: str
    sku: str
    name: str


class ProductReader(Protocol):
    """Leitura do catalogo (PostgreSQL) para montar documentos/versoes."""

    def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        """Percorre TODOS os produtos por paginacao de chave (id crescente)."""
        ...

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        """Carrega um produto pelo id (qualquer status) para reaplicar um evento."""
        ...

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        """Carrega varios produtos de uma vez (hidratacao pos-busca)."""
        ...

    async def get_company_price_rules(
        self, *, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        """Regras de preco da empresa por produto (RLS; vazio sem tenant).

        Usado apenas para usuario autenticado; visitante nunca recebe valor
        (preco consultivo). Nada disto vem de indice ou vetor.
        """
        ...


class SearchReader(Protocol):
    """Motor de busca lexical (leitura): implementado pelo ES e pelo fallback Postgres."""

    async def search(self, query: SearchQuery) -> SearchResult:
        """Busca lexical paginada; devolve ids ordenados e total."""
        ...

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        """Autocomplete por prefixo/texto; devolve no maximo ``limit`` sugestoes."""
        ...


class ProductIndex(Protocol):
    """Indice de produtos (indice versionado + alias; escrita pelo alias)."""

    @property
    def alias(self) -> str:
        """Alias estavel usado pela aplicacao (leitura e escrita)."""
        ...

    async def create_versioned_index(self, *, version: int, replicas: int) -> str:
        """Garante o indice versionado (idempotente) e devolve o nome."""
        ...

    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        """Indexa/atualiza documentos com versionamento externo (upsert)."""
        ...

    async def delete_documents(self, *, target: str, ids: Sequence[str]) -> IndexBulkResult:
        """Remove documentos por id (ausencia nao e erro)."""
        ...

    async def fetch_versions(self, *, target: str) -> dict[str, int]:
        """Mapa id -> versao de todos os documentos do indice (reconciliacao)."""
        ...

    async def count(self, *, target: str) -> int:
        """Numero de documentos no indice alvo."""
        ...

    async def refresh(self, *, target: str) -> None:
        """Torna as escritas visiveis (refresh explicito)."""
        ...

    async def swap_alias(self, *, index_name: str) -> None:
        """Aponta o alias para o indice informado (troca atomica)."""
        ...


class SearchOutboxRepository(Protocol):
    """Outbox transacional da sincronizacao do indice (global)."""

    async def list_due(self, *, limit: int, max_attempts: int) -> list[SearchOutboxEvent]:
        """Eventos pendentes (ou falhos ainda retentaveis)."""
        ...

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        """Marca o evento como PROCESSED."""
        ...

    async def mark_failed(self, event_id: uuid.UUID, *, error: str) -> None:
        """Incrementa tentativas e registra o erro (retentavel)."""
        ...


class EmbeddingProvider(Protocol):
    """Provedor de embeddings (local). Nenhum detalhe do modelo vaza daqui."""

    @property
    def model(self) -> str:
        """Identificador do modelo (ex.: ``intfloat/multilingual-e5-small``)."""
        ...

    @property
    def dimension(self) -> int:
        """Dimensao dos vetores produzidos."""
        ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Gera vetores (prefixo ``passage:``) para indexacao."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Gera o vetor de consulta (prefixo ``query:``)."""
        ...


@dataclass(frozen=True, kw_only=True)
class EmbeddingEntry:
    """Vetor pronto para persistir (com hash do conteudo embutido)."""

    product_id: uuid.UUID
    model: str
    dimension: int
    embedding: list[float]
    content_hash: str


@dataclass(frozen=True, kw_only=True)
class VectorHit:
    """Resultado de uma consulta vetorial (similaridade por cosseno)."""

    product_id: uuid.UUID
    score: float


class VectorStore(Protocol):
    """Armazenamento vetorial (pgvector) e busca por similaridade."""

    async def upsert_many(self, entries: Sequence[EmbeddingEntry]) -> int:
        """Grava/atualiza vetores (idempotente por ``product_id``)."""
        ...

    async def get_hashes(self) -> dict[uuid.UUID, str]:
        """Mapa ``product_id`` -> ``content_hash`` de todos os vetores."""
        ...

    async def get_hash(self, product_id: uuid.UUID) -> str | None:
        """``content_hash`` atual de um produto (``None`` se nao houver vetor)."""
        ...

    async def search_similar(
        self, *, embedding: Sequence[float], filters: SearchQuery, limit: int
    ) -> list[VectorHit]:
        """Top-N por similaridade de cosseno, restrito a produtos vendaveis."""
        ...

    async def delete(self, product_ids: Sequence[uuid.UUID]) -> int:
        """Remove vetores por produto (ausencia nao e erro)."""
        ...
