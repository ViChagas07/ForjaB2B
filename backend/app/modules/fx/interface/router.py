"""Endpoint publico das taxas de cambio usadas apenas para exibicao.

Nenhum valor de pedido, pagamento ou total passa por aqui. A resposta inclui a
fonte e a data de referencia da taxa para transparencia; quando o provedor falha
e existe ultima taxa conhecida, `stale` vem verdadeiro e o cache HTTP fica mais
curto.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response

from app.modules.fx.application.get_rates import FxRatesView, GetFxRates
from app.modules.fx.interface.schemas import CurrencyCode, FxRatesResponse

router = APIRouter(prefix="/fx", tags=["fx"])

_FRESH_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
_STALE_CACHE_CONTROL = "public, max-age=60"


def _get_fx_rates(request: Request) -> GetFxRates:
    return cast(GetFxRates, request.app.state.fx_get_rates)


def _to_response(view: FxRatesView) -> FxRatesResponse:
    rates = cast(dict[CurrencyCode, Decimal], dict(view.rates.rates))
    return FxRatesResponse(
        base=view.rates.base,
        rates=rates,
        rate_date=view.rates.rate_date,
        fetched_at=view.rates.fetched_at,
        source=view.rates.source,
        stale=view.stale,
    )


@router.get(
    "/rates",
    response_model=FxRatesResponse,
    summary="Taxas de cambio BRL para exibicao",
    description=(
        "Retorna a taxa de 1 BRL para as moedas suportadas, a fonte e a data de "
        "referencia do provedor. Valores convertidos no storefront sao aproximados; "
        "a cobranca permanece em BRL."
    ),
)
async def get_fx_rates(
    use_case: Annotated[GetFxRates, Depends(_get_fx_rates)],
    response: Response,
) -> FxRatesResponse:
    view = await use_case.run()
    response.headers["Cache-Control"] = _STALE_CACHE_CONTROL if view.stale else _FRESH_CACHE_CONTROL
    return _to_response(view)
