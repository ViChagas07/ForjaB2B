"""Portas da administracao de cupons (dependencias invertidas)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.modules.ordering.domain.coupon_admin import (
    CouponAdminView,
    CouponListFilters,
    CouponPage,
    CouponRedemptionView,
    CouponWriteData,
)


class CouponAdminRepository(Protocol):
    """Persistencia administrativa de cupons (role forja_admin, sem tenant)."""

    async def code_exists(self, code: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        """Indica se o codigo normalizado ja esta em uso."""

    async def create(self, data: CouponWriteData, *, created_by: uuid.UUID) -> CouponAdminView:
        """Cria o cupom e devolve a visao com agregados zerados."""

    async def get(self, coupon_id: uuid.UUID) -> CouponAdminView | None:
        """Consulta um cupom com total de usos e valor descontado."""

    async def list_coupons(self, filters: CouponListFilters, *, now: datetime) -> CouponPage:
        """Lista cupons com filtros de status/busca e paginacao."""

    async def update(self, coupon_id: uuid.UUID, data: CouponWriteData) -> CouponAdminView:
        """Atualiza o cupom e devolve a visao atualizada."""

    async def delete(self, coupon_id: uuid.UUID) -> None:
        """Remove o cupom (o chamador ja garantiu que nao ha resgates)."""

    async def has_redemptions(self, coupon_id: uuid.UUID) -> bool:
        """Indica se existe qualquer resgate, inclusive liberado."""

    async def recent_redemptions(
        self, coupon_id: uuid.UUID, *, limit: int = 10
    ) -> list[CouponRedemptionView]:
        """Ultimos resgates do cupom, mais recentes primeiro."""


class CouponAuditPort(Protocol):
    """Trilha de auditoria tenant-scoped (mesmo contrato do catalogo)."""

    async def record(
        self,
        *,
        company_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        resource: str,
        resource_id: uuid.UUID,
        details: dict[str, object] | None = None,
    ) -> None:
        """Grava a entrada; falha de auditoria propaga."""
