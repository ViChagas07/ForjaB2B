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
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
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
    BrandCount,
    BrandListData,
    BrandProductsData,
    BrandResolution,
    CatalogOverviewData,
    CatalogTools,
    CategoryCount,
    PriceRangeData,
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
_GENERIC_QUERY_TERMS = frozenset(
    {
        "produto",
        "produtos",
        "item",
        "itens",
        "coisa",
        "coisas",
        "loja",
        "catalogo",
        "catalog",
        "product",
        "products",
        "items",
        "store",
        "catalogue",
    }
)


@dataclass(frozen=True, kw_only=True)
class EvalProduct:
    product_id: str
    sku: str
    name: str
    category: str
    brand: str
    price: Decimal
    stock: int
    min_order_qty: int = 1
    tokens: tuple[str, ...] = ()


class FixtureSearch:
    """Busca lexical simples (singular/plural + tokens) sobre o fixture."""

    def __init__(self, products: list[EvalProduct]) -> None:
        self._products = products

    async def search(  # noqa: C901 - fixture de busca para a bateria
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
        combined = " ".join((query, query_pt, query_en)).strip()
        generic = not combined or combined.casefold() in _GENERIC_QUERY_TERMS
        terms = set() if generic else _terms(combined)
        if not generic and not terms:
            return ProductSearchResult(products=(), capped=False)
        scored: list[tuple[int, EvalProduct]] = []
        for item in self._products:
            if category is not None and item.category != category:
                continue
            if brand is not None and brand.casefold() not in item.brand.casefold():
                continue
            if price_min is not None and item.price < Decimal(str(price_min)):
                continue
            if price_max is not None and item.price > Decimal(str(price_max)):
                continue
            haystack = _terms(
                f"{item.name} {item.category} {item.brand} {' '.join(item.tokens)}"
            )
            score = len(terms & haystack)
            if not terms or score:
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


class FixtureInsights:
    """Agregacoes do fixture com o mesmo contrato do adaptador real."""

    def __init__(self, products: list[EvalProduct]) -> None:
        self._products = products

    async def resolve_brand(self, *, text: str) -> BrandResolution:
        brands = _fixture_brands(self._products)
        wanted = _norm_key(text)
        names = tuple(brand.name for brand in brands[:5])
        if not wanted:
            return BrandResolution(matched=None, available=names)
        exact = [
            brand
            for brand in brands
            if wanted in {_norm_key(brand.name), _norm_key(brand.slug)}
        ]
        if exact:
            return BrandResolution(matched=exact[0], available=names)
        scored = [
            (
                max(
                    SequenceMatcher(None, wanted, _norm_key(brand.name)).ratio(),
                    SequenceMatcher(None, wanted, _norm_key(brand.slug)).ratio(),
                ),
                brand,
            )
            for brand in brands
        ]
        scored.sort(key=lambda item: (-item[0], item[1].name))
        if not scored or scored[0][0] < 0.78:
            return BrandResolution(matched=None, available=names)
        close = [brand for ratio, brand in scored if ratio >= 0.75]
        if len(close) > 1:
            return BrandResolution(
                matched=None, candidates=tuple(close[:3]), available=names
            )
        return BrandResolution(matched=scored[0][1], available=names)

    async def list_brands(
        self,
        *,
        category: str | None,
        query: str | None,
        limit: int,
        locale: str,
        auth: Any,
    ) -> BrandListData:
        items = self._filter(category=category, query=query)
        brands = tuple(_fixture_brands(items))
        return BrandListData(
            brands=brands[:limit],
            total=len(brands),
            query=query,
            category=category,
        )

    async def brand_products(
        self,
        *,
        brand: str,
        category: str | None,
        sort: str | None,
        limit: int,
        locale: str,
        auth: Any,
    ) -> BrandProductsData:
        resolution = await self.resolve_brand(text=brand)
        if resolution.matched is None:
            return BrandProductsData(
                brand=None,
                products=(),
                candidates=resolution.candidates,
                available=resolution.available,
                reason_code=(
                    "brand_ambiguous" if resolution.candidates else "brand_not_found"
                ),
            )
        items = [
            item
            for item in self._filter(category=category)
            if item.brand.casefold() == resolution.matched.name.casefold()
        ]
        if sort == "asc":
            items.sort(key=lambda item: (item.price, item.name.casefold()))
        elif sort == "desc":
            items.sort(key=lambda item: (-item.price, item.name.casefold()))
        return BrandProductsData(
            brand=resolution.matched,
            products=tuple(_tool_product(item) for item in items[:limit]),
            available=resolution.available,
            reason_code=None if items else "brand_products_empty",
        )

    async def overview(
        self, *, locale: str, category_query: str | None
    ) -> CatalogOverviewData:
        categories = _fixture_categories(self._products)
        query = (category_query or "").strip()
        if query:
            wanted = _norm_key(query)
            categories = tuple(
                item
                for item in categories
                if wanted in _norm_key(item.name) or wanted in _norm_key(item.slug)
            )
        brands = _fixture_brands(self._products)
        return CatalogOverviewData(
            categories=categories,
            total_products=sum(item.count for item in categories),
            total_brands=len(brands),
            brand_names=tuple(item.name for item in brands[:10]),
            category_query=query or None,
        )

    async def price_range(
        self,
        *,
        category: str | None,
        query: str | None,
        locale: str,
        auth: Any,
    ) -> PriceRangeData:
        items = self._filter(category=category, query=query)
        if not items:
            return PriceRangeData(min_price=None, max_price=None, count=0)
        cheapest = min(items, key=lambda item: (item.price, item.name.casefold()))
        priciest = max(items, key=lambda item: (item.price, item.name.casefold()))
        return PriceRangeData(
            min_price=cheapest.price,
            max_price=priciest.price,
            count=len(items),
            min_product=_tool_product(cheapest),
            max_product=_tool_product(priciest),
        )

    async def count_products(
        self,
        *,
        category: str | None,
        brand: str | None,
        query: str | None,
        locale: str,
        auth: Any,
    ) -> int:
        if category:
            resolved_category = self._resolve_category(category)
            if resolved_category is not None:
                category = resolved_category
            else:
                query = f"{query or ''} {category}".strip()
                category = None
        items = self._filter(category=category, query=query)
        if brand:
            resolution = await self.resolve_brand(text=brand)
            if resolution.matched is None:
                return 0
            items = [
                item
                for item in items
                if item.brand.casefold() == resolution.matched.name.casefold()
            ]
        return len(items)

    def _resolve_category(self, text: str) -> str | None:
        wanted = _norm_key(text)
        if not wanted:
            return None
        categories = _fixture_categories(self._products)
        exact = [
            item
            for item in categories
            if wanted in {_norm_key(item.name), _norm_key(item.slug)}
        ]
        if exact:
            return exact[0].slug
        contains = [
            item
            for item in categories
            if wanted in _norm_key(item.name) or wanted in _norm_key(item.slug)
        ]
        if len(contains) == 1:
            return contains[0].slug
        if contains:
            scored = sorted(
                (
                    (
                        max(
                            SequenceMatcher(None, wanted, _norm_key(item.name)).ratio(),
                            SequenceMatcher(None, wanted, _norm_key(item.slug)).ratio(),
                        ),
                        item,
                    )
                    for item in contains
                ),
                key=lambda pair: pair[0],
            )
            if scored[-1][0] >= 0.82:
                return scored[-1][1].slug
        return None

    def _filter(
        self, *, category: str | None = None, query: str | None = None
    ) -> list[EvalProduct]:
        terms = _terms(query or "")
        items: list[EvalProduct] = []
        for item in self._products:
            if category is not None and item.category != category:
                continue
            if terms:
                haystack = _terms(
                    f"{item.name} {item.category} {item.brand} {' '.join(item.tokens)}"
                )
                if not (terms & haystack):
                    continue
            items.append(item)
        return items


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
            brand=str(item.get("brand", "Forja")),
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
        insights_port=FixtureInsights(products),
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


def _fixture_brands(products: Sequence[EvalProduct]) -> tuple[BrandCount, ...]:
    counts = Counter(item.brand for item in products)
    return tuple(
        BrandCount(name=name, slug=_norm_key(name), count=count)
        for name, count in counts.most_common()
    )


_FIXTURE_CATEGORY_NAMES = {
    "protecao-maos": "Proteção das Mãos",
    "ferramentas-eletricas": "Ferramentas Elétricas",
    "maquinas-estacionarias": "Máquinas Estacionárias",
    "protecao-pes": "Proteção dos Pés",
    "protecao-respiratoria": "Proteção Respiratória",
    "protecao-visual": "Proteção Visual",
    "protecao-auditiva": "Proteção Auditiva",
    "protecao-quedas": "Proteção contra Quedas",
    "epis": "EPIs",
    "protecao-cabeca": "Proteção da Cabeça",
    "epi-recovery": "EPI Recovery",
    "maquinas-e-ferramentas": "Máquinas e Ferramentas",
}


def _fixture_categories(products: Sequence[EvalProduct]) -> tuple[CategoryCount, ...]:
    counts = Counter(item.category for item in products)
    return tuple(
        CategoryCount(
            name=_FIXTURE_CATEGORY_NAMES.get(slug, slug), slug=slug, count=count
        )
        for slug, count in counts.most_common()
    )


def _norm_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", folded)


def _tool_product(item: EvalProduct) -> ToolProduct:
    return ToolProduct(
        product_id=item.product_id,
        name=item.name,
        sku=item.sku,
        brand=item.brand,
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

