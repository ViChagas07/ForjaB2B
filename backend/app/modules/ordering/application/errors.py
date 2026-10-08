"""Erros de aplicacao do contexto de pedidos (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class ProductNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "product_not_found"


class ProductNotSellableError(AppError):
    status_code = 409
    title = "Conflict"
    code = "product_not_sellable"


class QuantityBelowMinimumError(AppError):
    status_code = 422
    title = "Unprocessable Entity"
    code = "quantity_below_minimum"


class InsufficientCreditError(AppError):
    status_code = 409
    title = "Conflict"
    code = "insufficient_credit"


class CreditAccountNotFoundError(AppError):
    status_code = 409
    title = "Conflict"
    code = "credit_account_not_found"


class IdempotencyConflictError(AppError):
    status_code = 409
    title = "Conflict"
    code = "idempotency_conflict"


class OrderNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "order_not_found"


class EmptyOrderError(AppError):
    status_code = 422
    title = "Unprocessable Entity"
    code = "empty_order"


class InvalidOrderStateError(AppError):
    status_code = 409
    title = "Conflict"
    code = "invalid_order_state"
