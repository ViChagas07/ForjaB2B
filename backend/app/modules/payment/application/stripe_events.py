"""Traducao de eventos do Stripe Checkout para o modelo interno.

Apenas eventos de ``checkout.session.*`` sao usados porque o
``provider_reference`` gravado no pagamento e o ID da Checkout Session. Eventos
de ``payment_intent.*`` nao sao mapeados: o PaymentIntent tambem tem metadata,
mas o ID nao coincide com a referencia persistida.

Eventos desconhecidos ou incompletos devolvem ``None`` e o webhook apenas
confirma o recebimento (HTTP 200) para evitar retentativas infinitas.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.payment.domain.enums import PaymentStatus

_PAID_EVENTS = frozenset({"checkout.session.completed", "checkout.session.async_payment_succeeded"})
_FAILED_EVENTS = frozenset({"checkout.session.async_payment_failed"})


@dataclass(frozen=True, kw_only=True)
class StripeCheckoutEvent:
    """Evento Stripe ja validado e traduzido para a maquina de estados."""

    event_id: str
    target_status: PaymentStatus
    company_id: uuid.UUID
    provider_reference: str


def _session_of(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = event.get("data")
    if not isinstance(data, Mapping):
        return None
    session = data.get("object")
    return session if isinstance(session, Mapping) else None


def _company_id_of(session: Mapping[str, Any]) -> uuid.UUID | None:
    metadata = session.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    raw = metadata.get("company_id")
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def map_stripe_checkout_event(event: Mapping[str, Any]) -> StripeCheckoutEvent | None:
    event_type = event.get("type")
    if event_type not in _PAID_EVENTS and event_type not in _FAILED_EVENTS:
        return None

    session = _session_of(event)
    if session is None:
        return None
    session_id = session.get("id")
    event_id = event.get("id")
    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(event_id, str) or not event_id:
        return None

    # Checkout concluido pode estar "unpaid" em metodos assincronos; nesse caso
    # aguardamos async_payment_succeeded/failed.
    if event_type == "checkout.session.completed" and session.get("payment_status") != "paid":
        return None

    company_id = _company_id_of(session)
    if company_id is None:
        return None

    target = PaymentStatus.FAILED if event_type in _FAILED_EVENTS else PaymentStatus.PAID
    return StripeCheckoutEvent(
        event_id=event_id,
        target_status=target,
        company_id=company_id,
        provider_reference=session_id,
    )
