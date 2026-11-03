"""Exclusao logica de pedidos pelo comprador e padroes dos cupons.

- ``orders.deleted_at`` remove o pedido do historico/rotas do painel sem apagar
  snapshots financeiros, faturas, pagamentos e resgates de cupom.
- Cupons passam a valer ate 31/12/2029, com 20 usos por empresa e sem limite
  global (o limite exibido no painel e sempre por comprador).

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op
from app.core.migration_helpers import (
    add_column_if_owner,
    create_index_if_owner,
    is_owner,
)

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    add_column_if_owner(conn, "orders", "deleted_at", "TIMESTAMPTZ", nullable=True)
    create_index_if_owner(
        conn,
        "orders",
        "ix_orders_company_buyer_deleted",
        ["company_id", "buyer_user_id", "deleted_at"],
    )
    op.execute(
        "UPDATE coupons SET usage_limit_per_company = 20, usage_limit_total = NULL, "
        "valid_until = CASE "
        "WHEN valid_until IS NULL "
        "OR valid_until < TIMESTAMPTZ '2029-12-31 23:59:59+00' "
        "THEN TIMESTAMPTZ '2029-12-31 23:59:59+00' "
        "ELSE valid_until END"
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not is_owner(conn, "orders"):
        return
    op.execute("DROP INDEX IF EXISTS ix_orders_company_buyer_deleted")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS deleted_at")
