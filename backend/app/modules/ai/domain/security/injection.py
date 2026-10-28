"""Detector de injecao/jailbreak (item A.2) e resposta neutra (item A.4).

Padroes em arquivo de dados versionado (`data/injection_patterns.v1.txt`,
formato `id|LEVEL|regex`, case-insensitive, anti-ReDoS) — nunca espalhados
pelo codigo. O veredito e ALLOW | SANITIZE | BLOCK com `reason_code` estavel.
Conteudo CODIFICADO (base64/hex/rot13) e re-escaneado apos decodificacao:
jailbreak escondido em base64 = BLOCK.

A resposta de bloqueio e UNICA, curta, traduzida nos 11 locales
(`data/neutral_responses.v1.json`), sem explicar regras nem revelar o que
foi detectado. Funcoes puras: sem I/O fora da leitura do arquivo de dados.
"""

from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache, lru_cache
from typing import cast

from app.modules.ai.domain.security.normalize import decode_hidden_candidates
from app.modules.ai.domain.types import Locale

_DATA_PACKAGE = "app.modules.ai.domain.security.data"
_PATTERN_FILE = "injection_patterns.v1.txt"
_NEUTRAL_FILE = "neutral_responses.v1.json"

# Validacao de regex do arquivo de dados: quantificadores aninhados proibidos
# (anti-ReDoS). Ex.: `(a+)+`, `(a|b)*` dentro de outro quantificador.
_NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*][^()]*\)[+*{]")


class VerdictLevel(StrEnum):
    """Nivel de veredito das checagens deterministicas."""

    ALLOW = "ALLOW"
    SANITIZE = "SANITIZE"
    BLOCK = "BLOCK"


@dataclass(frozen=True, kw_only=True)
class InjectionVerdict:
    """Resultado do detector sobre um texto."""

    level: VerdictLevel = VerdictLevel.ALLOW
    reason_code: str | None = None
    matched_pattern_id: str | None = None
    via_encoding: bool = False


@dataclass(frozen=True, kw_only=True)
class _Pattern:
    pattern_id: str
    level: VerdictLevel
    regex: re.Pattern[str]


@lru_cache(maxsize=1)
def _compiled_patterns() -> tuple[tuple[_Pattern, ...], int]:
    """Carrega e compila os padroes do arquivo de dados (uma vez por processo)."""
    resource = importlib.resources.files("app.modules.ai.domain.security").joinpath(
        f"data/{_PATTERN_FILE}"
    )
    patterns: list[_Pattern] = []
    version = 0
    for raw_line in resource.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if line.lower().startswith("# version:"):
                version = int(line.split(":", 1)[1].strip())
            continue
        pattern_id, level_raw, regex_raw = line.split("|", 2)
        if _NESTED_QUANTIFIER.search(regex_raw):
            raise ValueError(f"padrao com risco de ReDoS: {pattern_id}")
        patterns.append(
            _Pattern(
                pattern_id=pattern_id,
                level=VerdictLevel(level_raw),
                regex=re.compile(regex_raw, re.IGNORECASE),
            )
        )
    return tuple(patterns), version


def injection_patterns_version() -> int:
    """Versao do arquivo de padroes (para audit log)."""
    return _compiled_patterns()[1]


def scan_injection(text: str) -> InjectionVerdict:
    """Veredito deterministico sobre um texto (mensagem, argumento, documento)."""
    for pattern in _compiled_patterns()[0]:
        if pattern.regex.search(text):
            return _verdict_for(pattern)
    for decoded in decode_hidden_candidates(text):
        for pattern in _compiled_patterns()[0]:
            if pattern.regex.search(decoded):
                return InjectionVerdict(
                    level=VerdictLevel.BLOCK,
                    reason_code=pattern.pattern_id,
                    matched_pattern_id=pattern.pattern_id,
                    via_encoding=True,
                )
    return InjectionVerdict(level=VerdictLevel.ALLOW)


def _verdict_for(pattern: _Pattern, *, via_encoding: bool = False) -> InjectionVerdict:
    return InjectionVerdict(
        level=pattern.level,
        reason_code=pattern.pattern_id,
        matched_pattern_id=pattern.pattern_id,
        via_encoding=via_encoding,
    )


@cache
def _neutral_messages() -> dict[str, str]:
    import json

    resource = importlib.resources.files("app.modules.ai.domain.security").joinpath(
        f"data/{_NEUTRAL_FILE}"
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return cast("dict[str, str]", payload["messages"])


def neutral_response(locale: Locale) -> str:
    """Resposta unica de bloqueio/encerramento, no locale do site (fallback pt-BR)."""
    messages = _neutral_messages()
    return messages.get(locale.value, messages["pt-BR"])
