"""Verificacao centralizada de estado do schema (Alembic revision).

Unifica a logica usada pelo:
- lifespan do FastAPI (startup)
- endpoint /health/ready (readiness probe)
- script scripts/predeploy.py (pre-deploy do Render)

A funcao principal `check_schema_current` retorna uma tupla (is_current, current_rev, head_rev, error).
- is_current: True se o banco esta no head, False se ha drift
- current_rev: revisao atual do banco (ou None se erro)
- head_rev: revisao esperada (head do ScriptDirectory)
- error: mensagem de erro se a verificacao falhou tecnicamente (excecao inesperada)

Semantica:
- O app so deve ABORTAR no startup quando is_current=False (drift real).
- Se error != None (falha tecnica do check), registra erro e NAO aborta;
  o /health/ready deve retornar 503 com o motivo.
- ALLOW_START_WITH_FAILED_MIGRATION so se aplica quando is_current=False.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.logging import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class SchemaCheckResult:
    """Resultado da verificacao de schema."""
    is_current: bool
    current_revision: str | None
    head_revision: str
    error: str | None = None

    @property
    def has_technical_failure(self) -> bool:
        return self.error is not None

    @property
    def has_drift(self) -> bool:
        return not self.is_current and self.error is None


def _get_alembic_config() -> AlembicConfig:
    """Carrega configuracao do Alembic a partir do backend root."""
    backend_root = Path(__file__).resolve().parents[3]
    config = AlembicConfig(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _get_head_revision() -> str:
    """Obtem a revisao head do ScriptDirectory."""
    config = _get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("Alembic nao possui head revision (nenhuma migration?)")
    return head


async def _get_current_revision_async(engine: AsyncEngine) -> str | None:
    """Le a revisao atual do banco usando conexao assincrona + run_sync."""
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync_conn: MigrationContext.configure(sync_conn).get_current_revision()
        )


async def check_schema_current(engine: AsyncEngine) -> SchemaCheckResult:
    """Verifica se o schema do banco esta no head das migrations.

    Args:
        engine: AsyncEngine ja configurado (ex.: app.state.db_engine).

    Returns:
        SchemaCheckResult com is_current, current_revision, head_revision, error.
    """
    head_rev = _get_head_revision()

    try:
        current_rev = await _get_current_revision_async(engine)
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        _logger.error("schema_check_failed", error=error_msg, exc_info=True)
        return SchemaCheckResult(
            is_current=False,
            current_revision=None,
            head_revision=head_rev,
            error=error_msg,
        )

    is_current = (current_rev == head_rev)
    if not is_current:
        _logger.warning(
            "migrations_not_current",
            current_revision=current_rev,
            head_revision=head_rev,
        )
    return SchemaCheckResult(
        is_current=is_current,
        current_revision=current_rev,
        head_revision=head_rev,
        error=None,
    )


async def check_schema_current_from_url(database_url: str) -> SchemaCheckResult:
    """Verifica schema a partir de uma URL de conexao (para scripts standalone).

    Cria engine temporario, verifica, e descarta. Usado por scripts como predeploy.
    """
    engine = create_async_engine(database_url)
    try:
        return await check_schema_current(engine)
    finally:
        await engine.dispose()
