"""Adaptador LLM via API compativel com OpenAI (langchain-openai).

Unico ponto que conhece langchain-openai. Aponta para `LLM_BASE_URL`
(LM Studio local, OpenAI, gateways ou modelos com endpoint OpenAI-like); a
chave fica na memoria do processo e NUNCA em logs/mensagens de erro.

Particularidades do Qwen 3.5 no LM Studio:
- o modelo "pensa" por padrao e devolve o texto em `reasoning_content`, com
  `content` vazio. Enviamos `reasoning_effort=none` (suportado pelo LM Studio)
  para respostas rapidas; blocos <think>...</think> que ainda escaparem sao
  removidos no pos-processador.
- `response_format=json_schema` funciona no LM Studio; quando o provedor nao
  suportar, caimos para prompt JSON rigido + parser tolerante + validacao
  Pydantic + UMA tentativa de reparo.
- sem retry aqui: a politica (timeout + 1 retry com backoff) e do envelope
  `ResilientLLM`. Qualquer falha vira `LLMUnavailableError`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.modules.ai.application.errors import LLMUnavailableError
from app.modules.ai.application.ports import (
    ConcurrencyLimitedLLM,
    LLMMessage,
    ResilientLLM,
)

TModel = TypeVar("TModel", bound=BaseModel)

_THINK_CLOSED = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN = re.compile(r"<think\b[^>]*>.*\Z", re.IGNORECASE | re.DOTALL)
_SPECIAL_TOKENS = re.compile(r"<\|[^|>]{1,40}\|>")
_JSON_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_UNSUPPORTED_FORMAT_STATUS = frozenset({400, 404, 422})


def strip_reasoning(text: str) -> str:
    """Remove blocos de raciocinio/tokens especiais antes de entregar ao usuario.

    Unico ponto de limpeza do cliente. Cobre <think>...</think> fechado,
    <think> sem fechamento (remove ate o fim), tokens especiais do template e
    espacos nas pontas.
    """
    cleaned = _THINK_CLOSED.sub("", text)
    cleaned = _THINK_OPEN.sub("", cleaned)
    cleaned = _SPECIAL_TOKENS.sub("", cleaned)
    return cleaned.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON de uma resposta possivelmente suja.

    Tolerante a cercas Markdown, texto antes/depois e virgula final. Nao
    tenta "adivinhar" JSON sem chaves: falha rapido para o fallback.
    """
    cleaned = strip_reasoning(text)
    fenced = _JSON_FENCE.search(cleaned)
    if fenced is not None:
        cleaned = fenced.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("resposta sem objeto JSON")
    candidate = cleaned[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        payload = json.loads(_TRAILING_COMMA.sub(r"\1", candidate))
    if not isinstance(payload, dict):
        raise ValueError("JSON nao e um objeto")
    return payload


class LangChainOpenAILLM:
    """LLMPort sobre `ChatOpenAI` (texto e saida estruturada validada)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float = 0.3,
        reasoning_effort: str | None = "none",
    ) -> None:
        self._chat = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,  # so na memoria do processo; nunca logado
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )

    async def complete_structured(
        self, *, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel:
        try:
            result = await self._structured_json_schema(schema, messages)
        except (APITimeoutError, APIConnectionError) as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        except APIStatusError as exc:
            if exc.status_code not in _UNSUPPORTED_FORMAT_STATUS:
                raise LLMUnavailableError("llm_transport_failed") from exc
            # Provedor sem response_format: prompt rigido + parser tolerante.
            return await self._prompt_structured_with_repair(schema, messages)
        except LLMUnavailableError:
            raise
        except (ValidationError, ValueError):
            # Saida fora do schema: tenta UMA reparacao com prompt rigido.
            return await self._prompt_structured_with_repair(schema, messages)
        except Exception as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        if not isinstance(result, schema):
            raise LLMUnavailableError("llm_schema_mismatch")
        return _clean_model_strings(result)

    async def complete_text(self, *, messages: Sequence[LLMMessage]) -> str:
        try:
            response = await self._chat.ainvoke(self._as_langchain_messages(messages))
        except (APITimeoutError, APIConnectionError) as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        except APIStatusError as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        except Exception as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        content = _content_to_text(response.content)
        if not content:
            # Qwen gastou todos os tokens em reasoning_content: nao vaza
            # cadeia de pensamento; o chamador degrada para o fallback.
            raise LLMUnavailableError("llm_reasoning_only")
        cleaned = strip_reasoning(content)
        if not cleaned:
            raise LLMUnavailableError("llm_empty_response")
        return cleaned

    async def _structured_json_schema(
        self, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel:
        structured = self._chat.with_structured_output(schema, method="json_schema")
        result = await structured.ainvoke(self._as_langchain_messages(messages))
        if result is None:
            raise ValueError("saida estruturada vazia")
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)

    async def _prompt_structured_with_repair(
        self, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel:
        instruction = _json_instruction(schema)
        prompt: list[dict[str, Any]] = [
            *self._as_langchain_messages(messages),
            {"role": "user", "content": instruction},
        ]
        raw = await self._invoke_text(prompt)
        try:
            return schema.model_validate(extract_json_object(raw))
        except (ValueError, ValidationError):
            repair: list[dict[str, Any]] = [
                *prompt,
                {"role": "assistant", "content": raw[:2000]},
                {
                    "role": "user",
                    "content": (
                        "Sua resposta anterior nao e JSON valido para o schema. "
                        "Responda SOMENTE com o objeto JSON corrigido, sem texto extra."
                    ),
                },
            ]
            repaired = await self._invoke_text(repair)
            try:
                return schema.model_validate(extract_json_object(repaired))
            except (ValueError, ValidationError) as exc:
                raise LLMUnavailableError("llm_schema_mismatch") from exc

    async def _invoke_text(self, messages: Sequence[dict[str, Any]]) -> str:
        try:
            response = await self._chat.ainvoke(self._as_langchain_messages(messages))
        except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        except LLMUnavailableError:
            raise
        except Exception as exc:
            raise LLMUnavailableError("llm_transport_failed") from exc
        content = _content_to_text(response.content)
        if not content:
            raise LLMUnavailableError("llm_reasoning_only")
        return strip_reasoning(content)

    @staticmethod
    def _as_langchain_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        # Dicts {role, content} sao convertidos pelo langchain-core; copiamos
        # para nao expor a lista original a mutacoes do adapter.
        return [dict(message) for message in messages]


def _json_instruction(schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    return (
        "FORMATO OBRIGATORIO: responda SOMENTE com um objeto JSON valido, sem "
        "Markdown, sem comentarios e sem texto antes ou depois. O objeto deve "
        f"validar exatamente este JSON Schema: {schema_json}"
    )


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Conteudo em blocos (provedores multimodais): concatena os textos.
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _clean_model_strings[TModel: BaseModel](model: TModel) -> TModel:
    """Remove <think>/tokens especiais de TODOS os campos string do schema."""
    cleaned = _clean_value(model.model_dump())
    return type(model).model_validate(cleaned)


def _clean_value(value: object) -> object:
    # StrEnum (intent/acao) tambem e `str`; preservar o enum evita falha no
    # `strict=True` dos schemas ao revalidar.
    if isinstance(value, str) and not isinstance(value, Enum):
        return strip_reasoning(value)
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_value(item) for key, item in value.items()}
    return value


def build_langchain_llm(settings: Settings) -> LangChainOpenAILLM:
    """Fabrica para a raiz de composicao (so chamada com a IA habilitada)."""
    base_url = settings.llm_base_url
    api_key = settings.llm_api_key
    if not settings.llm_ready or base_url is None or api_key is None:
        raise LLMUnavailableError("llm_not_configured")
    return LangChainOpenAILLM(
        base_url=base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_s,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def build_resilient_llm(settings: Settings) -> ResilientLLM | None:
    """Cliente UNICO usado pelo chat e pelo job de carrinho.

    Devolve None quando o kill switch esta off, o LLM esta desabilitado ou
    falta configuracao. Envelopa semaforo/fila (GPU pequena) + timeout/retry.
    """
    if not settings.ai_agents_enabled or not settings.llm_ready:
        return None
    limited = ConcurrencyLimitedLLM(
        build_langchain_llm(settings),
        max_concurrency=settings.llm_max_concurrency,
        queue_size=settings.llm_queue_size,
        queue_timeout_seconds=settings.llm_queue_timeout_seconds,
    )
    return ResilientLLM(limited, timeout_seconds=settings.llm_timeout_s)
