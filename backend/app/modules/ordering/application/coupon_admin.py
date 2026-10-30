"""Casos de uso da administracao de cupons (somente papel ADMIN)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import NoReturn

from app.application.security import AuthContext, require_role
from app.core.errors import AppError
from app.modules.ordering.application.coupon_admin_ports import (
    CouponAdminRepository,
    CouponAuditPort,
)
from app.modules.ordering.domain.coupon_admin import (
    CouponAdminError,
    CouponAdminView,
    CouponCodeConflictError,
    CouponCompanyNotFoundError,
    CouponCreateData,
    CouponHasRedemptionsError,
    CouponImmutableFieldError,
    CouponListFilters,
    CouponNotFoundError,
    CouponPage,
    CouponUpdateData,
    merge_coupon_update,
    normalize_valid_coupon_code,
    prepare_coupon_create,
    validate_coupon_write,
)

_MAX_RECENT_REDEMPTIONS = 10


class CouponNotFoundAppError(AppError):
    status_code = 404
    title = "Not Found"
    code = "coupon_not_found"


class CouponConflictAppError(AppError):
    status_code = 409
    title = "Conflict"
    code = "coupon_conflict"


class CouponValidationAppError(AppError):
    status_code = 422
    title = "Unprocessable Entity"
    code = "invalid_coupon"


def _raise_coupon_error(exc: CouponAdminError) -> NoReturn:
    if isinstance(exc, CouponNotFoundError):
        raise CouponNotFoundAppError(str(exc)) from exc
    if isinstance(
        exc,
        (CouponCodeConflictError, CouponImmutableFieldError, CouponHasRedemptionsError),
    ):
        raise CouponConflictAppError(str(exc)) from exc
    if isinstance(exc, CouponCompanyNotFoundError):
        raise CouponValidationAppError(str(exc)) from exc
    raise CouponValidationAppError(str(exc)) from exc


class CreateCoupon:
    """Cria um cupom (valida codigo/campos e registra auditoria)."""

    def __init__(self, *, repository: CouponAdminRepository, audit: CouponAuditPort) -> None:
        self._repository = repository
        self._audit = audit

    async def execute(self, auth: AuthContext, data: CouponCreateData) -> CouponAdminView:
        require_role(auth, "ADMIN")
        try:
            write = prepare_coupon_create(data)
            if await self._repository.code_exists(write.code):
                raise CouponCodeConflictError(f"Código '{write.code}' já existe.")
            view = await self._repository.create(write, created_by=auth.user_id)
        except CouponAdminError as exc:
            _raise_coupon_error(exc)
        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="coupon.created",
            resource="coupon",
            resource_id=view.id,
            details={"code": view.code, "type": view.type.value},
        )
        return view


class ListCoupons:
    """Lista cupons com busca, status e paginacao."""

    def __init__(self, *, repository: CouponAdminRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext, filters: CouponListFilters) -> CouponPage:
        require_role(auth, "ADMIN")
        return await self._repository.list_coupons(filters, now=datetime.now(UTC))


class GetCoupon:
    """Detalha um cupom com agregados e ultimos resgates."""

    def __init__(self, *, repository: CouponAdminRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext, coupon_id: uuid.UUID) -> CouponAdminView:
        require_role(auth, "ADMIN")
        view = await self._repository.get(coupon_id)
        if view is None:
            raise CouponNotFoundAppError("Cupom não encontrado.")
        redemptions = await self._repository.recent_redemptions(
            coupon_id, limit=_MAX_RECENT_REDEMPTIONS
        )
        return replace(view, last_redemptions=tuple(redemptions))


class UpdateCoupon:
    """Edita um cupom; codigo/tipo ficam imutaveis apos o primeiro resgate."""

    def __init__(self, *, repository: CouponAdminRepository, audit: CouponAuditPort) -> None:
        self._repository = repository
        self._audit = audit

    async def execute(
        self, auth: AuthContext, coupon_id: uuid.UUID, update: CouponUpdateData
    ) -> CouponAdminView:
        require_role(auth, "ADMIN")
        try:
            current = await self._repository.get(coupon_id)
            if current is None:
                raise CouponNotFoundError("Cupom não encontrado.")
            if await self._repository.has_redemptions(coupon_id):
                _ensure_immutable(current, update)
            write = validate_coupon_write(merge_coupon_update(current, update))
            if write.code != current.code and await self._repository.code_exists(
                write.code, exclude_id=coupon_id
            ):
                raise CouponCodeConflictError(f"Código '{write.code}' já existe.")
            view = await self._repository.update(coupon_id, write)
        except CouponAdminError as exc:
            _raise_coupon_error(exc)
        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="coupon.updated",
            resource="coupon",
            resource_id=view.id,
            details={"code": view.code, "fields": sorted(update.provided)},
        )
        return view


class DeleteCoupon:
    """Exclui um cupom sem resgates; com resgates, orienta desativar."""

    def __init__(self, *, repository: CouponAdminRepository, audit: CouponAuditPort) -> None:
        self._repository = repository
        self._audit = audit

    async def execute(self, auth: AuthContext, coupon_id: uuid.UUID) -> None:
        require_role(auth, "ADMIN")
        current = await self._repository.get(coupon_id)
        if current is None:
            raise CouponNotFoundAppError("Cupom não encontrado.")
        if await self._repository.has_redemptions(coupon_id):
            raise CouponConflictAppError(
                "Cupom possui resgates e não pode ser excluído; desative-o em vez disso."
            )
        try:
            await self._repository.delete(coupon_id)
        except CouponHasRedemptionsError as exc:
            _raise_coupon_error(exc)
        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="coupon.deleted",
            resource="coupon",
            resource_id=coupon_id,
            details={"code": current.code},
        )


def _ensure_immutable(current: CouponAdminView, update: CouponUpdateData) -> None:
    if "code" in update.provided and update.code is not None:
        normalized = normalize_valid_coupon_code(update.code)
        if normalized != current.code:
            raise CouponImmutableFieldError(
                "O código não pode ser alterado depois que o cupom tiver resgates."
            )
    if "type" in update.provided and update.type is not None and update.type != current.type:
        raise CouponImmutableFieldError(
            "O tipo não pode ser alterado depois que o cupom tiver resgates."
        )
