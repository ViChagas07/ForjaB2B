"""Preferencia de privacidade: ocultar os gastos no painel do cliente.

A coluna guarda apenas a escolha de exibicao do usuario. Nenhum valor
financeiro e alterado; o painel usa a preferencia para mascarar o total gasto
e os totais do historico de compras.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from alembic import op
from app.core.migration_helpers import add_column_if_owner

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    add_column_if_owner(
        conn,
        "users",
        "hide_spending",
        "BOOLEAN",
        nullable=False,
        default="false",
    )


def downgrade() -> None:
    op.drop_column("users", "hide_spending")
