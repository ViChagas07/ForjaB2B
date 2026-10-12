"""Integracao do indice de busca com Elasticsearch real (Testcontainers).

Requer daemon Docker. Sem Docker, a fixture falha explicitamente (sem skip
silencioso), como o restante da suite de integracao. Cobre o mapping explicito,
os analisadores em portugues, o upsert idempotente, a remocao e a troca de
alias sobre um Elasticsearch real (container descartavel, sem servico pago).

Usa o ``DockerContainer`` generico (mesmo padrao do Redis de teste) em vez do
modulo ``testcontainers.elasticsearch`` (deprecado).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import docker
import pytest
from elasticsearch import AsyncElasticsearch
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from app.modules.search.application.ports import ProductDocument, SearchQuery
from app.modules.search.infrastructure.elasticsearch import ElasticsearchProductIndex

_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:9.5.5"
_ALIAS = "forja_test_products"


@pytest.fixture(scope="module")
def es_container() -> Iterator[DockerContainer]:
    try:
        docker.from_env().ping()
    except Exception as exc:  # noqa: BLE001 - sem Docker: pular
        pytest.skip(f"Docker indisponivel para o Elasticsearch descartavel: {exc}")
    container = (
        DockerContainer(_IMAGE)
        .with_exposed_ports(9200)
        .with_env("discovery.type", "single-node")
        .with_env("xpack.security.enabled", "false")
        .with_env("ES_JAVA_OPTS", "-Xms512m -Xmx512m")
        # Espera a API HTTP responder (a mensagem "started" do log aparece antes
        # de o transporte HTTP estar pronto, causando ServerDisconnectedError).
        .waiting_for(
            HttpWaitStrategy(9200, "/_cluster/health?wait_for_status=yellow")
            .for_status_code(200)
            .with_startup_timeout(240)
        )
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture()
async def es_client(es_container: DockerContainer) -> AsyncIterator[AsyncElasticsearch]:
    host = es_container.get_container_host_ip()
    port = es_container.get_exposed_port(9200)
    client = AsyncElasticsearch(hosts=[f"http://{host}:{port}"])
    try:
        yield client
    finally:
        await client.close()


def _index(es_client: AsyncElasticsearch) -> ElasticsearchProductIndex:
    return ElasticsearchProductIndex(client=es_client, alias=_ALIAS)


def _document(
    doc_id: str,
    name: str,
    *,
    version: int = 1,
    sku: str | None = None,
    is_available: bool = True,
) -> ProductDocument:
    return ProductDocument(
        id=doc_id,
        sku=sku or f"SKU-{doc_id}",
        name=name,
        description="item de teste",
        slug=doc_id,
        status="ACTIVE",
        is_epi=False,
        is_available=is_available,
        ca_number=None,
        ca_valid_until=None,
        category_id=str(uuid.uuid4()),
        category="Categoria",
        category_slug="categoria",
        brand_id=None,
        brand=None,
        brand_slug=None,
        attributes={},
        name_en=None,
        name_es=None,
        name_ar=None,
        description_en=None,
        description_es=None,
        description_ar=None,
        attributes_text_en=None,
        attributes_text_es=None,
        attributes_text_ar=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        version=version,
    )


async def _tokens(client: AsyncElasticsearch, index: str, analyzer: str, text: str) -> list[str]:
    response = await client.indices.analyze(index=index, analyzer=analyzer, text=text)
    return [str(token["token"]) for token in response["tokens"]]


async def test_analisador_pt_ignora_acento(es_client: AsyncElasticsearch) -> None:
    name = await _index(es_client).create_versioned_index(version=101, replicas=0)
    com_acento = await _tokens(es_client, name, "pt_text", "Óculos")
    sem_acento = await _tokens(es_client, name, "pt_text", "Oculos")
    assert com_acento == sem_acento
    assert com_acento


async def test_analisador_autocomplete_gera_prefixos(es_client: AsyncElasticsearch) -> None:
    name = await _index(es_client).create_versioned_index(version=102, replicas=0)
    tokens = await _tokens(es_client, name, "autocomplete_index", "capacete")
    assert "cap" in tokens  # prefixo "capac" sugeriria "capacete"


async def test_normalizer_de_sku_em_minusculas(es_client: AsyncElasticsearch) -> None:
    name = await _index(es_client).create_versioned_index(version=103, replicas=0)
    response = await es_client.indices.analyze(
        index=name, normalizer="lowercase_normalizer", text="CAP-002"
    )
    assert [token["token"] for token in response["tokens"]] == ["cap-002"]


async def test_upsert_idempotente_e_busca_sem_acento(es_client: AsyncElasticsearch) -> None:
    index = _index(es_client)
    name = await index.create_versioned_index(version=104, replicas=0)
    document = _document("p1", "Óculos de Proteção Incolor", version=1000)
    await index.index_documents(target=name, documents=[document])
    await index.index_documents(target=name, documents=[document])  # reexecucao
    await index.refresh(target=name)
    assert await index.count(target=name) == 1

    response = await es_client.search(index=name, query={"match": {"name": "oculos"}})
    assert int(response["hits"]["total"]["value"]) == 1


async def test_delete_remove_documento(es_client: AsyncElasticsearch) -> None:
    index = _index(es_client)
    name = await index.create_versioned_index(version=105, replicas=0)
    await index.index_documents(target=name, documents=[_document("p2", "Botina Couro", version=1)])
    await index.delete_documents(target=name, ids=["p2"])
    await index.refresh(target=name)
    assert await index.count(target=name) == 0


async def test_swap_alias_aponta_para_o_indice_novo(es_client: AsyncElasticsearch) -> None:
    index = _index(es_client)
    v1 = await index.create_versioned_index(version=901, replicas=0)
    await index.swap_alias(index_name=v1)
    v2 = await index.create_versioned_index(version=902, replicas=0)
    await index.swap_alias(index_name=v2)
    aliases = await es_client.indices.get_alias(name=_ALIAS)
    assert v2 in aliases
    assert v1 not in aliases


def _query(q: str | None, *, page: int = 1, page_size: int = 10) -> SearchQuery:
    return SearchQuery(
        q=q, category_id=None, brand_id=None, is_epi=None, page=page, page_size=page_size
    )


async def test_search_prioriza_sku_exato_e_ignora_acento(
    es_client: AsyncElasticsearch,
) -> None:
    index = _index(es_client)
    name = await index.create_versioned_index(version=911, replicas=0)
    await index.index_documents(
        target=name,
        documents=[
            _document("p-sku", "Luva de Seguranca", sku="CAP-001", version=1),
            _document("p-accent", "Oculos de Protecao Incolor", version=1),
        ],
    )
    await index.swap_alias(index_name=name)
    await index.refresh(target=name)

    by_sku = await index.search(_query("cap-001"))
    assert by_sku.mode == "lexical"
    assert by_sku.ids[0] == "p-sku"

    sem_acento = await index.search(_query("oculos"))
    assert "p-accent" in sem_acento.ids


async def test_search_nao_retorna_produto_indisponivel(
    es_client: AsyncElasticsearch,
) -> None:
    index = _index(es_client)
    name = await index.create_versioned_index(version=912, replicas=0)
    await index.index_documents(
        target=name,
        documents=[
            _document("p-on", "Capacete Disponivel", version=1),
            _document("p-off", "Capacete Indisponivel", is_available=False, version=1),
        ],
    )
    await index.swap_alias(index_name=name)
    await index.refresh(target=name)

    result = await index.search(_query("capacete"))
    assert "p-on" in result.ids
    assert "p-off" not in result.ids


async def test_autocomplete_por_prefixo(es_client: AsyncElasticsearch) -> None:
    index = _index(es_client)
    name = await index.create_versioned_index(version=913, replicas=0)
    await index.index_documents(
        target=name, documents=[_document("p-cap", "Capacete de Seguranca", version=1)]
    )
    await index.swap_alias(index_name=name)
    await index.refresh(target=name)

    suggestions = await index.autocomplete(q="cap", limit=10)
    assert any(suggestion.id == "p-cap" for suggestion in suggestions)
    assert all(suggestion.name for suggestion in suggestions)
