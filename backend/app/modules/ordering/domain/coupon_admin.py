"""Dominio puro da administracao de cupons (sem frameworks nem I/O).

Concentra validacao de campos, normalizacao de codigo, geracao de codigo
aleatorio e os modelos de leitura usados pela API admin. A persistencia e a
autorizacao ficam nas camadas de aplicacao/infraestrutura.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.modules.ordering.domain.coupon import (
    CouponRedemptionStatus,
    CouponType,
    is_valid_coupon_code,
    normalize_coupon_code,
)

_ZERO = Decimal("0.00")
_MIN_PERCENT = Decimal("0.01")
_MAX_PERCENT = Decimal("100")
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_SUFFIX_LENGTH = 6
_CODE_PREFIX = "FORJA-"


class CouponAdminError(Exception):
    """Erro base da administracao de cupons."""

    code = "coupon_admin_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CouponValidationError(CouponAdminError):
    """Campo ou combinacao de campos invalida."""

    code = "invalid_coupon"


class CouponCodeConflictError(CouponAdminError):
    """Codigo ja cadastrado."""

    code = "coupon_code_conflict"


class CouponCompanyNotFoundError(CouponAdminError):
    """Empresa usada na restricao nao existe."""

    code = "coupon_company_not_found"


class CouponNotFoundError(CouponAdminError):
    """Cupom inexistente."""

    code = "coupon_not_found"


class CouponImmutableFieldError(CouponAdminError):
    """Tentativa de alterar codigo/tipo depois de existir resgate."""

    code = "coupon_immutable_field"


class CouponHasRedemptionsError(CouponAdminError):
    """Exclusao bloqueada porque o cupom possui resgates."""

    code = "coupon_has_redemptions"


@dataclass(frozen=True, slots=True)
class CouponCreateData:
    """Dados de criacao; ``code`` nulo pede geracao automatica."""

    code: str | None
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
class CouponWriteData:
    """Estado completo de um cupom para criacao ou atualizacao."""

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
class CouponUpdateData:
    """Campos opcionais de PATCH; ``provided`` distingue omitido de nulo."""

    provided: frozenset[str]
    code: str | None = None
    type: CouponType | None = None
    percent: Decimal | None = None
    max_discount_amount: Decimal | None = None
    min_order_amount: Decimal | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = None
    usage_limit_per_company: int | None = None
    restricted_company_id: uuid.UUID | None = None
    is_active: bool | None = None


@dataclass(frozen=True, slots=True)
class CouponListFilters:
    """Filtros e paginacao da listagem administrativa."""

    q: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class CouponRedemptionView:
    """Resgate exibido no detalhe administrativo."""

    id: uuid.UUID
    order_id: uuid.UUID
    company_id: uuid.UUID
    amount_discounted: Decimal
    status: CouponRedemptionStatus
    created_at: datetime
    released_at: datetime | None


@dataclass(frozen=True, slots=True)
class CouponAdminView:
    """Cupom com agregados de uso para a API administrativa."""

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
    total_uses: int = 0
    total_discounted: Decimal = _ZERO
    last_redemptions: tuple[CouponRedemptionView, ...] = ()


@dataclass(frozen=True, slots=True)
class CouponPage:
    """Pagina de cupons para a listagem administrativa."""

    items: list[CouponAdminView]
    total: int
    page: int
    page_size: int
    pages: int


def generate_coupon_code() -> str:
    """Gera um codigo no formato ``FORJA-XXXXXX`` (sem I/O de persistencia)."""
    suffix = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_SUFFIX_LENGTH))
    return f"{_CODE_PREFIX}{suffix}"


def prepare_coupon_create(data: CouponCreateData) -> CouponWriteData:
    """Gera o codigo quando omitido e devolve o estado validado."""
    code = data.code if data.code is not None else generate_coupon_code()
    return validate_coupon_write(
        CouponWriteData(
            code=code,
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
        )
    )


def normalize_valid_coupon_code(code: str) -> str:
    """Normaliza e valida o formato do codigo."""
    normalized = normalize_coupon_code(code)
    if not is_valid_coupon_code(normalized):
        raise CouponValidationError(
            "Código inválido: use de 4 a 32 caracteres A-Z, 0-9, hífen ou underscore."
        )
    return normalized


def validate_coupon_write(data: CouponWriteData) -> CouponWriteData:
    """Normaliza o codigo e valida todos os campos do cupom.

    Retorna uma copia com o codigo normalizado; levanta
    ``CouponValidationError`` com mensagem segura para o admin.
    """
    normalized = normalize_valid_coupon_code(data.code)
    if data.percent < _MIN_PERCENT or data.percent > _MAX_PERCENT:
        raise CouponValidationError("O percentual deve estar entre 0,01 e 100.")
    if data.max_discount_amount is not None and data.max_discount_amount <= _ZERO:
        raise CouponValidationError("O teto de desconto deve ser maior que zero.")
    if data.min_order_amount is not None and data.min_order_amount < _ZERO:
        raise CouponValidationError("O pedido mínimo não pode ser negativo.")
    if data.usage_limit_total is not None and data.usage_limit_total < 1:
        raise CouponValidationError("O limite total de usos deve ser pelo menos 1.")
    if data.usage_limit_per_company is not None and data.usage_limit_per_company < 1:
        raise CouponValidationError("O limite por empresa deve ser pelo menos 1.")
    if (
        data.valid_from is not None
        and data.valid_until is not None
        and data.valid_until <= data.valid_from
    ):
        raise CouponValidationError("A validade final deve ser posterior à inicial.")
    return replace(data, code=normalized)


def merge_coupon_update(current: CouponAdminView, update: CouponUpdateData) -> CouponWriteData:
    """Combina o estado atual com os campos enviados no PATCH."""
    provided = update.provided

    if "code" in provided and update.code is None:
        raise CouponValidationError("O código não pode ser nulo.")
    if "type" in provided and update.type is None:
        raise CouponValidationError("O tipo não pode ser nulo.")
    if "percent" in provided and update.percent is None:
        raise CouponValidationError("O percentual não pode ser nulo.")
    if "is_active" in provided and update.is_active is None:
        raise CouponValidationError("O status ativo não pode ser nulo.")

    return CouponWriteData(
        code=update.code if "code" in provided and update.code is not None else current.code,
        type=(update.type if "type" in provided and update.type is not None else current.type),
        percent=(
            update.percent
            if "percent" in provided and update.percent is not None
            else current.percent
        ),
        max_discount_amount=(
            update.max_discount_amount
            if "max_discount_amount" in provided
            else current.max_discount_amount
        ),
        min_order_amount=(
            update.min_order_amount if "min_order_amount" in provided else current.min_order_amount
        ),
        valid_from=(update.valid_from if "valid_from" in provided else current.valid_from),
        valid_until=(update.valid_until if "valid_until" in provided else current.valid_until),
        usage_limit_total=(
            update.usage_limit_total
            if "usage_limit_total" in provided
            else current.usage_limit_total
        ),
        usage_limit_per_company=(
            update.usage_limit_per_company
            if "usage_limit_per_company" in provided
            else current.usage_limit_per_company
        ),
        restricted_company_id=(
            update.restricted_company_id
            if "restricted_company_id" in provided
            else current.restricted_company_id
        ),
        is_active=(
            update.is_active
            if "is_active" in provided and update.is_active is not None
            else current.is_active
        ),
    )
