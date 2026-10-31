"""Preferencia de moeda de EXIBICAO no perfil do usuario.

A coluna guarda apenas a escolha visual (lista fechada). Nenhum valor
financeiro muda: pedidos, pagamentos e totais continuam em BRL.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.migration_helpers import (
    add_column_if_owner,
    create_check_constraint_if_owner,
)


revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    add_column_if_owner(
        conn,
        "users",
        "display_currency",
        "VARCHAR(3)",
        nullable=False,
        default="'BRL'",
    )
    create_check_constraint_if_owner(
        conn,
        "users",
        "display_currency",
        "display_currency IN ('BRL', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY')",
    )


def downgrade() -> None:
    op.drop_constraint("display_currency", "users", type_="check")
    op.drop_column("users", "display_currency")