"""Schemas HTTP do contexto de notificacao."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """Visao publica de uma notificacao (outbox)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    company_id: uuid.UUID
    event_type: str
    aggregate_id: uuid.UUID
    status: str
    attempts: int
    error: str | None = None
    created_at: datetime
