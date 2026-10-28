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

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import Field

from app.domain.shipping import BASE_FREIGHT, RATE_PER_KG
from app.modules.ai.application.security.tools import ToolRegistry, ToolSchema, ToolSpec
from app.modules.ai.domain.security.catalog_sanitizer import sanitize_catalog_document

CHAT_NODE = "chat"
MAX_TOOL_CALLS = 4

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,59}$"


class SearchProductsArgs(ToolSchema):
    """Busca no catalogo (consulta curta + categoria opcional + limite <= 6)."""

    query: str = Field(min_length=2, max_length=200)
    category: str | None = Field(default=None, pattern=_SLUG_PATTERN)
    limit: int = Field(default=5, ge=1, le=6)


class GetProductArgs(ToolSchema):
    """Detalhe de UM produto por id (UUID)."""

    product_id: str = Field(pattern=_UUID_PATTERN)


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
    ) -> list[ToolProduct]: ...

    async def get(self, *, product_id: uuid.UUID, locale: str, auth: Any) -> ToolProduct | None: ...


class CategoriesPort(Protocol):
    async def list_categories(self, *, locale: str) -> list[str]: ...


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

    def __init__(self, *, search_port: ProductSearchPort, categories_port: CategoriesPort) -> None:
        self._search = search_port
        self._categories = categories_port

    async def search_products(
        self, args: SearchProductsArgs, *, locale: str, auth: Any
    ) -> ToolOutput:
        products = await self._search.search(
            query=args.query,
            category=args.category,
            limit=min(args.limit, 6),
            locale=locale,
            auth=auth,
        )
        return _sanitize(products)

    async def get_product(self, args: GetProductArgs, *, locale: str, auth: Any) -> ToolOutput:
        product = await self._search.get(
            product_id=uuid.UUID(args.product_id), locale=locale, auth=auth
        )
        return _sanitize([product] if product else [])

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
            description="Detalhe de um produto por id (somente leitura)",
            schema=GetProductArgs,
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


def _sanitize(products: Sequence[ToolProduct]) -> ToolOutput:
    texts: list[str] = []
    allowed_ids: list[str] = []
    quarantined: list[QuarantinedDocument] = []
    for product in products:
        doc = sanitize_catalog_document(
            {
                "id": product.product_id,
                "name": product.name,
                "sku": product.sku,
                "brand": product.brand,
                "category": product.category,
                "attributes": dict(product.attributes or {}),
                "description": product.description,
            },
            include_description=True,
        )
        if doc.quarantined or not doc.context_text:
            quarantined.append(
                QuarantinedDocument(
                    product_id=product.product_id, reason_code=doc.reason_code or "empty"
                )
            )
            continue
        texts.append(doc.context_text)
        allowed_ids.append(product.product_id)
    return ToolOutput(
        context_text="\n".join(texts),
        product_ids=tuple(allowed_ids),
        quarantined=tuple(quarantined),
    )
