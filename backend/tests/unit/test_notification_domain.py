"""Testes unitarios do dominio de notificacao (templates e localizacao)."""

from __future__ import annotations

from app.modules.notification.domain.enums import NotificationEventType
from app.modules.notification.domain.notification import build_email, locale_key


def test_locale_key_fallback_pt_br() -> None:
    assert locale_key(None) == "pt-BR"
    assert locale_key("es") == "pt-BR"
    assert locale_key("en") == "en"
    assert locale_key("en-US") == "en"


def test_template_ordem_pt_br() -> None:
    subject, body = build_email(
        event_type=NotificationEventType.ORDER_CREATED.value,
        locale=None,
        order_id="abc-123",
    )
    assert subject == "Pedido recebido"
    assert "abc-123" in body


def test_template_ordem_en() -> None:
    subject, body = build_email(
        event_type=NotificationEventType.ORDER_CREATED.value,
        locale="en",
        order_id="abc-123",
    )
    assert subject == "Order received"
    assert "abc-123" in body


def test_template_fatura() -> None:
    subject, _ = build_email(
        event_type=NotificationEventType.INVOICE_ISSUED.value,
        locale="pt-BR",
        order_id="x",
    )
    assert subject == "Fatura emitida"


def test_template_pagamento() -> None:
    subject, _ = build_email(
        event_type=NotificationEventType.PAYMENT_CONFIRMED.value,
        locale="pt-BR",
        order_id="x",
    )
    assert subject == "Pagamento confirmado"


def test_template_evento_desconhecido_fallback() -> None:
    subject, body = build_email(event_type="unknown.event", locale="pt-BR", order_id="x")
    assert subject == "Notificacao"
    assert body == "x"
