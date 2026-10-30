"""Vocabulario e normalizacao de cupons de desconto (pure Python).

O codigo e normalizado (trim + maiusculas) e restrito a A-Z, 0-9, hifen e
underscore, com 4 a 32 caracteres. Estas funcoes sao a fonte unica para a API;
o banco repete o formato em CHECK para impedir dado fora do padrao.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

COUPON_CODE_MIN_LENGTH = 4
COUPON_CODE_MAX_LENGTH = 32
_COUPON_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{4,32}$")

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")
_ONE = Decimal("1")


class CouponType(StrEnum):
    """Escopo do desconto: total dos produtos ou valor do frete."""

    PRODUCT_TOTAL = "PRODUCT_TOTAL"
    SHIPPING = "SHIPPING"


class CouponRedemptionStatus(StrEnum):
    """Ciclo de vida do resgate de um cupom em um pedido."""

    APPLIED = "APPLIED"
    RELEASED = "RELEASED"


class CouponRejectionReason(StrEnum):
    """Motivos tipados de rejeicao, traduziveis na interface."""

    NOT_FOUND = "NOT_FOUND"
    INACTIVE = "INACTIVE"
    NOT_STARTED = "NOT_STARTED"
    EXPIRED = "EXPIRED"
    EXHAUSTED = "EXHAUSTED"
    COMPANY_LIMIT_REACHED = "COMPANY_LIMIT_REACHED"
    MIN_ORDER_NOT_MET = "MIN_ORDER_NOT_MET"
    NOT_ALLOWED_FOR_COMPANY = "NOT_ALLOWED_FOR_COMPANY"


class DiscountKind(StrEnum):
    """Descontos que podem compor o total de um pedido."""

    RECOVERY = "RECOVERY"
    COUPON_PRODUCT = "COUPON_PRODUCT"
    COUPON_SHIPPING = "COUPON_SHIPPING"
    PIX = "PIX"


@dataclass(frozen=True, slots=True)
class Coupon:
    """Dados imutaveis de um cupom necessarios para validar e calcular.

    O adaptador de persistencia monta esta entidade a partir da linha de
    ``coupons``. Nenhuma operacao de I/O acontece aqui.
    """

    code: str
    type: CouponType
    percent: Decimal
    max_discount_amount: Decimal | None = None
    min_order_amount: Decimal | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = None
    usage_limit_per_company: int | None = None
    restricted_company_id: uuid.UUID | None = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class CouponEligibility:
    """Resultado da elegibilidade: ``ok`` ou motivo tipado."""

    reason: CouponRejectionReason | None = None
    missing_amount: Decimal | None = None

    @property
    def ok(self) -> bool:
        return self.reason is None


@dataclass(frozen=True, slots=True)
class OrderTotals:
    """Totais imutaveis calculados no servidor, sem confiar no cliente."""

    subtotal: Decimal
    recovery_discount: Decimal
    coupon_discount: Decimal
    shipping_discount: Decimal
    pix_discount: Decimal
    total: Decimal
    applied_discounts: frozenset[DiscountKind]


def public_coupon_rejection_reason(
    reason: CouponRejectionReason,
) -> CouponRejectionReason:
    """Nao revela a existencia de cupom restrito a outra empresa.

    A elegibilidade interna continua distinguindo o motivo para logs/testes,
    mas a resposta publica usa NOT_FOUND, dificultando enumeracao.
    """
    if reason is CouponRejectionReason.NOT_ALLOWED_FOR_COMPANY:
        return CouponRejectionReason.NOT_FOUND
    return reason


def normalize_coupon_code(code: str) -> str:
    """Remove espacos das pontas e converte o codigo para maiusculas."""
    return code.strip().upper()


def is_valid_coupon_code(code: str) -> bool:
    """Indica se o codigo respeita o formato aceito pelo banco."""
    return _COUPON_CODE_PATTERN.fullmatch(code) is not None


def evaluate_coupon_eligibility(
    *,
    coupon: Coupon | None,
    company_id: uuid.UUID,
    subtotal: Decimal,
    total_uses: int,
    company_uses: int,
    now: datetime,
) -> CouponEligibility:
    """Valida o cupom para a empresa e o momento informados.

    Precedencia: inexistente -> restrito a outra empresa -> inativo -> ainda
    nao iniciado -> expirado -> esgotado -> limite da empresa -> pedido minimo.
    ``valid_from`` e inclusivo; ``valid_until`` e exclusivo (no instante final
    o cupom ja esta expirado).
    """
    subtotal = _non_negative_money("subtotal", subtotal)

    if coupon is None:
        return CouponEligibility(CouponRejectionReason.NOT_FOUND)

    reason = _scope_rejection(coupon, company_id)
    if reason is None:
        reason = _validity_rejection(coupon, now)
    if reason is None:
        reason = _usage_rejection(coupon, total_uses, company_uses)
    if reason is not None:
        return CouponEligibility(reason)

    if coupon.min_order_amount is not None and subtotal < coupon.min_order_amount:
        missing = _money(coupon.min_order_amount - subtotal)
        return CouponEligibility(CouponRejectionReason.MIN_ORDER_NOT_MET, missing)
    return CouponEligibility()


def calculate_order_totals(
    *,
    subtotal: Decimal,
    shipping: Decimal,
    coupon: Coupon | None = None,
    recovery_discount: Decimal = _ZERO,
    pix_discount_rate: Decimal | None = None,
) -> OrderTotals:
    """Aplica recovery -> cupom -> frete -> PIX, na ordem oficial.

    O cupom recebido deve ter passado por ``evaluate_coupon_eligibility``.
    ``recovery_discount`` e o valor ja apurado pela politica de recuperacao
    (zero quando nao ha oferta). Um cupom ``PRODUCT_TOTAL`` zera esse valor,
    pois os dois nunca acumulam. ``pix_discount_rate`` nulo desliga o PIX;
    quando informado, deve estar entre 0 e 1 (5% = ``Decimal("0.05")``).
    """
    subtotal = _money(_non_negative_money("subtotal", subtotal))
    shipping = _money(_non_negative_money("shipping", shipping))
    recovery_input = _money(_non_negative_money("recovery_discount", recovery_discount))

    recovery, coupon_discount = _product_discounts(subtotal, coupon, recovery_input)
    shipping_discount = _shipping_discount(shipping, coupon)

    product_net = max(subtotal - recovery - coupon_discount, _ZERO)
    shipping_net = max(shipping - shipping_discount, _ZERO)
    pre_pix = _money(product_net + shipping_net)
    pix_discount = _pix_discount(pre_pix, pix_discount_rate)
    total = _money(max(pre_pix - pix_discount, _ZERO))

    return OrderTotals(
        subtotal=subtotal,
        recovery_discount=recovery,
        coupon_discount=coupon_discount,
        shipping_discount=shipping_discount,
        pix_discount=pix_discount,
        total=total,
        applied_discounts=_applied_discounts(
            recovery=recovery,
            coupon_discount=coupon_discount,
            shipping_discount=shipping_discount,
            pix_discount=pix_discount,
        ),
    )


def _scope_rejection(coupon: Coupon, company_id: uuid.UUID) -> CouponRejectionReason | None:
    if coupon.restricted_company_id is not None and coupon.restricted_company_id != company_id:
        return CouponRejectionReason.NOT_ALLOWED_FOR_COMPANY
    if not coupon.is_active:
        return CouponRejectionReason.INACTIVE
    return None


def _validity_rejection(coupon: Coupon, now: datetime) -> CouponRejectionReason | None:
    if coupon.valid_from is not None and now < coupon.valid_from:
        return CouponRejectionReason.NOT_STARTED
    if coupon.valid_until is not None and now >= coupon.valid_until:
        return CouponRejectionReason.EXPIRED
    return None


def _usage_rejection(
    coupon: Coupon, total_uses: int, company_uses: int
) -> CouponRejectionReason | None:
    if coupon.usage_limit_total is not None and total_uses >= coupon.usage_limit_total:
        return CouponRejectionReason.EXHAUSTED
    if (
        coupon.usage_limit_per_company is not None
        and company_uses >= coupon.usage_limit_per_company
    ):
        return CouponRejectionReason.COMPANY_LIMIT_REACHED
    return None


def _product_discounts(
    subtotal: Decimal, coupon: Coupon | None, recovery_input: Decimal
) -> tuple[Decimal, Decimal]:
    if coupon is not None and coupon.type == CouponType.PRODUCT_TOTAL:
        # O cupom de produtos prevalece e desliga a recuperacao.
        return _ZERO, _percent_discount(subtotal, coupon)
    return min(recovery_input, subtotal), _ZERO


def _shipping_discount(shipping: Decimal, coupon: Coupon | None) -> Decimal:
    if coupon is None or coupon.type == CouponType.PRODUCT_TOTAL:
        return _ZERO
    if coupon.type == CouponType.SHIPPING:
        return _percent_discount(shipping, coupon)
    raise ValueError("unsupported coupon type")


def _pix_discount(pre_pix: Decimal, pix_discount_rate: Decimal | None) -> Decimal:
    if pix_discount_rate is None:
        return _ZERO
    rate = _require_decimal("pix_discount_rate", pix_discount_rate)
    if rate < _ZERO or rate > _ONE:
        raise ValueError("pix_discount_rate must be between 0 and 1")
    if rate == _ZERO:
        return _ZERO
    return min(_money(pre_pix * rate), pre_pix)


def _applied_discounts(
    *,
    recovery: Decimal,
    coupon_discount: Decimal,
    shipping_discount: Decimal,
    pix_discount: Decimal,
) -> frozenset[DiscountKind]:
    applied: set[DiscountKind] = set()
    if recovery > _ZERO:
        applied.add(DiscountKind.RECOVERY)
    if coupon_discount > _ZERO:
        applied.add(DiscountKind.COUPON_PRODUCT)
    if shipping_discount > _ZERO:
        applied.add(DiscountKind.COUPON_SHIPPING)
    if pix_discount > _ZERO:
        applied.add(DiscountKind.PIX)
    return frozenset(applied)


def _percent_discount(base: Decimal, coupon: Coupon) -> Decimal:
    percent = _require_decimal("coupon percent", coupon.percent)
    if percent <= _ZERO or percent > _HUNDRED:
        raise ValueError("coupon percent must be between 0 (exclusive) and 100")
    raw = base * percent / _HUNDRED
    if coupon.max_discount_amount is not None:
        ceiling = _positive_money("max_discount_amount", coupon.max_discount_amount)
        raw = min(raw, ceiling)
    return _money(max(min(raw, base), _ZERO))


def _require_decimal(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal, never float")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _non_negative_money(name: str, value: Decimal) -> Decimal:
    amount = _require_decimal(name, value)
    if amount < _ZERO:
        raise ValueError(f"{name} must be non-negative")
    return amount


def _positive_money(name: str, value: Decimal) -> Decimal:
    amount = _non_negative_money(name, value)
    if amount == _ZERO:
        raise ValueError(f"{name} must be positive")
    return amount


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)
