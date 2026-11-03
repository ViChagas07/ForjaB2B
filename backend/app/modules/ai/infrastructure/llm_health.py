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
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(f"{self._base_url}/models")
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return set()
        ids: set[str] = set()
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.add(item["id"])
        return ids
