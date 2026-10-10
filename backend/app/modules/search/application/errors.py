"""Erros de aplicacao do contexto de busca (mapeados para HTTP/RFC 7807).

`SearchUnavailableError` representa o motor de busca inacessivel (conexao,
timeout ou 5xx) e e distinto de "sem resultados", que nao e erro.
`SearchIndexError` representa falha na construcao/reconciliacao do indice
derivado (nenhum dado comercial e perdido: o PostgreSQL e a fonte de verdade).
"""

from __future__ import annotations

from app.core.errors import AppError


class SearchUnavailableError(AppError):
    """Motor de busca indisponivel (conexao, timeout ou resposta 5xx)."""

    status_code = 503
    title = "Service Unavailable"
    code = "search_unavailable"


class SearchIndexError(Exception):
    """Falha na construcao/reconciliacao do indice de busca."""


class InvalidSearchQueryError(AppError):
    """Parametros de busca invalidos (paginacao, tamanho do texto etc.)."""

    status_code = 400
    title = "Bad Request"
    code = "invalid_search_query"
