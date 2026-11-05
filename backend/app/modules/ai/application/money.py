# ruff: noqa: RUF001 - simbolos e nomes de moeda em varios idiomas
"""Leitura de dinheiro, moedas e faixas de preco do chat.

Regras:
- sem simbolo/codigo de moeda, o valor e BRL (moeda do catalogo);
- valores em moeda de exibicao suportada (USD/EUR/GBP/CAD/AUD/JPY/CNY) sao
  convertidos para BRL pelo chamador (nunca tratados como BRL por engano);
- moeda citada fora da lista suportada (ou cambio indisponivel) NAO vira
  filtro: o chamador pede UMA confirmacao objetiva;
- separadores locais ("1.234,56" e "1,234.56"), digitos arabico-indicos e
  faixas ("entre X e Y") sao aceitos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.modules.ai.application.lexicon import (
    NUMBER_WORDS,
    PRICE_MAX_TERMS,
    PRICE_MIN_TERMS,
    PRICE_SORT_ASC,
    PRICE_SORT_DESC,
    matches_any,
    term_present,
)
from app.modules.ai.domain.types import Locale

SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"BRL", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY"}
)

_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬٫",
    "01234567890123456789,.",
)
_AMOUNT = re.compile(
    r"(?<![\w])(\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![\w])"
)

# (regex, codigo, suportado). A ordem e importante: simbolos compostos antes
# do "$" generico; nomes longos antes dos curtos.
_CURRENCY_PATTERNS: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    (re.compile(r"R\$", re.IGNORECASE), "BRL", True),
    (re.compile(r"US\$", re.IGNORECASE), "USD", True),
    (re.compile(r"C\$", re.IGNORECASE), "CAD", True),
    (re.compile(r"A\$", re.IGNORECASE), "AUD", True),
    (re.compile(r"(?<!\w)BRL(?!\w)", re.IGNORECASE), "BRL", True),
    (re.compile(r"(?<!\w)USD(?!\w)", re.IGNORECASE), "USD", True),
    (re.compile(r"(?<!\w)EUR(?!\w)", re.IGNORECASE), "EUR", True),
    (re.compile(r"(?<!\w)GBP(?!\w)", re.IGNORECASE), "GBP", True),
    (re.compile(r"(?<!\w)CAD(?!\w)", re.IGNORECASE), "CAD", True),
    (re.compile(r"(?<!\w)AUD(?!\w)", re.IGNORECASE), "AUD", True),
    (re.compile(r"(?<!\w)JPY(?!\w)", re.IGNORECASE), "JPY", True),
    (re.compile(r"(?<!\w)(?:CNY|RMB)(?!\w)", re.IGNORECASE), "CNY", True),
    (re.compile(r"(?<!\w)CHF(?!\w)", re.IGNORECASE), "CHF", False),
    (re.compile(r"(?<!\w)RUB(?!\w)", re.IGNORECASE), "RUB", False),
    (re.compile(r"(?<!\w)KRW(?!\w)", re.IGNORECASE), "KRW", False),
    (re.compile(r"€"), "EUR", True),
    (re.compile(r"£"), "GBP", True),
    (re.compile(r"[¥￥]"), "JPY", True),
    (re.compile(r"₩"), "KRW", False),
    (re.compile(r"₽"), "RUB", False),
    (re.compile(r"(?<!\w)\$"), "USD", True),
    (re.compile(r"(?<!\w)(?:reais|real)(?!\w)", re.IGNORECASE), "BRL", True),
    (re.compile(r"(?<!\w)(?:d[oó]lares?|dollars?)(?!\w)", re.IGNORECASE), "USD", True),
    (re.compile(r"(?<!\w)euros?(?!\w)", re.IGNORECASE), "EUR", True),
    (re.compile(r"(?<!\w)(?:libras?|pounds?)(?!\w)", re.IGNORECASE), "GBP", True),
    (re.compile(r"(?<!\w)(?:ienes?|yen)(?!\w)", re.IGNORECASE), "JPY", True),
    (re.compile(r"(?<!\w)(?:yuans?|yuan)(?!\w)", re.IGNORECASE), "CNY", True),
    (re.compile(r"(?<!\w)(?:rublos?|руб(?:ль|ля|лей)?)(?!\w)", re.IGNORECASE), "RUB", False),
    (re.compile(r"(?<!\w)(?:wons?|won)(?!\w)", re.IGNORECASE), "KRW", False),
    (re.compile(r"(?<!\w)(?:francos?|francs?)(?!\w)", re.IGNORECASE), "CHF", False),
    (re.compile(r"元|人民币|人民幣"), "CNY", True),
    (re.compile(r"円"), "JPY", True),
    (re.compile(r"원"), "KRW", False),
    (re.compile(r"루블"), "RUB", False),
    (re.compile(r"دولار"), "USD", True),
    (re.compile(r"يورو"), "EUR", True),
    (re.compile(r"جنيه"), "GBP", True),
    (re.compile(r"ين"), "JPY", True),
    (re.compile(r"وون"), "KRW", False),
    (re.compile(r"روبل"), "RUB", False),
    (re.compile(r"فرنك"), "CHF", False),
    (re.compile(r"ريال"), "SAR", False),
)

_RANGE_STRONG: tuple[str, ...] = (
    "entre",
    "between",
    "zwischen",
    "tra",
    "fra",
    "между",
    "بين",
    "から",
    "에서",
    "从",
    "從",
    "到",
)


@dataclass(frozen=True, kw_only=True)
class CurrencyMention:
    code: str
    supported: bool
    raw: str


@dataclass(frozen=True, kw_only=True)
class MoneyAmount:
    value: float
    currency: str | None
    supported: bool
    raw: str
    start: int
    end: int


@dataclass(frozen=True, kw_only=True)
class PriceFilters:
    sort: str | None
    min: float | None
    max: float | None
    currency: str = "BRL"
    needs_confirmation: bool = False
    mentions: tuple[CurrencyMention, ...] = ()


def normalize_digits(text: str) -> str:
    """Converte digitos arabico-indicos e separadores arabes para ASCII."""
    return text.translate(_DIGITS)


def detect_currency_mentions(text: str) -> tuple[CurrencyMention, ...]:
    """Moedas citadas, na ordem de aparicao (sem duplicar o mesmo codigo)."""
    normalized = normalize_digits(text)
    found: list[tuple[int, CurrencyMention]] = []
    seen: set[str] = set()
    for pattern, code, supported in _CURRENCY_PATTERNS:
        for match in pattern.finditer(normalized):
            if code in seen:
                continue
            seen.add(code)
            found.append(
                (
                    match.start(),
                    CurrencyMention(code=code, supported=supported, raw=match.group(0)),
                )
            )
    found.sort(key=lambda item: item[0])
    return tuple(mention for _position, mention in found)


def detect_currency(text: str) -> str | None:
    """Primeira moeda citada (None = sem simbolo/codigo; assumir BRL)."""
    mentions = detect_currency_mentions(text)
    return mentions[0].code if mentions else None


def extract_money_amounts(text: str) -> tuple[MoneyAmount, ...]:
    """Valores monetarios com a moeda mais proxima (ou None)."""
    normalized = normalize_digits(text)
    mentions = detect_currency_mentions(normalized)
    amounts: list[MoneyAmount] = []
    for match in _AMOUNT.finditer(normalized):
        value = parse_amount(match.group(1))
        if value is None:
            continue
        nearest = _nearest_mention(mentions, position=match.start(), text=normalized)
        amounts.append(
            MoneyAmount(
                value=value,
                currency=nearest.code if nearest else None,
                supported=nearest.supported if nearest else True,
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )
    return tuple(amounts)


def parse_amount(raw: str) -> float | None:
    """Interpreta 1.234,56 / 1,234.56 / 1 234,56 / 1234.56."""
    value = normalize_digits(raw).strip().replace("\u00a0", " ").replace(" ", "")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif "." in value and value.count(".") == 1 and len(value.split(".")[-1]) <= 2:
        pass
    elif "." in value:
        value = value.replace(".", "")
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


_POSTFIX_MAX = frozenset({"以下", "以内", "이하", "미만"})
_POSTFIX_MIN = frozenset({"以上", "이상", "초과"})


def _extract_before_amount(message: str, terms: frozenset[str]) -> float | None:
    for term in terms:
        index = _term_index(message, term)
        if index is None:
            continue
        amounts = extract_money_amounts(message[max(0, index - 40) : index])
        if amounts:
            return amounts[-1].value
    return None


def _extract_before_number_word(message: str, terms: frozenset[str]) -> float | None:
    for term in terms:
        index = _term_index(message, term)
        if index is None:
            continue
        values = _number_word_values(message[max(0, index - 40) : index])
        if values:
            return float(_compose_numbers(values))
    return None


def _extract_number_word_after(message: str, terms: tuple[str, ...]) -> float | None:
    for term in terms:
        index = _term_index(message, term)
        if index is None:
            continue
        tail = message[index + len(term) : index + len(term) + 50]
        values = _number_word_values(tail)
        if values:
            return float(_compose_numbers(values))
    return None


def _number_word_values(text: str) -> list[int]:
    """Valores de numeros por extenso na ordem do texto, sem sobreposicao."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    matches: list[tuple[int, int, int]] = []
    for word, value in sorted(NUMBER_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        if word.isascii():
            for match in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", normalized):
                matches.append((match.start(), match.end(), value))
        else:
            start = normalized.find(word)
            while start >= 0:
                matches.append((start, start + len(word), value))
                start = normalized.find(word, start + len(word))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    deduped: list[tuple[int, int, int]] = []
    for start, end, value in matches:
        if any(s <= start and end <= e for s, e, _ in deduped):
            continue
        deduped.append((start, end, value))
    deduped.sort(key=lambda item: item[0])
    return [value for _start, _end, value in deduped]


def _compose_numbers(values: list[int]) -> int:
    total = 0
    for value in values:
        if value in (100, 1000) and 0 < total < 100:
            total *= value
        else:
            total += value
    return total


_PRICE_QUESTION = re.compile(
    r"(?i)\b(?:quanto\s+custa|qual\s+o\s+pre[cç]o|pre[cç]o|price|cost|"
    r"cu[aá]nto\s+cuesta|precio|was\s+kostet|preis|combien|prix|"
    r"quanto\s+costa|prezzo|сколько\s+стоит|цена|كم\s+سعر|سعر)\b"
    r"|多少钱|多少錢|价格|價格|いくら|価格|얼마|가격"
)


def has_price_context(text: str) -> bool:
    """True quando ha valor + marcador de preco/faixa/moeda na mensagem.

    Usado para NAO aceitar `price_min`/`price_max`/`price_currency_confirmation`
    inventados pelo roteador LLM quando a mensagem nao tem nenhum preco. Um
    numero solto (ex.: "3 luvas") nao e preco.
    """
    has_amount = bool(extract_money_amounts(text)) or bool(_number_word_values(text))
    if not has_amount:
        return False
    if detect_currency_mentions(text) or _range_requested(text):
        return True
    if any(term_present(text, term) for term in _flatten(PRICE_MAX_TERMS)):
        return True
    if any(term_present(text, term) for term in _flatten(PRICE_MIN_TERMS)):
        return True
    return bool(_PRICE_QUESTION.search(text))


def extract_price_filters(message: str) -> PriceFilters:
    """Ordenacao, faixa e moeda citadas; nunca aplica moeda estrangeira como BRL."""
    sort: str | None = None
    if matches_any(message, _flatten(PRICE_SORT_ASC)):
        sort = "asc"
    elif matches_any(message, _flatten(PRICE_SORT_DESC)):
        sort = "desc"

    amounts = extract_money_amounts(message)
    price_min, price_max = _extract_range(message, amounts)
    if price_min is not None and price_max is not None and price_min > price_max:
        price_min, price_max = price_max, price_min

    mentions = detect_currency_mentions(message)
    currency, needs_confirmation = _resolve_currency(mentions)
    return PriceFilters(
        sort=sort,
        min=price_min,
        max=price_max,
        currency=currency,
        needs_confirmation=needs_confirmation,
        mentions=mentions,
    )


def _extract_range(
    message: str, amounts: tuple[MoneyAmount, ...]
) -> tuple[float | None, float | None]:
    price_min = _extract_after(message, _flatten(PRICE_MIN_TERMS))
    price_max = _extract_after(message, _flatten(PRICE_MAX_TERMS))
    if price_min is None:
        price_min = _extract_number_word_after(message, _flatten(PRICE_MIN_TERMS))
    if price_max is None:
        price_max = _extract_number_word_after(message, _flatten(PRICE_MAX_TERMS))
    if price_min is None:
        price_min = _extract_before_number_word(message, _POSTFIX_MIN) or _extract_before_amount(
            message, _POSTFIX_MIN
        )
    if price_max is None:
        price_max = _extract_before_number_word(message, _POSTFIX_MAX) or _extract_before_amount(
            message, _POSTFIX_MAX
        )
    if not _range_requested(message):
        return price_min, price_max
    if len(amounts) >= 2:
        return min(amounts[0].value, amounts[1].value), max(amounts[0].value, amounts[1].value)
    words = _number_word_values(message)
    if len(words) >= 2:
        return float(min(words[0], words[1])), float(max(words[0], words[1]))
    return price_min, price_max


def strip_money_from_query(message: str) -> str:
    """Remove valores, moedas e marcadores de faixa para a consulta de produto."""
    normalized = normalize_digits(message)
    cleaned = _AMOUNT.sub(" ", normalized)
    for pattern, _code, _supported in _CURRENCY_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    for term in (*_flatten(PRICE_MAX_TERMS), *_flatten(PRICE_MIN_TERMS)):
        cleaned = _remove_term(cleaned, term)
    for term in _RANGE_STRONG:
        cleaned = _remove_term(cleaned, term)
    return re.sub(r"\s+", " ", cleaned).strip(" .,!?;:-")


def _resolve_currency(mentions: tuple[CurrencyMention, ...]) -> tuple[str, bool]:
    if not mentions:
        return "BRL", False
    codes = {mention.code for mention in mentions}
    if len(codes) != 1:
        return "BRL", True
    mention = mentions[0]
    if not mention.supported:
        return mention.code, True
    return mention.code, False


def _nearest_mention(
    mentions: tuple[CurrencyMention, ...], *, position: int, text: str
) -> CurrencyMention | None:
    if not mentions:
        return None
    best: tuple[int, CurrencyMention] | None = None
    for mention in mentions:
        index = text.find(mention.raw)
        if index < 0:
            continue
        distance = position - index
        if distance < -20 or distance > 40:
            continue
        score = abs(position - index)
        if best is None or score < best[0]:
            best = (score, mention)
    return best[1] if best else mentions[0]


def _extract_after(message: str, terms: tuple[str, ...]) -> float | None:
    normalized = normalize_digits(message)
    for term in terms:
        index = _term_index(normalized, term)
        if index is None:
            continue
        tail = normalized[index + len(term) : index + len(term) + 45]
        amounts = extract_money_amounts(tail)
        if amounts:
            return amounts[0].value
    return None


def _range_requested(message: str) -> bool:
    return any(term_present(message, term) for term in _RANGE_STRONG)


def _flatten(table: dict[Locale, tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(term for terms in table.values() for term in terms))


def _term_index(text: str, term: str) -> int | None:
    if term.isascii():
        match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE)
        return match.start() if match else None
    index = text.casefold().find(term.casefold())
    return index if index >= 0 else None


def _remove_term(text: str, term: str) -> str:
    if term.isascii():
        return re.sub(rf"(?<!\w){re.escape(term)}(?!\w)", " ", text, flags=re.IGNORECASE)
    return re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
