"""Contrato OpenAPI: metadados, erros padronizados e seguranca.

O teste varre TODAS as operacoes publicadas e falha se uma rota nova nao
declarar resumo, tag e resposta de erro no formato Problem Details. Tambem
verifica o enriquecimento global (info, licenca, securitySchemes e exemplos).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.interface.schemas import ProblemDetails
from app.main import create_app

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


@pytest.fixture()
async def schema() -> AsyncIterator[dict[str, Any]]:
    app = create_app(Settings(environment="test", otel_enabled=False, elasticsearch_enabled=False))
    try:
        yield app.openapi()
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


def _operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    result: list[tuple[str, str, dict[str, Any]]] = []
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in _HTTP_METHODS:
                result.append((method, path, operation))
    return result


def test_info_contem_versao_contato_e_licenca(schema: dict[str, Any]) -> None:
    info = schema["info"]
    assert info["title"] == "Forja B2B API"
    assert info["version"]
    assert info["contact"]["name"]
    assert info["license"]["name"] == "[A DEFINIR pelo responsável]"
    assert "Problem Details" in info["description"]


def test_esquema_de_seguranca_jwt(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]
    assert schemes["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT de acesso emitido por /api/v1/auth/login ou /oauth/exchange.",
    }
    assert schemes["adminKey"]["in"] == "header"


def test_problem_details_documentado_com_request_id_e_erros_por_campo(
    schema: dict[str, Any],
) -> None:
    problem = schema["components"]["schemas"]["ProblemDetails"]
    assert "request_id" in problem["properties"]
    assert "errors" in problem["properties"]
    assert "FieldError" in schema["components"]["schemas"]

    generated = ProblemDetails.model_json_schema()
    assert "request_id" in generated["properties"]


def test_todas_as_rotas_tem_summary_tags_e_erro_documentado(schema: dict[str, Any]) -> None:
    declaradas = {tag["name"] for tag in schema.get("tags", [])}
    problemas: list[str] = []

    for method, path, operation in _operations(schema):
        if not operation.get("summary"):
            problemas.append(f"{method.upper()} {path}: sem summary")
        tags = operation.get("tags") or []
        if not tags:
            problemas.append(f"{method.upper()} {path}: sem tags")
        if any(tag not in declaradas for tag in tags):
            problemas.append(f"{method.upper()} {path}: tag nao declarada no topo")

        error_responses = [
            (status, response)
            for status, response in operation["responses"].items()
            if status.startswith(("4", "5"))
        ]
        if not error_responses:
            problemas.append(f"{method.upper()} {path}: sem resposta de erro")
            continue
        documentados = [
            response for _, response in error_responses if _has_problem_schema(response)
        ]
        if not documentados:
            problemas.append(f"{method.upper()} {path}: erro sem schema Problem Details")

    assert not problemas, "\n".join(problemas)


def _has_problem_schema(response: dict[str, Any]) -> bool:
    content = response.get("content") or {}
    media = content.get("application/problem+json") or {}
    schema = media.get("schema") or {}
    return schema.get("$ref") == "#/components/schemas/ProblemDetails"


def test_rotas_protegidas_declaram_bearer(schema: dict[str, Any]) -> None:
    order = schema["paths"]["/api/v1/orders"]["post"]
    assert order["security"] == [{"bearerAuth": []}]
    assert any(
        parameter["name"] == "Idempotency-Key" for parameter in order["parameters"]
    )
    assert "Idempotent-Replayed" in order["responses"]["201"]["headers"]

    admin = schema["paths"]["/api/v1/admin/catalog/products"]["post"]
    assert admin["security"] == [{"bearerAuth": []}]

    catalog = schema["paths"]["/api/v1/catalog/products"]["get"]
    assert {"bearerAuth": []} in catalog["security"]
    assert {} in catalog["security"]


def test_rotas_principais_tem_exemplos(schema: dict[str, Any]) -> None:
    login = schema["paths"]["/api/v1/auth/login"]["post"]
    assert login["requestBody"]["content"]["application/json"]["example"]["email"]

    order = schema["paths"]["/api/v1/orders"]["post"]
    assert order["requestBody"]["content"]["application/json"]["example"]["items"]
    assert order["responses"]["201"]["content"]["application/json"]["example"]["id"]

    product = schema["paths"]["/api/v1/admin/catalog/products"]["post"]
    assert product["requestBody"]["content"]["application/json"]["example"]["sku"]

    search = schema["paths"]["/api/v1/search/products"]["get"]
    assert search["responses"]["200"]["content"]["application/json"]["example"]["items"]
