"""Testes unitarios da integracao Stripe (gateway, config e eventos)."""

from __future__ import annotations

import types
import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
import stripe

from app.core.config import Settings
from app.modules.payment.application.errors import StripeNotConfiguredError
from app.modules.payment.application.stripe_events import map_stripe_checkout_event
from app.modules.payment.domain.enums import PaymentMethod, PaymentStatus
from app.modules.payment.infrastructure.gateway import (
    FakePaymentGateway,
    PaymentGatewayRouter,
    StripeCheckoutGateway,
)

_COMPANY = uuid.UUID("bbbb0000-0000-4000-8000-000000000001")
_ORDER = uuid.UUID("bbbb0000-0000-4000-8000-000000000002")


def test_config_aceita_chave_sk_no_alias_historico() -> None:
    settings = Settings(
        _env_file=None,
        stripe_webhook_secret="sk_test_123",  # noqa: S106 - credencial dummy de teste
    )

    assert settings.stripe_enabled is True
    assert settings.effective_stripe_secret_key == "sk_test_123"
    assert settings.effective_stripe_webhook_secret is None


def test_config_exige_whsec_para_webhook() -> None:
    settings = Settings(
        _env_file=None,
        stripe_webhook_secret="whsec_abc",  # noqa: S106 - credencial dummy de teste
    )

    assert settings.stripe_enabled is False
    assert settings.effective_stripe_secret_key is None
    assert settings.effective_stripe_webhook_secret == "whsec_abc"


def test_config_aceita_ambas_as_credenciais() -> None:
    settings = Settings(
        _env_file=None,
        stripe_secret_key="sk_test_abc",  # noqa: S106 - credencial dummy de teste
        stripe_webhook_secret="whsec_def",  # noqa: S106 - credencial dummy de teste
    )

    assert settings.stripe_enabled is True
    assert settings.effective_stripe_secret_key == "sk_test_abc"
    assert settings.effective_stripe_webhook_secret == "whsec_def"


@pytest.mark.asyncio
async def test_gateway_cria_checkout_session_com_valor_e_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> types.SimpleNamespace:
        captured.update(kwargs)
        return types.SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.com/c/pay/cs_test_123",
        )

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    gateway = StripeCheckoutGateway(
        api_key="sk_test_123",
        frontend_base_url="https://forja-b2b.vercel.app/",
    )

    instruction = await gateway.initiate(
        method=PaymentMethod.CARD,
        amount=Decimal("32.90"),
        currency="BRL",
        order_id=_ORDER,
        company_id=_COMPANY,
        locale="ar",
    )

    assert instruction.provider == "STRIPE"
    assert instruction.provider_reference == "cs_test_123"
    assert instruction.checkout_url == "https://checkout.stripe.com/c/pay/cs_test_123"
    line_items = cast(list[dict[str, Any]], captured["line_items"])
    price_data = cast(dict[str, Any], line_items[0]["price_data"])
    assert price_data["currency"] == "brl"
    assert price_data["unit_amount"] == 3290
    assert captured["client_reference_id"] == str(_ORDER)
    assert captured["metadata"] == {
        "order_id": str(_ORDER),
        "company_id": str(_COMPANY),
    }
    assert "/ar/checkout/success" in captured["success_url"]
    assert "/ar/checkout/cancel" in captured["cancel_url"]


@pytest.mark.asyncio
async def test_router_exige_stripe_para_cartao() -> None:
    router = PaymentGatewayRouter(fake=FakePaymentGateway(), stripe=None)

    with pytest.raises(StripeNotConfiguredError):
        await router.initiate(
            method=PaymentMethod.CARD,
            amount=Decimal("10.00"),
            currency="BRL",
            order_id=_ORDER,
            company_id=_COMPANY,
        )

    instruction = await router.initiate(
        method=PaymentMethod.PIX,
        amount=Decimal("10.00"),
        currency="BRL",
        order_id=_ORDER,
        company_id=_COMPANY,
    )
    assert instruction.provider == "FAKE_PIX"


def _event(event_type: str, *, payment_status: str = "paid") -> dict[str, object]:
    return {
        "id": "evt_123",
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_status": payment_status,
                "metadata": {"company_id": str(_COMPANY)},
            }
        },
    }


def test_evento_completed_pago_vira_paid() -> None:
    mapped = map_stripe_checkout_event(_event("checkout.session.completed"))

    assert mapped is not None
    assert mapped.target_status == PaymentStatus.PAID
    assert mapped.company_id == _COMPANY
    assert mapped.provider_reference == "cs_test_123"


def test_evento_completed_unpaid_e_ignorado() -> None:
    assert (
        map_stripe_checkout_event(_event("checkout.session.completed", payment_status="unpaid"))
        is None
    )


def test_evento_async_failed_vira_failed() -> None:
    mapped = map_stripe_checkout_event(_event("checkout.session.async_payment_failed"))

    assert mapped is not None
    assert mapped.target_status == PaymentStatus.FAILED


def test_evento_desconhecido_ou_sem_metadata_e_ignorado() -> None:
    assert map_stripe_checkout_event(_event("payment_intent.succeeded")) is None

    event = _event("checkout.session.completed")
    data = cast(dict[str, Any], event["data"])
    session = cast(dict[str, Any], data["object"])
    session.pop("metadata")
    assert map_stripe_checkout_event(event) is None
