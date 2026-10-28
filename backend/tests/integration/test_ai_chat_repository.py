"""Integracao do repositorio de conversas (FASE 5a) — Postgres real + RLS.

Cobre: visitante so acessa a propria conversa (UUID), logado so a da propria
empresa/usuario, escrita fora do escopo rejeitada, historico truncado, TTL e
limpeza diaria via funcao SECURITY DEFINER.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from psycopg import Connection

from app.modules.ai.application.conversation_service import (
    ConversationScope,
    ConversationService,
)
from app.modules.ai.application.errors import ConversationAccessError
from app.modules.ai.infrastructure.chat_repository import SqlAlchemyConversationRepository

COMPANY = uuid.UUID("ffff0000-0000-4000-8000-00000000f001")
OTHER_COMPANY = uuid.UUID("ffff0000-0000-4000-8000-00000000f002")
USER = uuid.UUID("ffff0000-0000-4000-8000-00000000f011")
OTHER_USER = uuid.UUID("ffff0000-0000-4000-8000-00000000f012")


@contextmanager
def db_tx(pg: object, company_id: uuid.UUID | None = None) -> Iterator[Connection]:
    conn = pg.connect_admin(autocommit=False)  # type: ignore[attr-defined]
    try:
        if company_id is not None:
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
        yield conn
        conn.commit()
    finally:
        conn.close()


def seed(pg: object) -> None:
    for company_id, cnpj, name in (
        (COMPANY, "33333333000191", "Chat Alfa"),
        (OTHER_COMPANY, "33333333000272", "Chat Beta"),
    ):
        with db_tx(pg, company_id) as conn:
            conn.execute(
                "INSERT INTO companies (id, cnpj, legal_name, status) VALUES "
                "(%s, %s, %s, 'ACTIVE') ON CONFLICT DO NOTHING",
                (company_id, cnpj, name),
            )
    with db_tx(pg, COMPANY) as conn:
        for user_id, email in ((USER, "chat-a@test"), (OTHER_USER, "chat-b@test")):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
                "VALUES (%s, %s, %s, 'Chat User', %s, 'ACTIVE') ON CONFLICT DO NOTHING",
                (user_id, COMPANY, email, "0" * 64),
            )


@pytest.fixture(autouse=True)
def _cleanup_after(pg: object, migrated_domain_schema: None) -> Iterator[None]:
    seed(pg)
    yield
    # RLS: limpeza por escopo (tenant) e depois conversas de visitante.
    for company_id in (COMPANY, OTHER_COMPANY):
        with db_tx(pg, company_id) as conn:
            conn.execute("DELETE FROM chat_conversations WHERE company_id = %s", (company_id,))
    with db_tx(pg) as conn:
        conn.execute("DELETE FROM chat_conversations WHERE company_id IS NULL")
    with db_tx(pg, COMPANY) as conn:
        conn.execute("DELETE FROM users WHERE company_id = %s", (COMPANY,))
    for company_id in (COMPANY, OTHER_COMPANY):
        with db_tx(pg, company_id) as conn:
            conn.execute("DELETE FROM companies WHERE id = %s", (company_id,))


def make_repository(uow_factory: object) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(uow_factory)  # type: ignore[arg-type]


async def test_visitante_acessa_somente_a_propria_conversa(uow_factory: object) -> None:
    repository = make_repository(uow_factory)
    visitor_id = await repository.create(
        company_id=None,
        user_id=None,
        locale="en",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    view = await repository.get(visitor_id, company_id=None, user_id=None)
    assert view is not None and view.locale == "en"
    # Usuario logado NAO reabre conversa de visitante (escopo do servico).
    service = ConversationService(repository=repository, ttl_days=30, history_turns=10)
    denied = await service.open_or_resume(
        conversation_id=visitor_id,
        scope=ConversationScope(company_id=COMPANY, user_id=USER),
        locale="pt-BR",
    )
    assert denied is None
    # E outro UUID nao adivinhavel nao existe.
    assert await repository.get(uuid.uuid4(), company_id=None, user_id=None) is None


async def test_outra_empresa_e_outro_usuario_nao_leem(uow_factory: object) -> None:
    repository = make_repository(uow_factory)
    conversation_id = await repository.create(
        company_id=COMPANY,
        user_id=USER,
        locale="pt-BR",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert await repository.get(conversation_id, company_id=OTHER_COMPANY, user_id=USER) is None
    assert await repository.get(conversation_id, company_id=None, user_id=None) is None
    service = ConversationService(repository=repository, ttl_days=30, history_turns=10)
    denied = await service.open_or_resume(
        conversation_id=conversation_id,
        scope=ConversationScope(company_id=COMPANY, user_id=OTHER_USER),
        locale="pt-BR",
    )
    assert denied is None


async def test_escrita_fora_do_escopo_e_rejeitada(uow_factory: object) -> None:
    repository = make_repository(uow_factory)
    conversation_id = await repository.create(
        company_id=COMPANY,
        user_id=USER,
        locale="pt-BR",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    with pytest.raises(ConversationAccessError):
        await repository.append_message(
            conversation_id,
            role="user",
            content="intruso",
            company_id=None,
            user_id=None,
        )
    with pytest.raises(ConversationAccessError):
        await repository.append_message(
            conversation_id,
            role="user",
            content="intruso",
            company_id=OTHER_COMPANY,
            user_id=USER,
        )


async def test_historico_truncado_na_ordem_cronologica(uow_factory: object) -> None:
    repository = make_repository(uow_factory)
    conversation_id = await repository.create(
        company_id=None,
        user_id=None,
        locale="pt-BR",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    for index in range(5):
        await repository.append_message(
            conversation_id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"m{index}",
            company_id=None,
            user_id=None,
        )
    turns = await repository.last_messages(conversation_id, limit=3, company_id=None, user_id=None)
    assert [turn.content for turn in turns] == ["m2", "m3", "m4"]
    assert [turn.role for turn in turns] == ["user", "assistant", "user"]


async def test_limpeza_ttl_remove_conversas_expiradas(pg: object, uow_factory: object) -> None:
    with db_tx(pg) as conn:
        expired_id = conn.execute(
            "INSERT INTO chat_conversations (locale, expires_at) "
            "VALUES ('pt-BR', now() - interval '1 day') RETURNING id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO chat_messages (conversation_id, role, content) "
            "VALUES (%s, 'user', 'velha')",
            (expired_id,),
        )
    repository = make_repository(uow_factory)
    removed = await repository.delete_expired(limit=50)
    assert removed >= 1
    with db_tx(pg) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM chat_conversations WHERE id = %s", (expired_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM chat_messages WHERE conversation_id = %s", (expired_id,)
            ).fetchone()[0]
            == 0
        )
