"""Infraestrutura de testes de banco: PostgreSQL real via Testcontainers.

Reproduz o bootstrap REAL da aplicacao: os mesmos wrappers/sQLs de
docker/postgres sao copiados para /docker-entrypoint-initdb.d/ de um container
descartavel, com credenciais exclusivas de teste. Nenhum SQL e copiado ou
reimplementado aqui; nenhum volume nomeado (forja_postgres_data) e utilizado.

Requer daemon Docker acessivel. Se Docker for obrigatorio e estiver
indisponivel, a fixture falha explicitamente (sem skip silencioso).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import docker
import psycopg
import pytest
from pydantic import PostgresDsn, RedisDsn
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from app.core.config import Settings
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory

# Mesma imagem fixada no plano congelado e no docker-compose.yml.
POSTGRES_IMAGE = "postgres:16.4-alpine"

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTGRES_SCRIPTS_DIR = REPO_ROOT / "docker" / "postgres"

# Credenciais exclusivas do ambiente descartavel de teste (nunca usadas fora).
BOOTSTRAP_USER = "forja_bootstrap_test"
BOOTSTRAP_PASSWORD = "test_bootstrap_password_ephemeral"
ADMIN_USER = "forja_admin"
ADMIN_PASSWORD = "test_admin_password_ephemeral"
APP_USER = "forja_app"
APP_PASSWORD = "test_app_password_ephemeral"
DB_NAME = "forja_db_test"

_INITDB_FILES = (
    ("01-init-roles.sh", "/docker-entrypoint-initdb.d/01-init-roles.sh", 0o755),
    ("02-rls-setup.sh", "/docker-entrypoint-initdb.d/02-rls-setup.sh", 0o755),
    ("init-roles.sql", "/docker-entrypoint-initdb.d/sql/init-roles.sql", 0o644),
    ("02-rls-setup.sql", "/docker-entrypoint-initdb.d/sql/02-rls-setup.sql", 0o644),
)


class PostgresInstance:
    """Parametros de conexao do container descartavel."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def connect(self, user: str, password: str, *, autocommit: bool = True) -> psycopg.Connection:
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=DB_NAME,
            user=user,
            password=password,
            autocommit=autocommit,
        )

    def connect_app(self, *, autocommit: bool = True) -> psycopg.Connection:
        """Conexao com a role de runtime (sujeita a RLS)."""
        return self.connect(APP_USER, APP_PASSWORD, autocommit=autocommit)

    def connect_admin(self, *, autocommit: bool = True) -> psycopg.Connection:
        """Conexao com a role administrativa restrita (migracoes/DDL)."""
        return self.connect(ADMIN_USER, ADMIN_PASSWORD, autocommit=autocommit)


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresInstance]:
    """Sobe PostgreSQL descartavel executando o bootstrap real do projeto.

    Falha explicita (sem skip silencioso) quando o daemon Docker obrigatorio
    esta indisponivel, distinguindo-a de falhas de provisionamento.
    """
    try:
        docker.from_env().ping()
    except Exception as exc:  # noqa: BLE001 - converter em falha explicita
        pytest.fail(
            "Docker e obrigatorio para os testes de banco (Testcontainers) e "
            "nao esta acessivel. Inicie o daemon Docker e rode novamente. "
            f"Detalhe: {exc}"
        )

    try:
        container = (
            PostgresContainer(
                image=POSTGRES_IMAGE,
                username=BOOTSTRAP_USER,
                password=BOOTSTRAP_PASSWORD,
                dbname=DB_NAME,
            )
            .with_env("POSTGRES_ADMIN_USER", ADMIN_USER)
            .with_env("POSTGRES_ADMIN_PASSWORD", ADMIN_PASSWORD)
            .with_env("POSTGRES_APP_USER", APP_USER)
            .with_env("POSTGRES_APP_PASSWORD", APP_PASSWORD)
        )
        for source_name, destination, mode in _INITDB_FILES:
            source = POSTGRES_SCRIPTS_DIR / source_name
            if not source.is_file():
                pytest.fail(f"Script de bootstrap ausente no repositorio: {source}")
            container.with_copy_into_container(source, destination, mode)
        container.start()
    except Exception as exc:  # noqa: BLE001 - falha de provisionamento
        pytest.fail(
            "Falha ao provisionar o PostgreSQL descartavel com o bootstrap "
            f"real do projeto (docker/postgres). Detalhe: {exc}"
        )

    try:
        yield PostgresInstance(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
        )
    finally:
        container.stop()


@pytest.fixture()
def admin_conn(pg: PostgresInstance) -> Iterator[psycopg.Connection]:
    conn = pg.connect_admin()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def app_conn(pg: PostgresInstance) -> Iterator[psycopg.Connection]:
    conn = pg.connect_app()
    try:
        yield conn
    finally:
        conn.close()


# ------------------------------------------------------------------------------
# Fixtures da fundacao backend (SQLAlchemy 2.x, Redis, Settings, FastAPI)
# ------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app_database_url(pg: PostgresInstance) -> str:
    """URL asyncpg com a role de runtime (forja_app, sujeita a RLS)."""
    return f"postgresql+asyncpg://{APP_USER}:{APP_PASSWORD}@{pg.host}:{pg.port}/{DB_NAME}"


@pytest.fixture(scope="session")
def admin_database_url(pg: PostgresInstance) -> str:
    """URL asyncpg com a role administrativa restrita (forja_admin, migrations)."""
    return f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{DB_NAME}"


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Redis descartavel (mesma imagem do docker-compose) para probes de readiness."""
    try:
        docker.from_env().ping()
    except Exception as exc:  # noqa: BLE001 - falha explicita, sem skip
        pytest.fail(f"Docker obrigatorio indisponivel para o Redis de teste: {exc}")

    container = (
        DockerContainer("redis:7-alpine")
        .with_exposed_ports(6379)
        .waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
    )
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
    finally:
        container.stop()


@pytest.fixture(scope="session")
def test_settings(app_database_url: str, redis_url: str) -> Settings:
    """Settings apontando para os containers descartaveis, sem OTel."""
    return Settings(
        environment="test",
        log_level="DEBUG",
        log_format="json",
        database_url=PostgresDsn(app_database_url),
        redis_url=RedisDsn(redis_url),
        otel_enabled=False,
    )


@pytest.fixture()
async def engine(app_database_url: str) -> AsyncIterator[AsyncEngine]:
    """Engine de runtime com pool unitario: forca reutilizacao de conexao.

    pool_size=1 e max_overflow=0 garantem que transacoes consecutivas usam a
    mesma conexao fisica, cenario exato para provar que o contexto de tenant
    nao vaza entre requests (pool reuse).
    """
    engine = create_async_engine(
        app_database_url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture()
def uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(session_factory)


@pytest.fixture(scope="session")
def migrated_domain_schema(admin_database_url: str) -> None:
    """Aplica as migrations de dominio uma unica vez por sessao (idempotente).

    O container PostgreSQL descartavel ja recebeu o bootstrap real (roles,
    schema ``app`` e helpers RLS) via initdb. Aqui entram apenas as tabelas de
    dominio da Fase 1, criadas pela role administrativa (forja_admin).

    Usa ``pytest.MonkeyPatch`` para injetar ``DATABASE_ADMIN_URL`` e desfazer
    imediatamente, evitando que a variavel vaze para os testes de unidade que
    leem ``Settings()`` do ambiente.
    """
    from alembic.config import Config

    from alembic import command

    patch = pytest.MonkeyPatch()
    patch.setenv("DATABASE_ADMIN_URL", admin_database_url)
    try:
        config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
        command.upgrade(config, "head")
    finally:
        patch.undo()
