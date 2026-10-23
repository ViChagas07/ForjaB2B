"""Endpoints do contexto de pagamento (iniciacao/consulta/webhook).

O webhook nao usa JWT: e um canal sistema-a-sistema autenticado por assinatura
HMAC-SHA256 do corpo (segredo compartilhado). O ``company_id`` vem DENTRO do
payload assinado (autenticado pela assinatura), nunca de header nao verificado.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import ValidationError

from app.application.idempotency import IdempotencyKeyRequiredError
from app.application.security import AuthContext
from app.core.logging import get_logger
from app.core.metrics import increment_payment_confirmed
from app.interface.deprecation import deprecated_route
from app.interface.deps import LocaleInfo, get_current_auth, get_locale_info
from app.interface.idempotency import IdempotencyGuard, get_idempotency_service
from app.interface.webhooks import read_limited_body, verify_hmac_signature
from app.modules.payment.application.errors import (
    InvalidWebhookEventError,
    PaymentForbiddenError,
    StripeWebhookNotConfiguredError,
    WebhookSignatureError,
)
from app.modules.payment.application.payment import (
    ConfirmPayment,
    GetPayment,
    InitiatePayment,
    ReconcileStripePayments,
    RefundPayment,
)
from app.modules.payment.application.ports import PaymentResult, PaymentView
from app.modules.payment.application.stripe_events import map_stripe_checkout_event
from app.modules.payment.domain.enums import PaymentStatus
from app.modules.payment.interface.schemas import (
    InitiatePaymentRequest,
    PaymentMethodsResponse,
    PaymentResponse,
    StripeReconcileResponse,
    StripeWebhookResponse,
    WebhookEventRequest,
    WebhookEventType,
    WebhookResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])

_logger = get_logger(__name__)

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


def _refund(request: Request) -> RefundPayment:
    return cast(RefundPayment, request.app.state.payment_refund)


def _reconcile(request: Request) -> ReconcileStripePayments:
    return cast(ReconcileStripePayments, request.app.state.payment_reconcile)


def _require_admin(auth: AuthContext) -> None:
    if auth.role != "ADMIN":
        raise PaymentForbiddenError()


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
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    locale_info: Annotated[LocaleInfo, Depends(get_locale_info)],
    use_case: Annotated[InitiatePayment, Depends(_initiate)],
    idempotency_header: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Obrigatorio. UUID ou string de 16 a 128 caracteres que identifica "
                "a tentativa; repeticoes com o mesmo payload devolvem a resposta original."
            ),
        ),
    ] = None,
) -> PaymentResponse:
    guard = IdempotencyGuard(
        request=request,
        auth=auth,
        service=get_idempotency_service(request),
        required=True,
        legacy_key=payload.idempotency_key,
    )
    await guard.start()
    if guard.key is None:  # pragma: no cover - required=True garante a chave
        raise IdempotencyKeyRequiredError("Envie o header Idempotency-Key (16 a 128 caracteres).")
    try:
        view = await use_case.initiate(
            company_id=auth.company_id,
            order_id=payload.order_id,
            method=payload.method,
            idempotency_key=guard.key,
            locale=locale_info.ui_locale,
        )
    except Exception:
        await guard.release()
        raise
    response = _to_response(view)
    await guard.complete(status.HTTP_201_CREATED, response.model_dump(mode="json"))
    return response


@router.post(
    "/stripe/reconcile",
    response_model=StripeReconcileResponse,
    status_code=status.HTTP_200_OK,
)
async def reconcile_stripe_payments(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[ReconcileStripePayments, Depends(_reconcile)],
) -> StripeReconcileResponse:
    """Concilia sessoes Stripe PENDING do tenant (webhooks perdidos)."""
    _require_admin(auth)
    report = await use_case.run(auth.company_id)
    return StripeReconcileResponse(
        checked=report.checked, applied=report.applied, skipped=report.skipped
    )


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
)
async def refund_payment(
    payment_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[RefundPayment, Depends(_refund)],
) -> PaymentResponse:
    """Estorna integralmente um pagamento Stripe PAID (somente ADMIN)."""
    _require_admin(auth)
    view = await use_case.refund(auth.company_id, payment_id)
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
    secrets = settings.stripe_webhook_secrets
    if not secrets:
        raise StripeWebhookNotConfiguredError()

    body = await read_limited_body(request, settings.webhook_max_body_bytes)
    if not signature:
        raise WebhookSignatureError()

    import stripe

    event = None
    last_error: Exception | None = None
    for secret in secrets:
        try:
            event = stripe.Webhook.construct_event(
                payload=body,
                sig_header=signature,
                secret=secret,
                tolerance=settings.webhook_timestamp_tolerance_seconds,
            )
            break
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            last_error = exc
    if event is None:
        raise WebhookSignatureError() from last_error

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


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
@deprecated_route(
    sunset=date(2027, 4, 30),
    successor="/api/v1/payments/stripe/webhook",
    reason="Webhook HMAC legado; use o webhook assinado do Stripe.",
)
async def payment_webhook(
    request: Request,
    use_case: Annotated[ConfirmPayment, Depends(_confirm)],
    signature: Annotated[str | None, Header(alias="X-Forja-Signature")] = None,
    timestamp: Annotated[str | None, Header(alias="X-Forja-Timestamp")] = None,
) -> WebhookResponse:
    # Le o corpo BRUTO antes de qualquer parse: a assinatura HMAC cobre os bytes
    # originais. Deixar o FastAPI/Pydantic consumir o stream antes da verificacao
    # invalidaria a comparacao e abriria brecha no controle de integridade.
    settings = request.app.state.settings
    body = await read_limited_body(request, settings.webhook_max_body_bytes)
    verify_hmac_signature(
        secrets=settings.payment_webhook_secrets,
        body=body,
        signature=signature,
        timestamp=timestamp,
        tolerance_seconds=settings.webhook_timestamp_tolerance_seconds,
    )
    if timestamp is None:
        # Compatibilidade temporaria: produtores antigos assinam apenas o corpo.
        # A rota esta depreciada; ver docs/API_VERSIONING.md.
        _logger.warning("webhook_legacy_without_timestamp")

    try:
        payload = WebhookEventRequest.model_validate_json(body)
    except ValidationError as exc:
        raise InvalidWebhookEventError() from exc
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
