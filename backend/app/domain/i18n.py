"""Resolucao de conteudo multilingue (dominio puro, sem frameworks).

Idioma de origem: portugues do Brasil (``pt-BR``). A resolucao e sempre
**campo a campo**: se nao houver traducao para um campo no idioma pedido, o
valor cai para o pt-BR (fallback), sem nunca servir traducao de outro produto
ou de outro conteudo (o ``source_hash`` garante o vinculo com a origem).

Nada aqui chama servico de traducao: as traducoes sao armazenadas e o runtime
apenas as serve. Marcas, SKU, CA e numeros NAO passam por traducao.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_LOCALE = "pt-BR"


class TranslationStatus(StrEnum):
    """Estado de uma traducao armazenada.

    - ``machine``: gerada automaticamente (ainda nao revisada por humano);
    - ``reviewed``: revisada/confirmada por humano;
    - ``stale``: a origem pt-BR mudou; a traducao antiga continua sendo servida
      ate ser atualizada (nunca se perde conteudo por isso).
    """

    MACHINE = "machine"
    REVIEWED = "reviewed"
    STALE = "stale"


def match_supported_locale(requested: str, supported: list[str]) -> str | None:
    """Casa o codigo pedido com um idioma suportado (por codigo ou sub-tag).

    Ex.: ``pt``/``pt-BR``/``PT-br`` -> ``pt-BR``; ``en-US`` -> ``en``;
    ``es-419`` -> ``es``; ``ar-SA`` -> ``ar``. Sem match, devolve ``None``.
    """
    code = requested
    if not code or code != code.strip():
        return None
    lowered = {value.lower(): value for value in supported}
    if code.lower() in lowered:
        return lowered[code.lower()]
    primary = code.split("-")[0].lower()
    for value in supported:
        if value.lower() == primary or value.lower().split("-")[0] == primary:
            return value
    return None


def negotiate_locale(
    *,
    accept_language: str | None = None,
    lang_param: str | None = None,
    supported: list[str],
    default: str = DEFAULT_LOCALE,
) -> str:
    """Resolve o idioma: parametro explicito > Accept-Language > default.

    Valor nao suportado cai no default sem erro.
    """
    explicit = (lang_param or "").strip()
    if explicit:
        matched = match_supported_locale(explicit, supported)
        if matched is not None:
            return matched
        return default
    for candidate in _parse_accept_language(accept_language or ""):
        matched = match_supported_locale(candidate, supported)
        if matched is not None:
            return matched
    return default


def _parse_accept_language(header: str) -> list[str]:
    """Lista os idiomas do header por prioridade (respeitando ``q=``)."""
    entries: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        token = part.strip()
        if not token:
            continue
        code, _, params = token.partition(";")
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        entries.append((quality, index, code.strip()))
    entries.sort(key=lambda item: (-item[0], item[1]))
    return [code for _q, _i, code in entries if code and code != "*"]


@dataclass(frozen=True, kw_only=True)
class ResolvedText:
    """Resultado da resolucao de um texto: valor, idioma entregue e fallback."""

    value: str | None
    content_locale: str
    fallback: bool


def resolve_text(
    *,
    source: str | None,
    translated: str | None,
    locale: str,
    source_locale: str = DEFAULT_LOCALE,
) -> ResolvedText:
    """Resolve um texto campo a campo (traduzido > origem pt-BR)."""
    if locale == source_locale:
        return ResolvedText(value=source, content_locale=source_locale, fallback=False)
    if translated is not None and translated.strip() != "":
        return ResolvedText(value=translated, content_locale=locale, fallback=False)
    return ResolvedText(value=source, content_locale=source_locale, fallback=True)


def resolve_attributes(
    *,
    source: dict[str, object] | None,
    translated: dict[str, object] | None,
    locale: str,
    source_locale: str = DEFAULT_LOCALE,
) -> tuple[dict[str, object] | None, bool]:
    """Resolve atributos de texto campo a campo; devolve (atributos, fallback).

    ``fallback`` e True quando ao menos um valor veio do pt-BR. Chaves/numeros
    sem traducao permanecem iguais (nunca sao inventados).
    """
    if not source:
        return (translated, False) if translated else (source, False)
    if locale == source_locale or not translated:
        return source, locale != source_locale
    merged: dict[str, object] = {}
    fell_back = False
    for key, value in source.items():
        replacement = translated.get(key)
        if isinstance(replacement, str) and replacement.strip() != "":
            merged[key] = replacement
        else:
            merged[key] = value
            if isinstance(value, str):
                fell_back = True
    return merged, fell_back


def product_source_hash(
    *, name: str | None, description: str | None, attributes: dict[str, object] | None
) -> str:
    """Hash deterministico do conteudo de origem (pt-BR) de um produto.

    Muda quando nome, descricao ou atributos de texto mudam: e o gatilho para
    marcar as traducoes existentes como ``stale``.
    """
    payload = json.dumps(
        {"name": name, "description": description, "attributes": attributes or {}},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_translation_stale(
    *,
    stored_source_hash: str,
    name: str | None,
    description: str | None,
    attributes: dict[str, object] | None,
) -> bool:
    """True se a origem pt-BR mudou desde que a traducao foi gerada.

    Gatilho do status ``stale``: compara o hash armazenado com o hash da origem
    atual. Nao marca no banco (isso depende do fluxo de escrita do admin, fora
    de escopo desta fase); apenas detecta a divergencia de forma testavel,
    servindo tanto ao seed quanto a um futuro endpoint de admin.
    """
    current = product_source_hash(name=name, description=description, attributes=attributes)
    return current != stored_source_hash


def sanitize_translated_text(value: str | None, *, max_length: int) -> str | None:
    """Normaliza texto traduzido simples (sem HTML) e valida o tamanho.

    Texto traduzido e dado nao confiavel: rejeita marcas de HTML e acima do
    limite. Devolve a string sem espacos nas pontas ou ``None`` se vazia.
    """
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    if "<" in text or ">" in text:
        raise ValueError("translated text must be plain text (no HTML)")
    if len(text) > max_length:
        raise ValueError(f"translated text exceeds {max_length} characters")
    return text
