"""Mapeador ORM das regras de preco por empresa (CompanyPriceRule).

Diferente do catalogo (global), esta tabela e TENANT-SCOPED: cada empresa so
enxerga as proprias regras (FORCE ROW LEVEL SECURITY por ``company_id``). Ela
permite duas condicoes comerciais por empresa:

- ``FIXED_PRICE``: preco unitario negociado para um produto (vence a lista);
- ``PERCENT_DISCOUNT``: desconto percentual sobre o preco de lista, por
  categoria (``category_id``) ou global (``category_id`` nulo).

Precos por empresa NUNCA entram no indice de busca nem no texto de embedding:
sao hidratados do PostgreSQL no momento da leitura (ver app/domain/pricing.py).
Os mapeadores existem tambem para o ``Base.metadata`` (drift detection).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin, currency_column, unit_money

FIXED_PRICE = "FIXED_PRICE"
PERCENT_DISCOUNT = "PERCENT_DISCOUNT"
RULE_TYPES = (FIXED_PRICE, PERCENT_DISCOUNT)


class CompanyPriceRule(TimestampMixin, Base):
    """Regra de preco negociado/desconto de uma empresa (tenant-scoped)."""

    __tablename__ = "company_price_rules"
    __table_args__ = (
        CheckConstraint("rule_type IN ('FIXED_PRICE', 'PERCENT_DISCOUNT')", name="rule_type"),
        CheckConstraint(
            "rule_type <> 'FIXED_PRICE' OR (product_id IS NOT NULL AND unit_price IS NOT NULL "
            "AND unit_price > 0 AND percent IS NULL AND category_id IS NULL)",
            name="fixed_price_fields",
        ),
        CheckConstraint(
            "rule_type <> 'PERCENT_DISCOUNT' OR (percent IS NOT NULL AND percent > 0 "
            "AND percent <= 100 AND unit_price IS NULL)",
            name="percent_discount_fields",
        ),
        Index(
            "uq_company_price_rules_fixed",
            "company_id",
            "product_id",
            unique=True,
            postgresql_where=text("rule_type = 'FIXED_PRICE'"),
        ),
        Index(
            "uq_company_price_rules_discount",
            "company_id",
            "category_id",
            unique=True,
            postgresql_where=text("rule_type = 'PERCENT_DISCOUNT' AND category_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    unit_price: Mapped[Decimal | None] = mapped_column(unit_money())
    currency: Mapped[str] = currency_column()
