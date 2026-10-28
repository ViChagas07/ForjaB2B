"""Ponte do output guard de IA para o slot {personal_note} (item 5).

A notification module NAO importa app.modules.ai (contrato de bounded
contexts): quem precisa do guard injeta esta funcao — montada AQUI, na raiz
de composicao (main.py e worker). A funcao devolve a nota sanitizada pelo
output guard da Fase 2 (com scan de injecao) e limite de 200 chars; reprovada
ou vazia, devolve "" (slot omitido).
"""

from __future__ import annotations

from collections.abc import Callable

from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import Locale

PERSONAL_NOTE_MAX_CHARS = 200

SanitizePersonalNote = Callable[[str | None, str | None], str]


def build_personal_note_sanitizer() -> SanitizePersonalNote:
    """Fabrica do sanitizador: (note, locale) -> texto aprovado ou ''."""

    def sanitize(note: str | None, locale: str | None) -> str:
        if note is None or not note.strip():
            return ""
        locale_value = str(locale) if locale else "pt-BR"
        guarded = guard_model_output(
            note.strip(), locale=Locale(locale_value), max_chars=PERSONAL_NOTE_MAX_CHARS
        )
        if guarded.blocked or not guarded.text:
            return ""
        if scan_injection(guarded.text).level.value == "BLOCK":
            return ""
        return guarded.text

    return sanitize
