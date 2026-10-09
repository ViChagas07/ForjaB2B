"""Health endpoints: liveness e readiness.

Semantica (plano congelado da Fase 0):
- GET /health/live: processo vivo. Nao depende de servicos externos.
  Resposta: 200 {"status": "alive"}.
- GET /health/ready: conectividade com dependencias essenciais (PostgreSQL
  e Redis). 200 {"status": "ready", "checks": {...}} ou 503 com o mapa de
  status por dependencia.

As probes sao ligadas na raiz de composicao (app.state.readiness_probes);
esta camada nao importa infraestrutura.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Request, Response, status

from app.core.metrics import prometheus_metrics
from app.interface.schemas import CheckStatus, LivenessResponse, ReadinessResponse

ReadinessProbe = Callable[[], Awaitable[bool]]

router = APIRouter(tags=["health"])


def _readiness_probes(request: Request) -> Mapping[str, ReadinessProbe]:
    probes: Mapping[str, ReadinessProbe] | None = getattr(
        request.app.state, "readiness_probes", None
    )
    if probes is None:
        return {}
    return probes


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/health", response_model=LivenessResponse, include_in_schema=False)
async def liveness_alias() -> LivenessResponse:
    """Alias de liveness usado pelos healthchecks do Docker/Compose."""
    return LivenessResponse()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    probes = _readiness_probes(request)
    checks: dict[str, CheckStatus] = {}
    for name, probe in probes.items():
        checks[name] = CheckStatus.OK if await probe() else CheckStatus.ERROR

    all_ok = bool(checks) and all(check is CheckStatus.OK for check in checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if all_ok else "not_ready", checks=checks)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=prometheus_metrics(), media_type="text/plain; version=0.0.4")
