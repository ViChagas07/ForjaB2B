"""Registro de templates por evento (item 4) — dados versionados, render em codigo.

Fonte unica: `data/templates.v1.json` (4 eventos x 11 locales: pt-BR, en,
zh-CN, ja, ko, ru, es, de, fr, it, ar), fallback pt-BR. Nunca ha chave vazia.

- `render_email`: devolve (subject, texto puro, HTML simples e SEGURO —
  valores SEMPRE escapados com `html.escape`; ar recebe `dir="rtl"`).
- `render_text` (WhatsApp): o mesmo texto puro, sem HTML.
- `build_email` (assinatura antiga, so {order_id}) continua funcionando:
  mantida para compatibilidade com os 3 eventos originais.
- `cart_url` (item 6): SEMPRE gerado pelo backend a partir do dominio do
  site em config — nunca vem do LLM.
- `{personal_note}` (item 5): unico slot vindo do LLM; `render_personal_note`
  aplica o output guard da Fase 2 e limite de 200 chars — reprovado, omite.
"""

from __future__ import annotations

import html
import importlib.resources
import json
import re
from functools import lru_cache
from typing import cast

from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import Locale

_TEMPLATES_FILE = "templates.v1.json"
_LOCALES = (
    "pt-BR",
    "en",
    "zh-CN",
    "ja",
    "ko",
    "ru",
    "es",
    "de",
    "fr",
    "it",
    "ar",
)
PERSONAL_NOTE_MAX_CHARS = 200
_RTL_LOCALES = frozenset({"ar"})

_NEWLINES = re.compile(r"\n{3,}")


@lru_cache(maxsize=1)
def _templates() -> dict[str, dict[str, dict[str, str]]]:
    resource = importlib.resources.files("app.modules.notification.domain").joinpath(
        f"data/{_TEMPLATES_FILE}"
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return cast("dict[str, dict[str, dict[str, str]]]", payload["events"])


def template_version() -> int:
    """Versao do arquivo de templates (audit)."""
    resource = importlib.resources.files("app.modules.notification.domain").joinpath(
        f"data/{_TEMPLATES_FILE}"
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return cast("int", payload["version"])


def _normalize_locale(locale: str | None) -> str:
    """Locale suportado mais proximo; fallback pt-BR."""
    if locale is None:
        return "pt-BR"
    if locale in _LOCALES:
        return locale
    prefix = locale.split("-", 1)[0]
    for supported in _LOCALES:
        if supported.split("-", 1)[0] == prefix:
            return supported
    return "pt-BR"


def _template_for(event_type: str, locale: str | None) -> tuple[str, str]:
    events = _templates()
    template = events.get(event_type)
    if template is None:
        return "Notificacao", "{order_id}"  # fallback historico (compat)
    resolved = template.get(_normalize_locale(locale)) or template["pt-BR"]
    return resolved["subject"], resolved["text"]


def locale_key(locale: str | None) -> str:
    """Compat (comportamento antigo): 'en' ou fallback pt-BR."""
    if locale in ("en", "en-US", "en-GB"):
        return "en"
    return "pt-BR"


def _render(template: str, slots: dict[str, str]) -> str:
    rendered = template.format(**slots)
    return _NEWLINES.sub("\n\n", rendered).strip()


def render_email(
    *, event_type: str, locale: str | None, slots: dict[str, str]
) -> tuple[str, str, str]:
    """Devolve (subject, texto puro, HTML simples e seguro com valores escapados)."""
    subject_template, text_template = _template_for(event_type, locale)
    subject = _render(subject_template, slots)
    text = _render(text_template, slots)
    return subject, text, render_html(text, locale=_normalize_locale(locale))


def render_html(text: str, *, locale: str) -> str:
    """HTML minimo e seguro: texto escapado, paragrafos, dir=rtl quando ar."""
    direction = ' dir="rtl"' if locale in _RTL_LOCALES else ""
    paragraphs = "".join(
        f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip()
    )
    return (
        f'<!DOCTYPE html><html lang="{html.escape(locale)}"><head>'
        f'<meta charset="utf-8"></head><body{direction}>{paragraphs}</body></html>'
    )


def render_text(*, event_type: str, locale: str | None, slots: dict[str, str]) -> tuple[str, str]:
    """Devolve (subject, texto puro) — canal WhatsApp (sem HTML)."""
    subject_template, text_template = _template_for(event_type, locale)
    return _render(subject_template, slots), _render(text_template, slots)


def render_personal_note(note: str | None, *, locale: str | None) -> str:
    """Slot {personal_note}: output guard da Fase 2 + 200 chars; reprovado = ''.

    Defesa em profundidade: alem do output guard, a nota tambem passa pelo
    detector de injecao (texto gerado por LLM nao leva jailbreak para o e-mail).
    """
    if note is None or not note.strip():
        return ""
    locale_value = _normalize_locale(locale)
    guarded = guard_model_output(
        note.strip(), locale=Locale(locale_value), max_chars=PERSONAL_NOTE_MAX_CHARS
    )
    if guarded.blocked or not guarded.text:
        return ""
    if scan_injection(guarded.text).level.value == "BLOCK":
        return ""
    return guarded.text


def cart_url(locale: str | None, *, frontend_base_url: str) -> str:
    """Link do carrinho gerado pelo BACKEND (dominio em config; nunca do LLM)."""
    resolved = _normalize_locale(locale)
    base = frontend_base_url.rstrip("/")
    return f"{base}/{resolved}/cart"


def build_email(*, event_type: str, locale: str | None, order_id: str) -> tuple[str, str]:
    """Assinatura antiga (eventos order.created/invoice.issued/payment.confirmed)."""
    subject, text = render_text(event_type=event_type, locale=locale, slots={"order_id": order_id})
    return subject, text
