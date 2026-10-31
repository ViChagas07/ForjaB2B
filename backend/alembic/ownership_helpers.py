"""Helpers para migrations seguras sem ownership de tabelas pre-existentes.

Estas funcoes permitem que migrations adicionem colunas, indices e constraints
em tabelas pre-existentes apenas quando o usuario atual e o dono da tabela.
Em dev/CI (usuario dono de tudo), o comportamento e identico ao Alembic nativo.
Em producao (role `forja` sem ownership), as operacoes sao puladas com aviso,
permitindo que a migration prossiga para criar novas tabelas (ex.: user_preferences).
"""

from __future__ import annotations

import logging
from typing import Any

from alembic.operations import Operations
from sqlalchemy import Connection, inspect, text

logger = logging.getLogger("alembic.migration")


def is_owner(conn: Connection, table_name: str, schema: str = "public") -> bool:
    """Verifica se o usuario atual e o dono da tabela."""
    result = conn.execute(
        text(
            "SELECT pg_class.relowner = current_user AS is_owner "
            "FROM pg_class "
            "JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace "
            "WHERE pg_class.relname = :table AND pg_namespace.nspname = :schema"
        ),
        {"table": table_name, "schema": schema},
    ).scalar()
    return bool(result)


def _column_exists(conn: Connection, table: str, column: str, schema: str = "public") -> bool:
    """Verifica se a coluna ja existe na tabela."""
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns(table, schema=schema)]
    return column in columns


def _index_exists(conn: Connection, table: str, index_name: str, schema: str = "public") -> bool:
    """Verifica se o indice ja existe na tabela."""
    inspector = inspect(conn)
    indexes = [i["name"] for i in inspector.get_indexes(table, schema=schema)]
    return index_name in indexes


def _constraint_exists(conn: Connection, table: str, constraint_name: str, schema: str = "public") -> bool:
    """Verifica se a constraint ja existe na tabela."""
    inspector = inspect(conn)
    constraints = [c["name"] for c in inspector.get_check_constraints(table, schema=schema)]
    return constraint_name in constraints


def _foreign_key_exists(conn: Connection, table: str, fk_name: str, schema: str = "public") -> bool:
    """Verifica se a foreign key ja existe na tabela."""
    inspector = inspect(conn)
    fks = [fk["name"] for fk in inspector.get_foreign_keys(table, schema=schema)]
    return fk_name in fks


def _execute_if_owner(
    conn: Connection,
    table: str,
    ddl: str,
    op_name: str,
    *,
    check_exists_sql: str | None = None,
    check_exists_params: dict[str, Any] | None = None,
) -> bool:
    """Executa o DDL apenas se o usuario for dono da tabela.

    Retorna True se executou, False se pulou.
    """
    if is_owner(conn, table):
        conn.execute(text(ddl))
        logger.info("DDL executed on %s: %s", table, op_name)
        return True

    # Nao e dono - verifica se o objeto ja existe para ser idempotente
    if check_exists_sql and check_exists_params:
        exists = conn.execute(text(check_exists_sql), check_exists_params).scalar()
        if exists:
            logger.info("Object already exists on %s (skipped, not owner): %s", table, op_name)
            return True

    logger.warning(
        "Skipped DDL on %s (not owner): %s. Run as table owner to apply.",
        table,
        op_name,
    )
    return False


def add_column_if_owner(
    conn: Connection,
    table: str,
    column_name: str,
    column_type: str,
    *,
    nullable: bool = True,
    default: str | None = None,
    schema: str = "public",
) -> bool:
    """Adiciona coluna se o usuario for dono da tabela."""
    ddl = f"ALTER TABLE {schema}.{table} ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
    if not nullable:
        ddl += " NOT NULL"
    if default is not None:
        ddl += f" DEFAULT {default}"

    return _execute_if_owner(
        conn,
        table,
        ddl,
        f"ADD COLUMN {column_name}",
        check_exists_sql=(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        check_exists_params={"schema": schema, "table": table, "column": column_name},
    )


def create_index_if_owner(
    conn: Connection,
    table: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
    schema: str = "public",
) -> bool:
    """Cria indice se o usuario for dono da tabela."""
    unique_str = "UNIQUE " if unique else ""
    cols = ", ".join(columns)
    ddl = f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {schema}.{table} ({cols})"

    return _execute_if_owner(
        conn,
        table,
        ddl,
        f"CREATE INDEX {index_name}",
        check_exists_sql=(
            "SELECT 1 FROM pg_indexes WHERE schemaname = :schema AND tablename = :table AND indexname = :index"
        ),
        check_exists_params={"schema": schema, "table": table, "index": index_name},
    )


def create_check_constraint_if_owner(
    conn: Connection,
    table: str,
    constraint_name: str,
    condition: str,
    *,
    schema: str = "public",
) -> bool:
    """Cria check constraint se o usuario for dono da tabela."""
    ddl = (
        f"ALTER TABLE {schema}.{table} "
        f"ADD CONSTRAINT {constraint_name} CHECK ({condition})"
    )

    return _execute_if_owner(
        conn,
        table,
        ddl,
        f"CHECK CONSTRAINT {constraint_name}",
        check_exists_sql=(
            "SELECT 1 FROM information_schema.check_constraints "
            "WHERE constraint_schema = :schema AND constraint_name = :name"
        ),
        check_exists_params={"schema": schema, "name": constraint_name},
    )


def add_foreign_key_if_owner(
    conn: Connection,
    source_table: str,
    fk_name: str,
    target_table: str,
    source_columns: list[str],
    target_columns: list[str],
    *,
    ondelete: str | None = None,
    schema: str = "public",
) -> bool:
    """Adiciona foreign key se o usuario for dono da tabela de origem."""
    src_cols = ", ".join(source_columns)
    tgt_cols = ", ".join(target_columns)
    ondelete_str = f" ON DELETE {ondelete}" if ondelete else ""
    ddl = (
        f"ALTER TABLE {schema}.{source_table} "
        f"ADD CONSTRAINT {fk_name} "
        f"FOREIGN KEY ({src_cols}) REFERENCES {schema}.{target_table} ({tgt_cols}){ondelete_str}"
    )

    return _execute_if_owner(
        conn,
        source_table,
        ddl,
        f"FOREIGN KEY {fk_name}",
        check_exists_sql=(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_schema = :schema AND table_name = :table AND constraint_name = :name"
        ),
        check_exists_params={"schema": schema, "table": source_table, "name": fk_name},
    )


def create_check_constraint_if_not_exists(
    op: Operations,
    table: str,
    constraint_name: str,
    condition: str,
    schema: str = "public",
) -> bool:
    """Wrapper para uso com op do Alembic - verifica ownership antes de criar."""
    conn = op.get_bind()
    return create_check_constraint_if_owner(
        conn, table, constraint_name, condition, schema=schema
    )
