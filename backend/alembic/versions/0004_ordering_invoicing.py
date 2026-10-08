"""Cria pedidos e faturas (migration 0004).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07

``orders`` e ``order_items`` preservam o estado financeiro no momento da
compra (snapshot de sku, nome, preco unitario, tier e impostos). ``invoices``
representa o boleto faturado (30/60 dias). Todas tenant-scoped com RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "buyer_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'RECEIVED'")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("shipping_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "shipping_address_id",
            sa.Uuid(),
            sa.ForeignKey("company_addresses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "billing_address_id",
            sa.Uuid(),
            sa.ForeignKey("company_addresses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("po_number", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'CREDIT_REVIEW', 'INVOICED', 'IN_TRANSIT', "
            "'DELIVERED', 'CANCELLED', 'CREDIT_REJECTED')",
            name="status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="subtotal"),
        sa.CheckConstraint("discount_total >= 0", name="discount_total"),
        sa.CheckConstraint("shipping_total >= 0", name="shipping_total"),
        sa.CheckConstraint("tax_total >= 0", name="tax_total"),
        sa.CheckConstraint("total >= 0", name="total"),
    )
    op.create_index("ix_orders_company_id", "orders", ["company_id"])
    op.create_index("ix_orders_buyer_user_id", "orders", ["buyer_user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index(
        "uq_orders_idempotency_key",
        "orders",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "price_tier_id",
            sa.Uuid(),
            sa.ForeignKey("product_price_tiers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("base_unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "discount_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("tier_min_quantity", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("quantity > 0", name="quantity"),
        sa.CheckConstraint("unit_price >= 0", name="unit_price"),
        sa.CheckConstraint("discount_amount >= 0", name="discount"),
        sa.CheckConstraint("tax_amount >= 0", name="tax"),
        sa.CheckConstraint("line_total >= 0", name="line_total"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_company_id", "order_items", ["company_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("payment_terms", sa.String(24), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("boleto_reference", sa.String(100), nullable=True),
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
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'OVERDUE', 'CANCELLED')",
            name="status",
        ),
        sa.CheckConstraint("payment_terms IN ('NET_30', 'NET_60')", name="payment_terms"),
        sa.CheckConstraint("amount >= 0", name="amount"),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_due_at", "invoices", ["due_at"])

    _tenant_rls("orders")
    _tenant_rls("order_items")
    _tenant_rls("invoices")


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("order_items")
    op.drop_table("orders")
