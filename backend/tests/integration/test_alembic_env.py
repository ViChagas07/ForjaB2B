"""Testes de integracao do ambiente Alembic.

Valida a fronteira bootstrap vs. migrations:
- ``upgrade head`` funciona com a credencial administrativa (forja_admin),
  aplicando as migrations de dominio da Fase 1 (tabelas + policies RLS);
- sem DATABASE_ADMIN_URL o ambiente falha explicitamente (o runtime nao
  executa DDL, por desenho);
- existem revisions de dominio nesta fase.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def test_revisions_de_dominio_existem() -> None:
    revisions = list(VERSIONS_DIR.glob("*.py"))
    assert revisions != [], "Fase 1 deve ter migrations de dominio em alembic/versions"


def test_upgrade_head_com_credencial_administrativa(
    admin_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Alembic conecta como forja_admin e `upgrade head` cria o schema de dominio."""
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_database_url)
    command.upgrade(_alembic_config(), "head")
    command.current(_alembic_config())


def test_sem_credencial_administrativa_falha_explicitamente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(Exception, match="DATABASE_ADMIN_URL"):
        command.upgrade(_alembic_config(), "head")
