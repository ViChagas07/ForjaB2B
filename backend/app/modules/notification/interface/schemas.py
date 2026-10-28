"""Schemas HTTP do contexto de notificacao."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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


class WhatsAppOptInRequest(BaseModel):
    """Opt-in/opt-out do canal WhatsApp (usuario autenticado; E.164)."""

    model_config = ConfigDict(extra="forbid")

    opt_in: bool
    whatsapp_phone: str | None = None

    @field_validator("whatsapp_phone")
    @classmethod
    def _e164_when_opt_in(cls, phone: str | None, info: object) -> str | None:
        # Regra de negocio em CODIGO: opt-in exige numero E.164; opt-out limpa.
        if info is not None and getattr(info, "data", {}).get("opt_in"):
            digits = (phone or "").strip()
            if (
                not digits.startswith("+")
                or not digits[1:].isdigit()
                or not 8 <= len(digits) - 1 <= 14
            ):
                raise ValueError("whatsapp_phone deve estar em E.164 (ex.: +5511998765432)")
            return digits
        return None


class WhatsAppOptInResponse(BaseModel):
    """Estado do opt-in WhatsApp apos atualizacao."""

    model_config = ConfigDict(extra="forbid")

    opt_in: bool
    whatsapp_phone: str | None = None
