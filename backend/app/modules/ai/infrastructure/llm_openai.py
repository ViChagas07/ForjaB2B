"""Adaptador LLM via API compativel com OpenAI (langchain-openai).

Unico ponto que conhece langchain-openai. Aponta para `LLM_BASE_URL`
(OpenAI, gateways, modelos locais com endpoint OpenAI-like); a chave fica
na memoria do processo e NUNCA em logs/mensagens de erro. Sem retry aqui:
a politica de resiliencia (timeout + 1 retry) e do envelope `ResilientLLM`
na application. Qualquer falha de transporte/validacao vira
`LLMUnavailableError` (contrato: um unico erro tipado para o fallback).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.modules.ai.application.errors import LLMUnavailableError
from app.modules.ai.application.ports import LLMMessage

TModel = TypeVar("TModel", bound=BaseModel)


class LangChainOpenAILLM:
    """LLMPort sobre `ChatOpenAI` (saida estruturada por schema Pydantic)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
    ) -> None:
        self._chat = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,  # so na memoria do processo; nunca logado
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0,
        )

    async def complete_structured(
        self, *, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel:
        structured = self._chat.with_structured_output(schema)
        try:
            result = await structured.ainvoke(self._as_langchain_messages(messages))
        except LLMUnavailableError:
            raise
        except Exception as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        if not isinstance(result, schema):
            # Provedor incompativel devolveu dict/str em vez do schema.
            raise LLMUnavailableError("llm_schema_mismatch")
        return result

    async def complete_text(self, *, messages: Sequence[LLMMessage]) -> str:
        try:
            response = await self._chat.ainvoke(self._as_langchain_messages(messages))
        except LLMUnavailableError:
            raise
        except Exception as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        content = response.content
        if isinstance(content, str):
            return content
        # Conteudo em blocos (provedores multimodais): concatena os trechos de texto.
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )

    @staticmethod
    def _as_langchain_messages(messages: Sequence[LLMMessage]) -> list[dict[str, Any]]:
        # Dicts {role, content} sao convertidos pelo langchain-core; copiamos
        # para nao expor a lista original a mutacoes do adapter.
        return [dict(message) for message in messages]


def build_langchain_llm(settings: Settings) -> LangChainOpenAILLM:
    """Fabrica para a raiz de composicao (so chamada com a IA habilitada)."""
    base_url = settings.llm_base_url
    api_key = settings.llm_api_key
    if base_url is None or api_key is None:
        raise LLMUnavailableError("llm_not_configured")
    return LangChainOpenAILLM(
        base_url=base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_s,
        max_tokens=settings.llm_max_tokens,
    )
