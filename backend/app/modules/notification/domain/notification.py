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
- `{personal_note}` (item 5): unico slot possivelmente vindo do LLM. Este
  modulo NAO importa app.modules.ai (contrato de bounded contexts): o
  CHAMADOR injeta o sanitizador (output guard da Fase 2, limite 200 chars;
  reprovado = slot omitido) via `render_personal_note(..., sanitizer=...)`.
  Sem sanitizador injetado, fallback deterministico: normalizacao basica e
  truncamento em 200 chars.
"""

from __future__ import annotations

import html
import importlib.resources
import json
import re
import unicodedata
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import cast

PersonalNoteSanitizer = Callable[[str | None, str | None], str]

PERSONAL_NOTE_MAX_CHARS = 200

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
    resolved = _normalize_locale(locale)
    direction = ' dir="rtl"' if resolved in _RTL_LOCALES else ""
    paragraphs = "".join(
        f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip()
    )
    return (
        f'<!DOCTYPE html><html lang="{html.escape(resolved)}"><head>'
        f'<meta charset="utf-8"></head><body{direction}>{paragraphs}</body></html>'
    )


def render_text(*, event_type: str, locale: str | None, slots: dict[str, str]) -> tuple[str, str]:
    """Devolve (subject, texto puro) — canal WhatsApp (sem HTML)."""
    subject_template, text_template = _template_for(event_type, locale)
    return _render(subject_template, slots), _render(text_template, slots)


_SUMMARY_LABELS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "subtotal": "Subtotal",
        "recovery": "Oferta de recuperação",
        "coupon": "Cupom",
        "shipping": "Frete",
        "shipping_discount": "Desconto no frete",
        "total": "Total",
        "free": "Grátis",
    },
    "en": {
        "subtotal": "Subtotal",
        "recovery": "Recovery offer",
        "coupon": "Coupon",
        "shipping": "Shipping",
        "shipping_discount": "Shipping discount",
        "total": "Total",
        "free": "Free",
    },
    "es": {
        "subtotal": "Subtotal",
        "recovery": "Oferta de recuperación",
        "coupon": "Cupón",
        "shipping": "Envío",
        "shipping_discount": "Descuento en el envío",
        "total": "Total",
        "free": "Gratis",
    },
    "fr": {
        "subtotal": "Sous-total",
        "recovery": "Offre de récupération",
        "coupon": "Code promo",
        "shipping": "Livraison",
        "shipping_discount": "Remise sur la livraison",
        "total": "Total",
        "free": "Gratuit",
    },
    "de": {
        "subtotal": "Zwischensumme",
        "recovery": "Rückgewinnungsangebot",
        "coupon": "Gutschein",
        "shipping": "Versand",
        "shipping_discount": "Versandrabatt",
        "total": "Gesamt",
        "free": "Kostenlos",
    },
    "it": {
        "subtotal": "Subtotale",
        "recovery": "Offerta di recupero",
        "coupon": "Coupon",
        "shipping": "Spedizione",
        "shipping_discount": "Sconto sulla spedizione",
        "total": "Totale",
        "free": "Gratis",
    },
    "ar": {
        "subtotal": "المجموع الفرعي",
        "recovery": "عرض استعادة",
        "coupon": "القسيمة",
        "shipping": "الشحن",
        "shipping_discount": "خصم الشحن",
        "total": "الإجمالي",
        "free": "مجاني",
    },
    "ja": {
        "subtotal": "小計",
        "recovery": "復帰オファー",
        "coupon": "クーポン",
        "shipping": "配送",
        "shipping_discount": "配送割引",
        "total": "合計",
        "free": "無料",
    },
    "ko": {
        "subtotal": "소계",
        "recovery": "복구 혜택",
        "coupon": "쿠폰",
        "shipping": "배송",
        "shipping_discount": "배송 할인",
        "total": "합계",
        "free": "무료",
    },
    "ru": {
        "subtotal": "Промежуточный итог",
        "recovery": "Предложение по возврату",
        "coupon": "Купон",
        "shipping": "Доставка",
        "shipping_discount": "Скидка на доставку",
        "total": "Итого",
        "free": "Бесплатно",
    },
    "zh-CN": {
        "subtotal": "小计",
        "recovery": "挽回优惠",
        "coupon": "优惠券",
        "shipping": "运费",
        "shipping_discount": "运费折扣",
        "total": "合计",
        "free": "免费",
    },
}


def _payload_decimal(payload: dict[str, object], key: str) -> Decimal | None:
    raw = payload.get(key)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _format_money(value: Decimal, currency: str) -> str:
    return f"{currency} {value:.2f}"


def render_order_summary(payload: dict[str, object], locale: str | None) -> str:
    """Resumo de valores do pedido para a notificacao de confirmacao.

    Os valores vem do payload gravado na outbox pelo backend; nenhum valor e
    recalculado aqui (o frete bruto e derivado apenas para exibicao do
    desconto, pois o pedido guarda o frete liquido). Retorna "" para payloads
    antigos sem subtotal/total.
    """
    subtotal = _payload_decimal(payload, "subtotal")
    total = _payload_decimal(payload, "total")
    if subtotal is None or total is None:
        return ""
    labels = _SUMMARY_LABELS[_normalize_locale(locale)]
    currency = str(payload.get("currency") or "BRL")
    recovery = _payload_decimal(payload, "discount_total") or Decimal("0.00")
    coupon_code = str(payload.get("coupon_code") or "")
    coupon_discount = _payload_decimal(payload, "coupon_discount_amount") or Decimal("0.00")
    shipping_total = _payload_decimal(payload, "shipping_total") or Decimal("0.00")
    shipping_discount = _payload_decimal(payload, "shipping_discount_amount") or Decimal("0.00")

    lines = [f"{labels['subtotal']}: {_format_money(subtotal, currency)}"]
    if recovery > 0:
        lines.append(f"{labels['recovery']}: -{_format_money(recovery, currency)}")
    if coupon_code and coupon_discount > 0:
        lines.append(
            f"{labels['coupon']} ({coupon_code}): -{_format_money(coupon_discount, currency)}"
        )
    if shipping_discount > 0:
        gross_shipping = shipping_total + shipping_discount
        lines.append(f"{labels['shipping']}: {_format_money(gross_shipping, currency)}")
        discount_label = labels["shipping_discount"]
        if coupon_code:
            discount_label = f"{discount_label} ({coupon_code})"
        lines.append(f"{discount_label}: -{_format_money(shipping_discount, currency)}")
    elif shipping_total == 0:
        lines.append(f"{labels['shipping']}: {labels['free']}")
    else:
        lines.append(f"{labels['shipping']}: {_format_money(shipping_total, currency)}")
    lines.append(f"{labels['total']}: {_format_money(total, currency)}")
    return "\n".join(lines)


def render_personal_note(
    note: str | None,
    *,
    locale: str | None,
    sanitizer: PersonalNoteSanitizer | None = None,
) -> str:
    """Slot {personal_note}: sanitizador injetado (IA) ou fallback deterministico.

    Com sanitizador (raiz de composicao injeta o output guard da Fase 2 +
    scan de injecao): texto aprovado ou "" (reprovado/vazio omite o slot).
    Sem sanitizador: apenas normalizacao basica e truncamento em 200 chars —
    nunca estoura o limite.
    """
    if sanitizer is not None:
        return sanitizer(note, locale)
    if note is None or not note.strip():
        return ""
    normalized = unicodedata.normalize("NFKC", note.strip())
    collapsed = " ".join(normalized.split())
    return collapsed[:PERSONAL_NOTE_MAX_CHARS]


def cart_url(locale: str | None, *, frontend_base_url: str) -> str:
    """Link do carrinho gerado pelo BACKEND (dominio em config; nunca do LLM)."""
    resolved = _normalize_locale(locale)
    base = frontend_base_url.rstrip("/")
    return f"{base}/{resolved}/cart"


def build_email(*, event_type: str, locale: str | None, order_id: str) -> tuple[str, str]:
    """Assinatura antiga (eventos order.created/invoice.issued/payment.confirmed)."""
    subject, text = render_text(event_type=event_type, locale=locale, slots={"order_id": order_id})
    return subject, text
