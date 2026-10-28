"""Auditoria do chat em agent_audit_log (FASE 5c) — sem PII.

Payload SEMPRE via `build_audit_payload` (hash sha256 + tamanho + prefixo
sanitizado de 80 chars). Nunca grava texto completo do usuario, resposta do
assistente, saida de ferramenta ou system prompt.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.domain.audit_payload import build_audit_payload

_INSERT_AUDIT = text(
    "INSERT INTO agent_audit_log (agent, event, company_id, verdict, reason_code, payload) "
    "VALUES ('chat', :event, :company_id, :verdict, :reason_code, CAST(:payload AS jsonb))"
)


class SqlAlchemyChatAudit:
    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def record(
        self,
        *,
        company_id: uuid.UUID | None,
        event: str,
        verdict: str,
        reason_code: str,
        text: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = dict(extra or {})
        if text is not None:
            payload["message"] = build_audit_payload(text)
        # RLS: evento de tenant exige o contexto da empresa; visitante (None)
        # grava com company_id NULL (policy de INSERT permite) — sem GUC.
        tenant = TenantContext(company_id=company_id) if company_id is not None else None
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "event": event,
                    "company_id": company_id,
                    "verdict": verdict,
                    "reason_code": reason_code,
                    "payload": json.dumps(payload),
                },
            )
            await uow.commit()
