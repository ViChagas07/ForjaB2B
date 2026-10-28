"""Testes do ConversationService (FASE 5a) — repository fake, sem I/O."""

import uuid
from datetime import UTC, datetime

from app.modules.ai.application.conversation_service import (
    ConversationScope,
    ConversationService,
)
from app.modules.ai.application.errors import ConversationAccessError
from app.modules.ai.application.ports import ChatTurn, ConversationView

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
COMPANY = uuid.UUID("eeee0000-0000-4000-8000-00000000e001")
USER = uuid.UUID("eeee0000-0000-4000-8000-00000000e002")
OTHER_USER = uuid.UUID("eeee0000-0000-4000-8000-00000000e003")
CONVERSATION = uuid.UUID("eeee0000-0000-4000-8000-00000000e004")


class FakeRepo:
    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, ConversationView] = {}
        self.messages: list[tuple[uuid.UUID, str, str]] = []
        self.touched: list[tuple[uuid.UUID, datetime]] = []
        self.deleted_limits: list[int] = []

    async def create(self, *, company_id, user_id, locale, expires_at) -> uuid.UUID:
        view = ConversationView(
            id=CONVERSATION,
            company_id=company_id,
            user_id=user_id,
            locale=locale,
            expires_at=expires_at,
        )
        self.conversations[CONVERSATION] = view
        return CONVERSATION

    async def get(self, conversation_id, *, company_id, user_id):
        view = self.conversations.get(conversation_id)
        if view is None:
            return None
        # Simula RLS: visitante so ve conversa sem dono; logado so a propria.
        if company_id is None and user_id is None:
            return view if view.company_id is None else None
        return view if view.company_id == company_id and view.user_id == user_id else None

    async def append_message(self, conversation_id, *, role, content, company_id, user_id) -> None:
        view = self.conversations[conversation_id]
        if company_id is None and user_id is None:
            if view.company_id is not None:
                raise ConversationAccessError("visitor cannot write")
        elif view.company_id != company_id or view.user_id != user_id:
            raise ConversationAccessError("owner mismatch")
        self.messages.append((conversation_id, role, content))

    async def last_messages(self, conversation_id, *, limit, company_id, user_id):
        rows = [m for m in self.messages if m[0] == conversation_id][-limit:]
        return [ChatTurn(role=r, content=c, created_at=NOW) for _cid, r, c in rows]

    async def touch(self, conversation_id, *, expires_at, company_id, user_id) -> None:
        self.touched.append((conversation_id, expires_at))

    async def delete_expired(self, *, limit) -> int:
        self.deleted_limits.append(limit)
        return 3


def make_service(repo: FakeRepo) -> ConversationService:
    return ConversationService(repository=repo, ttl_days=30, history_turns=4, now=lambda: NOW)


def visitor() -> ConversationScope:
    return ConversationScope(company_id=None, user_id=None)


def logged(user_id: uuid.UUID = USER) -> ConversationScope:
    return ConversationScope(company_id=COMPANY, user_id=user_id)


async def test_visitante_cria_e_retoma_a_propria_conversa() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    created = await service.open_or_resume(conversation_id=None, scope=visitor(), locale="pt-BR")
    assert created is not None and created.company_id is None and created.user_id is None
    resumed = await service.open_or_resume(
        conversation_id=created.id, scope=visitor(), locale="pt-BR"
    )
    assert resumed is not None


async def test_visitante_nao_reabre_conversa_de_logado() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    created = await service.open_or_resume(conversation_id=None, scope=logged(), locale="pt-BR")
    assert created is not None
    denied = await service.open_or_resume(
        conversation_id=created.id, scope=visitor(), locale="pt-BR"
    )
    assert denied is None


async def test_logado_de_outra_empresa_ou_outro_usuario_nao_le() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    created = await service.open_or_resume(conversation_id=None, scope=logged(), locale="pt-BR")
    assert created is not None
    other_user = await service.open_or_resume(
        conversation_id=created.id, scope=logged(OTHER_USER), locale="pt-BR"
    )
    assert other_user is None
    # Repo fake ja simula RLS; o servico tambem valida o dono exato.
    repo.conversations[created.id] = ConversationView(
        id=created.id, company_id=COMPANY, user_id=USER, locale="pt-BR", expires_at=NOW
    )
    assert (
        await service.open_or_resume(
            conversation_id=created.id, scope=logged(OTHER_USER), locale="pt-BR"
        )
        is None
    )


async def test_logado_reabre_somente_a_propria_conversa() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    created = await service.open_or_resume(conversation_id=None, scope=logged(), locale="pt-BR")
    resumed = await service.open_or_resume(
        conversation_id=created.id, scope=logged(), locale="pt-BR"
    )
    assert resumed is not None and resumed.user_id == USER


async def test_somente_user_e_assistant_sao_persistidos() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    conversation = await service.open_or_resume(
        conversation_id=None, scope=visitor(), locale="pt-BR"
    )
    assert conversation is not None
    await service.append_user_message(conversation, sanitized_text="capacete para soldador")
    await service.append_assistant_message(conversation, approved_text="Veja os cartoes abaixo.")
    roles = [role for _cid, role, _content in repo.messages]
    assert roles == ["user", "assistant"]
    # Nao existe API para gravar saida de ferramenta/produto/system prompt.
    public = {name for name in dir(service) if not name.startswith("_")}
    assert public == {
        "open_or_resume",
        "last_turns",
        "append_user_message",
        "append_assistant_message",
    }


async def test_mensagem_de_usuario_e_renormalizada_ao_gravar() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    conversation = await service.open_or_resume(
        conversation_id=None, scope=visitor(), locale="pt-BR"
    )
    assert conversation is not None
    await service.append_user_message(conversation, sanitized_text="comprar  capacete\u200b ")
    assert repo.messages[0][2] == "comprar capacete"


async def test_historico_truncado_em_ai_chat_history_turns() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    conversation = await service.open_or_resume(
        conversation_id=None, scope=visitor(), locale="pt-BR"
    )
    assert conversation is not None
    for index in range(10):
        await service.append_user_message(conversation, sanitized_text=f"msg {index}")
    turns = await service.last_turns(conversation)
    assert len(turns) == 4
    assert turns[-1].content == "msg 9"


async def test_ttl_definido_na_criacao_e_renovado_ao_gravar() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    conversation = await service.open_or_resume(
        conversation_id=None, scope=visitor(), locale="pt-BR"
    )
    assert conversation is not None
    assert (conversation.expires_at - NOW).days == 30
    await service.append_assistant_message(conversation, approved_text="ok")
    assert repo.touched and (repo.touched[-1][1] - NOW).days == 30


async def test_conversa_desconhecida_nao_e_criada_silenciosamente() -> None:
    repo = FakeRepo()
    service = make_service(repo)
    result = await service.open_or_resume(
        conversation_id=uuid.uuid4(), scope=visitor(), locale="pt-BR"
    )
    assert result is None
    assert repo.conversations == {}
