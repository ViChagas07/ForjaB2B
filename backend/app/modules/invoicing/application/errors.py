"""Erros de aplicacao do contexto de faturamento (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class OrderNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "order_not_found"


class OrderNotInvoiceableError(AppError):
    """Pedido nao faturavel (PIX sem credito, ou estado ja avançado)."""

    status_code = 409
    title = "Conflict"
    code = "order_not_invoiceable"


class InvoiceNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "invoice_not_found"


class InsufficientCreditError(AppError):
    """Reserva de credito menor que o valor a faturar."""

    status_code = 409
    title = "Conflict"
    code = "insufficient_credit"


class IdempotencyConflictError(AppError):
    status_code = 409
    title = "Conflict"
    code = "idempotency_conflict"
