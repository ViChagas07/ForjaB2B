"""Output guard deterministico (item C.7 e canary B.6).

Verifica a resposta do modelo ANTES de entregar ao usuario:
- NUNCA deixa passar HTML/Markdown executavel (BLOCK);
- remove URLs absolutas e links fora das rotas geradas pelo backend
  (so caminhos relativos do proprio site sao permitidos);
- remove e-mails, telefones, padroes de segredo (chaves/tokens) e valores
  monetarios no TEXTO do modelo (preco so existe em cartoes do backend);
- BLOCK quando o idioma diverge do locale (quando detectavel por script
  Unicode), quando o canary vazou ou quando ha trecho do system prompt;
- limita o tamanho da resposta.

Funcoes puras: sem I/O, sem LLM. Texto limpo segue com `actions` (para
audit/metricas); BLOCK devolve `blocked=True` e o chamador responde neutro.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.ai.domain.types import Locale

# ------------------------- padroes de remocao --------------------------------
_HTML_TAG = re.compile(r"<[^<>\n]{0,200}>")
_EXECUTABLE_HTML = re.compile(
    r"(?i)<\s*(script|iframe|object|embed|link|meta|form)\b|\bon[a-z]+\s*=|javascript:|data:text/html"
)
_ABSOLUTE_URL = re.compile(r"(?i)(?:https?://|www\.)[^\s<>\"']{1,300}")
_MARKDOWN_LINK = re.compile(r"\[([^\]\n]{0,120})\]\(([^)\n]{1,300})\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]\n]{0,120}\]\(([^)\n]{1,300})\)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b\+?\d{1,3}?\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}\b")
_SECRET = re.compile(
    r"(?i)(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{8,}"
    r"|whsec_[A-Za-z0-9]{8,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|Bearer\s+[A-Za-z0-9._-]{10,}"
    r"|(?:api[_-]?key|api[_-]?secret|token|senha|password)\s*[:=]\s*\S{8,}"
)
_MONEY = re.compile(
    r"(?:R\$\s?|US\$\s?|\$\s?|€\s?|£\s?)\d{1,3}(?:\.\d{3})*(?:,\d{2})?"
    r"|\b\d{1,3}(?:\.\d{3})+,\d{2}\b"
    r"|\b\d{1,3}(?:,\d{3})+(?:\.\d{2})\b"
)

# ------------------------- scripts Unicode -----------------------------------
_SCRIPT_RANGES: tuple[tuple[str, str], ...] = (
    ("cyrillic", "\u0400-\u04ff"),
    ("greek", "\u0370-\u03ff"),
    ("arabic", "\u0600-\u06ff\u0750-\u077f"),
    ("han", "\u4e00-\u9fff"),
    ("kana", "\u3040-\u30ff"),
    ("hangul", "\uac00-\ud7af"),
)
_LATIN = re.compile(r"[A-Za-z\u00c0-\u024f\u1e00-\u1eff]")
_EXPECTED_SCRIPTS: dict[str, frozenset[str]] = {
    "pt-BR": frozenset({"latin"}),
    "en": frozenset({"latin"}),
    "es": frozenset({"latin"}),
    "de": frozenset({"latin"}),
    "fr": frozenset({"latin"}),
    "it": frozenset({"latin"}),
    "ru": frozenset({"cyrillic", "latin"}),
    "ar": frozenset({"arabic", "latin"}),
    "ja": frozenset({"latin", "kana", "han"}),
    "ko": frozenset({"latin", "hangul"}),
    "zh-CN": frozenset({"latin", "han"}),
}
_SCRIPT_DIVERSION_RATIO = 0.5


@dataclass(frozen=True, kw_only=True)
class GuardedOutput:
    """Resposta do modelo apos o guard: limpa, bloqueada ou truncada."""

    text: str
    blocked: bool = False
    reason_code: str | None = None
    actions: tuple[str, ...] = ()


def check_canary(output: str, *, canary: str) -> bool:
    """True se o canary token vazou na saida do modelo."""
    return bool(canary) and canary in output


def leaks_system_prompt(output: str, *, system_prompt: str) -> bool:
    """True se um trecho literal (linha >= 24 chars) do system prompt vazou."""
    for line in system_prompt.splitlines():
        fragment = line.strip()
        if len(fragment) >= 24 and fragment in output:
            return True
    return False


def guard_model_output(
    text: str,
    *,
    locale: Locale,
    max_chars: int,
    allowed_url_prefixes: Sequence[str] = ("/catalog", "/cart", "/checkout", "/orders", "/"),
    canary: str | None = None,
    system_prompt: str | None = None,
) -> GuardedOutput:
    """Aplica as regras de saida; BLOCK devolve texto vazio + motivo."""
    blocked = _block_reason(text, locale=locale, canary=canary, system_prompt=system_prompt)
    if blocked is not None:
        return GuardedOutput(text="", blocked=True, reason_code=blocked)

    actions: list[str] = []
    cleaned = _clean_text(text, actions=actions, allowed_url_prefixes=tuple(allowed_url_prefixes))
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
        actions.append("output_truncado")
    return GuardedOutput(text=cleaned, actions=tuple(actions))


def _block_reason(
    text: str,
    *,
    locale: Locale,
    canary: str | None,
    system_prompt: str | None,
) -> str | None:
    """Motivo de BLOCK (canary/system prompt/html executavel/idioma), se houver."""
    if canary and check_canary(text, canary=canary):
        return "canary_vazado"
    if system_prompt and leaks_system_prompt(text, system_prompt=system_prompt):
        return "system_prompt_vazado"
    if _EXECUTABLE_HTML.search(text):
        return "html_executavel"
    if _language_diverges(text, locale=locale):
        return "idioma_divergente"
    return None


def _clean_text(
    text: str,
    *,
    actions: list[str],
    allowed_url_prefixes: tuple[str, ...],
) -> str:
    """Remove conteudo proibido da saida, registrando cada acao."""
    state = {"value": _MARKDOWN_IMAGE.sub("", text)}

    def _keep_relative_link(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith(allowed_url_prefixes):
            return match.group(0)
        actions.append("link_externo_removido")
        return label

    def _sub(pattern: re.Pattern[str], replacement: str, action: str) -> None:
        value, count = pattern.subn(replacement, state["value"])
        if count:
            actions.append(action)
        state["value"] = value

    state["value"] = _MARKDOWN_LINK.sub(_keep_relative_link, state["value"])
    _sub(_ABSOLUTE_URL, "", "url_removida")
    _sub(_HTML_TAG, " ", "html_removido")
    _sub(_EMAIL, "", "email_removido")
    _sub(_PHONE, "", "telefone_removido")
    _sub(_SECRET, "[removido]", "segredo_removido")
    _sub(_MONEY, "", "preco_removido")
    return state["value"]


def _language_diverges(text: str, *, locale: Locale) -> bool:
    """Detecta divergencia por script Unicode (quando o texto tem letras)."""
    allowed = _EXPECTED_SCRIPTS.get(locale.value, frozenset({"latin"}))
    foreign = 0
    latin = len(_LATIN.findall(text))
    for name, pattern_range in _SCRIPT_RANGES:
        count = len(re.findall(f"[{pattern_range}]", text))
        if name not in allowed:
            foreign += count
    letters = foreign + latin
    if letters == 0:
        return False
    return foreign / letters > _SCRIPT_DIVERSION_RATIO
