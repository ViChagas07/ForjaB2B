"""Probe leve do LLM local para `GET /health/llm` (nunca afeta `/health`).

Faz GET em `{base_url}/models` com timeout curto, verifica se o modelo
configurado esta carregado e cacheia o resultado por ~30 s para nao gerar
carga na GPU a cada abertura do chat. Qualquer falha vira `available=False`;
o probe nunca levanta excecao e nunca bloqueia o readiness da aplicacao.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx


@dataclass(frozen=True, kw_only=True)
class LLMHealthResult:
    available: bool
    enabled: bool
    model: str


class LLMHealthProbe:
    """Cache curto do ping ao endpoint OpenAI-like (LM Studio)."""

    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str | None,
        model: str,
        timeout_seconds: float = 3.0,
        cache_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        fetch_model_ids: Callable[[], Awaitable[set[str]]] | None = None,
    ) -> None:
        self._enabled = enabled
        self._base_url = (base_url or "").rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._fetch_model_ids = fetch_model_ids or self._default_fetch
        self._cached: LLMHealthResult | None = None
        self._cached_at = 0.0

    async def check(self) -> LLMHealthResult:
        if not self._enabled or not self._base_url:
            return LLMHealthResult(available=False, enabled=False, model=self._model)
        now = self._clock()
        if self._cached is not None and (now - self._cached_at) < self._cache_seconds:
            return self._cached
        available = False
        try:
            model_ids = await self._fetch_model_ids()
            available = self._model in model_ids
        except Exception:  # noqa: BLE001 - probe nunca derruba a rota
            available = False
        result = LLMHealthResult(available=available, enabled=True, model=self._model)
        self._cached = result
        self._cached_at = now
        return result

    async def _default_fetch(self) -> set[str]:
        """IDs REALMENTE carregados (LM Studio) ou listados (OpenAI-like).

        No LM Studio, `/v1/models` lista modelos que ainda estao carregando ou
        descarregados. Consultamos primeiro `/api/v0/models` e exigimos
        `state == "loaded"`; se o provedor nao tiver a API nativa (404),
        caimos para o comportamento OpenAI-like de `/v1/models`.
        """
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            native = await self._fetch_native_loaded(client)
            if native is not None:
                return native
            response = await client.get(f"{self._base_url}/models")
            response.raise_for_status()
            payload = response.json()
        return listed_model_ids(payload)

    async def _fetch_native_loaded(self, client: httpx.AsyncClient) -> set[str] | None:
        base = self._base_url.removesuffix("/v1")
        try:
            response = await client.get(f"{base}/api/v0/models")
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return loaded_model_ids(response.json())


def listed_model_ids(payload: object) -> set[str]:
    """IDs de `/v1/models` (provedor OpenAI-like)."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return set()
    return {
        item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def loaded_model_ids(payload: object) -> set[str]:
    """IDs de `/api/v0/models` com `state == "loaded"` (LM Studio)."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return set()
    ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        state = item.get("state")
        if state is None or state == "loaded":
            ids.add(item["id"])
    return ids
