"""Regras de disponibilidade/venda do catalogo (re-export do dominio compartilhado).

A regra de CA/EPI foi promovida a ``app.domain.product_availability`` para ser
compartilhada com cart/ordering sem acoplamento entre bounded contexts. Este
modulo preserva o caminho de importacao existente do catalogo.
"""

from __future__ import annotations

from app.domain.product_availability import CaStatus, ca_status, is_ca_expired, is_sellable

__all__ = ["CaStatus", "ca_status", "is_ca_expired", "is_sellable"]
