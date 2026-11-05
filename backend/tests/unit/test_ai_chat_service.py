"""ChatService: idioma por mensagem sem perder conversa/historico/filtros."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from app.modules.ai.application.chat import ChatService
from app.modules.ai.application.chat_graph import ChatGraph, ChatRunResult
from app.modules.ai.application.conversation_service import (
    ConversationScope,
    ConversationService,
)
from app.modules.ai.application.ports import ConversationView
from app.modules.ai.domain.degradation import language_switch_alert
from app.modules.ai.domain.language import LanguageDetection
from app.modules.ai.domain.types import Locale

CONVERSATION_ID = uuid.UUID("12340000-0000-4000-8000-000000001234")
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
VISITOR = ConversationScope(company_id=None, user_id=None)


class FakeDetector:
    def __init__(self, detections: dict[str, LanguageDetection]) -> None:
        self.detections = detections

    def detect(self, text: str) -> LanguageDetection:
        return self.detections.get(text, LanguageDetection(language=None))


class FakeConversations:
    def __init__(self, *, language: str = "pt-BR") -> None:
        self.language = language
        self.history: list[Any] = []

    async def open_or_resume(
        self,
        *,
        conversation_id: uuid.UUID | None,
        scope: Any,
        locale: str,
        conversation_language: str | None = None,
    ) -> ConversationView:
        return ConversationView(
            id=CONVERSATION_ID,
            company_id=None,
            user_id=None,
            locale=locale,
            expires_at=NOW,
            conversation_language=self.language if conversation_id else conversation_language,
        )

    async def last_turns(self, _conversation: ConversationView) -> list[Any]:
        return self.history


class FakeGraph:
    def __init__(self, conversations: FakeConversations) -> None:
        self.conversations = conversations
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> ChatRunResult:
        self.calls.append(kwargs)
        self.conversations.language = str(kwargs["reply_language"])
        return ChatRunResult(reply="ok", cards=[])


def service(
    *, conversations: FakeConversations, graph: FakeGraph, detector: FakeDetector
) -> ChatService:
    return ChatService(
        conversations=cast(ConversationService, conversations),
        graph=cast(ChatGraph, graph),
        language_detector=detector,
    )


async def test_idioma_detectado_vale_so_para_a_mensagem_atual() -> None:
    conversations = FakeConversations()
    graph = FakeGraph(conversations)
    detector = FakeDetector(
        {
            "Quiero ver los guantes más baratos del catálogo": LanguageDetection(
                language=Locale.ES, confidence=0.98, source="detector"
            )
        }
    )
    chat = service(conversations=conversations, graph=graph, detector=detector)
    await chat.handle(
        conversation_id=None,
        scope=VISITOR,
        site_locale="es",
        content_locale="pt-BR",
        message="Quiero ver los guantes más baratos del catálogo",
        auth=None,
    )
    assert graph.calls[0]["reply_language"] == "es"
    assert graph.calls[0]["content_locale"] == "pt-BR"


async def test_mensagem_curta_mantem_idioma_da_conversa() -> None:
    conversations = FakeConversations(language="es")
    graph = FakeGraph(conversations)
    detector = FakeDetector(
        {"ok": LanguageDetection(language=Locale.EN, confidence=0.99, source="detector")}
    )
    chat = service(conversations=conversations, graph=graph, detector=detector)
    await chat.handle(
        conversation_id=CONVERSATION_ID,
        scope=VISITOR,
        site_locale="pt-BR",
        content_locale="en",
        message="ok",
        auth=None,
    )
    assert graph.calls[0]["reply_language"] == "es"
    assert graph.calls[0]["content_locale"] == "en"


async def test_pedido_explicito_troca_e_persiste_ate_nova_deteccao() -> None:
    conversations = FakeConversations()
    graph = FakeGraph(conversations)
    chat = service(conversations=conversations, graph=graph, detector=FakeDetector({}))
    await chat.handle(
        conversation_id=None,
        scope=VISITOR,
        site_locale="pt-BR",
        content_locale="pt-BR",
        message="please answer in English",
        auth=None,
    )
    assert graph.calls[0]["reply_language"] == "en"
    await chat.handle(
        conversation_id=CONVERSATION_ID,
        scope=VISITOR,
        site_locale="pt-BR",
        content_locale="pt-BR",
        message="ok",
        auth=None,
    )
    assert graph.calls[1]["reply_language"] == "en"


async def test_idioma_diferente_do_app_alerta_sem_chamar_grafo() -> None:
    conversations = FakeConversations()
    graph = FakeGraph(conversations)
    detector = FakeDetector(
        {
            "Привет, есть перчатки?": LanguageDetection(
                language=Locale.RU, confidence=0.99, source="script"
            )
        }
    )
    chat = service(conversations=conversations, graph=graph, detector=detector)
    result = await chat.handle(
        conversation_id=None,
        scope=VISITOR,
        site_locale="en",
        content_locale="en",
        message="Привет, есть перчатки?",
        auth=None,
    )
    assert result is not None
    assert result.language_mismatch is True
    assert result.detected_language == "ru"
    assert result.language == "en"
    assert result.reply == language_switch_alert(Locale.EN)
    assert graph.calls == []


async def test_historico_e_conversa_sao_os_mesmos_na_troca() -> None:
    conversations = FakeConversations()
    conversations.history = [object()]
    graph = FakeGraph(conversations)
    detector = FakeDetector(
        {
            "Quiero ver los guantes más baratos del catálogo": LanguageDetection(
                language=Locale.ES, confidence=0.98, source="detector"
            )
        }
    )
    chat = service(conversations=conversations, graph=graph, detector=detector)
    await chat.handle(
        conversation_id=CONVERSATION_ID,
        scope=VISITOR,
        site_locale="es",
        content_locale="pt-BR",
        message="Quiero ver los guantes más baratos del catálogo",
        auth=None,
    )
    assert graph.calls[0]["conversation"].id == CONVERSATION_ID
    assert graph.calls[0]["history"] is conversations.history
