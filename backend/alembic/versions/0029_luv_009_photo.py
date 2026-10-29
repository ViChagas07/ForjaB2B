"""Aplica a foto fornecida ao produto descontinuado de luva de raspa.

O SKU ``LUV-009`` (Luva de Raspa fora de linha) deixa a ilustracao e passa a
usar a foto real em ``/catalog/photos/luv-009.webp``. Bancos existentes
recebem a atualizacao sem exigir um novo seed; o seed tambem aponta para a
mesma foto em ``_PRODUCT_IMAGES``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SKU = "LUV-009"
_PHOTO = "/catalog/photos/luv-009.webp"
_ILLUSTRATION = "/catalog/illustrations/luva-de-raspa.svg"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE products SET image_url = :image_url, updated_at = now() "
            "WHERE sku = :sku AND image_url IS DISTINCT FROM :image_url"
        ).bindparams(image_url=_PHOTO, sku=_SKU)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE products SET image_url = :image_url, updated_at = now() "
            "WHERE sku = :sku AND image_url IS DISTINCT FROM :image_url"
        ).bindparams(image_url=_ILLUSTRATION, sku=_SKU)
    )
