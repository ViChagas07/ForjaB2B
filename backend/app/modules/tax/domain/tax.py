"""Simulacao tributaria (re-export do dominio compartilhado).

Promovido a ``app.domain.tax`` para que qualquer contexto (ordering/invoicing)
consiga consultar o calculo de ICMS-ST sem acoplar-se ao modulo tax. O calculo
e puro (sem persistencia nem movimento de credito).
"""

from __future__ import annotations

from app.domain.tax import compute_icms_st, icms_rate, icms_st_applies, round_money

__all__ = [
    "compute_icms_st",
    "icms_rate",
    "icms_st_applies",
    "round_money",
]
