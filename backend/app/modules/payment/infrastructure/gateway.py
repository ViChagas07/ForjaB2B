"""Adaptador Fake/local do provedor de pagamento (deterministico e local).

Nenhuma chamada real a servico pago: o gateway gera referencias deterministas
(PIX/BOLETO por pedido) ou aleatorias por pagamento (cartao), reproduziveis em
teste. Em producao real, um adaptador Stripe/PIX substituiria esta classe sem
alterar a porta ``PaymentGateway``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.modules.payment.application.ports import GatewayInstruction
from app.modules.payment.domain.enums import PaymentMethod


class FakePaymentGateway:
    """Implementacao fake da porta PaymentGateway (local, sem credenciais)."""

    async def initiate(
        self, *, method: PaymentMethod, amount: Decimal, order_id: uuid.UUID
    ) -> GatewayInstruction:
        if method == PaymentMethod.PIX:
            return GatewayInstruction(provider="FAKE_PIX", provider_reference=f"PIX-{order_id}")
        if method == PaymentMethod.CARD:
            return GatewayInstruction(
                provider="FAKE_CARD", provider_reference=f"pi_{uuid.uuid4().hex[:24]}"
            )
        return GatewayInstruction(provider="FAKE_BOLETO", provider_reference=f"BOLETO-{order_id}")
