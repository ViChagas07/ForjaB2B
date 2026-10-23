"""Utilitarios compartilhados dos scripts operacionais de banco.

Os scripts deste diretorio rodam no host e usam o Docker Compose para falar com
o PostgreSQL de desenvolvimento. Nenhuma credencial e impressa ou passada como
argumento de linha de comando: os valores lidos do container sao injetados no
ambiente do subprocesso e repassados ao `docker compose` por nome (`-e VAR`).

Regras de seguranca aplicadas aqui:

* bancos descartaveis SEMPRE comecam com ``forja_scratch_``;
* apenas nomes criados pela propria execucao podem ser removidos;
* o banco operacional (``POSTGRES_DB``) nunca e alvo de DROP/recriacao.
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

SCRATCH_PREFIX = "forja_scratch_"
_SCRATCH_RE = re.compile(r"^forja_scratch_[a-z0-9_]{1,48}$")
_BACKUP_RE = re.compile(r"^forja_db_\d{8}T\d{6}Z\.dump$")


class OpsError(RuntimeError):
    """Falha operacional com mensagem segura para o operador."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def _command_text(command: Sequence[str]) -> str:
    """Representacao segura do comando (sem variaveis de ambiente)."""
    return " ".join(command)


def run(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
    cwd: Path = REPO_ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """Executa um comando e devolve stdout/stderr em bytes."""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    completed = subprocess.run(  # noqa: S603 - comandos fixos, sem shell
        list(command),
        cwd=str(cwd),
        env=process_env,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise OpsError(
            f"comando falhou (exit {completed.returncode}): {_command_text(command)}\n{stderr}"
        )
    return completed


def run_to_file(
    command: Sequence[str],
    destination: Path,
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> subprocess.CompletedProcess[bytes]:
    """Executa um comando gravando stdout diretamente no arquivo (dumps grandes)."""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    with destination.open("wb") as handle:
        completed = subprocess.run(  # noqa: S603 - comandos fixos, sem shell
            list(command),
            cwd=str(cwd),
            env=process_env,
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise OpsError(
            f"comando falhou (exit {completed.returncode}): {_command_text(command)}\n{stderr}"
        )
    return completed


def run_with_stdin_file(
    command: Sequence[str],
    source: Path,
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> subprocess.CompletedProcess[bytes]:
    """Executa um comando alimentando stdin a partir de um arquivo (pg_restore)."""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    with source.open("rb") as handle:
        completed = subprocess.run(  # noqa: S603 - comandos fixos, sem shell
            list(command),
            cwd=str(cwd),
            env=process_env,
            stdin=handle,
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise OpsError(
            f"comando falhou (exit {completed.returncode}): {_command_text(command)}\n{stderr}"
        )
    return completed


def compose(*args: str, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    """Executa `docker compose ...` na raiz do repositorio."""
    return run(["docker", "compose", *args], env=env)


def compose_exec(
    service: str,
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return run(
        ["docker", "compose", "exec", "-T", service, *args],
        env=env,
        input_bytes=input_bytes,
    )


def compose_run_backend(
    args: Sequence[str],
    *,
    env: Mapping[str, str],
    mount_source: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """Roda um comando no container do backend com o codigo da arvore de trabalho.

    O bind mount evita reconstruir a imagem a cada alteracao de codigo. As
    variaveis de ``env`` sao repassadas por nome, nunca por valor na linha de
    comando.
    """
    command: list[str] = ["docker", "compose", "run", "--rm", "--no-deps"]
    if mount_source:
        command.extend(["-v", f"{BACKEND_DIR.as_posix()}:/app:ro"])
    for key in env:
        command.extend(["-e", key])
    command.extend(["backend", *args])
    return run(command, env=env)


def postgres_container_env() -> dict[str, str]:
    """Le as variaveis do container PostgreSQL (sem imprimir valores)."""
    completed = compose_exec("postgres", ["env"])
    values: dict[str, str] = {}
    for line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


@dataclass(frozen=True, kw_only=True)
class PostgresConfig:
    """Configuracao local do cluster de desenvolvimento."""

    bootstrap_user: str
    bootstrap_password: str
    admin_user: str
    admin_password: str
    app_user: str
    app_password: str
    database: str
    host: str
    port: int

    @classmethod
    def from_environment(cls) -> PostgresConfig:
        values = postgres_container_env()
        published = compose("port", "postgres", "5432").stdout.decode("utf-8").strip()
        port_text = published.rsplit(":", 1)[-1] if ":" in published else published
        if not port_text.isdigit():
            raise OpsError(f"porta publicada do PostgreSQL invalida: {published!r}")
        config = cls(
            bootstrap_user=values.get("POSTGRES_USER", "postgres"),
            bootstrap_password=values.get("POSTGRES_PASSWORD", ""),
            admin_user=values.get("POSTGRES_ADMIN_USER", "forja_admin"),
            admin_password=values.get("POSTGRES_ADMIN_PASSWORD", ""),
            app_user=values.get("POSTGRES_APP_USER", "forja_app"),
            app_password=values.get("POSTGRES_APP_PASSWORD", ""),
            database=values.get("POSTGRES_DB", "forja_db"),
            host="localhost",
            port=int(port_text),
        )
        if not config.admin_password or not config.bootstrap_password:
            raise OpsError("credenciais locais do PostgreSQL ausentes no container")
        return config

    def _url(self, *, user: str, password: str, database: str, driver: str) -> str:
        # Os comandos rodam em containers da rede do Compose; o servico do
        # PostgreSQL e alcancado por "postgres:5432", nao pelo host publicado.
        return (
            f"postgresql+{driver}://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@postgres:5432/{quote(database, safe='')}"
        )

    def admin_url(self, database: str) -> str:
        return self._url(
            user=self.admin_user,
            password=self.admin_password,
            database=database,
            driver="asyncpg",
        )

    def bootstrap_url(self, database: str) -> str:
        return self._url(
            user=self.bootstrap_user,
            password=self.bootstrap_password,
            database=database,
            driver="asyncpg",
        )

    def app_url(self, database: str) -> str:
        return self._url(
            user=self.app_user,
            password=self.app_password,
            database=database,
            driver="asyncpg",
        )


def new_scratch_name(purpose: str) -> str:
    """Nome unico e reconhecivel de banco descartavel."""
    normalized = re.sub(r"[^a-z0-9]+", "_", purpose.lower()).strip("_") or "ops"
    name = f"{SCRATCH_PREFIX}{normalized}_{timestamp_slug().lower()}_{secrets.token_hex(3)}"
    assert_scratch_name(name)
    return name


def assert_scratch_name(name: str) -> None:
    """Recusa qualquer nome que nao seja um banco descartavel do projeto."""
    if not _SCRATCH_RE.match(name):
        raise OpsError(f"nome de banco descartavel invalido: {name!r}")


def database_exists(config: PostgresConfig, name: str) -> bool:
    assert_scratch_name(name)
    completed = compose_exec(
        "postgres",
        [
            "psql",
            "-U",
            config.bootstrap_user,
            "-d",
            "postgres",
            "-tAc",
            # Nome validado por assert_scratch_name (regex + prefixo fixo).
            f"SELECT 1 FROM pg_database WHERE datname = '{name}'",  # noqa: S608
        ],
    )
    return completed.stdout.decode("utf-8").strip() == "1"


def create_scratch_database(config: PostgresConfig, purpose: str) -> str:
    """Cria um banco descartavel e devolve o nome (o chamador deve dropar)."""
    name = new_scratch_name(purpose)
    if name == config.database:
        raise OpsError("recusado: banco descartavel com o mesmo nome do banco operacional")
    compose_exec(
        "postgres",
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            config.bootstrap_user,
            "-d",
            "postgres",
            "-c",
            f'CREATE DATABASE "{name}" OWNER "{config.admin_user}"',
        ],
    )
    return name


def drop_scratch_database(config: PostgresConfig, name: str, *, created: bool) -> None:
    """Remove APENAS um banco criado por esta execucao e com o prefixo permitido."""
    if not created:
        raise OpsError("recusado: o banco nao foi criado por esta execucao")
    assert_scratch_name(name)
    if name == config.database:
        raise OpsError("recusado: nunca remover o banco operacional")
    # Encerra somente conexoes do proprio banco descartavel e entao remove sem
    # WITH (FORCE): o FORCE derrubou o servidor em um teste no Windows e deixou
    # o cluster em recovery. O terminate explicito e suficiente e mais seguro.
    compose_exec(
        "postgres",
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            config.bootstrap_user,
            "-d",
            "postgres",
            "-c",
            # Nome validado por assert_scratch_name (regex + prefixo fixo).
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "  # noqa: S608
            f"WHERE datname = '{name}' AND pid <> pg_backend_pid()",
        ],
    )
    last_error: OpsError | None = None
    for attempt in range(5):
        try:
            compose_exec(
                "postgres",
                [
                    "psql",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    config.bootstrap_user,
                    "-d",
                    "postgres",
                    "-c",
                    f'DROP DATABASE IF EXISTS "{name}"',
                ],
            )
            return
        except OpsError as exc:
            last_error = exc
            time.sleep(1.0 + attempt)
    if last_error is None:
        raise OpsError(f"falha desconhecida ao remover {name}")
    raise last_error


def bootstrap_scratch_database(config: PostgresConfig, name: str) -> None:
    """Replica o bootstrap real (roles, extensoes, schema app) no banco descartavel.

    As senhas das roles nao sao reais: as roles ja existem no cluster e o SQL
    so usaria os valores se precisasse cria-las. Valores fixos evitam expor
    credenciais em argumentos de processo.
    """
    assert_scratch_name(name)
    variables = [
        "-v",
        f"app_user={config.app_user}",
        "-v",
        "app_password=unused_scratch_role",
        "-v",
        f"admin_user={config.admin_user}",
        "-v",
        "admin_password=unused_scratch_role",
        "-v",
        f"db_name={name}",
    ]
    compose_exec(
        "postgres",
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            config.bootstrap_user,
            "-d",
            name,
            *variables,
            "-f",
            "/docker-entrypoint-initdb.d/sql/init-roles.sql",
        ],
    )
    compose_exec(
        "postgres",
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            config.admin_user,
            "-d",
            name,
            "-v",
            f"app_user={config.app_user}",
            "-v",
            f"admin_user={config.admin_user}",
            "-f",
            "/docker-entrypoint-initdb.d/sql/02-rls-setup.sql",
        ],
    )


def psql(
    config: PostgresConfig,
    database: str,
    sql: str,
    *,
    user: str | None = None,
) -> str:
    """Executa SQL e devolve stdout (somente leitura nos chamadores)."""
    completed = compose_exec(
        "postgres",
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            user or config.admin_user,
            "-d",
            database,
            "-tAc",
            sql,
        ],
    )
    return completed.stdout.decode("utf-8").strip()


def alembic(
    config: PostgresConfig,
    database: str,
    args: Sequence[str],
    *,
    role: str = "admin",
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    migration_url = (
        config.bootstrap_url(database) if role == "bootstrap" else config.admin_url(database)
    )
    env = {
        "DATABASE_ADMIN_URL": migration_url,
        "DATABASE_URL": config.app_url(database),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if extra_env:
        env.update(extra_env)
    return compose_run_backend(["alembic", *args], env=env)


def seed(
    config: PostgresConfig,
    database: str,
) -> subprocess.CompletedProcess[bytes]:
    env = {
        "DATABASE_ADMIN_URL": config.admin_url(database),
        "DATABASE_URL": config.app_url(database),
        "DEMO_USER_PASSWORD": "scratch_demo_password_only",
        "ENVIRONMENT": "test",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return compose_run_backend(
        ["python", "-m", "app.infrastructure.db.seeds"],
        env=env,
    )


def backup_name(moment: datetime | None = None) -> str:
    return f"forja_db_{(moment or utc_now()).strftime('%Y%m%dT%H%M%SZ')}.dump"


def is_backup_name(name: str) -> bool:
    return bool(_BACKUP_RE.match(name))


def validate_backup_file(path: Path) -> int:
    """Valida tamanho e magic header do dump custom (PGDMP)."""
    if not path.is_file():
        raise OpsError(f"backup nao encontrado: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise OpsError(f"backup vazio: {path}")
    with path.open("rb") as handle:
        header = handle.read(5)
    if header != b"PGDMP":
        raise OpsError(f"arquivo nao e um dump custom do pg_dump: {path}")
    return size


def rotate_backups(directory: Path, *, keep: int, database: str = "forja_db") -> list[Path]:
    """Remove backups antigos do proprio padrao, preservando os ``keep`` mais novos."""
    if keep < 1:
        raise OpsError("retencao deve ser >= 1")
    if not directory.is_dir():
        return []
    candidates = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.name.startswith(f"{database}_") and is_backup_name(path.name)
        ),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    removed: list[Path] = []
    for path in candidates[keep:]:
        path.unlink()
        removed.append(path)
    return removed


def print_report(title: str, lines: Sequence[str]) -> None:
    print(title)
    for line in lines:
        print(f"  {line}")


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1
