"""Base declarativa do SQLAlchemy 2.x e metadados para o Alembic.

Nenhum modelo de dominio na Fase 0: este modulo existe para ancorar
`target_metadata` do Alembic e os futuros mapeadores ORM por modulo.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convencao de nomes para constraints/indexes: migrations deterministicas.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa compartilhada pelos mapeadores ORM dos modulos."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
