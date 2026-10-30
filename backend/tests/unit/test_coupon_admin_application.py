"""Casos de uso do CRUD admin de cupons com repositorio fake."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.security import AuthContext, AuthorizationError
from app.modules.ordering.application.coupon_admin import (
    CouponConflictAppError,
    CouponNotFoundAppError,
    CouponValidationAppError,
    CreateCoupon,
    DeleteCoupon,
    GetCoupon,
    ListCoupons,
    UpdateCoupon,
)
from app.modules.ordering.domain.coupon import (
    CouponRedemptionStatus,
    CouponType,
)
from app.modules.ordering.domain.coupon_admin import (
    CouponAdminView,
    CouponCreateData,
    CouponListFilters,
    CouponPage,
    CouponRedemptionView,
    CouponUpdateData,
    CouponWriteData,
)

_NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
_COMPANY = uuid.UUID("ffff0000-0000-4000-8000-00000000f101")
_USER = uuid.UUID("ffff0000-0000-4000-8000-00000000f102")
_COUPON = uuid.UUID("ffff0000-0000-4000-8000-00000000f103")

_ADMIN = AuthContext(user_id=_USER, company_id=_COMPANY, role="ADMIN", token_id="t-admin")
_BUYER = AuthContext(user_id=_USER, company_id=_COMPANY, role="BUYER", token_id="t-buyer")


def _view(
    *,
    coupon_id: uuid.UUID = _COUPON,
    code: str = "CUPOM10",
    coupon_type: CouponType = CouponType.PRODUCT_TOTAL,
    percent: str = "10.00",
    is_active: bool = True,
    total_uses: int = 0,
) -> CouponAdminView:
    return CouponAdminView(
        id=coupon_id,
        code=code,
        type=coupon_type,
        percent=Decimal(percent),
        max_discount_amount=None,
        min_order_amount=None,
        valid_from=None,
        valid_until=None,
        usage_limit_total=None,
        usage_limit_per_company=None,
        restricted_company_id=None,
        is_active=is_active,
        created_by=_USER,
        created_at=_NOW,
        updated_at=_NOW,
        total_uses=total_uses,
    )


class FakeRepository:
    def __init__(
        self,
        coupons: dict[uuid.UUID, CouponAdminView] | None = None,
        *,
        has_redemptions: bool = False,
    ) -> None:
        self.coupons = coupons or {}
        self.redemptions = has_redemptions
        self.deleted: list[uuid.UUID] = []

    async def code_exists(self, code: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        return any(item.code == code and item.id != exclude_id for item in self.coupons.values())

    async def create(self, data: CouponWriteData, *, created_by: uuid.UUID) -> CouponAdminView:
        view = _view(
            coupon_id=uuid.uuid4(),
            code=data.code,
            coupon_type=data.type,
            percent=str(data.percent),
            is_active=data.is_active,
        )
        self.coupons[view.id] = view
        return view

    async def get(self, coupon_id: uuid.UUID) -> CouponAdminView | None:
        return self.coupons.get(coupon_id)

    async def list_coupons(self, filters: CouponListFilters, *, now: datetime) -> CouponPage:
        items = list(self.coupons.values())
        return CouponPage(
            items=items,
            total=len(items),
            page=filters.page,
            page_size=filters.page_size,
            pages=1 if items else 0,
        )

    async def update(self, coupon_id: uuid.UUID, data: CouponWriteData) -> CouponAdminView:
        current = self.coupons[coupon_id]
        updated = _view(
            coupon_id=coupon_id,
            code=data.code,
            coupon_type=data.type,
            percent=str(data.percent),
            is_active=data.is_active,
            total_uses=current.total_uses,
        )
        self.coupons[coupon_id] = updated
        return updated

    async def delete(self, coupon_id: uuid.UUID) -> None:
        self.deleted.append(coupon_id)
        self.coupons.pop(coupon_id, None)

    async def has_redemptions(self, coupon_id: uuid.UUID) -> bool:
        return self.redemptions

    async def recent_redemptions(
        self, coupon_id: uuid.UUID, *, limit: int = 10
    ) -> list[CouponRedemptionView]:
        return [
            CouponRedemptionView(
                id=uuid.uuid4(),
                order_id=uuid.uuid4(),
                company_id=_COMPANY,
                amount_discounted=Decimal("10.00"),
                status=CouponRedemptionStatus.APPLIED,
                created_at=_NOW,
                released_at=None,
            )
        ][:limit]


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def record(self, **kwargs: object) -> None:
        self.entries.append(kwargs)


def _create_data(code: str | None = "CUPOM10") -> CouponCreateData:
    return CouponCreateData(
        code=code,
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
    )


async def test_create_exige_admin() -> None:
    use_case = CreateCoupon(repository=FakeRepository(), audit=FakeAudit())
    with pytest.raises(AuthorizationError):
        await use_case.execute(_BUYER, _create_data())


async def test_create_gera_codigo_quando_omitido() -> None:
    repository = FakeRepository()
    audit = FakeAudit()
    use_case = CreateCoupon(repository=repository, audit=audit)
    view = await use_case.execute(_ADMIN, _create_data(None))
    assert re.fullmatch(r"FORJA-[A-Z0-9]{6}", view.code)
    assert audit.entries[0]["action"] == "coupon.created"
    details = audit.entries[0]["details"]
    assert details == {"code": view.code, "type": "PRODUCT_TOTAL"}
    assert "email" not in details and "password" not in details


async def test_create_codigo_duplicado_409() -> None:
    repository = FakeRepository({_COUPON: _view()})
    use_case = CreateCoupon(repository=repository, audit=FakeAudit())
    with pytest.raises(CouponConflictAppError) as exc:
        await use_case.execute(_ADMIN, _create_data("cupom10"))
    assert exc.value.status_code == 409
    assert "já existe" in exc.value.detail


async def test_update_codigo_bloqueado_com_resgate() -> None:
    repository = FakeRepository({_COUPON: _view()}, has_redemptions=True)
    use_case = UpdateCoupon(repository=repository, audit=FakeAudit())
    update = CouponUpdateData(provided=frozenset({"code"}), code="NOVO-CODIGO")
    with pytest.raises(CouponConflictAppError) as exc:
        await use_case.execute(_ADMIN, _COUPON, update)
    assert "código" in exc.value.detail


async def test_update_tipo_bloqueado_com_resgate() -> None:
    repository = FakeRepository({_COUPON: _view()}, has_redemptions=True)
    use_case = UpdateCoupon(repository=repository, audit=FakeAudit())
    update = CouponUpdateData(provided=frozenset({"type"}), type=CouponType.SHIPPING)
    with pytest.raises(CouponConflictAppError) as exc:
        await use_case.execute(_ADMIN, _COUPON, update)
    assert "tipo" in exc.value.detail


async def test_update_percentual_permitido_com_resgate() -> None:
    repository = FakeRepository({_COUPON: _view()}, has_redemptions=True)
    audit = FakeAudit()
    use_case = UpdateCoupon(repository=repository, audit=audit)
    update = CouponUpdateData(provided=frozenset({"percent"}), percent=Decimal("20.00"))
    view = await use_case.execute(_ADMIN, _COUPON, update)
    assert view.percent == Decimal("20.00")
    assert audit.entries[0]["action"] == "coupon.updated"


async def test_update_codigo_permitido_sem_resgate() -> None:
    repository = FakeRepository({_COUPON: _view()})
    use_case = UpdateCoupon(repository=repository, audit=FakeAudit())
    update = CouponUpdateData(provided=frozenset({"code"}), code="  novo-codigo ")
    view = await use_case.execute(_ADMIN, _COUPON, update)
    assert view.code == "NOVO-CODIGO"


async def test_update_codigo_duplicado_409() -> None:
    other_id = uuid.uuid4()
    repository = FakeRepository(
        {_COUPON: _view(), other_id: _view(coupon_id=other_id, code="OUTRO")}
    )
    use_case = UpdateCoupon(repository=repository, audit=FakeAudit())
    update = CouponUpdateData(provided=frozenset({"code"}), code="OUTRO")
    with pytest.raises(CouponConflictAppError):
        await use_case.execute(_ADMIN, _COUPON, update)


async def test_update_validade_invalida_422() -> None:
    repository = FakeRepository({_COUPON: _view()})
    use_case = UpdateCoupon(repository=repository, audit=FakeAudit())
    update = CouponUpdateData(
        provided=frozenset({"valid_from", "valid_until"}),
        valid_from=_NOW,
        valid_until=_NOW,
    )
    with pytest.raises(CouponValidationAppError):
        await use_case.execute(_ADMIN, _COUPON, update)


async def test_update_inexistente_404() -> None:
    use_case = UpdateCoupon(repository=FakeRepository(), audit=FakeAudit())
    update = CouponUpdateData(provided=frozenset({"percent"}), percent=Decimal("20.00"))
    with pytest.raises(CouponNotFoundAppError):
        await use_case.execute(_ADMIN, _COUPON, update)


async def test_delete_com_resgate_409_e_nao_exclui() -> None:
    repository = FakeRepository({_COUPON: _view()}, has_redemptions=True)
    use_case = DeleteCoupon(repository=repository, audit=FakeAudit())
    with pytest.raises(CouponConflictAppError) as exc:
        await use_case.execute(_ADMIN, _COUPON)
    assert "desative" in exc.value.detail
    assert repository.deleted == []


async def test_delete_sem_resgate_audita() -> None:
    repository = FakeRepository({_COUPON: _view()})
    audit = FakeAudit()
    use_case = DeleteCoupon(repository=repository, audit=audit)
    await use_case.execute(_ADMIN, _COUPON)
    assert repository.deleted == [_COUPON]
    assert audit.entries[0]["action"] == "coupon.deleted"


async def test_get_inexistente_404() -> None:
    use_case = GetCoupon(repository=FakeRepository())
    with pytest.raises(CouponNotFoundAppError):
        await use_case.execute(_ADMIN, _COUPON)


async def test_get_inclui_ultimos_resgates() -> None:
    use_case = GetCoupon(repository=FakeRepository({_COUPON: _view()}))
    view = await use_case.execute(_ADMIN, _COUPON)
    assert len(view.last_redemptions) == 1


async def test_list_exige_admin() -> None:
    use_case = ListCoupons(repository=FakeRepository())
    with pytest.raises(AuthorizationError):
        await use_case.execute(_BUYER, CouponListFilters())
