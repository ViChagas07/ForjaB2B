"""Schemas HTTP do chat de IA (FASE 5c)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.application.product_cards import ProductCard


class ChatRequest(BaseModel):
    """Mensagem do usuario; `conversation_id` ausente = nova conversa."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


class ProductCardOut(BaseModel):
    """Cartao montado pelo BACKEND (preco so para usuario logado)."""

    model_config = ConfigDict(extra="forbid")

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


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    reply: str
    product_cards: list[ProductCardOut]


def card_to_out(card: ProductCard) -> ProductCardOut:
    return ProductCardOut(
        product_id=card.product_id,
        name=card.name,
        sku=card.sku,
        image_url=card.image_url,
        image_alt=card.image_alt,
        link=card.link,
        price=card.price,
        currency=card.currency,
        price_on_request=card.price_on_request,
        min_order_qty=card.min_order_qty,
        ca_status=card.ca_status,
    )
