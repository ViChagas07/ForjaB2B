"""Sistema de cupons: cadastro global, resgates e snapshot no pedido.

- ``coupons`` e GLOBAL como o catalogo: administrada pela role ``forja_admin``;
  ``forja_app`` (runtime) apenas le. ``restricted_company_id`` opcional limita
  o uso a uma empresa, sem tornar a tabela tenant-scoped.
- ``coupon_redemptions`` e TENANT-SCOPED com FORCE RLS por ``company_id`` e
  guarda o uso do cupom no pedido (``order_id`` unico: um cupom por pedido).
- ``orders`` recebe o snapshot do cupom (codigo, tipo, percentual) e os valores
  efetivamente descontados nos produtos e no frete; ``discount_total`` mantem
  o significado anterior (desconto de recuperacao de carrinho).

A normalizacao do codigo (trim + maiusculas) e feita pela aplicacao; o CHECK
do banco garante o formato final (A-Z, 0-9, hifen e underscore, 4..32).

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
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
        "coupons",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_order_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_limit_total", sa.Integer(), nullable=True),
        sa.Column("usage_limit_per_company", sa.Integer(), nullable=True),
        sa.Column(
            "restricted_company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        sa.CheckConstraint("type IN ('PRODUCT_TOTAL', 'SHIPPING')", name="type"),
        sa.CheckConstraint("code ~ '^[A-Z0-9_-]{4,32}$'", name="code_format"),
        sa.CheckConstraint("percent > 0 AND percent <= 100", name="percent_range"),
        sa.CheckConstraint(
            "max_discount_amount IS NULL OR max_discount_amount > 0",
            name="max_discount_amount_positive",
        ),
        sa.CheckConstraint(
            "min_order_amount IS NULL OR min_order_amount >= 0",
            name="min_order_amount_non_negative",
        ),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="validity_window",
        ),
        sa.CheckConstraint(
            "usage_limit_total IS NULL OR usage_limit_total > 0",
            name="usage_limit_total_positive",
        ),
        sa.CheckConstraint(
            "usage_limit_per_company IS NULL OR usage_limit_per_company > 0",
            name="usage_limit_per_company_positive",
        ),
    )

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "coupon_id",
            sa.Uuid(),
            sa.ForeignKey("coupons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "amount_discounted",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'APPLIED'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),
        sa.CheckConstraint(
            "status IN ('APPLIED', 'RELEASED')",
            name="status",
        ),
        sa.CheckConstraint(
            "amount_discounted >= 0",
            name="amount_discounted_non_negative",
        ),
    )
    op.create_index(
        "ix_coupon_redemptions_coupon_status",
        "coupon_redemptions",
        ["coupon_id", "status"],
    )
    op.create_index(
        "ix_coupon_redemptions_coupon_company_status",
        "coupon_redemptions",
        ["coupon_id", "company_id", "status"],
    )

    _tenant_rls("coupon_redemptions")

    # Cupons sao gerenciados pelo backoffice (role forja_admin): o runtime so le.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON coupons FROM {_APP_ROLE}")

    op.add_column("orders", sa.Column("coupon_code", sa.String(32), nullable=True))
    op.add_column("orders", sa.Column("coupon_type", sa.String(24), nullable=True))
    op.add_column("orders", sa.Column("coupon_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "coupon_discount_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "shipping_discount_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_check_constraint(
        "coupon_type",
        "orders",
        "coupon_type IS NULL OR coupon_type IN ('PRODUCT_TOTAL', 'SHIPPING')",
    )
    op.create_check_constraint(
        "coupon_percent_range",
        "orders",
        "coupon_percent IS NULL OR (coupon_percent > 0 AND coupon_percent <= 100)",
    )
    op.create_check_constraint(
        "coupon_discount_non_negative",
        "orders",
        "coupon_discount_amount >= 0",
    )
    op.create_check_constraint(
        "shipping_discount_non_negative",
        "orders",
        "shipping_discount_amount >= 0",
    )
    op.create_check_constraint(
        "coupon_discount_within_subtotal",
        "orders",
        "coupon_discount_amount <= subtotal",
    )
    op.create_check_constraint(
        "shipping_discount_within_shipping",
        "orders",
        "shipping_discount_amount <= shipping_total",
    )
    op.create_check_constraint(
        "coupon_code_format",
        "orders",
        "coupon_code IS NULL OR coupon_code ~ '^[A-Z0-9_-]{4,32}$'",
    )
    op.create_check_constraint(
        "coupon_snapshot_complete",
        "orders",
        "(coupon_code IS NULL AND coupon_type IS NULL AND coupon_percent IS NULL) "
        "OR (coupon_code IS NOT NULL AND coupon_type IS NOT NULL "
        "AND coupon_percent IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("coupon_snapshot_complete", "orders", type_="check")
    op.drop_constraint("coupon_code_format", "orders", type_="check")
    op.drop_constraint("shipping_discount_within_shipping", "orders", type_="check")
    op.drop_constraint("coupon_discount_within_subtotal", "orders", type_="check")
    op.drop_constraint("shipping_discount_non_negative", "orders", type_="check")
    op.drop_constraint("coupon_discount_non_negative", "orders", type_="check")
    op.drop_constraint("coupon_percent_range", "orders", type_="check")
    op.drop_constraint("coupon_type", "orders", type_="check")
    op.drop_column("orders", "shipping_discount_amount")
    op.drop_column("orders", "coupon_discount_amount")
    op.drop_column("orders", "coupon_percent")
    op.drop_column("orders", "coupon_type")
    op.drop_column("orders", "coupon_code")
    op.drop_table("coupon_redemptions")
    op.drop_table("coupons")
