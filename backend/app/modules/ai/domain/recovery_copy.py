"""Validacao do texto persuasivo do e-mail de recuperacao (dominio PURO).

O codigo calcula subtotal, frete, percentual (3%) e valor do desconto. O LLM
so escreve o paragrafo. Antes de aceitar o texto, cada valor/percentual
citado e comparado com os fatos calculados; URL, HTML, e-mail, telefone e
promessas de beneficio nao concedido reprovam. Reprovou/indisponivel => o
e-mail sai com o TEMPLATE fixo traduzido (sem IA), nunca sem e-mail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.modules.ai.domain.recovery import RecoveryAction, RecoveryFacts

_HTML = re.compile(r"(?i)<\s*(script|iframe|object|embed|link|meta|form)\b|<[^<>\n]{1,200}>")
_URL = re.compile(r"(?i)(?:https?://|www\.)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b\+?\d{1,3}?\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}\b")
_MONEY = re.compile(r"(?i)(?:R\$|US\$|\$|€|£)\s*\d[\d.,]*|\b\d[\d.,]*\s*(?:reais|brl)\b")
_PERCENT = re.compile(
    r"(?i)(\d+(?:[.,]\d+)?)\s*(?:%|por\s+cento|per\s+cent|percent|prozent|pour\s+cent)"
)
_FREE_SHIPPING_CLAIM = re.compile(
    r"(?i)gr[áa]tis|\bgratis\b|free\s+shipping|livraison\s+offerte|"
    r"kostenloser\s+versand|spedizione\s+gratuita|送料無料|무료\s*배송|"
    r"бесплатн\w*\s+доставк\w*|免运费|شحن\s+مجاني"
)

MAX_COPY_CHARS = 600
_NO_FREE_SHIPPING_ACTIONS = frozenset(
    {
        RecoveryAction.REMIND,
        RecoveryAction.DISCOUNT_3PCT,
        RecoveryAction.ESCALATE_HUMAN,
    }
)


@dataclass(frozen=True, kw_only=True)
class CopyValidation:
    ok: bool
    reason_code: str | None = None


def validate_recovery_copy(
    text: str,
    *,
    facts: RecoveryFacts,
    max_chars: int = MAX_COPY_CHARS,
) -> CopyValidation:
    """Aprova o texto somente se todos os numeros baterem com os do codigo."""
    cleaned = text.strip()
    basic_reason = _basic_reason(cleaned, facts=facts, max_chars=max_chars)
    if basic_reason is not None:
        return CopyValidation(ok=False, reason_code=basic_reason)
    if _has_mismatched_amount(cleaned, facts):
        return CopyValidation(ok=False, reason_code="copy_amount_mismatch")
    if _has_mismatched_percent(cleaned, facts):
        return CopyValidation(ok=False, reason_code="copy_percent_mismatch")
    return CopyValidation(ok=True)


def _basic_reason(text: str, *, facts: RecoveryFacts, max_chars: int) -> str | None:
    if not text:
        return "copy_empty"
    if len(text) > max_chars:
        return "copy_too_long"
    if _HTML.search(text):
        return "copy_html"
    if _URL.search(text):
        return "copy_url"
    if _EMAIL.search(text) or _PHONE.search(text):
        return "copy_pii"
    if facts.action in _NO_FREE_SHIPPING_ACTIONS and _FREE_SHIPPING_CLAIM.search(text):
        return "copy_false_free_shipping"
    return None


def _has_mismatched_amount(text: str, facts: RecoveryFacts) -> bool:
    allowed = _allowed_amounts(facts)
    return any(not _matches_any(raw, allowed) for raw in _MONEY.findall(text))


def _has_mismatched_percent(text: str, facts: RecoveryFacts) -> bool:
    allowed = {facts.discount_percent} if facts.discount_percent is not None else set()
    return any(not _matches_any(raw, allowed) for raw in _PERCENT.findall(text))


def _allowed_amounts(facts: RecoveryFacts) -> set[Decimal]:
    values = [facts.subtotal, facts.shipping_total, facts.free_shipping_min]
    if facts.discount_amount is not None:
        values.append(facts.discount_amount)
    return set(values)


def _matches_any(raw: str, allowed: set[Decimal]) -> bool:
    if not allowed:
        return False
    return bool(_parse_candidates(raw) & allowed)


def _parse_candidates(raw: str) -> set[Decimal]:
    """Interpreta separadores pt-BR/en-US sem escolher um unico formato.

    Devolve TODAS as leituras plausiveis; o texto e aceito se qualquer uma
    bater com um valor calculado (evita falso negativo em "1.600,00").
    """
    number = re.sub(r"[^\d.,]", "", raw)
    if not number:
        return set()
    candidates: list[Decimal | None] = []
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            candidates.append(_to_decimal(number.replace(".", "").replace(",", ".")))
        else:
            candidates.append(_to_decimal(number.replace(",", "")))
    elif "," in number:
        candidates.append(_to_decimal(number.replace(".", "").replace(",", ".")))
    elif "." in number:
        candidates.append(_to_decimal(number))
        candidates.append(_to_decimal(number.replace(".", "")))
    else:
        candidates.append(_to_decimal(number))
    return {value for value in candidates if value is not None}


def _to_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None
