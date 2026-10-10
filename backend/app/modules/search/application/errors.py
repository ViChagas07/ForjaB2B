"""Erros de aplicacao do contexto de busca (mapeados para HTTP/RFC 7807).

`SearchUnavailableError` representa o motor de busca inacessivel (conexao,
timeout ou 5xx) e e distinto de "sem resultados", que nao e erro.
"""

from __future__ import annotations

from app.core.errors import AppError


class SearchUnavailableError(AppError):
    """Motor de busca indisponivel (conexao, timeout ou resposta 5xx)."""

    status_code = 503
    title = "Service Unavailable"
    code = "search_unavailable"
