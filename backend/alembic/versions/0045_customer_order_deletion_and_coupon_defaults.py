"""Padroes dos cupons (limite por empresa e validade).

A exclusao de pedidos pelo comprador passou a usar a tabela nova
``customer_hidden_orders`` na 0046, porque a role de migrations do Render nao
e owner das tabelas pre-existentes e nao pode alterar ``orders``.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE coupons SET usage_limit_per_company = 20, usage_limit_total = NULL, "
        "valid_until = CASE "
        "WHEN valid_until IS NULL "
        "OR valid_until < TIMESTAMPTZ '2029-12-31 23:59:59+00' "
        "THEN TIMESTAMPTZ '2029-12-31 23:59:59+00' "
        "ELSE valid_until END"
    )


def downgrade() -> None:
    pass
