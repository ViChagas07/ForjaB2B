"""Construcao do payload de auditoria de agentes (privacidade por construcao).

O `agent_audit_log` NUNCA guarda o texto completo do usuario nem PII: o
payload carrega apenas

- `text_sha256`: hash sha256 do texto original (correlacao sem exposicao);
- `text_chars`: tamanho do texto original em caracteres;
- `text_prefix`: primeiros 80 caracteres SANITIZADOS (controles/novas
  linhas viram espaco, espacos colapsados) — util para diagnosticar o tipo
  de conteudo sem transportar o texto inteiro.

Funcao pura: sem I/O e sem framework. A regra e estrutural: o texto inteiro
NUNCA entra no payload, so o prefixo limitado e sanitizado.
"""

from __future__ import annotations

import hashlib

AUDIT_TEXT_PREFIX_CHARS = 80


def sanitize_prefix(text: str, *, limit: int = AUDIT_TEXT_PREFIX_CHARS) -> str:
    """Primeiros `limit` caracteres, sem controles e com espacos colapsados."""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in text)
    return " ".join(cleaned.split())[:limit]


def build_audit_payload(text: str) -> dict[str, object]:
    """Payload seguro para `agent_audit_log.payload` (sem PII/texto inteiro)."""
    return {
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_chars": len(text),
        "text_prefix": sanitize_prefix(text),
    }
