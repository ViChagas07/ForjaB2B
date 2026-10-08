"""Endpoints do contexto de pedidos (criacao/consulta/cancelamento).

O pedido e tenant-scoped; company_id/buyer vêm do token. Nenhum preco/total/
credito do cliente e aceito (recalculado no servidor).
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.ordering.application.order import CancelOrder, CreateOrder, GetOrder
from app.modules.ordering.application.ports import OrderItemInput, OrderView
from app.modules.ordering.interface.schemas import (
    CreateOrderRequest,
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


def _to_response(view: OrderView) -> OrderResponse:
    return OrderResponse(
        id=view.id,
        company_id=view.company_id,
        status=view.status,
        currency=view.currency,
        subtotal=view.subtotal,
        discount_total=view.discount_total,
        shipping_total=view.shipping_total,
        tax_total=view.tax_total,
        total=view.total,
        created_at=view.created_at,
        items=[
            OrderItemResponse(
                sku=i.sku,
                product_name=i.product_name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                base_unit_price=i.base_unit_price,
                tier_min_quantity=i.tier_min_quantity,
                line_total=i.line_total,
            )
            for i in view.items
        ],
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[CreateOrder, Depends(_create_order)],
) -> OrderResponse:
    view = await use_case.create(
        company_id=auth.company_id,
        buyer_user_id=auth.user_id,
        items=[OrderItemInput(product_id=i.product_id, quantity=i.quantity) for i in payload.items],
        payment_method=payload.payment_method,
        idempotency_key=payload.idempotency_key,
        po_number=payload.po_number,
        notes=payload.notes,
    )
    return _to_response(view)


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
