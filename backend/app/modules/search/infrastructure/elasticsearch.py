"""Adaptador do motor de busca sobre o cliente oficial do Elasticsearch.

O Elasticsearch NUNCA e fonte de verdade: este adaptador apenas mantem um
indice derivado (busca lexical) e reporta saude. Falhas de conexao, timeout ou
resposta 5xx sao traduzidas para ``SearchUnavailableError`` (distintas de "sem
resultados"). O cliente assincrono (``AsyncElasticsearch``) nao bloqueia o
event loop.

Em desenvolvimento usa-se HTTP sem TLS apenas na rede interna do Docker, com
autenticacao; a verificacao de TLS nunca e desabilitada no cliente. TLS e
obrigatorio em producao (Fase 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from elasticsearch import (
    ApiError,
    AsyncElasticsearch,
    ConnectionError,
    ConnectionTimeout,
    TransportError,
)
from elasticsearch.helpers import async_bulk, async_scan

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import (
    IndexBulkResult,
    ProductDocument,
    SearchEngine,
    SearchEngineHealth,
    SearchEngineState,
)
from app.modules.search.infrastructure.index_files import (
    load_index_mappings,
    load_index_settings,
    versioned_index_name,
)

_logger = get_logger(__name__)

# Falhas do cliente que representam indisponibilidade (conexao/timeout/5xx).
# `TransportError` cobre as demais variantes de transporte; `ApiError` cobre
# respostas HTTP 5xx do servidor.
_ELASTICSEARCH_ERRORS = (ConnectionError, ConnectionTimeout, TransportError, ApiError)
_VERSION_CONFLICT = "version_conflict_engine_exception"


def _basic_auth(settings: Settings) -> tuple[str, str] | None:
    if settings.elasticsearch_username is not None and settings.elasticsearch_api_key is None:
        return (settings.elasticsearch_username, settings.elasticsearch_password or "")
    return None


def _create_client(settings: Settings) -> AsyncElasticsearch:
    return AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        request_timeout=settings.elasticsearch_request_timeout_seconds,
        max_retries=settings.elasticsearch_max_retries,
        retry_on_timeout=True,
        basic_auth=_basic_auth(settings),
        api_key=settings.elasticsearch_api_key,
    )


class ElasticsearchSearchEngine(SearchEngine):
    """Adaptador de health do motor de busca (Fase 2)."""

    def __init__(
        self,
        *,
        url: str,
        username: str | None,
        password: str | None,
        api_key: str | None,
        index: str,
        request_timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._index = index
        # Autenticacao: API key tem precedencia; caso contrario, basic auth.
        basic_auth = (
            (username, password or "") if username is not None and api_key is None else None
        )
        self._client = AsyncElasticsearch(
            hosts=[url],
            request_timeout=request_timeout_seconds,
            max_retries=max_retries,
            retry_on_timeout=True,
            basic_auth=basic_auth,
            api_key=api_key,
        )

    @property
    def index(self) -> str:
        """Nome do alias configurado."""
        return self._index

    async def check_health(self) -> SearchEngineHealth:
        """Consulta o estado do cluster; nunca levanta excecao."""
        try:
            response = await self._client.cluster.health(wait_for_status="yellow")
        except _ELASTICSEARCH_ERRORS as exc:
            return SearchEngineHealth(
                state=SearchEngineState.UNAVAILABLE, detail=type(exc).__name__
            )
        status = str(response.get("status", ""))
        return SearchEngineHealth(state=classify_cluster_status(status), detail=status or None)

    async def close(self) -> None:
        """Fecha o cliente e libera as conexoes."""
        await self._client.close()


class ElasticsearchProductIndex:
    """Indice de produtos versionado (alias estavel + indice por versao).

    A aplicacao sempre escreve/le pelo alias; a reindexacao cria um indice novo
    (``<alias>_vN``), valida a contagem e troca o alias de forma atomica,
    mantendo o indice anterior para rollback.
    """

    def __init__(self, *, client: AsyncElasticsearch, alias: str) -> None:
        self._client = client
        self._alias = alias

    @property
    def alias(self) -> str:
        return self._alias

    async def create_versioned_index(self, *, version: int, replicas: int) -> str:
        name = versioned_index_name(alias=self._alias, version=version)
        try:
            exists = await self._client.indices.exists(index=name)
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        if exists:
            return name  # reexecucao idempotente: reutiliza o indice existente
        settings = dict(load_index_settings())
        settings["number_of_replicas"] = replicas
        try:
            await self._client.indices.create(
                index=name, settings=settings, mappings=load_index_mappings()
            )
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        _logger.info("search_index_created", index=name, replicas=replicas)
        return name

    async def index_documents(
        self, *, target: str, documents: Sequence[ProductDocument]
    ) -> IndexBulkResult:
        if not documents:
            return IndexBulkResult()
        actions: list[dict[str, Any]] = [
            {
                "_op_type": "index",
                "_index": target,
                "_id": document.id,
                "version": document.version,
                "version_type": "external",
                "_source": document.to_source(),
            }
            for document in documents
        ]
        return await self._bulk(actions)

    async def delete_documents(self, *, target: str, ids: Sequence[str]) -> IndexBulkResult:
        if not ids:
            return IndexBulkResult()
        actions: list[dict[str, Any]] = [
            {"_op_type": "delete", "_index": target, "_id": doc_id} for doc_id in ids
        ]
        return await self._bulk(actions)

    async def fetch_versions(self, *, target: str) -> dict[str, int]:
        versions: dict[str, int] = {}
        try:
            async for hit in async_scan(
                self._client,
                index=target,
                query={"query": {"match_all": {}}},
                source_includes=["version"],
                preserve_order=False,
            ):
                source = cast("dict[str, Any]", hit.get("_source", {}))
                versions[str(hit["_id"])] = int(source.get("version", 0))
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        return versions

    async def count(self, *, target: str) -> int:
        try:
            response = await self._client.count(index=target)
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        return int(response.get("count", 0))

    async def refresh(self, *, target: str) -> None:
        try:
            await self._client.indices.refresh(index=target)
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc

    async def close(self) -> None:
        """Fecha o cliente e libera as conexoes."""
        await self._client.close()

    async def swap_alias(self, *, index_name: str) -> None:
        actions: list[dict[str, Any]] = [
            {"remove": {"index": "*", "alias": self._alias, "must_exist": False}},
            {"add": {"index": index_name, "alias": self._alias}},
        ]
        try:
            await self._client.indices.update_aliases(actions=actions)
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        _logger.info("search_alias_swapped", alias=self._alias, index=index_name)

    async def _bulk(self, actions: list[dict[str, Any]]) -> IndexBulkResult:
        index_ops = sum(1 for action in actions if action["_op_type"] == "index")
        delete_ops = sum(1 for action in actions if action["_op_type"] == "delete")
        try:
            _success, errors = await async_bulk(self._client, actions, raise_on_error=False)
        except _ELASTICSEARCH_ERRORS as exc:
            raise translate_elasticsearch_error(exc) from exc
        failed_index = 0
        failed_delete = 0
        failed_items = errors if isinstance(errors, list) else []
        for item in failed_items:
            op_name = next(iter(item.keys()))
            op_detail = cast("dict[str, Any]", next(iter(item.values())))
            error_type = str(op_detail.get("error", {}).get("type", ""))
            if error_type == _VERSION_CONFLICT:
                continue  # versao mais antiga que a indexada: ignora (idempotente)
            if op_name == "index":
                failed_index += 1
            else:
                failed_delete += 1
        return IndexBulkResult(
            indexed=index_ops - failed_index,
            deleted=delete_ops - failed_delete,
            errors=failed_index + failed_delete,
        )


def classify_cluster_status(status: str) -> SearchEngineState:
    """Mapeia o status do cluster (`green`/`yellow`/`red`) para o estado da porta."""
    if status == "red":
        return SearchEngineState.DEGRADED
    return SearchEngineState.OK


def translate_elasticsearch_error(exc: Exception) -> SearchUnavailableError:
    """Traduz uma falha do Elasticsearch para ``SearchUnavailableError``.

    Usada pelos casos de uso de sincronizacao/busca (Fases 3/4/5) para
    distinguir indisponibilidade de "sem resultados". Nunca expoe credenciais.
    """
    return SearchUnavailableError(f"search engine unavailable: {type(exc).__name__}")


def build_search_engine(settings: Settings) -> SearchEngine | None:
    """Constroi o motor de busca (health); ``None`` quando desabilitado."""
    if not settings.elasticsearch_enabled:
        return None
    return ElasticsearchSearchEngine(
        url=settings.elasticsearch_url,
        username=settings.elasticsearch_username,
        password=settings.elasticsearch_password,
        api_key=settings.elasticsearch_api_key,
        index=settings.elasticsearch_index,
        request_timeout_seconds=settings.elasticsearch_request_timeout_seconds,
        max_retries=settings.elasticsearch_max_retries,
    )


def build_product_index(settings: Settings) -> ElasticsearchProductIndex | None:
    """Constroi o indice de produtos; ``None`` quando a integracao esta desabilitada."""
    if not settings.elasticsearch_enabled:
        return None
    return ElasticsearchProductIndex(
        client=_create_client(settings), alias=settings.elasticsearch_index
    )
