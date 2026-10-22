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


class StripeNotConfiguredError(AppError):
    """Cartao solicitado sem STRIPE_SECRET_KEY configurada."""

    status_code = 503
    title = "Service Unavailable"
    code = "stripe_not_configured"


class StripeWebhookNotConfiguredError(AppError):
    """Webhook Stripe chamado sem STRIPE_WEBHOOK_SECRET (whsec_)."""

    status_code = 503
    title = "Service Unavailable"
    code = "stripe_webhook_not_configured"


class PaymentProviderError(AppError):
    """Falha ao criar a sessao/cobranca no provedor de pagamento."""

    status_code = 502
    title = "Bad Gateway"
    code = "payment_provider_error"
