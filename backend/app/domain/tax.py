"""Simulacao tributaria do Forja (ICMS-ST), deterministica e explicita.

Nao e um motor fiscal de producao nem emite documentos fiscais reais. Apenas
simula o ICMS-ST para portfolio usando: valor dos produtos, frete, NCM e
UF origem/destino. Todos os calculos monetarios usam ``Decimal`` com
arredondamento ``ROUND_HALF_UP``. Nunca usar float.

Separacao explicita de responsabilidades:

- Tax calculation != Invoice generation: esta funcao e pura e nao persiste nada.
- Tax calculation != Payment: esta funcao nao movimenta credito nem dinheiro.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")

# NCMs (prefixo de 4 digitos) sujeitos a ICMS-ST nesta simulacao. Lista
# ilustrativa de portfolio; nao e a tabela fiscal oficial.
_ST_NCM_PREFIXES = frozenset({"3303", "3305", "3402", "3923"})

# Margem de Valor Agregado (MVA) padrao da simulacao.
_MVA = Decimal("0.40")

# Aliquota interna de ICMS por UF de destino (simplificada para portfolio).
_ICMS_RATE_BY_UF: dict[str, Decimal] = {
    "SP": Decimal("0.18"),
    "MG": Decimal("0.18"),
    "RJ": Decimal("0.18"),
    "PR": Decimal("0.18"),
    "RS": Decimal("0.17"),
    "SC": Decimal("0.17"),
    "BA": Decimal("0.18"),
    "PE": Decimal("0.18"),
    "CE": Decimal("0.18"),
    "DF": Decimal("0.18"),
    "GO": Decimal("0.17"),
    "MT": Decimal("0.17"),
    "MS": Decimal("0.17"),
    "AM": Decimal("0.18"),
    "PA": Decimal("0.17"),
}

_DEFAULT_ICMS_RATE = Decimal("0.18")


def round_money(value: Decimal) -> Decimal:
    """Arredondamento monetario deterministico (ROUND_HALF_UP, 2 casas)."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def icms_rate(destination_uf: str) -> Decimal:
    """Aliquota interna de ICMS da UF de destino (default 18%)."""
    uf = destination_uf.strip().upper()
    return _ICMS_RATE_BY_UF.get(uf, _DEFAULT_ICMS_RATE)


def icms_st_applies(*, ncm: str | None, origin_uf: str, destination_uf: str) -> bool:
    """ICMS-ST aplicavel somente quando ha NCM na lista e operacao interestadual.

    - NCM ausente -> nao aplica;
    - UF origem == UF destino (operacao interna) -> nao aplica;
    - NCM fora da lista ST -> nao aplica.
    """
    if ncm is None:
        return False
    if origin_uf.strip().upper() == destination_uf.strip().upper():
        return False
    return any(ncm.startswith(prefix) for prefix in _ST_NCM_PREFIXES)


def compute_icms_st(
    *,
    product_value: Decimal,
    freight: Decimal = _ZERO,
    ncm: str | None,
    origin_uf: str,
    destination_uf: str,
) -> Decimal:
    """ICMS-ST = (valor produtos + frete) * (1 + MVA) * aliquota(destino).

    O frete entra na base de calculo (encarece o imposto) quando informado.
    """
    if not icms_st_applies(ncm=ncm, origin_uf=origin_uf, destination_uf=destination_uf):
        return _ZERO
    base = product_value + freight
    st_base = base * (1 + _MVA)
    return round_money(st_base * icms_rate(destination_uf))
