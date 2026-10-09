"""Métricas Prometheus para fluxos críticos da Forja B2B.

Todas as metricas usam labels de baixa cardinalidade e NUNCA incluem dados
pessoais (email, CPF, nome, company_id, user_id). Os identificadores de
negocio (order_id, payment_id) tambem sao omitidos por padrao.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest

_HTTP_LABELS = ["method", "status"]

http_requests_total = Counter(
    "forja_http_requests_total",
    "Total de requisicoes HTTP por metodo/status",
    _HTTP_LABELS,
)
http_request_duration_seconds = Histogram(
    "forja_http_request_duration_seconds",
    "Latencia de requisicoes HTTP por metodo/status",
    _HTTP_LABELS,
)
orders_created_total = Counter(
    "forja_orders_created_total",
    "Total de pedidos criados",
    ["payment_method"],
)
payments_confirmed_total = Counter(
    "forja_payments_confirmed_total",
    "Total de eventos de pagamento confirmados",
    ["method", "outcome"],
)
notifications_dispatched_total = Counter(
    "forja_notifications_dispatched_total",
    "Total de notificacoes despachadas",
    ["status"],
)


def increment_request_counter(*, method: str, status_code: int) -> None:
    http_requests_total.labels(method=method, status=str(status_code)).inc()


def observe_request_duration(*, method: str, status_code: int, duration: float) -> None:
    http_request_duration_seconds.labels(method=method, status=str(status_code)).observe(duration)


def increment_order_created(payment_method: str) -> None:
    orders_created_total.labels(payment_method=payment_method).inc()


def increment_payment_confirmed(*, method: str, outcome: str) -> None:
    payments_confirmed_total.labels(method=method, outcome=outcome).inc()


def increment_notifications_dispatched(*, status: str) -> None:
    notifications_dispatched_total.labels(status=status).inc()


def prometheus_metrics() -> bytes:
    return generate_latest()
