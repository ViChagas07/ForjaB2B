"""Ferramentas SOMENTE LEITURA do chat (FASE 5b) — sem LLM.

Schemas Pydantic STRICT (`extra="forbid"`): `company_id`/`user_id` NUNCA sao
argumentos — vem do contexto de autenticacao do servidor (injetado pelo
chamador). Toda saida para o LLM passa pelo sanitizador de catalogo da Fase 2
(allowlist id/name/sku/brand/category/atributos; descricao <= 300; sem
HTML/URL); documentos suspeitos vao para QUARENTENA (devolvidos com
product_id/reason para audit, nunca ao modelo). SEM precos no contexto do
LLM: cartoes/precos sao montados em `product_cards.py`.
`get_shipping_policy` usa as constantes de `app.domain.shipping` (regra
publica do frete simulado; nao e preco de produto/contrato) e nunca promete
prazo. Registro por allowlist de no (Fase 2) com limite de 4 chamadas/turno.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from app.domain.shipping import BASE_FREIGHT, RATE_PER_KG
from app.modules.ai.application.security.tools import ToolRegistry, ToolSchema, ToolSpec
from app.modules.ai.domain.security.catalog_sanitizer import (
    CatalogSanitizeResult,
    sanitize_catalog_document,
    sanitize_tool_text,
)
from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.normalize import normalize_user_text

CHAT_NODE = "chat"
MAX_TOOL_CALLS = 4

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,59}$"


class SearchProductsArgs(ToolSchema):
    """Busca no catalogo (consulta + filtros + ordenacao por preco opcional)."""

    query: str = Field(min_length=2, max_length=200)
    category: str | None = Field(default=None, pattern=_SLUG_PATTERN)
    limit: int = Field(default=5, ge=1, le=6)
    price_sort: Literal["asc", "desc"] | None = None
    price_min: float | None = Field(default=None, ge=0, le=1_000_000)
    price_max: float | None = Field(default=None, ge=0, le=1_000_000)
    brand: str | None = Field(default=None, min_length=1, max_length=80)
    attributes: dict[str, str] = Field(default_factory=dict)
    offset: int = Field(default=0, ge=0, le=50)

    @field_validator("attributes")
    @classmethod
    def _bounded_attributes(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 6:
            raise ValueError("no maximo 6 atributos")
        for key, item in value.items():
            if len(key) > 40 or len(item) > 60:
                raise ValueError("atributo longo demais")
        return value

    @model_validator(mode="after")
    def _ordered_range(self) -> SearchProductsArgs:
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min maior que price_max")
        return self


class GetProductArgs(ToolSchema):
    """Detalhe de UM produto por ID, slug, SKU ou nome."""

    product_ref: str = Field(min_length=2, max_length=80)


class CompareProductsArgs(ToolSchema):
    """Comparacao de 2 a 4 produtos (dados NAO monetarios)."""

    product_refs: list[str] = Field(min_length=2, max_length=4)

    @field_validator("product_refs")
    @classmethod
    def _bounded_refs(cls, value: list[str]) -> list[str]:
        refs = [item.strip() for item in value if item.strip()]
        if len(refs) < 2 or len(refs) > 4:
            raise ValueError("informe de 2 a 4 produtos")
        if any(len(item) > 80 for item in refs):
            raise ValueError("referencia de produto longa demais")
        return refs


class OrderStatusArgs(ToolSchema):
    """Consulta de UM pedido do proprio usuario da sessao."""

    order_id: str = Field(min_length=4, max_length=64)


class ListCategoriesArgs(ToolSchema):
    """Lista categorias do catalogo (sem parametros)."""


class ShippingPolicyArgs(ToolSchema):
    """Regra publica de frete simulado (sem parametros)."""


@dataclass(frozen=True, kw_only=True)
class ToolProduct:
    """Produto BRUTO vindo da busca (sem preco): insumo do sanitizador."""

    product_id: str
    name: str
    sku: str
    brand: str = ""
    category: str = ""
    attributes: Mapping[str, object] | None = None
    description: str | None = None
    slug: str = ""
    stock_quantity: int | None = None
    ca_status: str | None = None
    ca_number: str | None = None
    min_order_qty: int | None = None
    price: Decimal | None = None
    price_on_request: bool = False


@dataclass(frozen=True, kw_only=True)
class GroundedProduct:
    """Produto no bloco CONTEXTO (JSON enxuto) entregue ao LLM."""

    product_id: str
    name: str
    sku: str
    brand: str
    category: str
    price: float | None
    price_on_request: bool
    stock: int | None
    attributes: Mapping[str, str]
    ca_status: str | None
    ca_number: str | None
    min_order_qty: int | None

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "id": self.product_id,
            "nome": self.name,
            "sku": self.sku,
            "preco": self.price,
            "preco_sob_consulta": self.price_on_request,
        }
        if self.brand:
            data["marca"] = self.brand
        if self.category:
            data["categoria"] = self.category
        if self.stock is not None:
            data["estoque"] = self.stock
        if self.attributes:
            data["atributos"] = dict(self.attributes)
        if self.ca_status is not None:
            data["ca_status"] = self.ca_status
        if self.ca_number is not None:
            data["ca"] = self.ca_number
        if self.min_order_qty is not None:
            data["qtd_minima"] = self.min_order_qty
        return data


@dataclass(frozen=True, kw_only=True)
class ToolOrderStatus:
    """Pedido do usuario (sem valores monetarios no contexto do LLM)."""

    order_id: str
    status: str
    created_at: str
    item_count: int


@dataclass(frozen=True, kw_only=True)
class QuarantinedDocument:
    """Documento suspeito (audit): product_id + motivo estavel, sem conteudo."""

    product_id: str
    reason_code: str | None


@dataclass(frozen=True, kw_only=True)
class ToolOutput:
    """Saida de ferramenta: texto sanitizado + ids do turno + quarentena."""

    context_text: str
    product_ids: tuple[str, ...]
    quarantined: tuple[QuarantinedDocument, ...] = ()
    reason_code: str | None = None
    price_scan_capped: bool = False
    grounded: tuple[GroundedProduct, ...] = ()
    allowed_prices: frozenset[Decimal] = frozenset()

    def grounded_json(self, *, limit: int = 5) -> str:
        if not self.grounded:
            return ""
        return json.dumps(
            [product.as_dict() for product in self.grounded[:limit]],
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True, kw_only=True)
class ProductSearchResult:
    """Produtos do turno + se o teto de varredura por preco foi atingido."""

    products: tuple[ToolProduct, ...]
    capped: bool = False


class ProductSearchPort(Protocol):
    """Adaptador da busca existente (composicao em app/wiring)."""

    async def search(
        self,
        *,
        query: str,
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
    ) -> ProductSearchResult: ...

    async def get(self, *, product_ref: str, locale: str, auth: Any) -> ToolProduct | None: ...


class CategoriesPort(Protocol):
    async def list_categories(self, *, locale: str) -> list[str]: ...


class OrderStatusPort(Protocol):
    async def get_order_status(
        self, *, order_id: str, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> ToolOrderStatus | None: ...


_SHIPPING_POLICY = {
    "pt-BR": (
        "Frete simulado no checkout: valor base de R$ {base} mais R$ {rate} por kg "
        "do pedido. Nao ha promessa de prazo de entrega."
    ),
    "en": (
        "Shipping is simulated at checkout: a base fee of R$ {base} plus R$ {rate} "
        "per kg of the order. No delivery deadline is promised."
    ),
    "es": (
        "El envio es simulado en el checkout: una tarifa base de R$ {base} mas R$ {rate} "
        "por kg del pedido. No se promete plazo de entrega."
    ),
    "ar": (
        "يُحتسب الشحن في الدفع: رسم أساسي {base} ريال Brazilian real أي R$ {base} "
        "زائد R$ {rate} لكل كيلوغرام من الطلب. لا يوجد وعد بمدة التسليم."
    ),
    "de": (
        "Der Versand wird an der Kasse simuliert: Grundbetrag R$ {base} plus R$ {rate} "
        "pro kg der Bestellung. Es wird keine Lieferfrist zugesagt."
    ),
    "fr": (
        "La livraison est simulée au paiement : forfait de base R$ {base} plus R$ {rate} "
        "par kg de la commande. Aucun délai de livraison n'est promis."
    ),
    "it": (
        "La spedizione è simulata al checkout: tariffa base R$ {base} più R$ {rate} "
        "per kg dell'ordine. Nessun termine di consegna è promesso."
    ),
    "ja": (
        "送料はチェックアウト時にシミュレーションされます：基本料金 R$ {base} に "  # noqa: RUF001
        "1kg あたり R$ {rate} を加算します。お届け期限の約束はありません。"
    ),
    "ko": (
        "배송비는 결제 시 시뮬레이션됩니다: 기본료 R$ {base}에 주문 1kg당 "
        "R$ {rate}를 더합니다. 배송 기한은 약속하지 않습니다."
    ),
    "ru": (
        "Доставка рассчитывается при оформлении: базовая ставка R$ {base} плюс "
        "R$ {rate} за кг заказа. Сроки доставки не обещаются."
    ),
    "zh-CN": (
        "运费在结账时模拟计算：基础费用 R$ {base} 加上每公斤 R$ {rate}。不承诺配送期限。"  # noqa: RUF001
    ),
}


class CatalogTools:
    """Executa as ferramentas somente leitura e sanitiza a saida."""

    def __init__(
        self,
        *,
        search_port: ProductSearchPort,
        categories_port: CategoriesPort,
        order_status_port: OrderStatusPort | None = None,
    ) -> None:
        self._search = search_port
        self._categories = categories_port
        self._order_status = order_status_port

    async def search_products(
        self, args: SearchProductsArgs, *, locale: str, auth: Any
    ) -> ToolOutput:
        result = await self._search.search(
            query=args.query,
            category=args.category,
            limit=min(args.limit, 6),
            locale=locale,
            auth=auth,
            price_sort=args.price_sort,
            price_min=args.price_min,
            price_max=args.price_max,
            brand=args.brand,
            attributes=args.attributes,
            offset=args.offset,
        )
        return _sanitize(result.products, price_scan_capped=result.capped, auth=auth)

    async def get_product(self, args: GetProductArgs, *, locale: str, auth: Any) -> ToolOutput:
        product = await self._search.get(product_ref=args.product_ref, locale=locale, auth=auth)
        if product is None:
            return ToolOutput(context_text="", product_ids=(), reason_code="product_not_found")
        return _sanitize((product,), auth=auth)

    async def compare_products(
        self, args: CompareProductsArgs, *, locale: str, auth: Any
    ) -> ToolOutput:
        products: list[ToolProduct] = []
        for ref in args.product_refs:
            product = await self._search.get(product_ref=ref, locale=locale, auth=auth)
            if product is not None:
                products.append(product)
        return _sanitize_compare(products, auth=auth)

    async def get_order_status(self, args: OrderStatusArgs, *, auth: Any) -> ToolOutput:
        if auth is None:
            return ToolOutput(context_text="", product_ids=(), reason_code="login_required")
        if self._order_status is None:
            return ToolOutput(context_text="", product_ids=(), reason_code="tool_unavailable")
        order = await self._order_status.get_order_status(
            order_id=args.order_id,
            company_id=auth.company_id,
            user_id=auth.user_id,
        )
        if order is None:
            return ToolOutput(context_text="", product_ids=(), reason_code="order_not_found")
        text = (
            f"pedido_id={order.order_id}; status={order.status}; "
            f"criado_em={order.created_at}; itens={order.item_count}"
        )
        doc = sanitize_tool_text(text, label="pedido", max_chars=400)
        if doc.quarantined or not doc.context_text:
            return ToolOutput(context_text="", product_ids=(), reason_code="order_sanitized")
        return ToolOutput(context_text=doc.context_text, product_ids=())

    async def list_categories(self, args: ListCategoriesArgs, *, locale: str) -> ToolOutput:
        names = await self._categories.list_categories(locale=locale)
        # Nomes de categoria sao dados de catalogo: sanitizador por item.
        text_parts: list[str] = []
        quarantined: list[QuarantinedDocument] = []
        for index, name in enumerate(names):
            doc = sanitize_catalog_document(
                {"id": f"cat-{index}", "name": name, "sku": "", "brand": "", "category": name}
            )
            if doc.quarantined or not doc.context_text:
                quarantined.append(
                    QuarantinedDocument(
                        product_id=f"cat-{index}", reason_code=doc.reason_code or "empty"
                    )
                )
                continue
            text_parts.append(doc.context_text)
        return ToolOutput(
            context_text="\n".join(text_parts),
            product_ids=(),
            quarantined=tuple(quarantined),
        )

    def get_shipping_policy(self, args: ShippingPolicyArgs, *, locale: str) -> ToolOutput:
        template = _SHIPPING_POLICY.get(locale, _SHIPPING_POLICY["pt-BR"])
        text = template.format(base=f"{BASE_FREIGHT:.2f}", rate=f"{RATE_PER_KG:.2f}")
        return ToolOutput(context_text=text, product_ids=())


def build_tool_registry() -> ToolRegistry:
    """Allowlist por no do grafo (Fase 2): so estas ferramentas, so leitura."""
    registry = ToolRegistry()
    for spec in (
        ToolSpec(
            name="search_products",
            description="Busca produtos do catalogo (somente leitura)",
            schema=SearchProductsArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
        ToolSpec(
            name="get_product",
            description="Detalhe de um produto por id/slug/SKU (somente leitura)",
            schema=GetProductArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
        ToolSpec(
            name="compare_products",
            description="Compara 2 a 4 produtos (somente leitura)",
            schema=CompareProductsArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
        ToolSpec(
            name="get_order_status",
            description="Status de um pedido do proprio usuario (somente leitura)",
            schema=OrderStatusArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
        ToolSpec(
            name="list_categories",
            description="Lista categorias do catalogo (somente leitura)",
            schema=ListCategoriesArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
        ToolSpec(
            name="get_shipping_policy",
            description="Regra publica de frete simulado (somente leitura)",
            schema=ShippingPolicyArgs,
            allowed_nodes=frozenset({CHAT_NODE}),
        ),
    ):
        registry.register(spec)
    return registry


def _sanitize(
    products: Sequence[ToolProduct], *, price_scan_capped: bool = False, auth: Any = None
) -> ToolOutput:
    texts: list[str] = []
    allowed_ids: list[str] = []
    valid_products: list[ToolProduct] = []
    quarantined: list[QuarantinedDocument] = []
    for product in products:
        doc = _sanitize_product_doc(product)
        if doc.quarantined or not doc.context_text:
            quarantined.append(
                QuarantinedDocument(
                    product_id=product.product_id, reason_code=doc.reason_code or "empty"
                )
            )
            continue
        texts.append(doc.context_text)
        allowed_ids.append(product.product_id)
        valid_products.append(product)
    grounded, prices = _grounded_products(valid_products, auth)
    return ToolOutput(
        context_text="\n".join(texts),
        product_ids=tuple(allowed_ids),
        quarantined=tuple(quarantined),
        price_scan_capped=price_scan_capped,
        grounded=grounded,
        allowed_prices=prices,
    )


def _sanitize_compare(products: Sequence[ToolProduct], *, auth: Any = None) -> ToolOutput:
    texts: list[str] = []
    allowed_ids: list[str] = []
    valid_products: list[ToolProduct] = []
    quarantined: list[QuarantinedDocument] = []
    for product in products:
        doc = _sanitize_product_doc(product)
        if doc.quarantined or not doc.context_text:
            quarantined.append(
                QuarantinedDocument(
                    product_id=product.product_id, reason_code=doc.reason_code or "empty"
                )
            )
            continue
        texts.append(doc.context_text)
        allowed_ids.append(product.product_id)
        valid_products.append(product)
    grounded, prices = _grounded_products(valid_products, auth)
    if len(allowed_ids) < 2:
        return ToolOutput(
            context_text="",
            product_ids=tuple(allowed_ids),
            quarantined=tuple(quarantined),
            reason_code="compare_needs_two",
        )
    return ToolOutput(
        context_text="comparacao_de_produtos:\n" + "\n---\n".join(texts),
        product_ids=tuple(allowed_ids),
        quarantined=tuple(quarantined),
        grounded=grounded,
        allowed_prices=prices,
    )


def _sanitize_product_doc(product: ToolProduct) -> CatalogSanitizeResult:
    doc: dict[str, object] = {
        "id": product.product_id,
        "name": product.name,
        "sku": product.sku,
        "brand": product.brand,
        "category": product.category,
        "attributes": dict(product.attributes or {}),
        "description": product.description,
    }
    if product.stock_quantity is not None:
        doc["stock"] = product.stock_quantity
    if product.ca_status is not None:
        doc["ca_status"] = product.ca_status
    if product.ca_number is not None:
        doc["ca_number"] = product.ca_number
    if product.min_order_qty is not None:
        doc["min_order_qty"] = product.min_order_qty
    return sanitize_catalog_document(doc, include_description=True)


def _grounded_products(
    products: Sequence[ToolProduct], auth: Any
) -> tuple[tuple[GroundedProduct, ...], frozenset[Decimal]]:
    grounded: list[GroundedProduct] = []
    prices: set[Decimal] = set()
    for product in products[:5]:
        price: float | None = None
        price_on_request = True
        if auth is not None and product.price is not None:
            value = Decimal(str(product.price)).quantize(Decimal("0.01"))
            price = float(value)
            price_on_request = False
            prices.add(value)
        grounded.append(
            GroundedProduct(
                product_id=product.product_id,
                name=product.name,
                sku=product.sku,
                brand=product.brand,
                category=product.category,
                price=price,
                price_on_request=price_on_request,
                stock=product.stock_quantity,
                attributes=_grounded_attributes(product.attributes),
                ca_status=product.ca_status,
                ca_number=product.ca_number,
                min_order_qty=product.min_order_qty,
            )
        )
    return tuple(grounded), frozenset(prices)


def _grounded_attributes(attributes: object) -> dict[str, str]:
    if not isinstance(attributes, Mapping):
        return {}
    result: dict[str, str] = {}
    for raw_key, raw_value in list(attributes.items())[:3]:
        key = normalize_user_text(str(raw_key), max_chars=40).text
        value = normalize_user_text(str(raw_value), max_chars=60).text
        if key and value and scan_injection(f"{key}={value}").level.value != "BLOCK":
            result[key] = value
    return result
