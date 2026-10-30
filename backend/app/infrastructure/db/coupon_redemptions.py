"""Liberacao de resgate de cupom compartilhada por pedido e pagamento.

O resgate e tenant-scoped (RLS por company_id). A liberacao acontece na mesma
transacao que cancela o pedido ou que trata a falha/expiração definitiva do
pagamento. O advisory lock por codigo serializa a liberacao com novos resgates
do mesmo cupom, mantendo os limites de uso corretos.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SELECT_ACTIVE_CODE = text(
    "SELECT c.code FROM coupon_redemptions r "
    "JOIN coupons c ON c.id = r.coupon_id "
    "WHERE r.order_id = :order_id AND r.company_id = :company_id "
    "AND r.status = 'APPLIED' LIMIT 1"
)
_LOCK_COUPON = text("SELECT pg_advisory_xact_lock(hashtextextended(:code, 0))")
_RELEASE = text(
    "UPDATE coupon_redemptions SET status = 'RELEASED', released_at = now() "
    "WHERE order_id = :order_id AND company_id = :company_id AND status = 'APPLIED'"
)


async def release_coupon_redemption(
    session: AsyncSession, *, company_id: uuid.UUID, order_id: uuid.UUID
) -> bool:
    """Marca o resgate APPLIED do pedido como RELEASED; devolve se mudou algo."""
    row = (
        await session.execute(
            _SELECT_ACTIVE_CODE,
            {"order_id": order_id, "company_id": company_id},
        )
    ).first()
    if row is None:
        return False
    await session.execute(_LOCK_COUPON, {"code": row.code})
    result = await session.execute(
        _RELEASE,
        {"order_id": order_id, "company_id": company_id},
    )
    return bool(getattr(result, "rowcount", 0))
