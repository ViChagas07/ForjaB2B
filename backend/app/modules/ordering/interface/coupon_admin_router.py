"""Endpoints administrativos de cupons (somente papel ADMIN da empresa)."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.application.security import AuthContext, require_role
from app.interface.deps import get_current_auth
from app.modules.ordering.application.coupon_admin import (
    CreateCoupon,
    DeleteCoupon,
    GetCoupon,
    ListCoupons,
    UpdateCoupon,
)
from app.modules.ordering.domain.coupon_admin import (
    CouponAdminView,
    CouponCreateData,
    CouponListFilters,
    CouponRedemptionView,
    CouponUpdateData,
    generate_coupon_code,
)
from app.modules.ordering.interface.coupon_admin_schemas import (
    CouponAdminDetail,
    CouponAdminListResponse,
    CouponAdminOut,
    CouponCodeOut,
    CouponCreate,
    CouponListQuery,
    CouponRedemptionOut,
    CouponUpdate,
)

router = APIRouter(prefix="/admin/coupons", tags=["coupons-admin"])


def _create_coupon(request: Request) -> CreateCoupon:
    return cast(CreateCoupon, request.app.state.coupon_admin_create)


def _list_coupons(request: Request) -> ListCoupons:
    return cast(ListCoupons, request.app.state.coupon_admin_list)


def _get_coupon(request: Request) -> GetCoupon:
    return cast(GetCoupon, request.app.state.coupon_admin_get)


def _update_coupon(request: Request) -> UpdateCoupon:
    return cast(UpdateCoupon, request.app.state.coupon_admin_update)


def _delete_coupon(request: Request) -> DeleteCoupon:
    return cast(DeleteCoupon, request.app.state.coupon_admin_delete)


@router.post(
    "",
    response_model=CouponAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar cupom",
)
async def create_coupon(
    payload: CouponCreate,
    use_case: Annotated[CreateCoupon, Depends(_create_coupon)],
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> CouponAdminOut:
    data = CouponCreateData(
        code=payload.code,
        type=payload.type,
        percent=payload.percent,
        max_discount_amount=payload.max_discount_amount,
        min_order_amount=payload.min_order_amount,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        usage_limit_total=payload.usage_limit_total,
        usage_limit_per_company=payload.usage_limit_per_company,
        restricted_company_id=payload.restricted_company_id,
        is_active=payload.is_active,
    )
    view = await use_case.execute(auth, data)
    return _to_out(view)


@router.post(
    "/generate-code",
    response_model=CouponCodeOut,
    status_code=status.HTTP_200_OK,
    summary="Gerar codigo de cupom",
)
async def generate_code(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> CouponCodeOut:
    # A autorizacao efetiva acontece nos casos de uso; esta rota nao persiste.
    require_role(auth, "ADMIN")
    return CouponCodeOut(code=generate_coupon_code())


@router.get(
    "",
    response_model=CouponAdminListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar cupons (admin)",
)
async def list_coupons(
    query: Annotated[CouponListQuery, Query()],
    use_case: Annotated[ListCoupons, Depends(_list_coupons)],
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> CouponAdminListResponse:
    filters = CouponListFilters(
        q=query.q,
        status=query.status,
        page=query.page,
        page_size=query.page_size,
    )
    page = await use_case.execute(auth, filters)
    return CouponAdminListResponse(
        items=[_to_out(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        pages=page.pages,
    )


@router.get(
    "/{coupon_id}",
    response_model=CouponAdminDetail,
    status_code=status.HTTP_200_OK,
    summary="Detalhar cupom (admin)",
)
async def get_coupon(
    coupon_id: uuid.UUID,
    use_case: Annotated[GetCoupon, Depends(_get_coupon)],
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> CouponAdminDetail:
    view = await use_case.execute(auth, coupon_id)
    return _to_detail(view)


@router.patch(
    "/{coupon_id}",
    response_model=CouponAdminOut,
    status_code=status.HTTP_200_OK,
    summary="Editar cupom (PATCH)",
)
async def update_coupon(
    coupon_id: uuid.UUID,
    payload: CouponUpdate,
    use_case: Annotated[UpdateCoupon, Depends(_update_coupon)],
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> CouponAdminOut:
    update = CouponUpdateData(
        provided=frozenset(payload.model_fields_set),
        code=payload.code,
        type=payload.type,
        percent=payload.percent,
        max_discount_amount=payload.max_discount_amount,
        min_order_amount=payload.min_order_amount,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        usage_limit_total=payload.usage_limit_total,
        usage_limit_per_company=payload.usage_limit_per_company,
        restricted_company_id=payload.restricted_company_id,
        is_active=payload.is_active,
    )
    view = await use_case.execute(auth, coupon_id, update)
    return _to_out(view)


@router.delete(
    "/{coupon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir cupom sem resgates",
)
async def delete_coupon(
    coupon_id: uuid.UUID,
    use_case: Annotated[DeleteCoupon, Depends(_delete_coupon)],
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> Response:
    await use_case.execute(auth, coupon_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_out(view: CouponAdminView) -> CouponAdminOut:
    return CouponAdminOut(
        id=view.id,
        code=view.code,
        type=view.type,
        percent=view.percent,
        max_discount_amount=view.max_discount_amount,
        min_order_amount=view.min_order_amount,
        valid_from=view.valid_from,
        valid_until=view.valid_until,
        usage_limit_total=view.usage_limit_total,
        usage_limit_per_company=view.usage_limit_per_company,
        restricted_company_id=view.restricted_company_id,
        is_active=view.is_active,
        created_by=view.created_by,
        created_at=view.created_at,
        updated_at=view.updated_at,
        total_uses=view.total_uses,
        total_discounted=view.total_discounted,
    )


def _to_detail(view: CouponAdminView) -> CouponAdminDetail:
    return CouponAdminDetail(
        **_to_out(view).model_dump(),
        last_redemptions=[_to_redemption(item) for item in view.last_redemptions],
    )


def _to_redemption(view: CouponRedemptionView) -> CouponRedemptionOut:
    return CouponRedemptionOut(
        id=view.id,
        order_id=view.order_id,
        company_id=view.company_id,
        amount_discounted=view.amount_discounted,
        status=view.status,
        created_at=view.created_at,
        released_at=view.released_at,
    )
