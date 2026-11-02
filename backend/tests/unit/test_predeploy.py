"""Testes do script de pre-deploy (migrations no Render)."""

import asyncio
from typing import Any

import pytest

from scripts import predeploy
from scripts.predeploy import PreDeployError, _admin_url, _preflight


class _FakeMappings:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    def one(self) -> dict[str, Any]:
        return self._row


class _FakeResult:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._row)


class _FakeConnection:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    async def execute(self, _statement: object) -> _FakeResult:
        return _FakeResult(self._row)

    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeEngine:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self._row)

    async def dispose(self) -> None:
        return None


def _preflight_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "role": "forja",
        "has_products": True,
        "can_act_as_owner": True,
        "can_create": True,
    }
    row.update(overrides)
    return row


def test_preflight_avisa_sem_ownership_sem_abortar(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    row = _preflight_row(can_act_as_owner=False)
    monkeypatch.setattr(predeploy, "create_async_engine", lambda _url: _FakeEngine(row))
    result = asyncio.run(_preflight("postgresql+asyncpg://forja:secret@localhost/db"))
    assert result["role"] == "forja"
    assert "nao e owner de products" in capsys.readouterr().err


def test_preflight_aborta_sem_create(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _preflight_row(can_create=False)
    monkeypatch.setattr(predeploy, "create_async_engine", lambda _url: _FakeEngine(row))
    with pytest.raises(PreDeployError, match="CREATE no schema public"):
        asyncio.run(_preflight("postgresql+asyncpg://forja:secret@localhost/db"))


def test_admin_url_exige_variavel_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    with pytest.raises(PreDeployError):
        _admin_url()


def test_admin_url_recusa_role_de_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://forja_app:secret@localhost:5432/forja_db"
    monkeypatch.setenv("DATABASE_ADMIN_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(PreDeployError):
        _admin_url()


def test_admin_url_permite_mesma_url_com_role_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Render gerenciado pode usar uma unica role owner ("forja") tambem no
    # runtime; o preflight e quem valida ownership/DDL.
    url = "postgresql://forja:secret@localhost:5432/forja_db"
    monkeypatch.setenv("DATABASE_ADMIN_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    assert _admin_url() == "postgresql+asyncpg://forja:secret@localhost:5432/forja_db"


def test_admin_url_normaliza_sslmode_para_asyncpg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_ADMIN_URL",
        "postgresql://forja_admin:secret@db.example.com:5432/forja_db?sslmode=require",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert (
        _admin_url()
        == "postgresql+asyncpg://forja_admin:secret@db.example.com:5432/forja_db?ssl=require"
    )
