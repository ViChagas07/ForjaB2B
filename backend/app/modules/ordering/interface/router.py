"""Endpoints do contexto de pedidos (criacao/consulta/cancelamento).

O pedido e tenant-scoped; company_id/buyer vêm do token. Nenhum preco/total/
credito do cliente e aceito (recalculado no servidor).
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.application.idempotency import IdempotencyKeyRequiredError
from app.application.security import AuthContext
from app.interface.deps import get_current_auth, get_locale
from app.interface.idempotency import IdempotencyGuard, get_idempotency_service
from app.modules.ordering.application.coupon_checkout import (
    CouponPreviewResult,
    PreviewCoupon,
)
from app.modules.ordering.application.customer_overview import (
    CustomerOverview,
    DeleteCustomerOrder,
    GetCustomerOverview,
)
from app.modules.ordering.application.order import CancelOrder, CreateOrder, GetOrder
from app.modules.ordering.application.ports import (
    AvailableCouponView,
    OrderItemInput,
    OrderView,
)
from app.modules.ordering.interface.schemas import (
    AvailableCouponResponse,
    CouponPreviewRequest,
    CouponPreviewResponse,
    CreateOrderRequest,
    CustomerOverviewResponse,
    OrderItemResponse,
    OrderResponse,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _create_order(request: Request) -> CreateOrder:
    return cast(CreateOrder, request.app.state.ordering_create)


def _get_order(request: Request) -> GetOrder:
    return cast(GetOrder, request.app.state.ordering_get)


def _cancel_order(request: Request) -> CancelOrder:
    return cast(CancelOrder, request.app.state.ordering_cancel)


def _preview_coupon(request: Request) -> PreviewCoupon:
    return cast(PreviewCoupon, request.app.state.ordering_coupon_preview)


def _customer_overview(request: Request) -> GetCustomerOverview:
    return cast(GetCustomerOverview, request.app.state.ordering_overview)


def _delete_customer_order(request: Request) -> DeleteCustomerOrder:
    return cast(DeleteCustomerOrder, request.app.state.ordering_delete)


def _to_response(view: OrderView) -> OrderResponse:
    return OrderResponse(
        id=view.id,
        company_id=view.company_id,
        status=view.status,
        currency=view.currency,
        subtotal=view.subtotal,
        list_subtotal=view.list_subtotal,
        cnpj_discount_total=view.cnpj_discount_total,
        discount_total=view.discount_total,
        shipping_total=view.shipping_total,
        tax_total=view.tax_total,
        total=view.total,
        created_at=view.created_at,
        content_locale=view.content_locale,
        coupon_code=view.coupon_code,
        coupon_type=view.coupon_type,
        coupon_percent=view.coupon_percent,
        coupon_discount_amount=view.coupon_discount_amount,
        shipping_discount_amount=view.shipping_discount_amount,
        items=[
            OrderItemResponse(
                sku=i.sku,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                base_unit_price=i.base_unit_price,
                list_unit_price=i.list_unit_price,
                list_line_total=i.list_line_total,
                cnpj_discount_percent=i.cnpj_discount_percent,
                cnpj_discount_band=i.cnpj_discount_band,
                cnpj_discount_amount=i.cnpj_discount_amount,
                tier_min_quantity=i.tier_min_quantity,
                line_total=i.line_total,
                content_locale=i.content_locale,
            )
            for i in view.items
        ],
    )


def _to_coupon_response(view: AvailableCouponView) -> AvailableCouponResponse:
    return AvailableCouponResponse(
        code=view.code,
        type=view.type,
        percent=view.percent,
        max_discount_amount=view.max_discount_amount,
        min_order_amount=view.min_order_amount,
        valid_until=view.valid_until,
        remaining_uses=view.remaining_uses,
    )


def _to_overview_response(view: CustomerOverview) -> CustomerOverviewResponse:
    return CustomerOverviewResponse(
        total_spent=view.total_spent,
        orders_count=view.orders_count,
        orders=[_to_response(order) for order in view.orders],
        coupons=[_to_coupon_response(coupon) for coupon in view.coupons],
    )


def _to_preview_response(result: CouponPreviewResult) -> CouponPreviewResponse:
    return CouponPreviewResponse(
        valid=result.valid,
        reason=result.reason,
        missing_amount=result.missing_amount,
        subtotal=result.subtotal,
        list_subtotal=result.list_subtotal,
        cnpj_discount_total=result.cnpj_discount_total,
        recovery_discount=result.recovery_discount,
        coupon_discount=result.coupon_discount,
        shipping_discount=result.shipping_discount,
        shipping_total=result.shipping_total,
        pix_discount=result.pix_discount,
        total=result.total,
        applied_discounts=sorted(result.applied_discounts, key=lambda item: item.value),
        currency=result.currency,
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    locale: Annotated[str, Depends(get_locale)],
    use_case: Annotated[CreateOrder, Depends(_create_order)],
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
) -> OrderResponse:
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
        view = await use_case.create(
            company_id=auth.company_id,
            buyer_user_id=auth.user_id,
            items=[
                OrderItemInput(product_id=i.product_id, quantity=i.quantity) for i in payload.items
            ],
            payment_method=payload.payment_method,
            idempotency_key=guard.key,
            po_number=payload.po_number,
            notes=payload.notes,
            locale=locale,
            coupon_code=payload.coupon_code,
        )
    except Exception:
        await guard.release()
        raise
    response = _to_response(view)
    await guard.complete(status.HTTP_201_CREATED, response.model_dump(mode="json"))
    return response


@router.post(
    "/coupon-preview",
    response_model=CouponPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Validar cupom e simular o checkout",
)
async def preview_coupon(
    payload: CouponPreviewRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    locale: Annotated[str, Depends(get_locale)],
    use_case: Annotated[PreviewCoupon, Depends(_preview_coupon)],
) -> CouponPreviewResponse:
    result = await use_case.execute(
        company_id=auth.company_id,
        user_id=auth.user_id,
        code=payload.code,
        payment_method=payload.payment_method,
        locale=locale,
        product_ids=payload.product_ids,
    )
    return _to_preview_response(result)


@router.get(
    "/overview",
    response_model=CustomerOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Painel do cliente: gastos, compras e cupons disponiveis",
)
async def get_customer_overview(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetCustomerOverview, Depends(_customer_overview)],
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
) -> CustomerOverviewResponse:
    return _to_overview_response(
        await use_case.execute(
            company_id=auth.company_id,
            buyer_user_id=auth.user_id,
            limit=limit,
        )
    )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_order(
    order_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[DeleteCustomerOrder, Depends(_delete_customer_order)],
) -> Response:
    await use_case.execute(
        company_id=auth.company_id,
        buyer_user_id=auth.user_id,
        order_id=order_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{order_id}", response_model=OrderResponse, status_code=status.HTTP_200_OK)
async def get_order(
    order_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetOrder, Depends(_get_order)],
) -> OrderResponse:
    return _to_response(await use_case.get(auth.company_id, order_id))


@router.post("/{order_id}/cancel", response_model=OrderResponse, status_code=status.HTTP_200_OK)
async def cancel_order(
    order_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[CancelOrder, Depends(_cancel_order)],
) -> OrderResponse:
    return _to_response(await use_case.cancel(auth.company_id, order_id))
