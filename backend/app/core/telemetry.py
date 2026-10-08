"""Fundacao de observabilidade OpenTelemetry (traces e metricas base).

Escopo da Fase 0: provider de traces/metricas, exportacao OTLP para o
collector do compose e instrumentacao HTTP (FastAPI) e SQLAlchemy.
Nenhuma metrica ou span de negocio e criado aqui.

A propagacao W3C (`traceparent`) e feita pela instrumentacao ASGI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

_TRACE_HEADER_TRACE_ID_HEX_LENGTH = 32


def current_trace_id() -> str | None:
    """Trace ID W3C do span ativo (hex de 32 chars) ou None fora de trace."""
    span = trace.get_current_span()
    context = span.get_span_context()
    if context.trace_id == 0:
        return None
    return format(context.trace_id, f"0{_TRACE_HEADER_TRACE_ID_HEX_LENGTH}x")


def configure_telemetry(settings: Settings) -> None:
    """Inicializa providers globais de traces e metricas.

    Deve ser chamado uma unica vez por processo, no startup da aplicacao.
    Quando `otel_enabled` e falso (testes), nenhum provider e instalado e a
    API global do OTel permanece no-op.
    """
    if not settings.otel_enabled:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": _app_version(),
            "deployment.environment": settings.environment,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)

    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

        metric_exporter = OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[PeriodicExportingMetricReader(metric_exporter)],
        )
        metrics.set_meter_provider(meter_provider)


def instrument_app(app: FastAPI) -> None:
    """Instrumentacao HTTP do FastAPI (traces de servidor + propagacao W3C)."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def instrument_engine(engine: AsyncEngine) -> None:
    """Instrumentacao SQLAlchemy (spans de queries) sobre o sync_engine."""
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def shutdown_telemetry() -> None:
    """Flush e shutdown dos providers globais, chamado no lifespan de saida."""
    tracer_provider = trace.get_tracer_provider()
    if isinstance(tracer_provider, TracerProvider):
        tracer_provider.shutdown()
    meter_provider = metrics.get_meter_provider()
    if isinstance(meter_provider, MeterProvider):
        meter_provider.shutdown()


def _app_version() -> str:
    from app import __version__

    return __version__
