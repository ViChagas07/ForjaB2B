"""Repositorio SQLAlchemy do chat (FASE 5a).

Usa as tabelas `chat_conversations`/`chat_messages` da migration 0026 e o
contexto RLS do projeto (`app.set_tenant_context` via `TenantContext`).

Escopo (defesa em profundidade com a RLS):
- VISITANTE (`company_id`/`user_id` None): so linhas sem dono; a conversa e
  acessivel APENAS por quem conhece o UUID (capacidade), nunca listavel.
- LOGADO: so conversas da MESMA empresa E do MESMO usuario; conversa de
  visitante nao e reaberta por usuario logado e vice-versa. Escrita fora do
  escopo levanta `ConversationAccessError` (nunca "grava no escuro").

NUNCA ha metodo generico de gravacao: `append_message` recebe role valido
(user|assistant) e o servico so expoe `append_user_message` (sanitizada) e
`append_assistant_message` (aprovada pelo output guard).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.errors import ConversationAccessError
from app.modules.ai.application.ports import ChatTurn, ConversationView

_INSERT_CONVERSATION = text(
    "INSERT INTO chat_conversations (company_id, user_id, locale, expires_at) "
    "VALUES (:company_id, :user_id, :locale, :expires_at) RETURNING id"
)
_SELECT_CONVERSATION = text(
    "SELECT id, company_id, user_id, locale, expires_at FROM chat_conversations WHERE id = :id"
)
# Guarda de dono NA MESMA instrucao: visitante so grava em conversa sem dono;
# logado so grava na conversa da propria empresa E do proprio usuario.
_INSERT_MESSAGE = text(
    "INSERT INTO chat_messages (conversation_id, role, content) "
    "SELECT :conversation_id, :role, :content WHERE EXISTS ("
    " SELECT 1 FROM chat_conversations c WHERE c.id = :conversation_id AND ("
    "  (CAST(:company_id AS uuid) IS NULL AND CAST(:user_id AS uuid) IS NULL "
    "   AND c.company_id IS NULL) OR "
    "  (CAST(:company_id AS uuid) IS NOT NULL AND c.company_id = CAST(:company_id AS uuid) "
    "   AND c.user_id = CAST(:user_id AS uuid))))"
)
_SELECT_MESSAGES = text(
    "SELECT role, content, created_at FROM chat_messages "
    "WHERE conversation_id = :id ORDER BY created_at DESC, id DESC LIMIT :limit"
)
_TOUCH = text(
    "UPDATE chat_conversations SET last_message_at = now(), expires_at = :expires_at WHERE id = :id"
)
_DELETE_EXPIRED = text("SELECT app.delete_expired_chat_conversations(:limit)")


class SqlAlchemyConversationRepository:
    """Implementacao da porta `ConversationRepositoryPort`."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        *,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        locale: str,
        expires_at: datetime,
    ) -> uuid.UUID:
        async with self._uow_factory.begin(self._tenant(company_id, user_id)) as uow:
            conversation_id = (
                await uow.session.execute(
                    _INSERT_CONVERSATION,
                    {
                        "company_id": company_id,
                        "user_id": user_id,
                        "locale": locale,
                        "expires_at": expires_at,
                    },
                )
            ).scalar_one()
            await uow.commit()
        return uuid.UUID(str(conversation_id))

    async def get(
        self,
        conversation_id: uuid.UUID,
        *,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> ConversationView | None:
        async with self._uow_factory.begin(self._tenant(company_id, user_id)) as uow:
            row = (await uow.session.execute(_SELECT_CONVERSATION, {"id": conversation_id})).first()
            await uow.commit()
        if row is None:
            return None
        return ConversationView(
            id=row.id,
            company_id=row.company_id,
            user_id=row.user_id,
            locale=row.locale,
            expires_at=row.expires_at,
        )

    async def append_message(
        self,
        conversation_id: uuid.UUID,
        *,
        role: str,
        content: str,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        if role not in ("user", "assistant"):
            raise ValueError("role invalido na memoria do chat")
        async with self._uow_factory.begin(self._tenant(company_id, user_id)) as uow:
            result = await uow.session.execute(
                _INSERT_MESSAGE,
                {
                    "conversation_id": conversation_id,
                    "role": role,
                    "content": content,
                    "company_id": company_id,
                    "user_id": user_id,
                },
            )
            if result.rowcount == 0:  # type: ignore[attr-defined]
                raise ConversationAccessError("conversation out of scope")
            await uow.commit()

    async def last_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> list[ChatTurn]:
        async with self._uow_factory.begin(self._tenant(company_id, user_id)) as uow:
            rows = (
                await uow.session.execute(
                    _SELECT_MESSAGES, {"id": conversation_id, "limit": max(limit, 0)}
                )
            ).all()
            await uow.commit()
        ordered = list(reversed(rows))
        return [
            ChatTurn(role=row.role, content=row.content, created_at=row.created_at)
            for row in ordered
        ]

    async def touch(
        self,
        conversation_id: uuid.UUID,
        *,
        expires_at: datetime,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        async with self._uow_factory.begin(self._tenant(company_id, user_id)) as uow:
            await uow.session.execute(_TOUCH, {"id": conversation_id, "expires_at": expires_at})
            await uow.commit()

    async def delete_expired(self, *, limit: int) -> int:
        # Cross-tenant: SECURITY DEFINER app.delete_expired_chat_conversations.
        async with self._uow_factory.begin() as uow:
            removed = (
                await uow.session.execute(_DELETE_EXPIRED, {"limit": max(limit, 1)})
            ).scalar_one()
            await uow.commit()
        return int(removed)

    @staticmethod
    def _tenant(company_id: uuid.UUID | None, user_id: uuid.UUID | None) -> TenantContext | None:
        if company_id is None:
            return None  # visitante: SEM contexto de tenant (RLS libera so NULL)
        return TenantContext(company_id=company_id, user_id=user_id)
