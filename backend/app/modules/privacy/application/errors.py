"""Erros de aplicacao do contexto de privacidade (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class PersonalDataNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "personal_data_not_found"
