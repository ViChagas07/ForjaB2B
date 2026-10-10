"""Texto embutido e hash de conteudo para embeddings (puro, sem frameworks).

O texto embutido contem apenas campos publicos do catalogo: nome, marca,
categoria e descricao. Nunca preco, estoque, credito ou dados de clientes.
O hash permite pular o recalculo quando o conteudo nao mudou.
"""

from __future__ import annotations

import hashlib

from app.modules.search.application.ports import ProductRow


def build_embedding_text(row: ProductRow) -> str:
    """Concatena os campos publicos usados no embedding (sem preco)."""
    parts = [row.name, row.brand_name, row.category_name, row.description]
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def compute_content_hash(text: str, model: str) -> str:
    """Hash estavel do conteudo embutido para um modelo (evita recalculo)."""
    payload = f"{model}\n{text}".encode()
    return hashlib.sha256(payload).hexdigest()
