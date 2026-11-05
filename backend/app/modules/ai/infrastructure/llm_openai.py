"""Adaptador LLM via API compativel com OpenAI (langchain-openai).

Unico ponto que conhece langchain-openai. Aponta para `LLM_BASE_URL`
(LM Studio local, OpenAI, gateways ou modelos com endpoint OpenAI-like); a
chave fica na memoria do processo e NUNCA em logs/mensagens de erro.

Particularidades do Qwen 3.5 no LM Studio:
- o modelo pode "pensar" e devolver o texto em `reasoning_content`, com
  `content` vazio, principalmente quando `max_tokens` e curto. O adaptador
  detecta `finish_reason=length` / `reasoning_content` e faz UMA nova tentativa
  com `reasoning_effort=none`, `chat_template_kwargs.enable_thinking=false`
  (parametros documentados do Qwen/LM Studio) e um teto de tokens maior.
- blocos <think>...</think> que ainda escaparem sao removidos.
- `response_format=json_schema` funciona no LM Studio; quando o provedor nao
  suportar, caimos para prompt JSON rigido + parser tolerante + validacao
  Pydantic + UMA tentativa de reparo.
- sem retry de transporte aqui: a politica (timeout + 1 retry) e do envelope
  `ResilientLLM`. Toda falha vira `LLMUnavailableError` com `kind` estavel.
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
from app.core.logging import get_logger
from app.modules.ai.application.errors import LLMUnavailableError
from app.modules.ai.application.ports import (
    ConcurrencyLimitedLLM,
    LLMMessage,
    ResilientLLM,
)

TModel = TypeVar("TModel", bound=BaseModel)

_logger = get_logger(__name__)
_THINK_CLOSED = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN = re.compile(r"<think\b[^>]*>.*\Z", re.IGNORECASE | re.DOTALL)
_SPECIAL_TOKENS = re.compile(r"<\|[^|>]{1,40}\|>")
_JSON_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_UNSUPPORTED_FORMAT_STATUS = frozenset({400, 404, 422})
_RECOVERABLE_KINDS = frozenset({"reasoning_only", "empty_response", "truncated"})
_MAX_RETRY_TOKENS = 2048


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
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._default_temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._chat = self._build_chat(temperature, max_tokens)
        self._chats: dict[tuple[float, int, bool], ChatOpenAI] = {
            (temperature, max_tokens, False): self._chat
        }

    def _build_chat(
        self, temperature: float, max_tokens: int | None, *, disable_thinking: bool = False
    ) -> ChatOpenAI:
        extra_body: dict[str, Any] | None = None
        if disable_thinking:
            # Parametro documentado do template Qwen3.5. O LM Studio 3.5 9B
            # pode ignora-lo em algumas versoes; por isso tambem enviamos
            # reasoning_effort=none e aumentamos max_tokens.
            extra_body = {"chat_template_kwargs": {"enable_thinking": False}}
        return ChatOpenAI(
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key,  # so na memoria do processo; nunca logado
            timeout=self._timeout_seconds,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature,
            reasoning_effort="none" if disable_thinking else self._reasoning_effort,
            extra_body=extra_body,
        )

    def _chat_for(
        self,
        temperature: float | None,
        max_tokens: int | None = None,
        *,
        disable_thinking: bool = False,
    ) -> ChatOpenAI:
        resolved_temperature = self._default_temperature if temperature is None else temperature
        resolved_tokens = max_tokens or self._max_tokens
        key = (resolved_temperature, resolved_tokens, disable_thinking)
        if key not in self._chats:
            self._chats[key] = self._build_chat(
                resolved_temperature, resolved_tokens, disable_thinking=disable_thinking
            )
        return self._chats[key]

    async def complete_structured(  # noqa: C901 - recuperacao/fallback do schema
        self,
        *,
        schema: type[TModel],
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> TModel:
        resolved_tokens = max_tokens or self._max_tokens
        try:
            return await self._structured_once(
                schema, messages, temperature, resolved_tokens, disable_thinking=False
            )
        except LLMUnavailableError as exc:
            if exc.kind in _RECOVERABLE_KINDS:
                _logger.warning(
                    "llm_response_recoverable",
                    stage="structured",
                    kind=exc.kind,
                    model=self._model,
                )
                try:
                    return await self._structured_once(
                        schema,
                        messages,
                        temperature,
                        _retry_tokens(resolved_tokens),
                        disable_thinking=True,
                    )
                except LLMUnavailableError as retry_exc:
                    _logger.warning(
                        "llm_retry_failed",
                        stage="structured",
                        kind=retry_exc.kind,
                        model=self._model,
                    )
                    if retry_exc.kind not in _RECOVERABLE_KINDS | {"invalid_json"}:
                        raise
                    return await self._prompt_structured_with_repair(
                        schema,
                        messages,
                        temperature,
                        _retry_tokens(resolved_tokens),
                        disable_thinking=True,
                    )
                except (APITimeoutError, APIConnectionError, APIStatusError) as retry_exc:
                    raise _as_unavailable(retry_exc) from retry_exc
            if exc.kind == "invalid_json":
                return await self._prompt_structured_with_repair(
                    schema, messages, temperature, resolved_tokens
                )
            raise
        except (APITimeoutError, APIConnectionError) as exc:
            raise _as_unavailable(exc) from exc
        except APIStatusError as exc:
            if exc.status_code not in _UNSUPPORTED_FORMAT_STATUS:
                raise _as_unavailable(exc) from exc
            # Provedor sem response_format: prompt rigido + parser tolerante.
            return await self._prompt_structured_with_repair(
                schema, messages, temperature, resolved_tokens
            )
        except (ValidationError, ValueError) as exc:
            _logger.warning(
                "llm_schema_invalid", stage="structured", error_type=type(exc).__name__
            )
            return await self._prompt_structured_with_repair(
                schema, messages, temperature, resolved_tokens
            )
        except Exception as exc:
            raise _as_unavailable(exc) from exc

    async def complete_text(  # noqa: C901 - recuperacao de content vazio/truncado
        self,
        *,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resolved_tokens = max_tokens or self._max_tokens
        try:
            response = await self._invoke_raw(
                messages,
                temperature,
                resolved_tokens,
                disable_thinking=False,
            )
        except (APITimeoutError, APIConnectionError) as exc:
            raise _as_unavailable(exc) from exc
        except APIStatusError as exc:
            raise _as_unavailable(exc) from exc
        except Exception as exc:
            raise _as_unavailable(exc) from exc
        text, reasoning, finish_reason = _extract_response(response)
        kind = _response_kind(text, reasoning, finish_reason)
        if kind is None:
            return strip_reasoning(text)
        _logger.warning(
            "llm_response_recoverable",
            stage="text",
            kind=kind,
            model=self._model,
        )
        try:
            retry = await self._invoke_raw(
                messages,
                temperature,
                _retry_tokens(resolved_tokens),
                disable_thinking=True,
            )
        except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
            if strip_reasoning(text):
                return strip_reasoning(text)
            raise _as_unavailable(exc) from exc
        except Exception as exc:
            if strip_reasoning(text):
                return strip_reasoning(text)
            raise _as_unavailable(exc) from exc
        retry_text, retry_reasoning, retry_finish = _extract_response(retry)
        retry_kind = _response_kind(retry_text, retry_reasoning, retry_finish)
        if retry_kind is None:
            return strip_reasoning(retry_text)
        _logger.warning(
            "llm_retry_failed",
            stage="text",
            kind=retry_kind,
            model=self._model,
        )
        if strip_reasoning(text):
            return strip_reasoning(text)
        raise LLMUnavailableError("llm_empty_response", kind=retry_kind)

    async def _structured_once(
        self,
        schema: type[TModel],
        messages: Sequence[LLMMessage],
        temperature: float | None,
        max_tokens: int,
        *,
        disable_thinking: bool,
    ) -> TModel:
        structured = self._chat_for(
            temperature, max_tokens, disable_thinking=disable_thinking
        ).with_structured_output(schema, method="json_schema", include_raw=True)
        result = await structured.ainvoke(self._as_langchain_messages(messages))
        if isinstance(result, dict):
            raw = result.get("raw")
            parsed = result.get("parsed")
            text, reasoning, finish_reason = _extract_response(raw)
            if parsed is None:
                kind = _response_kind(text, reasoning, finish_reason) or "invalid_json"
                raise LLMUnavailableError("llm_schema_mismatch", kind=kind)
            if not text.strip() or finish_reason == "length":
                kind = (
                    "truncated"
                    if finish_reason == "length"
                    else ("reasoning_only" if reasoning.strip() else "empty_response")
                )
                raise LLMUnavailableError("llm_schema_mismatch", kind=kind)
            if isinstance(parsed, schema):
                return _clean_model_strings(parsed)
            return _clean_model_strings(schema.model_validate(parsed))
        if result is None:
            raise LLMUnavailableError("llm_schema_mismatch", kind="empty_response")
        if isinstance(result, schema):
            return _clean_model_strings(result)
        return _clean_model_strings(schema.model_validate(result))

    async def _prompt_structured_with_repair(
        self,
        schema: type[TModel],
        messages: Sequence[LLMMessage],
        temperature: float | None,
        max_tokens: int,
        *,
        disable_thinking: bool = False,
    ) -> TModel:
        instruction = _json_instruction(schema)
        prompt: list[dict[str, Any]] = [
            *self._as_langchain_messages(messages),
            {"role": "user", "content": instruction},
        ]
        raw = await self._invoke_text(
            prompt,
            temperature,
            max_tokens,
            disable_thinking=disable_thinking,
        )
        try:
            return _clean_model_strings(schema.model_validate(extract_json_object(raw)))
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
            repaired = await self._invoke_text(
                repair,
                temperature,
                max_tokens,
                disable_thinking=True,
            )
            try:
                return _clean_model_strings(schema.model_validate(extract_json_object(repaired)))
            except (ValueError, ValidationError) as exc:
                raise LLMUnavailableError("llm_schema_mismatch", kind="invalid_json") from exc

    async def _invoke_text(  # noqa: C901 - recuperacao de content vazio/truncado
        self,
        messages: Sequence[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        disable_thinking: bool = False,
    ) -> str:
        resolved_tokens = max_tokens or self._max_tokens
        try:
            response = await self._invoke_raw(
                messages, temperature, resolved_tokens, disable_thinking=disable_thinking
            )
        except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
            raise _as_unavailable(exc) from exc
        except Exception as exc:
            raise _as_unavailable(exc) from exc
        text, reasoning, finish_reason = _extract_response(response)
        kind = _response_kind(text, reasoning, finish_reason)
        if kind is None:
            return strip_reasoning(text)
        _logger.warning(
            "llm_response_recoverable",
            stage="text_repair",
            kind=kind,
            model=self._model,
        )
        try:
            retry = await self._invoke_raw(
                messages,
                temperature,
                _retry_tokens(resolved_tokens),
                disable_thinking=True,
            )
        except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
            if strip_reasoning(text):
                return strip_reasoning(text)
            raise _as_unavailable(exc) from exc
        except Exception as exc:
            if strip_reasoning(text):
                return strip_reasoning(text)
            raise _as_unavailable(exc) from exc
        retry_text, retry_reasoning, retry_finish = _extract_response(retry)
        retry_kind = _response_kind(retry_text, retry_reasoning, retry_finish)
        if retry_kind is None:
            return strip_reasoning(retry_text)
        if strip_reasoning(text):
            return strip_reasoning(text)
        raise LLMUnavailableError("llm_empty_response", kind=retry_kind)

    async def _invoke_raw(
        self,
        messages: Sequence[Mapping[str, Any]],
        temperature: float | None,
        max_tokens: int,
        *,
        disable_thinking: bool,
    ) -> Any:
        return await self._chat_for(
            temperature, max_tokens, disable_thinking=disable_thinking
        ).ainvoke(self._as_langchain_messages(messages))

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


def _extract_response(message: object) -> tuple[str, str, str | None]:
    if message is None:
        return "", "", None
    text = _content_to_text(getattr(message, "content", ""))
    reasoning = _reasoning_content(message)
    metadata = getattr(message, "response_metadata", {}) or {}
    finish_reason = None
    if isinstance(metadata, Mapping):
        finish_reason = metadata.get("finish_reason") or metadata.get("stop_reason")
    return text, reasoning, str(finish_reason) if finish_reason is not None else None


def _reasoning_content(message: object) -> str:
    additional = getattr(message, "additional_kwargs", {}) or {}
    if isinstance(additional, Mapping):
        for key in ("reasoning_content", "reasoning"):
            value = additional.get(key)
            if isinstance(value, str) and value.strip():
                return value
    metadata = getattr(message, "response_metadata", {}) or {}
    if isinstance(metadata, Mapping):
        for key in ("reasoning_content", "reasoning"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _response_kind(text: str, reasoning: str, finish_reason: str | None) -> str | None:
    if finish_reason == "length":
        return "truncated"
    if not text.strip():
        return "reasoning_only" if reasoning.strip() else "empty_response"
    return None


def _retry_tokens(max_tokens: int) -> int:
    return min(_MAX_RETRY_TOKENS, max(1024, max_tokens * 3))


def _as_unavailable(exc: BaseException) -> LLMUnavailableError:
    if isinstance(exc, LLMUnavailableError):
        return exc
    if isinstance(exc, (APITimeoutError, TimeoutError)):
        return LLMUnavailableError("llm_timeout", kind="timeout")
    if isinstance(exc, APIConnectionError):
        return LLMUnavailableError("llm_transport_failed", kind=_connection_kind(exc))
    if isinstance(exc, APIStatusError):
        kind = "http_4xx" if 400 <= exc.status_code < 500 else "http_5xx"
        _logger.warning(
            "llm_http_error",
            stage="transport",
            kind=kind,
            status_code=exc.status_code,
        )
        return LLMUnavailableError("llm_transport_failed", kind=kind)
    return LLMUnavailableError("llm_failed", kind="unexpected")


def _connection_kind(exc: BaseException) -> str:
    names = {type(cause).__name__ for cause in _cause_chain(exc)}
    if names & {"ConnectionRefusedError", "ConnectError", "ClientConnectorError"}:
        return "connection_refused"
    if names & {"gaierror", "ClientConnectorDNSError"}:
        return "dns_error"
    return "connection_error"


def _cause_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = [exc]
    current = exc
    for _ in range(5):
        cause = current.__cause__ or current.__context__
        if cause is None or cause is current:
            break
        chain.append(cause)
        current = cause
    return chain


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
        raise LLMUnavailableError("llm_not_configured", kind="not_configured")
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
