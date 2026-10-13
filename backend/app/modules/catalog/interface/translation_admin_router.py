"""Endpoints de administração de traduções de produto (role ADMIN)."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.core.errors import AppError
from app.interface.deps import get_optional_auth
from app.modules.catalog.application.translation_admin import (
    GetProductTranslations,
    TranslationUpdateInput,
    UpdateTranslation,
)
from app.modules.catalog.interface.admin_schemas import (
    ProductTranslationsListResponse,
    TranslationAdminOut,
    TranslationUpdate,
)

router = APIRouter(prefix="/admin/catalog/translations", tags=["catalog-admin-translations"])


class AuthorizationError(AppError):
    """Acesso negado (403)."""

    status_code = 403
    title = "Forbidden"
    code = "forbidden"


def _get_product_translations_uc(request: Request) -> GetProductTranslations:
    return cast(GetProductTranslations, request.app.state.catalog_admin_get_translations)


def _update_translation_uc(request: Request) -> UpdateTranslation:
    return cast(UpdateTranslation, request.app.state.catalog_admin_update_translation)


def _require_admin(auth: AuthContext | None) -> AuthContext:
    if auth is None:
        raise AuthorizationError()
    return auth


def _to_update_input(payload: TranslationUpdate) -> TranslationUpdateInput:
    return TranslationUpdateInput(
        name=payload.name,
        description=payload.description,
        attributes=payload.attributes,
        mark_reviewed=payload.mark_reviewed,
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductTranslationsListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_product_translations(
    product_id: uuid.UUID,
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    use_case: Annotated[GetProductTranslations, Depends(_get_product_translations_uc)],
) -> ProductTranslationsListResponse:
    """Lista todas as traduções de um produto com status e flag stale."""
    auth = _require_admin(auth)
    translations = await use_case.execute(auth, product_id)
    return ProductTranslationsListResponse(
        product_id=product_id,
        translations=[TranslationAdminOut(**vars(t)) for t in translations],
    )


@router.patch(
    "/products/{product_id}/{locale}",
    response_model=TranslationAdminOut,
    status_code=status.HTTP_200_OK,
)
async def update_translation(
    product_id: uuid.UUID,
    locale: str,
    payload: TranslationUpdate,
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    use_case: Annotated[UpdateTranslation, Depends(_update_translation_uc)],
) -> TranslationAdminOut:
    """Edita manualmente uma tradução e opcionalmente marca como reviewed."""
    auth = _require_admin(auth)
    input_data = _to_update_input(payload)
    result = await use_case.execute(auth, product_id, locale, input_data)
    return TranslationAdminOut(**vars(result))
