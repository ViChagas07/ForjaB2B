"""Tabela de pedidos ocultos pelo comprador.

A role de migrations do Render nao e owner de ``orders`` nem tem REFERENCES nas
tabelas pre-existentes, entao a exclusao logica do historico fica em uma tabela
nova (mesmo padrao de ``order_item_pricing``). A 0045 chegou a adicionar
``orders.deleted_at`` em ambientes onde a role era owner; esta migration copia
esses dados e remove a coluna antiga quando possivel.

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op
from app.core.migration_helpers import is_owner

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_hidden_orders",
        sa.Column("order_id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_customer_hidden_orders_company_buyer",
        "customer_hidden_orders",
        ["company_id", "buyer_user_id"],
    )

    conn = op.get_bind()
    order_columns = {column["name"] for column in inspect(conn).get_columns("orders")}
    if "deleted_at" not in order_columns:
        return

    op.execute(
        "INSERT INTO customer_hidden_orders (order_id, company_id, buyer_user_id, deleted_at) "
        "SELECT id, company_id, buyer_user_id, deleted_at FROM orders "
        "WHERE deleted_at IS NOT NULL "
        "ON CONFLICT (order_id) DO NOTHING"
    )
    if is_owner(conn, "orders"):
        op.execute("DROP INDEX IF EXISTS ix_orders_company_buyer_deleted")
        op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS deleted_at")


def downgrade() -> None:
    op.drop_index(
        "ix_customer_hidden_orders_company_buyer",
        table_name="customer_hidden_orders",
    )
    op.drop_table("customer_hidden_orders")
