"""Normalizacao e mascara de telefone E.164 compartilhadas pela conta."""

from __future__ import annotations

import re

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_BR_NATIONAL_RE = re.compile(r"^[1-9][1-9]\d{8,9}$")
_PHONE_ALLOWED_RE = re.compile(r"^\+[0-9()\s.\-]+$")
_NON_DIGITS = re.compile(r"\D")


def normalize_phone_e164(value: str) -> str:
    """Normaliza para E.164; a mesma regra do request de recuperacao.

    Aceita apenas numeros com ``+`` explicito. Brasil (+55) exige DDD 11-99 e
    10/11 digitos nacionais; demais paises seguem E.164 estrito (8 a 15 digitos).
    """
    raw = value.strip()
    if not raw or not _PHONE_ALLOWED_RE.fullmatch(raw):
        raise ValueError("Telefone invalido. Use o formato E.164, por exemplo +5511999999999.")
    digits = _NON_DIGITS.sub("", raw)
    if digits.startswith("55"):
        national = digits[2:]
        if not _BR_NATIONAL_RE.fullmatch(national):
            raise ValueError("Telefone do Brasil invalido. Informe DDD e 10 ou 11 digitos.")
        return f"+55{national}"
    if not _E164_RE.fullmatch(f"+{digits}"):
        raise ValueError("Telefone invalido. Use o formato E.164, por exemplo +14155552671.")
    return f"+{digits}"


def mask_phone_e164(phone: str) -> str:
    """Mascara o telefone preservando DDI e os 4 ultimos digitos."""
    digits = _NON_DIGITS.sub("", phone)
    if len(digits) <= 4:
        return "+" + ("*" * len(digits))
    prefix = digits[:2]
    middle = digits[2:-4]
    last4 = digits[-4:]
    hidden = "*" * 2 + " " + "*" * (len(middle) - 2) if len(middle) >= 2 else "*" * len(middle)
    if not hidden:
        return f"+{prefix}-{last4}"
    return f"+{prefix} {hidden}-{last4}"
