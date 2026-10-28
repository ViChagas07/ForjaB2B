"""Sanitizador de documentos de catalogo para o contexto do LLM (item F.11).

ALLOWLIST de campos (id, name, sku, brand, category, atributos curtos e,
opcionalmente, descricao truncada em 300 chars): nada de preco, texto de
usuario (avaliacoes), URL ou HTML chega ao modelo. Cada valor e sanitizado
(sem HTML/URL/largura-zero, espacos colapsados) e truncado. Documento cujo
texto bate nos padroes de injecao vai para QUARENTENA: omitido do contexto
do LLM (F.12 — continua no catalogo normal) e marcado para audit com o
product_id, sem exposicao ao usuario. O hash do conteudo enviado ao modelo
e devolvido para auditoria.

Funcoes puras: sem I/O, sem LLM.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.normalize import normalize_user_text

DEFAULT_CONTEXT_FIELDS = ("id", "name", "sku", "brand", "category", "attributes")

_FIELD_LIMITS = {"id": 64, "name": 120, "sku": 40, "brand": 80, "category": 80, "description": 300}
_ATTRIBUTE_LIMITS = {"count": 8, "key": 40, "value": 60}

_HTML_TAG = re.compile(r"<[^<>\n]{0,200}>")
_URL = re.compile(r"(?i)(?:https?://|www\.)\S{0,300}|[a-z][a-z0-9+.-]*://\S{0,300}")


@dataclass(frozen=True, kw_only=True)
class CatalogSanitizeResult:
    """Documento prontos para o contexto, ou em quarentena."""

    context_text: str | None  # None = omitir do contexto do LLM
    content_hash: str  # sha256 do conteudo (enviado ou quarentenado, p/ audit)
    quarantined: bool
    reason_code: str | None = None


def sanitize_catalog_document(
    doc: Mapping[str, object],
    *,
    include_description: bool = False,
) -> CatalogSanitizeResult:
    """Sanitiza um produto para o contexto; quarentena se parecer injecao."""
    parts: list[str] = []
    for field_name in DEFAULT_CONTEXT_FIELDS:
        if field_name == "attributes":
            parts.extend(_attribute_lines(doc.get("attributes")))
            continue
        if field_name == "description" and not include_description:
            continue
        value = doc.get(field_name)
        if value is None:
            continue
        limit = _FIELD_LIMITS[field_name]
        parts.append(f"{field_name}={_clean(str(value), limit)}")
    description = doc.get("description")
    if include_description and description is not None:
        parts.append(f"description={_clean(str(description), _FIELD_LIMITS['description'])}")

    context = "\n".join(part for part in parts if part)
    content_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()

    verdict = scan_injection(context)
    if verdict.level.value == "BLOCK":
        return CatalogSanitizeResult(
            context_text=None,
            content_hash=content_hash,
            quarantined=True,
            reason_code=verdict.reason_code,
        )
    return CatalogSanitizeResult(context_text=context, content_hash=content_hash, quarantined=False)


def _clean(value: str, limit: int) -> str:
    without_html = _HTML_TAG.sub(" ", value)
    without_url = _URL.sub(" ", without_html)
    normalized = normalize_user_text(without_url, max_chars=limit)
    return normalized.text.strip()


def _attribute_lines(attributes: object) -> list[str]:
    if not isinstance(attributes, Mapping):
        return []
    lines: list[str] = []
    for raw_key, raw_value in list(attributes.items())[: _ATTRIBUTE_LIMITS["count"]]:
        key = _clean(str(raw_key), _ATTRIBUTE_LIMITS["key"])
        value = _clean(str(raw_value), _ATTRIBUTE_LIMITS["value"])
        if key and value:
            lines.append(f"attr {key}={value}")
    return lines
