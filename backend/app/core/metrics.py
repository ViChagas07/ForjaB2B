"""Métricas Prometheus para fluxos críticos da Forja B2B.

Todas as metricas usam labels de baixa cardinalidade e NUNCA incluem dados
pessoais (email, CPF, nome, company_id, user_id). Os identificadores de
negocio (order_id, payment_id) tambem sao omitidos por padrao.
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest

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
# Busca do catalogo (Fases 4/5/6): modo real, latencia e degradacoes.
# Labels de baixa cardinalidade (mode) e NUNCA incluem termo buscado nem tenant.
search_requests_total = Counter(
    "forja_search_requests_total",
    "Buscas de catalogo por modo real (hybrid/lexical/semantic_postgres/postgres_fallback)",
    ["mode"],
)
search_duration_seconds = Histogram(
    "forja_search_duration_seconds",
    "Latencia da busca de catalogo por modo real",
    ["mode"],
)
search_fallback_total = Counter(
    "forja_search_fallback_total",
    "Buscas que degradaram de modo (semantico/fallback) por modo real",
    ["mode"],
)

rate_limit_rejections_total = Counter(
    "forja_rate_limit_rejections_total",
    "Requisicoes rejeitadas pelo rate limiter por classe",
    ["rate_class"],
)
rate_limit_backend_failures_total = Counter(
    "forja_rate_limit_backend_failures_total",
    "Falhas do backend distribuido do rate limiter (fail-open local)",
    ["rate_class"],
)

# Outbox de busca e reconciliacao do indice (Prompt 05). Gauges sao atualizados
# pelo processo da API a partir do PostgreSQL; contadores registram o drift
# corrigido e falhas de reconciliacao.
outbox_pending = Gauge(
    "forja_outbox_pending",
    "Eventos de busca pendentes ou falhos ainda retentaveis",
)
outbox_dead_total = Gauge(
    "forja_outbox_dead_total",
    "Eventos de busca em DEAD_LETTERED",
)
outbox_oldest_pending_age_seconds = Gauge(
    "forja_outbox_oldest_pending_age_seconds",
    "Idade do evento de busca pendente mais antigo, em segundos",
)
reconcile_last_success_timestamp_seconds = Gauge(
    "forja_reconcile_last_success_timestamp_seconds",
    "Timestamp Unix da ultima reconciliacao bem-sucedida",
)
reconcile_duration_seconds = Histogram(
    "forja_reconcile_duration_seconds",
    "Duracao da reconciliacao do indice de busca",
)
reconcile_drift_total = Counter(
    "forja_reconcile_drift_total",
    "Correcoes aplicadas pela reconciliacao (upsert/delete)",
    ["kind"],
)
reconcile_failures_total = Counter(
    "forja_reconcile_failures_total",
    "Execucoes de reconciliacao que falharam",
)

_DEGRADED_SEARCH_MODES = frozenset({"semantic_postgres", "postgres_fallback"})


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


def observe_search(*, mode: str, duration: float) -> None:
    """Contabiliza uma busca: modo real, latencia e (se degradado) fallback."""
    search_requests_total.labels(mode=mode).inc()
    search_duration_seconds.labels(mode=mode).observe(duration)
    if mode in _DEGRADED_SEARCH_MODES:
        search_fallback_total.labels(mode=mode).inc()


def increment_rate_limit_rejection(*, rate_class: str) -> None:
    rate_limit_rejections_total.labels(rate_class=rate_class).inc()


def increment_rate_limit_backend_failure(*, rate_class: str) -> None:
    rate_limit_backend_failures_total.labels(rate_class=rate_class).inc()


def observe_outbox_snapshot(*, pending: int, dead: int, oldest_pending_age_seconds: float) -> None:
    """Atualiza os gauges da outbox com um instantaneo do PostgreSQL."""
    outbox_pending.set(pending)
    outbox_dead_total.set(dead)
    outbox_oldest_pending_age_seconds.set(max(0.0, oldest_pending_age_seconds))


def observe_reconcile_success(*, duration: float, upserted: int, deleted: int) -> None:
    """Registra sucesso, duracao e drift corrigido por uma reconciliacao."""
    reconcile_duration_seconds.observe(duration)
    reconcile_last_success_timestamp_seconds.set(time.time())
    if upserted > 0:
        reconcile_drift_total.labels(kind="upserted").inc(upserted)
    if deleted > 0:
        reconcile_drift_total.labels(kind="deleted").inc(deleted)


def observe_reconcile_failure(*, duration: float) -> None:
    """Registra falha sem atualizar o timestamp da ultima execucao valida."""
    reconcile_duration_seconds.observe(duration)
    reconcile_failures_total.inc()


def prometheus_metrics() -> bytes:
    return generate_latest()
