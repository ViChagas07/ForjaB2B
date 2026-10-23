"""Atualizacao periodica das metricas da outbox no processo da API.

O worker Celery nao expoe ``/metrics``; por isso a API le o estado persistido
da outbox e atualiza os gauges Prometheus. O loop roda em background, nao
bloqueia o startup e nunca derruba a aplicacao por falha de banco.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.modules.search.application.sync import RefreshSearchMetrics

_logger = get_logger(__name__)


class SearchMetricsLoop:
    """Loop de atualizacao dos gauges da outbox."""

    def __init__(self, *, updater: RefreshSearchMetrics, interval_seconds: int) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds deve ser > 0")
        self._updater = updater
        self._interval = float(interval_seconds)

    async def run_forever(self) -> None:
        while True:
            try:
                await self._updater.run()
            except Exception as exc:  # noqa: BLE001 - metrica nunca derruba a API
                _logger.warning("search_outbox_metrics_failed", error=type(exc).__name__)
            await asyncio.sleep(self._interval)
