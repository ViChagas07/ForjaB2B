"""Catalogo deterministico para a bateria offline do assistente.

Nao e usado em producao: permite rodar os ~60 casos de loja com o LLM
INDISPONIVEL, provando que busca, existencia, preco, cartoes e fallback
continuam funcionando por codigo. O catalogo espelha SKUs/precos reais do seed.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.modules.ai.application.chat_graph import ChatGraph
from app.modules.ai.application.chat_session import InMemoryChatSessionStore
from app.modules.ai.application.conversation_service import ConversationScope
from app.modules.ai.application.knowledge import default_knowledge_base
from app.modules.ai.application.ports import ConversationView
from app.modules.ai.application.product_cards import HydratedProduct, ProductCardService
from app.modules.ai.application.security.input_gate import InputGate
from app.modules.ai.application.security.ports import InMemoryBlockCounter
from app.modules.ai.application.tools import (
    CatalogTools,
    ProductSearchResult,
    ToolOrderStatus,
    ToolProduct,
)
from app.modules.ai.domain.types import Locale

_STOPWORDS = frozenset(
    {
        "a",
        "o",
        "as",
        "os",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "para",
        "com",
        "um",
        "uma",
        "the",
        "an",
        "of",
        "for",
        "with",
        "y",
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "que",
        "mais",
        "menos",
        "preciso",
        "quero",
        "tem",
        "voces",
        "vocês",
    }
)
_TOKEN = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True, kw_only=True)
class EvalProduct:
    product_id: str
    sku: str
    name: str
    category: str
    price: Decimal
    stock: int
    min_order_qty: int = 1
    tokens: tuple[str, ...] = ()


class FixtureSearch:
    """Busca lexical simples (singular/plural + tokens) sobre o fixture."""

    def __init__(self, products: list[EvalProduct]) -> None:
        self._products = products

    async def search(
        self,
        *,
        query: str,
        query_pt: str = "",
        query_en: str = "",
        category: str | None,
        limit: int,
        locale: str,
        auth: Any,
        price_sort: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        attributes: Mapping[str, str] | None = None,
        offset: int = 0,
    ) -> ProductSearchResult:
        terms = _terms(" ".join((query, query_pt, query_en)))
        scored: list[tuple[int, EvalProduct]] = []
        for item in self._products:
            if category is not None and item.category != category:
                continue
            if price_min is not None and item.price < Decimal(str(price_min)):
                continue
            if price_max is not None and item.price > Decimal(str(price_max)):
                continue
            haystack = _terms(f"{item.name} {item.category} {' '.join(item.tokens)}")
            score = len(terms & haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].name.casefold()))
        items = [item for _, item in scored]
        if price_sort == "asc":
            items.sort(key=lambda item: (item.price, item.name.casefold()))
        elif price_sort == "desc":
            items.sort(key=lambda item: (-item.price, item.name.casefold()))
        items = items[offset : offset + limit]
        return ProductSearchResult(
            products=tuple(_tool_product(item) for item in items),
            capped=False,
        )

    async def get(self, *, product_ref: str, locale: str, auth: Any) -> ToolProduct | None:
        wanted = product_ref.strip().casefold()
        for item in self._products:
            if item.product_id.casefold() == wanted or item.sku.casefold() == wanted:
                return _tool_product(item)
        return None


class FixtureCategories:
    def __init__(self, names: list[str]) -> None:
        self._names = names

    async def list_categories(self, *, locale: str) -> list[str]:
        return list(self._names)


class FixtureOrderStatus:
    async def get_order_status(
        self, *, order_id: object, company_id: object, user_id: object
    ) -> ToolOrderStatus | None:
        return None


class FixtureHydrator:
    def __init__(self, products: list[EvalProduct]) -> None:
        self._products = {item.product_id: item for item in products}

    async def hydrate(
        self, *, product_ids: Sequence[str], locale: str, auth: Any
    ) -> list[HydratedProduct]:
        result: list[HydratedProduct] = []
        for product_id in product_ids:
            item = self._products.get(product_id)
            if item is None:
                continue
            result.append(
                HydratedProduct(
                    product_id=item.product_id,
                    name=item.name,
                    sku=item.sku,
                    image_url=f"/images/products/{item.sku.lower()}.png",
                    image_alt=item.name,
                    currency="BRL",
                    min_order_qty=item.min_order_qty,
                    ca_status="VALID",
                    price=item.price,
                    price_on_request=False,
                )
            )
        return result


class FixtureConversations:
    def __init__(self) -> None:
        self.users: list[str] = []
        self.assistants: list[str] = []

    async def append_user_message(
        self, conversation: ConversationView, *, sanitized_text: str, language: str
    ) -> None:
        self.users.append(sanitized_text)

    async def append_assistant_message(
        self, conversation: ConversationView, *, approved_text: str, language: str
    ) -> None:
        self.assistants.append(approved_text)


class FixtureCartSummary:
    async def cart_summary(self, *, company_id: object, user_id: object) -> str:
        return ""


class FixtureAudit:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


def load_catalog(path: Path) -> list[EvalProduct]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvalProduct(
            product_id=str(item["product_id"]),
            sku=str(item["sku"]),
            name=str(item["name"]),
            category=str(item["category"]),
            price=Decimal(str(item["price"])),
            stock=int(item.get("stock", 0)),
            min_order_qty=int(item.get("min_order_qty", 1)),
            tokens=tuple(str(token) for token in item.get("tokens", ())),
        )
        for item in raw
    ]


def build_offline_graph(*, catalog_path: Path) -> ChatGraph:
    products = load_catalog(catalog_path)
    categories = sorted({item.category for item in products})
    tools = CatalogTools(
        search_port=FixtureSearch(products),
        categories_port=FixtureCategories([f"{name} (1)" for name in categories]),
        order_status_port=FixtureOrderStatus(),
    )
    return ChatGraph(
        llm=None,
        tools=tools,
        cards=ProductCardService(hydrator=FixtureHydrator(products)),
        input_gate=InputGate(
            max_message_chars=500,
            window_turns=10,
            block_counter=InMemoryBlockCounter(),
        ),
        conversations=FixtureConversations(),  # type: ignore[arg-type]
        cart_summary=FixtureCartSummary(),
        knowledge=default_knowledge_base(),
        session_store=InMemoryChatSessionStore(),
        audit=FixtureAudit(),
        ai_enabled=True,
        tag_factory=lambda: "EVALTAG",
    )


def new_conversation(*, scope: ConversationScope | None = None) -> ConversationView:
    return ConversationView(
        id=uuid.uuid4(),
        company_id=scope.company_id if scope else None,
        user_id=scope.user_id if scope else None,
        locale="pt-BR",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        conversation_language="pt-BR",
    )


def localized_locale(value: str) -> Locale:
    try:
        return Locale(value)
    except ValueError:
        return Locale.PT_BR


def _tool_product(item: EvalProduct) -> ToolProduct:
    return ToolProduct(
        product_id=item.product_id,
        name=item.name,
        sku=item.sku,
        brand="Forja",
        category=item.category,
        description=item.name,
        attributes={"estoque": str(item.stock)},
        stock_quantity=item.stock,
        min_order_qty=item.min_order_qty,
        price=item.price,
        price_on_request=False,
    )


def _terms(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    result: set[str] = set()
    for token in _TOKEN.findall(folded):
        if token in _STOPWORDS or len(token) < 3:
            continue
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        result.add(token)
    return result

