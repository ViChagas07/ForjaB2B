"""Testes unitarios das regras de CA/EPI e disponibilidade do catalogo."""

from __future__ import annotations

from datetime import date

from app.modules.catalog.domain.availability import CaStatus, ca_status, is_ca_expired, is_sellable
from app.modules.catalog.domain.enums import ProductStatus

_TODAY = date(2026, 10, 7)


def test_epi_ca_valido() -> None:
    assert ca_status(is_epi=True, ca_valid_until=date(2027, 1, 1), today=_TODAY) is CaStatus.VALID
    assert not is_ca_expired(is_epi=True, ca_valid_until=date(2027, 1, 1), today=_TODAY)
    assert is_sellable(
        status=ProductStatus.ACTIVE,
        is_epi=True,
        ca_valid_until=date(2027, 1, 1),
        today=_TODAY,
    )


def test_epi_ca_expirado() -> None:
    assert (
        ca_status(is_epi=True, ca_valid_until=date(2026, 10, 6), today=_TODAY) is CaStatus.EXPIRED
    )
    assert is_ca_expired(is_epi=True, ca_valid_until=date(2026, 10, 6), today=_TODAY)
    assert not is_sellable(
        status=ProductStatus.ACTIVE,
        is_epi=True,
        ca_valid_until=date(2026, 10, 6),
        today=_TODAY,
    )


def test_epi_ca_vence_exatamente_hoje_eh_valido() -> None:
    assert ca_status(is_epi=True, ca_valid_until=_TODAY, today=_TODAY) is CaStatus.VALID
    assert not is_ca_expired(is_epi=True, ca_valid_until=_TODAY, today=_TODAY)


def test_epi_sem_ca() -> None:
    assert ca_status(is_epi=True, ca_valid_until=None, today=_TODAY) is CaStatus.MISSING
    assert not is_ca_expired(is_epi=True, ca_valid_until=None, today=_TODAY)
    assert not is_sellable(
        status=ProductStatus.ACTIVE, is_epi=True, ca_valid_until=None, today=_TODAY
    )


def test_produto_nao_epi_ca_inexistente_permitido() -> None:
    assert ca_status(is_epi=False, ca_valid_until=None, today=_TODAY) is CaStatus.NOT_APPLICABLE
    assert is_sellable(status=ProductStatus.ACTIVE, is_epi=False, ca_valid_until=None, today=_TODAY)


def test_produto_inativo_nao_vende() -> None:
    assert not is_sellable(
        status=ProductStatus.INACTIVE,
        is_epi=False,
        ca_valid_until=None,
        today=_TODAY,
    )
    assert not is_sellable(
        status=ProductStatus.INACTIVE,
        is_epi=True,
        ca_valid_until=date(2027, 1, 1),
        today=_TODAY,
    )
