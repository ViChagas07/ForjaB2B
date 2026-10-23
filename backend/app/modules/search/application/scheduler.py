"""Agendador opcional da reconciliacao dentro do processo da API.

Desligado por padrao (``RECONCILE_INTERVAL_SECONDS=0``). Quando ligado, espera
um intervalo com jitter (para varias replicas nao dispararem juntas), impoe um
timeout total e nunca deixa uma falha de Elasticsearch/PostgreSQL derrubar a
API. A alternativa de producao e um Cron Job chamando o CLI ``reconcile``.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.core.metrics import observe_reconcile_failure
from app.modules.search.application.sync import ReconcileRun

_logger = get_logger(__name__)


class ReconcileScheduler:
    """Loop de reconciliacao periodica com jitter e timeout total."""

    def __init__(
        self,
        *,
        run_once: Callable[[], Awaitable[ReconcileRun]],
        interval_seconds: int,
        jitter_seconds: int,
        timeout_seconds: int,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds deve ser > 0")
        self._run_once = run_once
        self._interval = float(interval_seconds)
        self._jitter = float(max(0, jitter_seconds))
        self._timeout = float(timeout_seconds)

    def _next_delay(self) -> float:
        # Jitter nao e seguranca: apenas espalha o disparo entre replicas.
        jitter = (
            random.uniform(-self._jitter, self._jitter)  # noqa: S311
            if self._jitter
            else 0.0
        )
        return max(1.0, self._interval + jitter)

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(self._next_delay())
            try:
                async with asyncio.timeout(self._timeout):
                    run = await self._run_once()
            except TimeoutError:
                _logger.warning("search_reconcile_timeout", timeout_seconds=self._timeout)
                observe_reconcile_failure(duration=self._timeout)
                continue
            except Exception as exc:  # noqa: BLE001 - falha nao derruba a API
                _logger.warning("search_reconcile_failed", error=type(exc).__name__)
                continue
            if run.status == "skipped":
                _logger.info("search_reconcile_skipped", reason="advisory_lock_busy")
            elif run.status == "ok" and run.report is not None:
                _logger.info(
                    "search_reconcile_succeeded",
                    upserted=run.report.upserted,
                    deleted=run.report.deleted,
                    duration=round(run.duration, 3),
                )
