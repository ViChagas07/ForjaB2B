"""Repositorio administrativo de cupons (role forja_admin, sem tenant).

``coupons`` e global e a role administrativa escreve nela. ``coupon_redemptions``
tem FORCE RLS; a policy ``coupon_redemptions_admin_read`` (migration 0034)
permite que a role ``forja_admin`` leia os resgates de todas as empresas para
montar os agregados da listagem/detalhe.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NoReturn

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement

from app.infrastructure.db.models.coupons import Coupon, CouponRedemption
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ordering.domain.coupon import CouponRedemptionStatus, CouponType
from app.modules.ordering.domain.coupon_admin import (
    CouponAdminView,
    CouponCodeConflictError,
    CouponCompanyNotFoundError,
    CouponHasRedemptionsError,
    CouponListFilters,
    CouponNotFoundError,
    CouponPage,
    CouponRedemptionView,
    CouponWriteData,
)

_ZERO = Decimal("0.00")
_APPLIED = CouponRedemption.status == CouponRedemptionStatus.APPLIED


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


def _totals_select() -> Select[Any]:
    return (
        select(
            Coupon,
            func.count(CouponRedemption.id).label("total_uses"),
            func.coalesce(func.sum(CouponRedemption.amount_discounted), 0).label(
                "total_discounted"
            ),
        )
        .outerjoin(
            CouponRedemption,
            and_(CouponRedemption.coupon_id == Coupon.id, _APPLIED),
        )
        .group_by(Coupon.id)
    )


def _list_filters(
    filters: CouponListFilters, now: datetime
) -> tuple[list[ColumnElement[bool]], list[ColumnElement[bool]]]:
    conditions: list[ColumnElement[bool]] = []
    having: list[ColumnElement[bool]] = []
    if filters.q and filters.q.strip():
        conditions.append(Coupon.code.ilike(f"%{filters.q.strip()}%"))
    if filters.status == "ACTIVE":
        conditions.extend(
            [
                Coupon.is_active.is_(True),
                or_(Coupon.valid_from.is_(None), Coupon.valid_from <= now),
                or_(Coupon.valid_until.is_(None), Coupon.valid_until > now),
            ]
        )
        having.append(
            or_(
                Coupon.usage_limit_total.is_(None),
                func.count(CouponRedemption.id) < Coupon.usage_limit_total,
            )
        )
    elif filters.status == "EXPIRED":
        conditions.extend(
            [
                Coupon.valid_until.is_not(None),
                Coupon.valid_until <= now,
            ]
        )
    elif filters.status == "EXHAUSTED":
        conditions.append(Coupon.usage_limit_total.is_not(None))
        having.append(func.count(CouponRedemption.id) >= Coupon.usage_limit_total)
    return conditions, having


class SqlAlchemyCouponAdminRepository:
    """Implementacao da porta CouponAdminRepository sobre UoW administrativo."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def code_exists(self, code: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        async with self._uow_factory.begin() as uow:
            stmt = select(Coupon.id).where(Coupon.code == code)
            if exclude_id is not None:
                stmt = stmt.where(Coupon.id != exclude_id)
            row = (await uow.session.execute(stmt.limit(1))).first()
            await uow.commit()
            return row is not None

    async def create(self, data: CouponWriteData, *, created_by: uuid.UUID) -> CouponAdminView:
        async with self._uow_factory.begin() as uow:
            orm = Coupon(
                code=data.code,
                type=data.type,
                percent=data.percent,
                max_discount_amount=data.max_discount_amount,
                min_order_amount=data.min_order_amount,
                valid_from=data.valid_from,
                valid_until=data.valid_until,
                usage_limit_total=data.usage_limit_total,
                usage_limit_per_company=data.usage_limit_per_company,
                restricted_company_id=data.restricted_company_id,
                is_active=data.is_active,
                created_by=created_by,
            )
            uow.session.add(orm)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                await uow.rollback()
                _raise_write_error(exc, data.code)
            await uow.session.refresh(orm)
            await uow.commit()
            return _view(orm, 0, _ZERO)

    async def get(self, coupon_id: uuid.UUID) -> CouponAdminView | None:
        async with self._uow_factory.begin() as uow:
            row = (
                await uow.session.execute(_totals_select().where(Coupon.id == coupon_id))
            ).first()
            await uow.commit()
            if row is None:
                return None
            return _view(row[0], int(row[1]), _as_money(row[2]))

    async def list_coupons(self, filters: CouponListFilters, *, now: datetime) -> CouponPage:
        conditions, having = _list_filters(filters, now)
        async with self._uow_factory.begin() as uow:
            subquery = (
                select(Coupon.id)
                .outerjoin(
                    CouponRedemption,
                    and_(CouponRedemption.coupon_id == Coupon.id, _APPLIED),
                )
                .where(*conditions)
                .group_by(Coupon.id)
                .having(*having)
                .subquery()
            )
            total = int(
                (await uow.session.execute(select(func.count()).select_from(subquery))).scalar_one()
            )
            stmt = (
                _totals_select()
                .where(*conditions)
                .having(*having)
                .order_by(Coupon.created_at.desc(), Coupon.id.desc())
                .limit(filters.page_size)
                .offset((filters.page - 1) * filters.page_size)
            )
            rows = (await uow.session.execute(stmt)).all()
            await uow.commit()
        items = [_view(row[0], int(row[1]), _as_money(row[2])) for row in rows]
        pages = math.ceil(total / filters.page_size) if total else 0
        return CouponPage(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=pages,
        )

    async def update(self, coupon_id: uuid.UUID, data: CouponWriteData) -> CouponAdminView:
        async with self._uow_factory.begin() as uow:
            orm = await uow.session.get(Coupon, coupon_id)
            if orm is None:
                raise CouponNotFoundError("Cupom não encontrado.")
            orm.code = data.code
            orm.type = data.type
            orm.percent = data.percent
            orm.max_discount_amount = data.max_discount_amount
            orm.min_order_amount = data.min_order_amount
            orm.valid_from = data.valid_from
            orm.valid_until = data.valid_until
            orm.usage_limit_total = data.usage_limit_total
            orm.usage_limit_per_company = data.usage_limit_per_company
            orm.restricted_company_id = data.restricted_company_id
            orm.is_active = data.is_active
            orm.updated_at = datetime.now(UTC)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                await uow.rollback()
                _raise_write_error(exc, data.code)
            row = (
                await uow.session.execute(_totals_select().where(Coupon.id == coupon_id))
            ).first()
            await uow.commit()
            if row is None:  # pragma: no cover - o cupom acabou de ser atualizado
                raise CouponNotFoundError("Cupom não encontrado.")
            return _view(row[0], int(row[1]), _as_money(row[2]))

    async def delete(self, coupon_id: uuid.UUID) -> None:
        async with self._uow_factory.begin() as uow:
            orm = await uow.session.get(Coupon, coupon_id)
            if orm is None:
                raise CouponNotFoundError("Cupom não encontrado.")
            await uow.session.delete(orm)
            try:
                await uow.session.flush()
            except IntegrityError as exc:
                await uow.rollback()
                if "fk_coupon_redemptions_coupon_id_coupons" in _constraint_name(exc):
                    raise CouponHasRedemptionsError(
                        "Cupom possui resgates e não pode ser excluído; desative-o."
                    ) from exc
                raise
            await uow.commit()

    async def has_redemptions(self, coupon_id: uuid.UUID) -> bool:
        async with self._uow_factory.begin() as uow:
            total = (
                await uow.session.execute(
                    select(func.count())
                    .select_from(CouponRedemption)
                    .where(CouponRedemption.coupon_id == coupon_id)
                )
            ).scalar_one()
            await uow.commit()
            return int(total) > 0

    async def recent_redemptions(
        self, coupon_id: uuid.UUID, *, limit: int = 10
    ) -> list[CouponRedemptionView]:
        async with self._uow_factory.begin() as uow:
            rows = (
                (
                    await uow.session.execute(
                        select(CouponRedemption)
                        .where(CouponRedemption.coupon_id == coupon_id)
                        .order_by(
                            CouponRedemption.created_at.desc(),
                            CouponRedemption.id.desc(),
                        )
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            await uow.commit()
        return [
            CouponRedemptionView(
                id=row.id,
                order_id=row.order_id,
                company_id=row.company_id,
                amount_discounted=row.amount_discounted,
                status=CouponRedemptionStatus(row.status),
                created_at=row.created_at,
                released_at=row.released_at,
            )
            for row in rows
        ]


def _raise_write_error(exc: IntegrityError, code: str) -> NoReturn:
    constraint = _constraint_name(exc)
    if constraint == "uq_coupons_code":
        raise CouponCodeConflictError(f"Código '{code}' já existe.") from exc
    if constraint == "fk_coupons_restricted_company_id_companies":
        raise CouponCompanyNotFoundError("Empresa restrita não encontrada.") from exc
    raise exc


def _as_money(value: Any) -> Decimal:
    return Decimal(value) if value is not None else _ZERO


def _view(coupon: Coupon, total_uses: int, total_discounted: Decimal) -> CouponAdminView:
    return CouponAdminView(
        id=coupon.id,
        code=coupon.code,
        type=CouponType(coupon.type),
        percent=coupon.percent,
        max_discount_amount=coupon.max_discount_amount,
        min_order_amount=coupon.min_order_amount,
        valid_from=coupon.valid_from,
        valid_until=coupon.valid_until,
        usage_limit_total=coupon.usage_limit_total,
        usage_limit_per_company=coupon.usage_limit_per_company,
        restricted_company_id=coupon.restricted_company_id,
        is_active=coupon.is_active,
        created_by=coupon.created_by,
        created_at=coupon.created_at,
        updated_at=coupon.updated_at,
        total_uses=total_uses,
        total_discounted=total_discounted,
    )
