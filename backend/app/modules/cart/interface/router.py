"""Endpoints do carrinho (tenant-scoped, autenticado).

O company_id/user_id vem do token autenticado; nenhum preco enviado pelo
cliente e aceito (precos sao resolvidos no servidor pelo dominio de pricing).
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.cart.application.cart import CartService
from app.modules.cart.application.ports import CartView
from app.modules.cart.interface.schemas import (
    AddItemRequest,
    CartItemResponse,
    CartResponse,
    UpdateItemRequest,
)

router = APIRouter(prefix="/cart", tags=["cart"])


def _cart_service(request: Request) -> CartService:
    return cast(CartService, request.app.state.cart_service)


def _to_response(view: CartView) -> CartResponse:
    return CartResponse(
        cart_id=view.cart_id,
        company_id=view.company_id,
        user_id=view.user_id,
        items=[
            CartItemResponse(
                product_id=i.product_id,
                sku=i.sku,
                name=i.name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                line_total=i.line_total,
                tier_min_quantity=i.tier_min_quantity,
            )
            for i in view.items
        ],
        subtotal=view.subtotal,
    )


@router.get("", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def get_cart(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    service: Annotated[CartService, Depends(_cart_service)],
) -> CartResponse:
    view = await service.get_cart(auth.company_id, auth.user_id)
    return _to_response(view)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def add_item(
    payload: AddItemRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    service: Annotated[CartService, Depends(_cart_service)],
) -> CartResponse:
    view = await service.add_item(
        company_id=auth.company_id,
        user_id=auth.user_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
    )
    return _to_response(view)


@router.put("/items/{product_id}", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def update_item(
    product_id: uuid.UUID,
    payload: UpdateItemRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    service: Annotated[CartService, Depends(_cart_service)],
) -> CartResponse:
    view = await service.update_quantity(
        company_id=auth.company_id,
        user_id=auth.user_id,
        product_id=product_id,
        quantity=payload.quantity,
    )
    return _to_response(view)


@router.delete("/items/{product_id}", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def remove_item(
    product_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    service: Annotated[CartService, Depends(_cart_service)],
) -> CartResponse:
    view = await service.remove_item(
        company_id=auth.company_id, user_id=auth.user_id, product_id=product_id
    )
    return _to_response(view)


@router.delete("", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def clear_cart(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    service: Annotated[CartService, Depends(_cart_service)],
) -> CartResponse:
    view = await service.clear(company_id=auth.company_id, user_id=auth.user_id)
    return _to_response(view)
