"""FakeLLM deterministico para testes (implementa o contrato de LLMPort).

Nenhuma rede, nenhum pacote de LLM: as respostas sao roteirizadas pelo
próprio teste. Escoar o roteiro levanta AssertionError (bug de teste) e
NUNCA LLMUnavailableError, para nao mascarar um fallback no meio do teste.
Excecoes roteirizadas sao levantadas como estao (simulam falha do provedor).
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.modules.ai.application.ports import LLMMessage

ScriptedItem = object  # BaseModel (resposta), Exception (falha) ou str (texto)

TModel = TypeVar("TModel", bound=BaseModel)


class FakeLLM:
    """LLM de teste: respostas em fila, chamadas gravadas, zero I/O."""

    def __init__(
        self, *, structured: list[BaseModel] | None = None, texts: list[str] | None = None
    ) -> None:
        self._structured: list[BaseModel] = list(structured or [])
        self._texts: list[str] = list(texts or [])
        self.structured_calls: list[tuple[type[BaseModel], list[LLMMessage]]] = []
        self.text_calls: list[list[LLMMessage]] = []

    async def complete_structured(
        self, *, schema: type[TModel], messages: list[LLMMessage]
    ) -> TModel:
        self.structured_calls.append((schema, list(messages)))
        item = self._next(self._structured, schema=schema)
        if not isinstance(item, schema):
            raise AssertionError(f"FakeLLM: roteiro nao e {schema.__name__}")
        return item

    async def complete_text(self, *, messages: list[LLMMessage]) -> str:
        self.text_calls.append(list(messages))
        item = self._next(self._texts, schema=str)
        if not isinstance(item, str):
            raise AssertionError("FakeLLM: roteiro de texto nao e str")
        return item

    def _next(self, queue: list[BaseModel] | list[str], *, schema: object) -> ScriptedItem:
        if not queue:
            raise AssertionError(f"FakeLLM: roteiro esgotado (chamada inesperada para {schema})")
        return queue.pop(0)
