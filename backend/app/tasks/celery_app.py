"""Celery app do worker assincrono (notificacoes/outbox).

Broker RabbitMQ e result backend Redis, conforme a infraestrutura ja definida
no docker-compose. O beat agendado despacha a outbox periodicamente.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "forja",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "dispatch-outbox": {
        "task": "app.tasks.notifications.dispatch_outbox",
        "schedule": 10.0,
    },
}

celery_app.autodiscover_tasks(["app.tasks"])
