"""Eventos de dominio (base neutra).

Eventos sao imutaveis e carregam apenas dados de dominio. A publicacao
acontece via outbox (fases posteriores); aqui fica apenas o tipo base.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base imutavel para eventos de dominio."""

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
