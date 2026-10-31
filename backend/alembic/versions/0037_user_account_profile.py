"""Perfil de conta do usuario: nascimento, genero e CEP.

Campos opcionais em ``users`` para que qualquer conta (PERSON ou COMPANY)
possa manter o proprio perfil. Contas PERSON existentes continuam com os
dados em ``consumer_profiles``; a leitura da API faz fallback e a atualizacao
sincroniza as duas linhas.

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.migration_helpers import (
    add_column_if_owner,
    create_check_constraint_if_owner,
)


revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Adiciona colunas apenas se for dono da tabela users
    add_column_if_owner(conn, "users", "birth_date", "DATE", nullable=True)
    add_column_if_owner(conn, "users", "gender", "VARCHAR(24)", nullable=True)
    add_column_if_owner(conn, "users", "postal_code", "VARCHAR(8)", nullable=True)

    # Constraints apenas se for dono
    create_check_constraint_if_owner(
        conn,
        "users",
        "gender",
        "gender IS NULL OR gender IN ('FEMININO', 'MASCULINO', 'NAO_BINARIO', 'OUTRO', 'PREFIRO_NAO_INFORMAR')",
    )
    create_check_constraint_if_owner(
        conn,
        "users",
        "postal_code_format",
        "postal_code IS NULL OR postal_code ~ '^[0-9]{8}$'",
    )


def downgrade() -> None:
    # Downgrade so remove se for dono - alembic lida com IF EXISTS
    op.drop_constraint("postal_code_format", "users", type_="check")
    op.drop_constraint("gender", "users", type_="check")
    op.drop_column("users", "postal_code")
    op.drop_column("users", "gender")
    op.drop_column("users", "birth_date")