"""Normalizacao de texto de usuario e deteccao de conteudo codificado.

Toda mensagem passa por aqui ANTES de qualquer checagem (item A.1 do
pipeline de seguranca): Unicode NFKC, remocao de largura-zero/controles,
colapso de espacos e limite de tamanho. Apos normalizar, `detect_encoding_flags`
MARCA texto codificado (base64/hex/rot13 longos, homoglifos, letra a letra)
— a marcacao alimenta o veredito ALLOW/SANITIZE/BLOCK do gate de entrada.
`decode_hidden_candidates` devolve decodificacoes plausiveis para o detector
de injecao re-escanear (conteudo codificado que carrega jailbreak = BLOCK).

Funcoes puras: sem I/O, sem framework, sem LLM.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
import unicodedata
from dataclasses import dataclass

# Largura zero e variantes invisiveis usadas para esconder tokens/palavras.
_ZERO_WIDTH = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\ufeff",
)

_HEX_RUN = re.compile(r"\b[0-9a-fA-F]{32,}\b")
# Runs de base64 com "=" em qualquer posicao (payloads concatenados): o texto
# e procurado SEM "=" para nao quebrar o run; a decodificacao repõe o padding.
_B64_RUN = re.compile(r"[A-Za-z0-9+/]{40,}")
_ALPHA_RUN = re.compile(r"\b[A-Za-z]{40,}\b")
# Letra a letra: >= 7 grupos de "uma letra + separador" (i g n o r e  a s ...)
_SPACED = re.compile(r"(?:[^\w]{0,3}\b\w\b[^\w]{0,3}\s?){6,}", re.UNICODE)
# Homoglifo: cirillico/grego escondido em texto latino-dominante.
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_GREEK = re.compile(r"[\u0370-\u03ff]")
_LATIN = re.compile(r"[A-Za-z]")

_ROT13_SUSPICIOUS = re.compile(r"system|prompt|ignore|instru|regra|rule|secret", re.IGNORECASE)

_PRINTABLE_RATIO = 0.9


@dataclass(frozen=True, kw_only=True)
class NormalizedText:
    """Texto normalizado + marcadores de codificacao detectados."""

    text: str
    truncated: bool
    encoding_flags: frozenset[str]


def normalize_user_text(text: str, *, max_chars: int) -> NormalizedText:
    """Normaliza mensagem do usuario (NFKC, sem controles, colapsada, limitada)."""
    normalized = unicodedata.normalize("NFKC", text)
    without_invisible = "".join(
        " " if (ch in _ZERO_WIDTH or unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co")) else ch
        for ch in normalized
    )
    collapsed = " ".join(without_invisible.split())
    truncated = len(collapsed) > max_chars
    trimmed = collapsed[:max_chars]
    return NormalizedText(
        text=trimmed,
        truncated=truncated,
        encoding_flags=detect_encoding_flags(trimmed),
    )


def detect_encoding_flags(text: str) -> frozenset[str]:
    """Marca conteudo codificado/escondido (sinais, nao vereditos)."""
    flags: set[str] = set()
    no_padding = text.replace("=", "")
    if _HEX_RUN.search(text):
        flags.add("hex")
    if any(_decodable_base64(match.group(0)) for match in _B64_RUN.finditer(no_padding)):
        flags.add("base64")
    if _decodable_rot13(text) is not None:
        flags.add("rot13")
    if _SPACED.search(text):
        flags.add("letter_spaced")
    if _has_homoglyph(text):
        flags.add("homoglyph")
    return frozenset(flags)


def decode_hidden_candidates(text: str) -> tuple[str, ...]:
    """Decodificacoes plausiveis (base64/hex/rot13) para re-escanear injecao."""
    decoded: list[str] = []
    no_padding = text.replace("=", "")
    for match in _B64_RUN.finditer(no_padding):
        value = _decodable_base64(match.group(0))
        if value is not None:
            decoded.append(value)
    for match in _HEX_RUN.finditer(text):
        value = _decodable_hex(match.group(0))
        if value is not None:
            decoded.append(value)
    for match in _ALPHA_RUN.finditer(text):
        rot13 = codecs.decode(match.group(0), "rot13")
        if _ROT13_SUSPICIOUS.search(rot13):
            decoded.append(rot13)
    whole_rot13 = _decodable_rot13(text)
    if whole_rot13 is not None:
        decoded.append(whole_rot13)
    return tuple(decoded)


def _decodable_rot13(text: str) -> str | None:
    """Rot13 do texto inteiro quando contem palavra suspeita decodificada."""
    rot13 = codecs.decode(text, "rot13")
    if _ROT13_SUSPICIOUS.search(rot13):
        return rot13
    return None


def _decodable_base64(run: str) -> str | None:
    padded = run + "=" * (-len(run) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not value:
        return None
    printable = sum(1 for ch in value if ch.isprintable())
    if printable / len(value) < _PRINTABLE_RATIO:
        return None
    return value


def _decodable_hex(run: str) -> str | None:
    try:
        raw = bytes.fromhex(run)
    except ValueError:
        return None
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not value or sum(1 for ch in value if ch.isprintable()) / len(value) < _PRINTABLE_RATIO:
        return None
    return value


def _rot13_suspicious(run: str) -> bool:
    return bool(_ROT13_SUSPICIOUS.search(codecs.decode(run, "rot13")))


def _has_homoglyph(text: str) -> bool:
    foreign = len(_CYRILLIC.findall(text)) + len(_GREEK.findall(text))
    if foreign == 0:
        return False
    latin = len(_LATIN.findall(text))
    return foreign > 0 and foreign <= latin  # latino-dominante com intruso
