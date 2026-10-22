"""Adiciona ``content_locale`` a pedidos e itens de pedido (migration 0019).

A Fase 9B-a passou a gravar o idioma de conteudo resolvido no pedido
(snapshot do idioma exibido ao comprador), mas a coluna nunca foi criada
no banco: o repositorio de pedidos usa SQL direto com ``content_locale``.
Sem a coluna, criar pedido falha em qualquer banco migrado do zero.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS content_locale "
        "VARCHAR(10) NOT NULL DEFAULT 'pt-BR'"
    )
    op.execute(
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS content_locale "
        "VARCHAR(10) NOT NULL DEFAULT 'pt-BR'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE order_items DROP COLUMN IF EXISTS content_locale")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS content_locale")
