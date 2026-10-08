"""Regras de frete (re-export do dominio compartilhado).

Promovido a ``app.domain.shipping`` para ser compartilhado com o contexto
ordering (que calcula o frete no pedido) sem acoplamento entre bounded
contexts. Este modulo preserva o caminho de importacao do contexto shipping.
"""

from __future__ import annotations

from app.domain.shipping import compute_shipping, compute_total_weight

__all__ = [
    "compute_shipping",
    "compute_total_weight",
]
