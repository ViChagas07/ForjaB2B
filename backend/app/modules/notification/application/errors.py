"""Erros de aplicacao do contexto de notificacao (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class NotificationNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "notification_not_found"


class EmailTransientError(Exception):
    """Falha transitoria de envio (sera retentada)."""


class EmailPermanentError(Exception):
    """Falha permanente de envio (vai para dead-letter)."""
