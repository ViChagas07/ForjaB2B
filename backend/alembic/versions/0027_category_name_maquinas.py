"""Corrige a acentuacao do nome da categoria de maquinas.

O seed original gravou "Maquinas e Ferramentas" sem acento. O seed novo ja
nasce correto, mas bancos existentes precisam deste UPDATE idempotente.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SLUG = "maquinas-e-ferramentas"
_CORRECT_NAME = "Máquinas e Ferramentas"
_LEGACY_NAME = "Maquinas e Ferramentas"


def _rename(old_name: str, new_name: str) -> None:
    op.execute(
        sa.text(
            "UPDATE categories SET name = :new_name WHERE slug = :slug AND name = :old_name"
        ).bindparams(new_name=new_name, slug=_SLUG, old_name=old_name)
    )


def upgrade() -> None:
    _rename(_LEGACY_NAME, _CORRECT_NAME)


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE categories SET name = :new_name WHERE slug = :slug AND name = :old_name"
        ).bindparams(new_name=_LEGACY_NAME, slug=_SLUG, old_name=_CORRECT_NAME)
    )
