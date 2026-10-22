"""Endpoints do contexto de pagamento (iniciacao/consulta/webhook).

O webhook nao usa JWT: e um canal sistema-a-sistema autenticado por assinatura
HMAC-SHA256 do corpo (segredo compartilhado). O ``company_id`` vem DENTRO do
payload assinado (autenticado pela assinatura), nunca de header nao verificado.
"""

from __future__ import annotations

import hmac
import uuid
from hashlib import sha256
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, status

from app.application.security import AuthContext
from app.core.metrics import increment_payment_confirmed
from app.interface.deps import LocaleInfo, get_current_auth, get_locale_info
from app.modules.payment.application.errors import (
    InvalidWebhookEventError,
    StripeWebhookNotConfiguredError,
    WebhookSignatureError,
)
from app.modules.payment.application.payment import ConfirmPayment, GetPayment, InitiatePayment
from app.modules.payment.application.ports import PaymentResult, PaymentView
from app.modules.payment.application.stripe_events import map_stripe_checkout_event
from app.modules.payment.domain.enums import PaymentStatus
from app.modules.payment.interface.schemas import (
    InitiatePaymentRequest,
    PaymentMethodsResponse,
    PaymentResponse,
    StripeWebhookResponse,
    WebhookEventRequest,
    WebhookEventType,
    WebhookResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])

_SIGNATURE_PREFIX = "sha256="
_EVENT_TO_STATUS: dict[WebhookEventType, PaymentStatus] = {
    WebhookEventType.PAYMENT_PAID: PaymentStatus.PAID,
    WebhookEventType.PAYMENT_FAILED: PaymentStatus.FAILED,
}


def _initiate(request: Request) -> InitiatePayment:
    return cast(InitiatePayment, request.app.state.payment_initiate)


def _confirm(request: Request) -> ConfirmPayment:
    return cast(ConfirmPayment, request.app.state.payment_confirm)


def _get(request: Request) -> GetPayment:
    return cast(GetPayment, request.app.state.payment_get)


def _to_response(view: PaymentView) -> PaymentResponse:
    return PaymentResponse(
        id=view.id,
        company_id=view.company_id,
        order_id=view.order_id,
        invoice_id=view.invoice_id,
        method=view.method,
        amount=view.amount,
        discount_amount=view.discount_amount,
        status=view.status,
        provider=view.provider,
        provider_reference=view.provider_reference,
        created_at=view.created_at,
        paid_at=view.paid_at,
        checkout_url=view.checkout_url,
    )


def _verify_signature(secret: str, body: bytes, signature: str | None) -> None:
    if not signature or not signature.startswith(_SIGNATURE_PREFIX):
        raise WebhookSignatureError()
    provided = signature[len(_SIGNATURE_PREFIX) :]
    expected = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise WebhookSignatureError()


@router.get("/methods", response_model=PaymentMethodsResponse, status_code=status.HTTP_200_OK)
async def payment_methods(request: Request) -> PaymentMethodsResponse:
    """Meios disponiveis no checkout (CARD somente com Stripe configurado)."""
    settings = request.app.state.settings
    methods = ["PIX", "BOLETO"]
    if settings.stripe_enabled:
        methods.insert(1, "CARD")
    return PaymentMethodsResponse(methods=methods, stripe_enabled=settings.stripe_enabled)


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    payload: InitiatePaymentRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    locale_info: Annotated[LocaleInfo, Depends(get_locale_info)],
    use_case: Annotated[InitiatePayment, Depends(_initiate)],
) -> PaymentResponse:
    view = await use_case.initiate(
        company_id=auth.company_id,
        order_id=payload.order_id,
        method=payload.method,
        idempotency_key=payload.idempotency_key,
        locale=locale_info.ui_locale,
    )
    return _to_response(view)


@router.post(
    "/stripe/webhook",
    response_model=StripeWebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
    request: Request,
    use_case: Annotated[ConfirmPayment, Depends(_confirm)],
    signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> StripeWebhookResponse:
    """Webhook do Stripe: valida ``Stripe-Signature`` e aplica o evento.

    O corpo bruto e lido antes de qualquer parse porque a assinatura cobre os
    bytes originais. Eventos irrelevantes sao confirmados com 200 para o Stripe
    nao retentar; erros de assinatura respondem 401.
    """
    settings = request.app.state.settings
    secret = settings.effective_stripe_webhook_secret
    if secret is None:
        raise StripeWebhookNotConfiguredError()

    body = await request.body()
    if not signature:
        raise WebhookSignatureError()

    import stripe

    try:
        event = stripe.Webhook.construct_event(payload=body, sig_header=signature, secret=secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise WebhookSignatureError() from exc

    mapped = map_stripe_checkout_event(event.to_dict())
    if mapped is None:
        return StripeWebhookResponse(received=True, outcome=None)

    result: PaymentResult = await use_case.confirm(
        company_id=mapped.company_id,
        provider_reference=mapped.provider_reference,
        provider="STRIPE",
        event_id=mapped.event_id,
        target_status=mapped.target_status,
    )
    increment_payment_confirmed(method=result.payment.method, outcome=result.outcome)
    return StripeWebhookResponse(received=True, outcome=result.outcome)


@router.get("/{payment_id}", response_model=PaymentResponse, status_code=status.HTTP_200_OK)
async def get_payment(
    payment_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetPayment, Depends(_get)],
) -> PaymentResponse:
    return _to_response(await use_case.get(auth.company_id, payment_id))


@router.post("/webhook", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def payment_webhook(
    request: Request,
    use_case: Annotated[ConfirmPayment, Depends(_confirm)],
    signature: Annotated[str | None, Header(alias="X-Forja-Signature")] = None,
) -> WebhookResponse:
    # Le o corpo BRUTO antes de qualquer parse: a assinatura HMAC cobre os bytes
    # originais. Deixar o FastAPI/Pydantic consumir o stream antes da verificacao
    # invalidaria a comparacao e abriria brecha no controle de integridade.
    body = await request.body()
    secret = cast(str, request.app.state.settings.payment_webhook_secret)
    _verify_signature(secret, body, signature)

    payload = WebhookEventRequest.model_validate_json(body)
    target_status = _EVENT_TO_STATUS.get(payload.event_type)
    if target_status is None:  # pragma: no cover - enum ja valida o contrato
        raise InvalidWebhookEventError()

    result: PaymentResult = await use_case.confirm(
        company_id=payload.company_id,
        provider_reference=payload.provider_reference,
        provider=payload.provider,
        event_id=payload.event_id,
        target_status=target_status,
    )
    increment_payment_confirmed(
        method=result.payment.method,
        outcome=result.outcome,
    )
    return WebhookResponse(
        outcome=result.outcome,
        payment_id=result.payment.id,
        status=result.payment.status,
    )
