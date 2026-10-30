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

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(24), nullable=True))
    op.add_column("users", sa.Column("postal_code", sa.String(8), nullable=True))
    op.create_check_constraint(
        "gender",
        "users",
        "gender IS NULL OR gender IN ('FEMININO', 'MASCULINO', 'NAO_BINARIO', "
        "'OUTRO', 'PREFIRO_NAO_INFORMAR')",
    )
    op.create_check_constraint(
        "postal_code_format",
        "users",
        "postal_code IS NULL OR postal_code ~ '^[0-9]{8}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_postal_code_format", "users", type_="check")
    op.drop_constraint("ck_users_gender", "users", type_="check")
    op.drop_column("users", "postal_code")
    op.drop_column("users", "gender")
    op.drop_column("users", "birth_date")
