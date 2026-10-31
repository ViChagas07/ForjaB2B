"""Garante que o Stripe recebe o valor do pedido em BRL, nao a moeda de exibicao."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import stripe
from pytest import MonkeyPatch

from app.modules.payment.domain.enums import PaymentMethod
from app.modules.payment.infrastructure.gateway import StripeCheckoutGateway


def test_stripe_recebe_amount_em_centavos_e_currency_brl(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(id="cs_test_currency", url="https://checkout.stripe.test/cs")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    gateway = StripeCheckoutGateway(
        api_key="sk_test_currency",
        frontend_base_url="https://forja.test",
    )

    gateway._create_session(
        method=PaymentMethod.CARD,
        amount=Decimal("149.40"),
        currency="BRL",
        order_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        locale="pt-BR",
    )

    line_item = captured["line_items"]
    assert isinstance(line_item, list)
    price_data = line_item[0]["price_data"]
    assert price_data["currency"] == "brl"
    assert price_data["unit_amount"] == 14940
