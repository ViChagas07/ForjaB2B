"""Erros de aplicacao do contexto de credito (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class CreditAccountNotFoundError(AppError):
    """Empresa sem conta de credito."""

    status_code = 404
    title = "Not Found"
    code = "credit_account_not_found"


class InsufficientCreditError(AppError):
    """Reserva acima do limite disponivel."""

    status_code = 409
    title = "Conflict"
    code = "insufficient_credit"


class IdempotencyConflictError(AppError):
    """Mesma idempotency_key com payload conflitante."""

    status_code = 409
    title = "Conflict"
    code = "idempotency_conflict"
