"""Testes unitarios do schema Problem Details (RFC 7807)."""

from __future__ import annotations

from app.interface.schemas import CheckStatus, LivenessResponse, ProblemDetails, ReadinessResponse


def test_problem_details_serializa_sem_campos_none() -> None:
    problem = ProblemDetails(
        type="urn:forja:problem:http_404",
        title="Not Found",
        status=404,
    )
    payload = problem.model_dump(exclude_none=True)
    assert payload == {"type": "urn:forja:problem:http_404", "title": "Not Found", "status": 404}


def test_problem_details_completo() -> None:
    problem = ProblemDetails(
        type="urn:forja:problem:internal_error",
        title="Internal Server Error",
        status=500,
        detail="Erro interno inesperado.",
        instance="/api/v1/x",
        trace_id="0" * 32,
    )
    payload = problem.model_dump(exclude_none=True)
    assert payload["trace_id"] == "0" * 32
    assert payload["instance"] == "/api/v1/x"


def test_health_schemas() -> None:
    assert LivenessResponse().model_dump() == {"status": "alive"}
    ready = ReadinessResponse(
        status="ready", checks={"database": CheckStatus.OK, "redis": CheckStatus.OK}
    )
    assert ready.model_dump() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }
