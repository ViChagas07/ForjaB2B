"""Bases neutras de entidade e agregado.

Identidade por UUID e coleta de eventos de dominio no agregado. Nenhuma
dependencia de ORM: o mapeamento ORM <-> dominio vive na infraestrutura.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.events import DomainEvent


@dataclass(kw_only=True)
class Entity:
    """Entidade com identidade unica."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(kw_only=True)
class AggregateRoot(Entity):
    """Raiz de agregado que acumula eventos de dominio ate a persistencia."""

    _domain_events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def register_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Drena e devolve os eventos acumulados (usado pela infraestrutura)."""
        events = list(self._domain_events)
        self._domain_events.clear()
        return events
