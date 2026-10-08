"""Utilitarios compartilhados pelos mapeadores ORM da Fase 1.

Convencoes de persistencia que valem para todas as tabelas de dominio:

- Dinheiro nunca e FLOAT: NUMERIC com escala fixa.
  - ``unit_money()`` -> NUMERIC(12,2) para precos unitarios, descontos e
    impostos por item.
  - ``aggregate_money()`` -> NUMERIC(14,2) para totais de pedido/fatura e
    limites de credito.
- Moeda explicita por tabela monetaria (padrao BRL).
- Timestamps sempre timezone-aware (TIMESTAMPTZ), nunca datetime naive.
- Identidade por UUID v7-like via gen_random_uuid() do pgcrypto (ja
  instalado no bootstrap). A geracao UUID e do banco, deterministica e
  independente da aplicacao.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

DEFAULT_CURRENCY = "BRL"
CURRENCY_LENGTH = 3


def enum_check(column: str, enum_cls: type[StrEnum]) -> CheckConstraint:
    """CheckConstraint deterministica para um conjunto fechado de estados.

    Deriva os valores diretamente do enum Python, eliminando divergencia
    entre o vocabulario (dominio) e a constraint no banco. O nome final e
    ``ck_<table>_<column>`` (a convencao de nomes de ``Base.metadata``
    prefixa ``ck_<table>_`` sobre o sufixo ``column``).
    """
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return CheckConstraint(f"{column} IN ({values})", name=column)


def unit_money() -> Numeric[Decimal]:
    """Preco unitario, desconto e imposto por item: NUMERIC(12,2)."""
    return Numeric(12, 2)


def aggregate_money() -> Numeric[Decimal]:
    """Total de pedido/fatura e limite de credito: NUMERIC(14,2)."""
    return Numeric(14, 2)


def currency_column() -> Mapped[str]:
    """Coluna de moeda (ISO 4217, 3 letras) com padrao BRL."""
    return mapped_column(
        String(CURRENCY_LENGTH),
        nullable=False,
        server_default=DEFAULT_CURRENCY,
    )


class TimestampMixin:
    """created_at/updated_at padronizados, timezone-aware e no banco."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
