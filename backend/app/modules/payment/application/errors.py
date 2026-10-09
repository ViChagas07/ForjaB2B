"""Erros de aplicacao do contexto de pagamento (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class OrderNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "order_not_found"


class OrderNotPayableError(AppError):
    status_code = 409
    title = "Conflict"
    code = "order_not_payable"


class InvoiceNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "invoice_not_found"


class InvoiceNotPayableError(AppError):
    status_code = 409
    title = "Conflict"
    code = "invoice_not_payable"


class PaymentNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "payment_not_found"


class IdempotencyConflictError(AppError):
    status_code = 409
    title = "Conflict"
    code = "idempotency_conflict"


class InvalidWebhookEventError(AppError):
    status_code = 422
    title = "Unprocessable Entity"
    code = "invalid_webhook_event"


class WebhookSignatureError(AppError):
    status_code = 401
    title = "Unauthorized"
    code = "invalid_webhook_signature"
