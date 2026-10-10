"""Testes do documento indexavel de produto (puro, sem frameworks)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.modules.search.application.documents import build_product_document, is_row_sellable
from app.modules.search.application.ports import ProductRow


def _row(
    *,
    status: str = "ACTIVE",
    is_epi: bool = True,
    ca_valid_until: date | None = date(2029, 12, 31),
    updated_at: datetime = datetime(2026, 1, 2, tzinfo=UTC),
) -> ProductRow:
    return ProductRow(
        id=uuid.UUID("00000000-0000-0000-0000-000000000301"),
        sku="CAP-002",
        name="Capacete de Segurança Classe A",
        description="descricao",
        slug="capacete-de-seguranca-classe-a",
        status=status,
        is_epi=is_epi,
        ca_number="DEMO-CA-0001",
        ca_valid_until=ca_valid_until,
        category_id=uuid.UUID("00000000-0000-0000-0000-000000000401"),
        category_name="Proteção da Cabeça",
        category_slug="protecao-cabeca",
        brand_id=uuid.UUID("00000000-0000-0000-0000-000000000501"),
        brand_name="PROTEC",
        brand_slug="protec",
        attributes={"cor": "branco"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=updated_at,
    )


def test_documento_nao_contem_preco_nem_dados_sensiveis() -> None:
    source = build_product_document(_row(), today=date(2026, 6, 1)).to_source()
    assert not any("price" in key for key in source)
    assert "preco" not in " ".join(source)


def test_version_deriva_de_updated_at() -> None:
    row = _row()
    expected = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp() * 1000)
    assert row.version == expected
    assert build_product_document(row, today=date(2026, 6, 1)).version == expected


def test_disponibilidade_reflete_status_e_ca() -> None:
    today = date(2026, 6, 1)
    assert is_row_sellable(_row(), today=today) is True
    assert is_row_sellable(_row(ca_valid_until=date(2020, 1, 1)), today=today) is False
    assert is_row_sellable(_row(ca_valid_until=None), today=today) is False
    assert is_row_sellable(_row(status="INACTIVE"), today=today) is False
    assert is_row_sellable(_row(is_epi=False, ca_valid_until=None), today=today) is True


def test_documento_ca_e_iso_ou_ausente() -> None:
    with_ca = build_product_document(_row(), today=date(2026, 6, 1))
    assert with_ca.ca_valid_until == "2029-12-31"
    assert with_ca.is_available is True
    sem_ca = build_product_document(_row(ca_valid_until=None), today=date(2026, 6, 1))
    assert sem_ca.ca_valid_until is None
