"""Carrega settings/mappings versionados do indice de busca.

Os arquivos JSON em ``indices/`` sao versionados no repositorio (fonte do
schema do indice: mapping explicito com ``dynamic: strict`` e analisadores em
portugues). Uma mudanca de schema exige nova versao de indice
(``ELASTICSEARCH_INDEX_VERSION``) e revisao destes arquivos; o indice antigo
permanece para rollback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

_INDICES_DIR = Path(__file__).parent / "indices"
_SETTINGS_FILE = _INDICES_DIR / "products.settings.json"
_MAPPINGS_FILE = _INDICES_DIR / "products.mappings.json"


def load_index_settings() -> dict[str, Any]:
    """Settings do indice (analisadores, shards, replicas)."""
    return cast("dict[str, Any]", json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")))


def load_index_mappings() -> dict[str, Any]:
    """Mapping explicito do indice de produtos."""
    return cast("dict[str, Any]", json.loads(_MAPPINGS_FILE.read_text(encoding="utf-8")))


def versioned_index_name(*, alias: str, version: int) -> str:
    """Nome do indice versionado; a aplicacao sempre usa o alias."""
    return f"{alias}_v{version}"
