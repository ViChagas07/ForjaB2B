"""Testes do script de pre-deploy (migrations no Render)."""

import pytest

from scripts.predeploy import PreDeployError, _admin_url


def test_admin_url_exige_variavel_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    with pytest.raises(PreDeployError):
        _admin_url()


def test_admin_url_recusa_mesma_url_do_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://forja_app:secret@localhost:5432/forja_db"
    monkeypatch.setenv("DATABASE_ADMIN_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(PreDeployError):
        _admin_url()


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
