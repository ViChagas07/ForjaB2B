"""Carregamento dos dicionarios versionados de i18n do catalogo.

Leitura cacheada de dois arquivos JSON do repositorio:
- ``category_names.json``: nome da categoria por slug e idioma;
- ``attribute_dictionary.json``: rotulos e opcoes de atributos por idioma.

O idioma de origem (pt-BR) usa os valores da propria origem; qualquer idioma
sem entrada cai no valor padrao (origem).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.i18n import DEFAULT_LOCALE

_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_category_names() -> dict[str, dict[str, str]]:
    """Mapa ``locale -> {slug: nome}`` das categorias."""
    data = json.loads((_DIR / "category_names.json").read_text(encoding="utf-8"))
    return {str(locale): dict(names) for locale, names in data.items()}


@lru_cache(maxsize=1)
def load_attribute_dictionary() -> dict[str, dict[str, dict[str, object]]]:
    """Dicionario de ``labels`` e ``options`` por idioma."""
    data: dict[str, dict[str, dict[str, object]]] = json.loads(
        (_DIR / "attribute_dictionary.json").read_text(encoding="utf-8")
    )
    return data


def category_name(*, slug: str | None, locale: str, default_name: str) -> str:
    """Nome da categoria traduzido (fallback para o nome da origem)."""
    if locale == DEFAULT_LOCALE or not slug:
        return default_name
    return load_category_names().get(locale, {}).get(slug, default_name)
