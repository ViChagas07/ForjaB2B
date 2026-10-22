"""Adaptadores do provedor de pagamento.

- ``FakePaymentGateway``: determinístico e local (PIX/BOLETO e fallback de CARD
  quando o Stripe nao esta configurado).
- ``StripeCheckoutGateway``: cria uma Checkout Session real no Stripe e devolve
  a URL hospedada para o navegador. O cartao nunca passa pelos nossos servidores
  (Checkout hospedado; sem dados de cartao no backend).
- ``PaymentGatewayRouter``: escolhe Stripe para CARD quando habilitado.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.modules.payment.application.errors import (
    PaymentProviderError,
    StripeNotConfiguredError,
)
from app.modules.payment.application.ports import GatewayInstruction
from app.modules.payment.domain.enums import PaymentMethod


class FakePaymentGateway:
    """Implementacao fake da porta PaymentGateway (local, sem credenciais)."""

    async def initiate(
        self,
        *,
        method: PaymentMethod,
        amount: Decimal,
        currency: str,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str = "pt-BR",
    ) -> GatewayInstruction:
        if method == PaymentMethod.PIX:
            return GatewayInstruction(provider="FAKE_PIX", provider_reference=f"PIX-{order_id}")
        if method == PaymentMethod.CARD:
            return GatewayInstruction(
                provider="FAKE_CARD", provider_reference=f"pi_{uuid.uuid4().hex[:24]}"
            )
        return GatewayInstruction(provider="FAKE_BOLETO", provider_reference=f"BOLETO-{order_id}")


class StripeCheckoutGateway:
    """Cria Checkout Sessions no Stripe (modo hospedado, cartao)."""

    def __init__(
        self,
        *,
        api_key: str,
        frontend_base_url: str,
        success_path: str = "/checkout/success",
        cancel_path: str = "/checkout/cancel",
    ) -> None:
        self._api_key = api_key
        self._frontend_base_url = frontend_base_url.rstrip("/")
        self._success_path = success_path
        self._cancel_path = cancel_path

    async def initiate(
        self,
        *,
        method: PaymentMethod,
        amount: Decimal,
        currency: str,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str = "pt-BR",
    ) -> GatewayInstruction:
        if method != PaymentMethod.CARD:
            raise PaymentProviderError()
        return await asyncio.to_thread(
            self._create_session,
            amount=amount,
            currency=currency,
            order_id=order_id,
            company_id=company_id,
            locale=locale,
        )

    def _create_session(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str,
    ) -> GatewayInstruction:
        import stripe

        unit_amount = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
        if unit_amount <= 0:
            raise PaymentProviderError()

        metadata = {
            "order_id": str(order_id),
            "company_id": str(company_id),
        }
        success_url = (
            f"{self._frontend_base_url}/{locale}{self._success_path}"
            f"?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{self._frontend_base_url}/{locale}{self._cancel_path}?order_id={order_id}"

        try:
            session = stripe.checkout.Session.create(
                api_key=self._api_key,
                mode="payment",
                allowed_payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": currency.lower(),
                            "unit_amount": unit_amount,
                            "product_data": {"name": f"Forja B2B - Pedido {order_id}"},
                        },
                        "quantity": 1,
                    }
                ],
                client_reference_id=str(order_id),
                metadata=metadata,
                payment_intent_data={"metadata": metadata},
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe.error.StripeError as exc:  # pragma: no cover - rede/provedor
            raise PaymentProviderError() from exc

        session_id = getattr(session, "id", None)
        checkout_url = getattr(session, "url", None)
        if not session_id or not checkout_url:
            raise PaymentProviderError()
        return GatewayInstruction(
            provider="STRIPE",
            provider_reference=str(session_id),
            checkout_url=str(checkout_url),
        )


class PaymentGatewayRouter:
    """Encaminha CARD para o Stripe (quando configurado) e o resto para o fake."""

    def __init__(self, *, fake: FakePaymentGateway, stripe: StripeCheckoutGateway | None) -> None:
        self._fake = fake
        self._stripe = stripe

    async def initiate(
        self,
        *,
        method: PaymentMethod,
        amount: Decimal,
        currency: str,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str = "pt-BR",
    ) -> GatewayInstruction:
        if method == PaymentMethod.CARD:
            if self._stripe is None:
                raise StripeNotConfiguredError()
            return await self._stripe.initiate(
                method=method,
                amount=amount,
                currency=currency,
                order_id=order_id,
                company_id=company_id,
                locale=locale,
            )
        return await self._fake.initiate(
            method=method,
            amount=amount,
            currency=currency,
            order_id=order_id,
            company_id=company_id,
            locale=locale,
        )
