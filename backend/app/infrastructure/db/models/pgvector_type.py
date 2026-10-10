"""Registro do tipo `vector` (pgvector) na reflexao do SQLAlchemy (Fase 7).

A tabela ``product_embeddings`` e criada por migration com SQL puro (sem
mapeador ORM, por design). Sem este registro, o ``alembic check`` emite um
``SAWarning: Did not recognize type 'vector'`` ao refletir a coluna ``embedding``
e a suite (``filterwarnings=error``) falha. Aqui apenas ensinamos o dialeto a
reconhecer o tipo; o DDL continua 100% na migration.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType[object]):
    """Tipo `vector` do pgvector (somente para reflexao; sem DDL pelo ORM)."""

    cache_ok = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        # O inspetor instancia o tipo com os argumentos refletidos (ex.: a
        # dimensao); aceitamos e ignoramos, pois nao emitimos DDL pelo ORM.
        super().__init__()

    def get_col_spec(self, **kw: object) -> str:
        return "vector"


if "vector" not in ischema_names:
    ischema_names["vector"] = Vector
