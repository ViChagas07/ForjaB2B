"""Cria as regras de preco por empresa (migration 0014).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-10

``company_price_rules`` e TENANT-SCOPED (RLS por ``company_id``): cada empresa
so enxerga as proprias condicoes. Modela preco negociado (``FIXED_PRICE``) e
desconto percentual por categoria/global (``PERCENT_DISCOUNT``). A escrita e
revogada de ``forja_app`` (a role de runtime so le): as regras sao gerenciadas
pela plataforma/seed (``forja_admin``). Preco individualizado nunca vai ao
indice de busca nem ao texto de embedding.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "forja_app"


def _tenant_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_select ON {table} "
        "FOR SELECT USING (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_insert ON {table} "
        "FOR INSERT WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_update ON {table} "
        "FOR UPDATE USING (company_id = app.current_company_id()) "
        "WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_delete ON {table} "
        "FOR DELETE USING (company_id = app.current_company_id())"
    )


def upgrade() -> None:
    op.create_table(
        "company_price_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("rule_type IN ('FIXED_PRICE', 'PERCENT_DISCOUNT')", name="rule_type"),
        sa.CheckConstraint(
            "rule_type <> 'FIXED_PRICE' OR (product_id IS NOT NULL AND unit_price IS NOT NULL "
            "AND unit_price > 0 AND percent IS NULL AND category_id IS NULL)",
            name="fixed_price_fields",
        ),
        sa.CheckConstraint(
            "rule_type <> 'PERCENT_DISCOUNT' OR (percent IS NOT NULL AND percent > 0 "
            "AND percent <= 100 AND unit_price IS NULL)",
            name="percent_discount_fields",
        ),
    )
    op.create_index("ix_company_price_rules_company_id", "company_price_rules", ["company_id"])
    op.create_index("ix_company_price_rules_product_id", "company_price_rules", ["product_id"])
    op.create_index("ix_company_price_rules_category_id", "company_price_rules", ["category_id"])
    op.create_index(
        "uq_company_price_rules_fixed",
        "company_price_rules",
        ["company_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("rule_type = 'FIXED_PRICE'"),
    )
    op.create_index(
        "uq_company_price_rules_discount",
        "company_price_rules",
        ["company_id", "category_id"],
        unique=True,
        postgresql_where=sa.text("rule_type = 'PERCENT_DISCOUNT' AND category_id IS NOT NULL"),
    )

    _tenant_rls("company_price_rules")

    # Regras de preco sao gerenciadas pela plataforma/seed: o runtime so le.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON company_price_rules FROM {_APP_ROLE}")


def downgrade() -> None:
    op.drop_table("company_price_rules")
