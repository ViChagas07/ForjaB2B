"""Adaptador do motor de busca sobre o cliente oficial do Elasticsearch.

O Elasticsearch NUNCA e fonte de verdade: este adaptador apenas consulta o
indice lexical. Falhas de conexao, timeout ou resposta 5xx sao traduzidas para
``SearchUnavailableError`` (distintas de "sem resultados"). O cliente
assincrono (``AsyncElasticsearch``) nao bloqueia o event loop.

Em desenvolvimento usa-se HTTP sem TLS apenas na rede interna do Docker, com
autenticacao; a verificacao de TLS nunca e desabilitada no cliente. TLS e
obrigatorio em producao (Fase 6).
"""

from __future__ import annotations

from elasticsearch import (
    ApiError,
    AsyncElasticsearch,
    ConnectionError,
    ConnectionTimeout,
    TransportError,
)

from app.core.config import Settings
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import (
    SearchEngine,
    SearchEngineHealth,
    SearchEngineState,
)

# Falhas do cliente que representam indisponibilidade (conexao/timeout/5xx).
# `TransportError` cobre as demais variantes de transporte; `ApiError` cobre
# respostas HTTP 5xx do servidor.
_ELASTICSEARCH_ERRORS = (ConnectionError, ConnectionTimeout, TransportError, ApiError)


class ElasticsearchSearchEngine(SearchEngine):
    """Adaptador assincrono do Elasticsearch (indice lexical)."""

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
        """Nome do indice/alias configurado."""
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


def classify_cluster_status(status: str) -> SearchEngineState:
    """Mapeia o status do cluster (`green`/`yellow`/`red`) para o estado da porta."""
    if status == "red":
        return SearchEngineState.DEGRADED
    return SearchEngineState.OK


def translate_elasticsearch_error(exc: Exception) -> SearchUnavailableError:
    """Traduz uma falha do Elasticsearch para ``SearchUnavailableError``.

    Usada pelos casos de uso de busca (Fases 4/5) para distinguir
    indisponibilidade de "sem resultados". O detalhe nunca expoe credenciais.
    """
    return SearchUnavailableError(f"search engine unavailable: {type(exc).__name__}")


def build_search_engine(settings: Settings) -> SearchEngine | None:
    """Constroi o motor de busca; ``None`` quando a integracao esta desabilitada."""
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
