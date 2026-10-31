"""Preferencia de privacidade: ocultar os gastos no painel do cliente.

A coluna guarda apenas a escolha de exibicao do usuario. Nenhum valor
financeiro e alterado; o painel usa a preferencia para mascarar o total gasto
e os totais do historico de compras.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "hide_spending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "hide_spending")
