"""Mapeamento de excecoes para Problem Details (RFC 7807).

Formato unico de erro da API: application/problem+json com `type` estavel,
`status`, `detail` seguro (sem stack trace nem dados internos), `instance`
(caminho da requisicao) e `trace_id` para correlacao com logs/traces.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.correlation import get_request_id
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.telemetry import current_trace_id
from app.domain.errors import DomainError
from app.interface.idempotency import IdempotentReplay
from app.interface.schemas import FieldError, ProblemDetails

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"
_PROBLEM_TYPE_BASE = "urn:forja:problem:"

_logger = get_logger(__name__)


def _correlation_id() -> str | None:
    return current_trace_id() or get_request_id()


def _problem_response(
    problem: ProblemDetails, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        headers=headers,
    )


def _status_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP Error"


def _build_problem(
    *,
    code: str,
    status: int,
    title: str,
    detail: str | None,
    request: Request,
    errors: list[FieldError] | None = None,
) -> ProblemDetails:
    return ProblemDetails(
        type=f"{_PROBLEM_TYPE_BASE}{code}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        request_id=get_request_id(),
        trace_id=_correlation_id(),
        errors=errors,
    )


def _validation_errors(exc: RequestValidationError) -> list[FieldError]:
    """Converte erros do Pydantic em lista por campo sem expor o valor enviado.

    ``ctx`` e ``input`` podem conter PII/segredos; apenas ``loc``, ``msg`` e
    ``type`` sao propagados, e o caminho perde o prefixo de origem
    (body/query/path) para ficar estavel entre transportes.
    """
    result: list[FieldError] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ())]
        if location and location[0] in {"body", "query", "path", "header", "cookie"}:
            location = location[1:]
        field = ".".join(location) or "request"
        message = str(error.get("msg", "Valor invalido"))
        code = str(error.get("type", "value_error"))
        result.append(FieldError(field=field, message=message, code=code))
    return result


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registrado apenas para AppError (ver register_exception_handlers).
    error = cast(AppError, exc)
    if error.status_code >= 500:
        _logger.error("app_error", error_code=error.code, status=error.status_code)
    problem = _build_problem(
        code=error.code,
        status=error.status_code,
        title=error.title,
        detail=error.detail,
        request=request,
    )
    return _problem_response(problem, headers=error.headers)


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registrado apenas para DomainError.
    error = cast(DomainError, exc)
    problem = _build_problem(
        code=error.code,
        status=400,
        title="Domain Error",
        detail=error.message,
        request=request,
    )
    return _problem_response(problem)


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registrado apenas para HTTPException do Starlette.
    error = cast(StarletteHTTPException, exc)
    status = error.status_code
    detail = error.detail if isinstance(error.detail, str) else _status_title(status)
    problem = _build_problem(
        code=f"http_{status}",
        status=status,
        title=_status_title(status),
        detail=detail,
        request=request,
    )
    return _problem_response(problem)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registrado apenas para RequestValidationError; o detalhe dos erros de
    # validacao do Pydantic nao e exposto (pode conter dados internos).
    error = cast(RequestValidationError, exc)
    problem = _build_problem(
        code="validation_error",
        status=422,
        title="Unprocessable Entity",
        detail="Os dados enviados violam o contrato da API.",
        request=request,
        errors=_validation_errors(error),
    )
    return _problem_response(problem)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Nunca vazar stack trace ou detalhe interno: apenas log estruturado.
    _logger.exception("unhandled_error", path=request.url.path)
    problem = _build_problem(
        code="internal_error",
        status=500,
        title="Internal Server Error",
        detail="Erro interno inesperado.",
        request=request,
    )
    return _problem_response(problem)


async def idempotent_replay_handler(request: Request, exc: Exception) -> Response:
    # Registrado apenas para IdempotentReplay; devolve a resposta original
    # gravada, com o header ``Idempotent-Replayed``.
    _ = request
    replay = cast(IdempotentReplay, exc)
    return Response(
        content=replay.response.body,
        status_code=replay.response.status_code,
        headers=dict(replay.response.headers),
        media_type=replay.response.media_type,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IdempotentReplay, idempotent_replay_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
