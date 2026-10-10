"""Adiciona a imagem do produto (migration 0015).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-10

``products.image_url`` (opcional) guarda a foto real do produto (Fase 9A-3).
Enquanto estiver nulo, a API resolve a imagem padrao da categoria e, na
ausencia desta, um placeholder generico. A coluna e nullable e a escrita
segue revogada de ``forja_app`` (catalogo global e somente leitura em runtime).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_url")
