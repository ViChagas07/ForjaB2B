"""Elegibilidade de cupom: cada motivo tipado e a precedencia documentada."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponEligibility,
    CouponRejectionReason,
    CouponType,
    evaluate_coupon_eligibility,
)

_NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
_COMPANY = uuid.UUID("eeee0000-0000-4000-8000-00000000e001")
_OTHER_COMPANY = uuid.UUID("eeee0000-0000-4000-8000-00000000e002")
_BASE = Coupon(code="CUPOM10", type=CouponType.PRODUCT_TOTAL, percent=Decimal("10.00"))


def _coupon(**changes: object) -> Coupon:
    return replace(_BASE, **changes)


def _evaluate(
    coupon: Coupon | None,
    *,
    company_id: uuid.UUID = _COMPANY,
    subtotal: str = "1000.00",
    total_uses: int = 0,
    company_uses: int = 0,
    now: datetime = _NOW,
) -> CouponEligibility:
    return evaluate_coupon_eligibility(
        coupon=coupon,
        company_id=company_id,
        subtotal=Decimal(subtotal),
        total_uses=total_uses,
        company_uses=company_uses,
        now=now,
    )


def test_cupom_inexistente() -> None:
    result = _evaluate(None)
    assert result.reason is CouponRejectionReason.NOT_FOUND
    assert result.ok is False


def test_cupom_inativo() -> None:
    result = _evaluate(_coupon(is_active=False))
    assert result.reason is CouponRejectionReason.INACTIVE


def test_cupom_ainda_nao_iniciado() -> None:
    result = _evaluate(_coupon(valid_from=_NOW + timedelta(seconds=1)))
    assert result.reason is CouponRejectionReason.NOT_STARTED


def test_cupom_valido_no_inicio_da_janela() -> None:
    result = _evaluate(_coupon(valid_from=_NOW))
    assert result.ok is True


def test_cupom_expirado_no_instante_final() -> None:
    result = _evaluate(_coupon(valid_until=_NOW))
    assert result.reason is CouponRejectionReason.EXPIRED


def test_cupom_valido_um_segundo_antes_do_fim() -> None:
    result = _evaluate(_coupon(valid_until=_NOW + timedelta(seconds=1)))
    assert result.ok is True


def test_limite_total_esgotado() -> None:
    result = _evaluate(_coupon(usage_limit_total=2), total_uses=2)
    assert result.reason is CouponRejectionReason.EXHAUSTED


def test_limite_total_ainda_disponivel() -> None:
    result = _evaluate(_coupon(usage_limit_total=2), total_uses=1)
    assert result.ok is True


def test_limite_por_empresa_atingido() -> None:
    result = _evaluate(_coupon(usage_limit_per_company=1), company_uses=1)
    assert result.reason is CouponRejectionReason.COMPANY_LIMIT_REACHED


def test_limite_por_empresa_ainda_disponivel() -> None:
    result = _evaluate(_coupon(usage_limit_per_company=1), company_uses=0)
    assert result.ok is True


def test_pedido_minimo_informa_o_faltante() -> None:
    result = _evaluate(_coupon(min_order_amount=Decimal("1500.00")), subtotal="1000.00")
    assert result.reason is CouponRejectionReason.MIN_ORDER_NOT_MET
    assert result.missing_amount == Decimal("500.00")


def test_pedido_minimo_no_limite_e_aceito() -> None:
    result = _evaluate(_coupon(min_order_amount=Decimal("1000.00")), subtotal="1000.00")
    assert result.ok is True
    assert result.missing_amount is None


def test_cupom_restrito_a_outra_empresa() -> None:
    result = _evaluate(_coupon(restricted_company_id=_OTHER_COMPANY))
    assert result.reason is CouponRejectionReason.NOT_ALLOWED_FOR_COMPANY


def test_cupom_restrito_a_propria_empresa_e_aceito() -> None:
    result = _evaluate(_coupon(restricted_company_id=_COMPANY))
    assert result.ok is True


def test_restricao_a_outra_empresa_prevalece_sobre_inativo() -> None:
    result = _evaluate(_coupon(restricted_company_id=_OTHER_COMPANY, is_active=False))
    assert result.reason is CouponRejectionReason.NOT_ALLOWED_FOR_COMPANY


def test_inativo_prevalece_sobre_expirado() -> None:
    result = _evaluate(_coupon(is_active=False, valid_until=_NOW - timedelta(seconds=1)))
    assert result.reason is CouponRejectionReason.INACTIVE


def test_esgotado_prevalece_sobre_pedido_minimo() -> None:
    result = _evaluate(
        _coupon(usage_limit_total=1, min_order_amount=Decimal("9999.00")),
        total_uses=1,
    )
    assert result.reason is CouponRejectionReason.EXHAUSTED


def test_cupom_sem_restricoes_e_aceito() -> None:
    result = _evaluate(_coupon())
    assert result.ok is True
    assert result.reason is None


@pytest.mark.parametrize(
    "reason",
    [
        CouponRejectionReason.NOT_FOUND,
        CouponRejectionReason.INACTIVE,
        CouponRejectionReason.NOT_STARTED,
        CouponRejectionReason.EXPIRED,
        CouponRejectionReason.EXHAUSTED,
        CouponRejectionReason.COMPANY_LIMIT_REACHED,
        CouponRejectionReason.MIN_ORDER_NOT_MET,
        CouponRejectionReason.NOT_ALLOWED_FOR_COMPANY,
    ],
)
def test_motivos_sao_estaveis(reason: CouponRejectionReason) -> None:
    assert reason.value == reason.name
