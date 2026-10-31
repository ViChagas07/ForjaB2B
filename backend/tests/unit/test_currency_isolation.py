"""Isolamento da moeda de EXIBICAO em pedidos e pagamentos.

A moeda escolhida no storefront e apenas visual. Qualquer tentativa de envia-la
no corpo de criacao de pedido/pagamento deve ser rejeitada pelo schema estrito
(`extra="forbid"`), sem alterar o valor cobrado em BRL.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.modules.ordering.interface.schemas import CreateOrderRequest
from app.modules.payment.interface.schemas import InitiatePaymentRequest

_ORDER = {
    "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
    "payment_method": "PIX",
    "idempotency_key": "currency-isolation-1",
}

_PAYMENT = {
    "order_id": str(uuid.uuid4()),
    "method": "PIX",
    "idempotency_key": "currency-isolation-pay-1",
}

_DISPLAY_CURRENCY_FIELDS = ("currency", "display_currency", "fx_currency", "rates")


@pytest.mark.parametrize("field", _DISPLAY_CURRENCY_FIELDS)
def test_pedido_rejeita_campo_de_moeda_de_exibicao(field: str) -> None:
    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate({**_ORDER, field: "USD"})


@pytest.mark.parametrize("field", _DISPLAY_CURRENCY_FIELDS)
def test_pagamento_rejeita_campo_de_moeda_de_exibicao(field: str) -> None:
    with pytest.raises(ValidationError):
        InitiatePaymentRequest.model_validate({**_PAYMENT, field: "USD"})


def test_payloads_validos_nao_carregam_moeda() -> None:
    order = CreateOrderRequest.model_validate(_ORDER)
    payment = InitiatePaymentRequest.model_validate(_PAYMENT)

    assert "currency" not in order.model_dump()
    assert "display_currency" not in order.model_dump()
    assert "currency" not in payment.model_dump()
    assert "display_currency" not in payment.model_dump()
