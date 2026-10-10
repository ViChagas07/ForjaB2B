"""Habilita pgvector e cria o armazenamento de embeddings (migration 0013).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-10

``product_embeddings`` guarda o vetor semantico por produto em tabela separada,
para permitir regerar embeddings sem tocar em ``products``. Como o catalogo, e
GLOBAL (sem RLS e sem ``company_id``). O tipo ``vector(384)`` e fixado pela
migration: trocar o modelo/dimensao exige nova migration + reindexacao completa.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE product_embeddings (
            product_id uuid PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
            model varchar(200) NOT NULL,
            dimension integer NOT NULL,
            embedding vector(384) NOT NULL,
            content_hash varchar(64) NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_product_embeddings_hnsw "
        "ON product_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS product_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
