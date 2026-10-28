"""Cartoes de produto do chat (FASE 5b) — montados pelo BACKEND.

Recebe os ids que o LLM quer mostrar e o conjunto de ids devolvidos pelas
ferramentas NESTE turno: qualquer id fora do conjunto e DESCARTADO (anti-id
forjado). A hidratacao (preco/imagem/selo) vem de um adaptador que reusa a
logica do SearchProducts (mesma resolucao de preco da empresa); visitante
NUNCA recebe preco (price_on_request). Link e URL de imagem sao montados AQUI,
no servidor. Maximo de 6 cartoes, sem duplicatas, preservando a ordem pedida.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

MAX_PRODUCT_CARDS = 6


@dataclass(frozen=True, kw_only=True)
class HydratedProduct:
    """Produto hidratado do PostgreSQL (dados do servidor, nunca do LLM)."""

    product_id: str
    name: str
    sku: str
    image_url: str
    image_alt: str
    currency: str
    min_order_qty: int
    ca_status: str
    price: Decimal | None
    price_on_request: bool


@dataclass(frozen=True, kw_only=True)
class ProductCard:
    """Cartao publico (sem HTML; preco so para usuario logado)."""

    product_id: str
    name: str
    sku: str
    image_url: str
    image_alt: str
    link: str
    price: str | None
    currency: str
    price_on_request: bool
    min_order_qty: int
    ca_status: str


class ProductHydratorPort(Protocol):
    """Adaptador de hidratacao (mesma logica de preco do SearchProducts)."""

    async def hydrate(
        self, *, product_ids: Sequence[str], locale: str, auth: Any
    ) -> list[HydratedProduct]: ...


class ProductCardService:
    def __init__(self, *, hydrator: ProductHydratorPort) -> None:
        self._hydrator = hydrator

    async def build(
        self,
        *,
        requested_ids: Sequence[str],
        allowed_product_ids: set[str],
        locale: str,
        auth: Any,
        max_cards: int = MAX_PRODUCT_CARDS,
    ) -> list[ProductCard]:
        # 1) id forjado (fora do que as ferramentas devolveram no turno) cai fora.
        safe_ids = _unique(pid for pid in requested_ids if pid in allowed_product_ids)
        safe_ids = safe_ids[:max_cards]
        if not safe_ids:
            return []
        hydrated = await self._hydrator.hydrate(product_ids=safe_ids, locale=locale, auth=auth)
        by_id = {product.product_id: product for product in hydrated}
        visitor = auth is None
        cards: list[ProductCard] = []
        for product_id in safe_ids:
            product = by_id.get(product_id)
            if product is None:
                continue  # inexistente/nao vendavel: nunca inventa cartao
            # Visitante: NUNCA preco. Logado: preco da PROPRIA empresa ja resolvido
            # na hidratacao (inclui FIXED_PRICE); price_on_request quando aplicavel.
            price = None if visitor else _format_price(product)
            cards.append(
                ProductCard(
                    product_id=product.product_id,
                    name=product.name,
                    sku=product.sku,
                    image_url=product.image_url,
                    image_alt=product.image_alt,
                    link=f"/catalog/{product.product_id}",  # montado no servidor
                    price=price,
                    currency=product.currency,
                    price_on_request=True if visitor else product.price_on_request,
                    min_order_qty=product.min_order_qty,
                    ca_status=product.ca_status,
                )
            )
        return cards


def _format_price(product: HydratedProduct) -> str | None:
    if product.price_on_request or product.price is None:
        return None
    return f"{product.price:.2f}"


def _unique(ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for product_id in ids:
        if product_id not in seen:
            seen.add(product_id)
            ordered.append(product_id)
    return ordered
