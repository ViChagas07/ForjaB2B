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
    PaymentAmountTooLowError,
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
        if method not in (PaymentMethod.CARD, PaymentMethod.PIX):
            raise PaymentProviderError()
        return await asyncio.to_thread(
            self._create_session,
            method=method,
            amount=amount,
            currency=currency,
            order_id=order_id,
            company_id=company_id,
            locale=locale,
        )

    def _create_session(
        self,
        *,
        method: PaymentMethod,
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
        # Minimo do Stripe para BRL: R$ 0,50 por cobranca.
        if currency.upper() == "BRL" and unit_amount < 50:
            raise PaymentAmountTooLowError()

        metadata = {
            "order_id": str(order_id),
            "company_id": str(company_id),
        }
        success_url = (
            f"{self._frontend_base_url}/{locale}{self._success_path}"
            f"?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{self._frontend_base_url}/{locale}{self._cancel_path}?order_id={order_id}"

        payment_method = "card" if method == PaymentMethod.CARD else "pix"
        try:
            session = stripe.checkout.Session.create(
                api_key=self._api_key,
                mode="payment",
                allowed_payment_method_types=[payment_method],
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
                billing_address_collection="required",
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

    async def refund(self, *, provider_reference: str) -> None:
        await asyncio.to_thread(self._refund, provider_reference)

    def _refund(self, provider_reference: str) -> None:
        import stripe

        try:
            session = stripe.checkout.Session.retrieve(provider_reference, api_key=self._api_key)
            payment_intent = getattr(session, "payment_intent", None)
            if not payment_intent:
                raise PaymentProviderError()
            stripe.Refund.create(
                api_key=self._api_key,
                payment_intent=str(payment_intent),
            )
        except stripe.error.StripeError as exc:  # pragma: no cover - rede/provedor
            raise PaymentProviderError() from exc

    async def retrieve_status(self, *, provider_reference: str) -> str:
        return await asyncio.to_thread(self._retrieve_status, provider_reference)

    def _retrieve_status(self, provider_reference: str) -> str:
        import stripe

        try:
            session = stripe.checkout.Session.retrieve(provider_reference, api_key=self._api_key)
        except stripe.error.StripeError as exc:  # pragma: no cover - rede/provedor
            raise PaymentProviderError() from exc

        if getattr(session, "payment_status", None) == "paid":
            return "paid"
        if getattr(session, "status", None) == "expired":
            return "expired"
        return "pending"


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
        if method in (PaymentMethod.CARD, PaymentMethod.PIX):
            if self._stripe is None:
                if method == PaymentMethod.CARD:
                    raise StripeNotConfiguredError()
                return await self._fake.initiate(
                    method=method,
                    amount=amount,
                    currency=currency,
                    order_id=order_id,
                    company_id=company_id,
                    locale=locale,
                )
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

    async def refund(self, *, provider_reference: str) -> None:
        if self._stripe is None:
            raise StripeNotConfiguredError()
        await self._stripe.refund(provider_reference=provider_reference)

    async def retrieve_status(self, *, provider_reference: str) -> str:
        if self._stripe is None:
            raise StripeNotConfiguredError()
        return await self._stripe.retrieve_status(provider_reference=provider_reference)
