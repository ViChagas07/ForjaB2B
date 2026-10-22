"""Testes unitarios das partes puras dos scripts operacionais (sem Docker).

Os scripts de backup/restore/migration moram em ``scripts/`` (fora do pacote
``app``). Aqui eles sao carregados por caminho para testar rotacao, validacao
de dump e as travas de nome de banco descartavel.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ops = cast(Any, _load("ops_common"))


def test_scratch_name_tem_prefixo_e_e_aceito() -> None:
    name = ops.new_scratch_name("migration")
    assert name.startswith("forja_scratch_")
    assert name.islower()
    ops.assert_scratch_name(name)


@pytest.mark.parametrize(
    "name",
    ["forja_db", "postgres", "forja_scratch_", "forja_scratch_UPPER", "forja_scratch_x;drop"],
)
def test_scratch_name_recusa_nomes_perigosos(name: str) -> None:
    with pytest.raises(ops.OpsError):
        ops.assert_scratch_name(name)


def test_drop_recusa_banco_nao_criado_por_esta_execucao() -> None:
    with pytest.raises(ops.OpsError):
        ops.drop_scratch_database(cast(Any, object()), "forja_scratch_test_123", created=False)


def test_rotate_backups_preserva_os_mais_novos_e_ignora_outros_arquivos(tmp_path: Path) -> None:
    base = time.time()
    names = [
        "forja_db_20260101T000000Z.dump",
        "forja_db_20260102T000000Z.dump",
        "forja_db_20260103T000000Z.dump",
        "forja_db_20260104T000000Z.dump",
    ]
    for index, name in enumerate(names):
        path = tmp_path / name
        path.write_bytes(b"PGDMP")
        timestamp = base + index * 60
        path.touch()
        os.utime(path, (timestamp, timestamp))

    (tmp_path / "anotacoes.txt").write_text("nao remover", encoding="utf-8")
    (tmp_path / "forja_db_manual.dump").write_bytes(b"nao remover")

    removed = ops.rotate_backups(tmp_path, keep=2, database="forja_db")

    assert {path.name for path in removed} == set(names[:2])
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        [
            "forja_db_20260103T000000Z.dump",
            "forja_db_20260104T000000Z.dump",
            "anotacoes.txt",
            "forja_db_manual.dump",
        ]
    )


def test_rotate_backups_exige_retencao_positiva(tmp_path: Path) -> None:
    with pytest.raises(ops.OpsError):
        ops.rotate_backups(tmp_path, keep=0)


def test_validate_backup_rejeita_arquivo_vazio_e_formato_invalido(tmp_path: Path) -> None:
    empty = tmp_path / "vazio.dump"
    empty.write_bytes(b"")
    with pytest.raises(ops.OpsError):
        ops.validate_backup_file(empty)

    wrong = tmp_path / "errado.dump"
    wrong.write_bytes(b"NAO-E-PGDMP")
    with pytest.raises(ops.OpsError):
        ops.validate_backup_file(wrong)


def test_validate_backup_aceita_magic_e_devolve_tamanho(tmp_path: Path) -> None:
    valid = tmp_path / "ok.dump"
    valid.write_bytes(b"PGDMP" + b"\x00" * 16)
    assert ops.validate_backup_file(valid) == 21


def test_nome_de_backup_segue_padrao_esperado() -> None:
    name = ops.backup_name()
    assert ops.is_backup_name(name)
    assert not ops.is_backup_name("backup.dump")
