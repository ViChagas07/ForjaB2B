"""Regras de dominio da notificacao (pure Python, sem frameworks).

Constroi o assunto/corpo do e-mail a partir do tipo de evento e do idioma do
destinatario. Templates minimos e explicitos (simulacao de portfolio), sem
motor de template externo; a localizacao faz fallback para ``pt-BR``.
"""

from __future__ import annotations

from app.modules.notification.domain.enums import NotificationEventType

_DEFAULT_LOCALE = "pt-BR"

_TEMPLATES: dict[tuple[str, str], tuple[str, str]] = {
    (NotificationEventType.ORDER_CREATED.value, "pt-BR"): (
        "Pedido recebido",
        "Seu pedido {order_id} foi recebido e esta em processamento.",
    ),
    (NotificationEventType.ORDER_CREATED.value, "en"): (
        "Order received",
        "Your order {order_id} has been received and is being processed.",
    ),
    (NotificationEventType.INVOICE_ISSUED.value, "pt-BR"): (
        "Fatura emitida",
        "A fatura {order_id} foi emitida e aguarda pagamento.",
    ),
    (NotificationEventType.INVOICE_ISSUED.value, "en"): (
        "Invoice issued",
        "Invoice {order_id} has been issued and is awaiting payment.",
    ),
    (NotificationEventType.PAYMENT_CONFIRMED.value, "pt-BR"): (
        "Pagamento confirmado",
        "O pagamento do pedido {order_id} foi confirmado.",
    ),
    (NotificationEventType.PAYMENT_CONFIRMED.value, "en"): (
        "Payment confirmed",
        "Payment for order {order_id} has been confirmed.",
    ),
}


def locale_key(locale: str | None) -> str:
    """Normaliza o idioma para a chave de template (fallback pt-BR)."""
    if locale in ("en", "en-US", "en-GB"):
        return "en"
    return _DEFAULT_LOCALE


def build_email(*, event_type: str, locale: str | None, order_id: str) -> tuple[str, str]:
    """Devolve (subject, body) para um evento, com fallback de template/local."""
    key = locale_key(locale)
    subject, body = _TEMPLATES.get(
        (event_type, key),
        _TEMPLATES.get((event_type, _DEFAULT_LOCALE), ("Notificacao", "{order_id}")),
    )
    return subject, body.format(order_id=order_id)
