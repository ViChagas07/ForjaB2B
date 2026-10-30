"""Validacao pura do CRUD administrativo de cupons."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.ordering.domain.coupon import CouponType
from app.modules.ordering.domain.coupon_admin import (
    CouponAdminView,
    CouponCreateData,
    CouponUpdateData,
    CouponValidationError,
    CouponWriteData,
    generate_coupon_code,
    merge_coupon_update,
    prepare_coupon_create,
    validate_coupon_write,
)

_NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
_COMPANY = uuid.UUID("ffff0000-0000-4000-8000-00000000f001")


def _write(**changes: object) -> CouponWriteData:
    base = CouponWriteData(
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
    )
    return replace(base, **changes)


def _view(**changes: object) -> CouponAdminView:
    base = CouponAdminView(
        id=uuid.UUID("ffff0000-0000-4000-8000-00000000f002"),
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
        max_discount_amount=None,
        min_order_amount=None,
        valid_from=None,
        valid_until=None,
        usage_limit_total=None,
        usage_limit_per_company=None,
        restricted_company_id=None,
        is_active=True,
        created_by=_COMPANY,
        created_at=_NOW,
        updated_at=_NOW,
    )
    return replace(base, **changes)


def test_normaliza_codigo_no_write() -> None:
    result = validate_coupon_write(_write(code="  cupom-10  "))
    assert result.code == "CUPOM-10"


@pytest.mark.parametrize("code", ["abc", "AB", "COM ESPACO", "PONTO.10", "ÁBC1"])
def test_codigo_invalido(code: str) -> None:
    with pytest.raises(CouponValidationError, match="Código inválido"):
        validate_coupon_write(_write(code=code))


@pytest.mark.parametrize("percent", ["0", "0.00", "100.01", "-1"])
def test_percentual_fora_da_faixa(percent: str) -> None:
    with pytest.raises(CouponValidationError, match="percentual"):
        validate_coupon_write(_write(percent=Decimal(percent)))


@pytest.mark.parametrize("percent", ["0.01", "100.00"])
def test_percentual_nos_limites(percent: str) -> None:
    result = validate_coupon_write(_write(percent=Decimal(percent)))
    assert result.percent == Decimal(percent)


def test_teto_de_desconto_deve_ser_positivo() -> None:
    with pytest.raises(CouponValidationError, match="teto"):
        validate_coupon_write(_write(max_discount_amount=Decimal("0.00")))


def test_pedido_minimo_nao_pode_ser_negativo() -> None:
    with pytest.raises(CouponValidationError, match="pedido mínimo"):
        validate_coupon_write(_write(min_order_amount=Decimal("-1.00")))


@pytest.mark.parametrize("field", ["usage_limit_total", "usage_limit_per_company"])
def test_limites_devem_ser_positivos(field: str) -> None:
    with pytest.raises(CouponValidationError, match="limite"):
        validate_coupon_write(_write(**{field: 0}))


def test_validade_final_deve_ser_posterior() -> None:
    with pytest.raises(CouponValidationError, match="validade final"):
        validate_coupon_write(_write(valid_from=_NOW, valid_until=_NOW))


def test_validade_valida_e_aceita() -> None:
    result = validate_coupon_write(_write(valid_from=_NOW, valid_until=_NOW + timedelta(days=1)))
    assert result.valid_until == _NOW + timedelta(days=1)


def test_codigo_gerado_tem_formato_esperado() -> None:
    code = generate_coupon_code()
    assert re.fullmatch(r"FORJA-[A-Z0-9]{6}", code)
    assert code != generate_coupon_code()


def test_create_sem_codigo_gera_codigo() -> None:
    result = prepare_coupon_create(
        CouponCreateData(
            code=None,
            type=CouponType.SHIPPING,
            percent=Decimal("100.00"),
        )
    )
    assert re.fullmatch(r"FORJA-[A-Z0-9]{6}", result.code)


def test_create_com_codigo_mantem_normalizacao() -> None:
    result = prepare_coupon_create(
        CouponCreateData(
            code="  shipping-100 ",
            type=CouponType.SHIPPING,
            percent=Decimal("100.00"),
        )
    )
    assert result.code == "SHIPPING-100"


def test_merge_omite_campos_ausentes() -> None:
    current = _view()
    update = CouponUpdateData(provided=frozenset({"is_active"}), is_active=False)
    result = merge_coupon_update(current, update)
    assert result.code == "CUPOM10"
    assert result.percent == Decimal("10.00")
    assert result.is_active is False


def test_merge_permite_limpar_opcionais_com_null() -> None:
    current = _view(
        max_discount_amount=Decimal("50.00"),
        min_order_amount=Decimal("100.00"),
        valid_from=_NOW,
        valid_until=_NOW + timedelta(days=1),
        usage_limit_total=10,
        usage_limit_per_company=2,
        restricted_company_id=_COMPANY,
    )
    update = CouponUpdateData(
        provided=frozenset(
            {
                "max_discount_amount",
                "min_order_amount",
                "valid_from",
                "valid_until",
                "usage_limit_total",
                "usage_limit_per_company",
                "restricted_company_id",
            }
        )
    )
    result = merge_coupon_update(current, update)
    assert result.max_discount_amount is None
    assert result.min_order_amount is None
    assert result.valid_from is None
    assert result.valid_until is None
    assert result.usage_limit_total is None
    assert result.usage_limit_per_company is None
    assert result.restricted_company_id is None


@pytest.mark.parametrize(
    "field",
    ["code", "type", "percent", "is_active"],
)
def test_merge_rejeita_null_em_campo_obrigatorio(field: str) -> None:
    update = CouponUpdateData(provided=frozenset({field}))
    with pytest.raises(CouponValidationError):
        merge_coupon_update(_view(), update)
