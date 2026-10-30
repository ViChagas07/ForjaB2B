"""Erros do contexto de cambio.

`FxProviderError` e interno: indica falha transitoria/permanente do provedor e
nunca chega cru ao cliente. `FxRatesUnavailableError` e o erro estavel exposto
pela API quando nao existe sequer uma taxa conhecida em cache.
"""

from __future__ import annotations

from app.core.errors import AppError


class FxProviderError(Exception):
    """O provedor de cambio falhou ou devolveu um payload invalido."""


class FxRatesUnavailableError(AppError):
    """Nao ha taxa disponivel (nem fresh nem ultima conhecida)."""

    status_code = 503
    title = "Service Unavailable"
    code = "fx_rates_unavailable"

    def __init__(self) -> None:
        super().__init__("Taxas de cambio indisponiveis no momento.")
