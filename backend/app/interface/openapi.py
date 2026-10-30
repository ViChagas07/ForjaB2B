"""Enriquecimento deterministico do contrato OpenAPI.

O FastAPI gera o esquema em runtime, mas nao documenta respostas de erro
padronizadas, esquema de seguranca JWT nem exemplos por rota. Este modulo
aplica uma camada unica e deterministica sobre o esquema, sem duplicar a
declaracao em cada decorator:

- informacoes da API (titulo, versao, contato, licenca);
- tags com descricao (por modulo);
- ``summary`` obrigatorio em toda operacao;
- respostas Problem Details (RFC 9457) para os status reais de cada rota;
- ``bearerAuth`` (JWT) nas rotas autenticadas;
- exemplos de requisicao/resposta nas rotas principais.

O resultado e consumido por ``scripts/export_openapi.py`` e pelo teste que
varre o esquema. Nada aqui muda o comportamento em runtime.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.interface.deps import get_current_auth, get_optional_auth
from app.interface.schemas import ProblemDetails

_PROBLEM_REF = "#/components/schemas/ProblemDetails"
_PROBLEM_MEDIA_TYPE = "application/problem+json"
_WRITE_METHODS = frozenset({"post", "put", "patch", "delete"})

_TAG_DESCRIPTIONS: dict[str, str] = {
    "auth": "Autenticacao, sessao e OAuth Google.",
    "companies": "Cadastro, aprovacao e consulta da empresa do tenant.",
    "catalog": "Catalogo publico de categorias, marcas e produtos.",
    "catalog-admin": "Administracao de catalogo (somente papel ADMIN).",
    "catalog-admin-translations": "Traducoes de conteudo do catalogo (ADMIN).",
    "coupons-admin": "Administracao de cupons (somente papel ADMIN).",
    "search": "Busca lexical/semantica com fallback PostgreSQL.",
    "cart": "Carrinho de compras do tenant.",
    "orders": "Criacao, consulta e cancelamento de pedidos.",
    "invoicing": "Faturas e boletos.",
    "credit": "Conta de credito e lancamentos do tenant.",
    "payments": "Checkout, estorno e webhooks de pagamento.",
    "notifications": "Notificacoes transacionais.",
    "privacy": "Direitos do titular (LGPD).",
    "health": "Liveness, readiness e saude da busca.",
    "default": "Operacoes da API.",
}

_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Requisicao invalida ou corpo recusado.",
    401: "Credencial ausente/invalida ou assinatura de webhook invalida.",
    403: "Autenticado, mas sem permissao para o recurso.",
    404: "Recurso inexistente no tenant autenticado.",
    409: "Conflito de estado, concorrencia ou idempotencia.",
    413: "Corpo maior que o limite aceito.",
    422: "Payload invalido ou chave de idempotencia reutilizada com outro payload.",
    429: "Limite de requisicoes excedido (Retry-After).",
    500: "Erro interno inesperado.",
    503: "Dependencia externa indisponivel.",
}

_ERROR_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Content Too Large",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}

# Exemplos das rotas principais. Chave: (metodo, path do OpenAPI).
_OPERATION_EXAMPLES: dict[tuple[str, str], dict[str, Any]] = {
    ("post", "/api/v1/auth/login"): {
        "request": {"email": "compras@empresa.example", "password": "senha-de-exemplo"},
        "response": {
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "refresh_token": "rt_...",
            "token_type": "bearer",
            "expires_in": 1800,
        },
        "response_status": "200",
    },
    ("post", "/api/v1/orders"): {
        "request": {
            "items": [{"product_id": "0b6f1f7e-8f4c-4f7a-9a4d-2b7f6c1d9e10", "quantity": 2}],
            "payment_method": "PIX",
            "po_number": "PO-2026-001",
            "notes": "Entrega no CD do centro de distribuicao.",
        },
        "response": {
            "id": "5a8c0e6b-7a4d-4d7e-9c1a-3f2b6d8e0a11",
            "company_id": "1f0c3a2b-4d5e-4f60-8a7b-9c1d2e3f4a5b",
            "status": "RECEIVED",
            "currency": "BRL",
            "subtotal": "49.80",
            "discount_total": "0.00",
            "shipping_total": "0.00",
            "tax_total": "0.00",
            "total": "49.80",
            "items": [
                {
                    "sku": "EPI-LUV-001",
                    "product_name": "Luva de Seguranca",
                    "quantity": 2,
                    "unit_price": "24.90",
                    "base_unit_price": "24.90",
                    "tier_min_quantity": None,
                    "line_total": "49.80",
                    "content_locale": "pt-BR",
                }
            ],
            "created_at": "2026-10-22T12:00:00Z",
            "content_locale": "pt-BR",
        },
        "response_status": "201",
    },
    ("post", "/api/v1/payments"): {
        "request": {
            "order_id": "5a8c0e6b-7a4d-4d7e-9c1a-3f2b6d8e0a11",
            "method": "PIX",
        },
        "response": {
            "id": "9d2e4f6a-1b3c-4d5e-8f70-1a2b3c4d5e6f",
            "company_id": "1f0c3a2b-4d5e-4f60-8a7b-9c1d2e3f4a5b",
            "order_id": "5a8c0e6b-7a4d-4d7e-9c1a-3f2b6d8e0a11",
            "invoice_id": None,
            "method": "PIX",
            "amount": "47.31",
            "discount_amount": "2.49",
            "status": "PENDING",
            "provider": "FAKE_PIX",
            "provider_reference": "PIX-5a8c0e6b",
            "created_at": "2026-10-22T12:01:00Z",
            "paid_at": None,
            "checkout_url": None,
        },
        "response_status": "201",
    },
    ("post", "/api/v1/admin/catalog/products"): {
        "request": {
            "sku": "EPI-LUV-001",
            "name": "Luva de Seguranca",
            "description": "Luva de protecao para uso geral.",
            "category_id": "b1a2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "brand_id": "c1b2a3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "base_unit_price": "24.90",
            "currency": "BRL",
        },
        "response": {
            "id": "d1c2b3a4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "sku": "EPI-LUV-001",
            "name": "Luva de Seguranca",
            "slug": "epi-luv-001",
            "status": "DRAFT",
            "version": 1761134400000,
        },
        "response_status": "201",
    },
    ("get", "/api/v1/search/products"): {
        "response": {
            "items": [
                {
                    "id": "0b6f1f7e-8f4c-4f7a-9a4d-2b7f6c1d9e10",
                    "sku": "EPI-LUV-001",
                    "name": "Luva de Seguranca",
                    "base_unit_price": None,
                    "price_on_request": True,
                    "content_locale": "pt-BR",
                    "fallback": False,
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "search_mode": "lexical",
            "content_locale": "pt-BR",
        },
        "response_status": "200",
    },
}


def _depends_on(dependant: Any, target: Any, *, seen: set[int] | None = None) -> bool:
    """Procura ``target`` na arvore de dependencias de uma rota."""
    if seen is None:
        seen = set()
    if id(dependant) in seen:
        return False
    seen.add(id(dependant))
    for dependency in getattr(dependant, "dependencies", ()) or ():
        if getattr(dependency, "call", None) is target:
            return True
        if _depends_on(dependency, target, seen=seen):
            return True
    return False


def _route_metadata(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    metadata: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or ():
            metadata[(method.lower(), route.path)] = route
    return metadata


def _humanize(name: str) -> str:
    cleaned = name.replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Operacao"


def _problem_components() -> dict[str, Any]:
    schema = ProblemDetails.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", {})
    components: dict[str, Any] = {"ProblemDetails": schema}
    components.update(definitions)
    return components


def _problem_example(status: int) -> dict[str, Any]:
    return {
        "type": f"urn:forja:problem:http_{status}",
        "title": _ERROR_TITLES[status],
        "status": status,
        "detail": _ERROR_DESCRIPTIONS[status],
        "instance": "/api/v1/recurso",
        "request_id": "0f9a4b2c7d8e4f1a9b3c5d6e7f8091a2",
        "trace_id": "0f9a4b2c7d8e4f1a9b3c5d6e7f8091a2",
    }


def _error_response(status: int) -> dict[str, Any]:
    response: dict[str, Any] = {
        "description": _ERROR_DESCRIPTIONS[status],
        "content": {
            _PROBLEM_MEDIA_TYPE: {
                "schema": {"$ref": _PROBLEM_REF},
                "example": _problem_example(status),
            }
        },
    }
    if status == 429:
        response["headers"] = {
            "Retry-After": {
                "description": "Segundos ate a proxima tentativa permitida.",
                "schema": {"type": "integer"},
            }
        }
    return response


def _required_auth(route: APIRoute) -> bool:
    return _depends_on(route.dependant, get_current_auth)


def _optional_auth(route: APIRoute) -> bool:
    return _depends_on(route.dependant, get_optional_auth)


def _error_statuses(
    *, path: str, method: str, requires_auth: bool, optional_auth: bool
) -> set[int]:
    statuses: set[int] = {422, 429, 500}
    if requires_auth or optional_auth or path == "/api/v1/auth/login":
        statuses.add(401)
    if requires_auth and (
        path.startswith("/api/v1/admin")
        or path.endswith("/approve")
        or path.endswith("/refund")
        or path.endswith("/reconcile")
        or "/translations/" in path
    ):
        statuses.add(403)
    if "{" in path:
        statuses.add(404)
    if method in _WRITE_METHODS:
        statuses.add(400)
        statuses.add(409)
    if path in {"/api/v1/payments/webhook", "/api/v1/payments/stripe/webhook"}:
        statuses.update({400, 401, 413})
    if path.startswith(("/health", "/api/v1/search", "/api/v1/payments")):
        statuses.add(503)
    return statuses


def _ensure_summary(operation: dict[str, Any], route: APIRoute) -> None:
    summary = operation.get("summary") or route.summary
    if not summary:
        summary = _humanize(route.name)
    operation["summary"] = summary


def _ensure_tags(operation: dict[str, Any]) -> None:
    tags = operation.get("tags") or ["default"]
    operation["tags"] = tags


def _ensure_security(operation: dict[str, Any], route: APIRoute) -> None:
    if _required_auth(route):
        operation["security"] = [{"bearerAuth": []}]
    elif _optional_auth(route):
        operation["security"] = [{"bearerAuth": []}, {}]
    elif route.path.endswith("/approve"):
        operation["security"] = [{"adminKey": []}]


def _ensure_error_responses(operation: dict[str, Any], route: APIRoute, method: str) -> None:
    responses = operation.setdefault("responses", {})
    statuses = _error_statuses(
        path=route.path,
        method=method,
        requires_auth=_required_auth(route),
        optional_auth=_optional_auth(route),
    )
    for status in sorted(statuses):
        key = str(status)
        if key not in responses:
            responses[key] = _error_response(status)
        else:
            response = responses[key]
            response.setdefault("description", _ERROR_DESCRIPTIONS[status])
            response.setdefault(
                "content",
                {
                    _PROBLEM_MEDIA_TYPE: {
                        "schema": {"$ref": _PROBLEM_REF},
                        "example": _problem_example(status),
                    }
                },
            )


def _ensure_idempotency_headers(operation: dict[str, Any]) -> None:
    parameters = operation.get("parameters") or []
    has_key = any(
        str(parameter.get("name", "")).lower() == "idempotency-key"
        for parameter in parameters
        if isinstance(parameter, dict)
    )
    if not has_key:
        return
    responses = operation.get("responses") or {}
    for status, response in responses.items():
        if not isinstance(response, dict):
            continue
        if status.startswith("2"):
            response.setdefault("headers", {})["Idempotent-Replayed"] = {
                "description": "true quando a resposta original foi reaproveitada.",
                "schema": {"type": "string"},
            }
        if status == "409":
            response.setdefault("headers", {})["Retry-After"] = {
                "description": "Segundos antes de repetir a mesma Idempotency-Key.",
                "schema": {"type": "integer"},
            }


def _ensure_example(operation: dict[str, Any], method: str, path: str) -> None:
    example = _OPERATION_EXAMPLES.get((method, path))
    if example is None:
        return
    request_example = example.get("request")
    if request_example is not None:
        request_body = operation.get("requestBody")
        if isinstance(request_body, dict):
            content = request_body.setdefault("content", {})
            media = content.setdefault("application/json", {})
            media.setdefault("example", request_example)
    response_example = example.get("response")
    if response_example is not None:
        status = str(example.get("response_status", "200"))
        response = operation.get("responses", {}).get(status)
        if isinstance(response, dict):
            content = response.setdefault("content", {})
            media = content.setdefault("application/json", {})
            media.setdefault("example", response_example)


def enrich_openapi_schema(schema: dict[str, Any], app: FastAPI) -> dict[str, Any]:
    """Aplica metadados e respostas de erro ao esquema gerado pelo FastAPI."""
    info = schema.setdefault("info", {})
    info["title"] = info.get("title") or "Forja B2B API"
    info["version"] = info.get("version") or app.version
    info["description"] = (
        "API REST multi-tenant da Forja B2B. Autenticacao por JWT (Bearer), "
        "isolamento por empresa via RLS e erros no formato Problem Details "
        "(RFC 9457) em application/problem+json."
    )
    info["contact"] = {"name": "Forja B2B"}
    info["license"] = {"name": "[A DEFINIR pelo responsável]"}

    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, definition in _problem_components().items():
        schemas.setdefault(name, definition)
    components.setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT de acesso emitido por /api/v1/auth/login ou /oauth/exchange.",
    }
    components["securitySchemes"]["adminKey"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-Admin-Key",
        "description": "Chave de operador de plataforma (aprovacao de empresas).",
    }

    routes = _route_metadata(app)
    used_tags: set[str] = set()
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            route = routes.get((method.lower(), path))
            if route is None:
                continue
            if not isinstance(operation, dict):
                continue
            _ensure_summary(operation, route)
            _ensure_tags(operation)
            _ensure_security(operation, route)
            _ensure_error_responses(operation, route, method.lower())
            _ensure_idempotency_headers(operation)
            _ensure_example(operation, method.lower(), path)
            used_tags.update(operation["tags"])

    schema["tags"] = [
        {"name": tag, "description": _TAG_DESCRIPTIONS.get(tag, _TAG_DESCRIPTIONS["default"])}
        for tag in sorted(used_tags)
    ]
    return schema


def configure_openapi(app: FastAPI) -> None:
    """Instala o enriquecimento no app (idempotente e cacheado pelo FastAPI)."""
    original = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = enrich_openapi_schema(original(), app)
        app.openapi_schema = schema
        return schema

    setattr(app, "openapi", custom_openapi)  # noqa: B010 - atribuicao de metodo no app
