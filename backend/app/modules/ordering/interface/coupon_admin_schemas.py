"""Schemas HTTP da API administrativa de cupons (extra="forbid")."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.ordering.domain.coupon import (
    CouponRedemptionStatus,
    CouponType,
)


def _validate_timezone(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Use data/hora com fuso horário (ISO 8601).")
    return value


class CouponCreate(BaseModel):
    """Payload de criacao; codigo nulo gera ``FORJA-XXXXXX``."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=32)
    type: CouponType
    percent: Decimal = Field(ge=Decimal("0.01"), le=Decimal("100"), max_digits=5, decimal_places=2)
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_company: int | None = Field(default=None, ge=1)
    restricted_company_id: uuid.UUID | None = None
    is_active: bool = True

    @field_validator("valid_from", "valid_until")
    @classmethod
    def _timezone(cls, value: datetime | None) -> datetime | None:
        return _validate_timezone(value)


class CouponUpdate(BaseModel):
    """PATCH: campos omitidos permanecem; ``null`` limpa os opcionais."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=32)
    type: CouponType | None = None
    percent: Decimal | None = Field(
        default=None, ge=Decimal("0.01"), le=Decimal("100"), max_digits=5, decimal_places=2
    )
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_company: int | None = Field(default=None, ge=1)
    restricted_company_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("valid_from", "valid_until")
    @classmethod
    def _timezone(cls, value: datetime | None) -> datetime | None:
        return _validate_timezone(value)


class CouponListQuery(BaseModel):
    """Filtros da listagem administrativa."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=32)
    status: Literal["ACTIVE", "EXPIRED", "EXHAUSTED"] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class CouponRedemptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    order_id: uuid.UUID
    company_id: uuid.UUID
    amount_discounted: Decimal
    status: CouponRedemptionStatus
    created_at: datetime
    released_at: datetime | None


class CouponAdminOut(BaseModel):
    """Cupom com agregados de uso."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    code: str
    type: CouponType
    percent: Decimal
    max_discount_amount: Decimal | None
    min_order_amount: Decimal | None
    valid_from: datetime | None
    valid_until: datetime | None
    usage_limit_total: int | None
    usage_limit_per_company: int | None
    restricted_company_id: uuid.UUID | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    total_uses: int
    total_discounted: Decimal


class CouponAdminDetail(CouponAdminOut):
    """Detalhe com os ultimos resgates (mais recentes primeiro)."""

    last_redemptions: list[CouponRedemptionOut]


class CouponAdminListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CouponAdminOut]
    total: int
    page: int
    page_size: int
    pages: int


class CouponCodeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
