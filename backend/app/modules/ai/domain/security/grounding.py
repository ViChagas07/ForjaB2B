"""Validacao numerica da resposta ancorada no CONTEXTO (anti-alucinacao).

O LLM pode citar precos quando o usuario tem permissao e o CONTEXTO tem o
preco resolvido pelo backend. Cada valor monetario da resposta precisa bater
com um preco do contexto; qualquer numero inventado reprova e a resposta cai
no fallback seguro (os cartoes continuam com o preco correto).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

_MONEY = re.compile(
    r"(?i)(?:R\$|US\$|\$|€|£)\s*(?:\d[\d.,]*\d|\d)"
    r"|\b\d[\d.,]*\s*(?:reais|brl)\b"
)


def prices_are_grounded(text: str, allowed: Iterable[Decimal]) -> bool:
    """True se todo valor monetario citado existe no conjunto do contexto."""
    allowed_set = {Decimal(str(value)).quantize(Decimal("0.01")) for value in allowed}
    for raw in _MONEY.findall(text):
        candidates = _parse_candidates(raw)
        if not candidates:
            return False
        normalized = {value.quantize(Decimal("0.01")) for value in candidates}
        if not normalized & allowed_set:
            return False
    return True


def _parse_candidates(raw: str) -> set[Decimal]:
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
