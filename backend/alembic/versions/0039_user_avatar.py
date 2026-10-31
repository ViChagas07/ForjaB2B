"""Foto de perfil do usuario (bytes no banco + chave publica aleatoria).

Limite de 2 MB e tipos JPG/PNG/WebP validados tambem na aplicacao. A URL
publica inclui company_id/user_id/chave e e cacheavel de forma imutavel: cada
upload gera uma chave nova.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("avatar_content_type", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column(
        "users", sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "avatar_content_type",
        "users",
        "avatar_content_type IS NULL OR "
        "avatar_content_type IN ('image/jpeg', 'image/png', 'image/webp')",
    )
    op.create_check_constraint(
        "avatar_consistency",
        "users",
        "(avatar_key IS NULL AND avatar_content_type IS NULL AND avatar_data IS NULL "
        "AND avatar_updated_at IS NULL) OR (avatar_key IS NOT NULL AND "
        "avatar_content_type IS NOT NULL AND avatar_data IS NOT NULL AND "
        "avatar_updated_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "avatar_size",
        "users",
        "avatar_data IS NULL OR octet_length(avatar_data) <= 2097152",
    )


def downgrade() -> None:
    op.drop_constraint("avatar_size", "users", type_="check")
    op.drop_constraint("avatar_consistency", "users", type_="check")
    op.drop_constraint("avatar_content_type", "users", type_="check")
    op.drop_column("users", "avatar_updated_at")
    op.drop_column("users", "avatar_data")
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_key")
