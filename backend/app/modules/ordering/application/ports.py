"""Portas do contexto de pedidos (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.pricing import CompanyPriceRule, PriceTier
from app.modules.ordering.domain.coupon import Coupon, CouponType


@dataclass(frozen=True, kw_only=True)
class ProductForOrder:
    """Produto + tiers + regras de empresa para validar e precificar um item."""

    id: uuid.UUID
    sku: str
    name: str
    status: str
    is_epi: bool
    ca_valid_until: date | None
    category_id: uuid.UUID
    base_unit_price: Decimal
    min_order_qty: int
    weight_kg: Decimal | None
    tiers: list[PriceTier]
    company_rules: list[CompanyPriceRule]


@dataclass(frozen=True, kw_only=True)
class OrderItemInput:
    product_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, kw_only=True)
class ResolvedItem:
    """Item com preco resolvido e snapshot pronto para persistir."""

    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price: Decimal
    base_unit_price: Decimal
    tier_min_quantity: int | None
    price_tier_id: uuid.UUID | None
    line_total: Decimal
    # Recuperacao de carrinho (FASE 4): desconto de 3% NAO se aplica a linhas
    # com preco negociado (PriceSource.NEGOTIATED).
    is_negotiated: bool = False


@dataclass(frozen=True, kw_only=True)
class RecoveryOfferView:
    """Oferta de recuperacao ativa do carrinho do comprador (uso unico)."""

    id: uuid.UUID
    type: str  # FREE_SHIPPING | PERCENT_DISCOUNT
    percent: Decimal | None


@dataclass(frozen=True, kw_only=True)
class CheckoutCartItem:
    """Linha do carrinho do proprio comprador usada na simulacao do checkout."""

    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    weight_kg: Decimal | None
    is_negotiated: bool


@dataclass(frozen=True, kw_only=True)
class CheckoutCartSnapshot:
    """Carrinho do comprador com totais ja resolvidos pelo carrinho."""

    items: list[CheckoutCartItem]
    subtotal: Decimal


@dataclass(frozen=True, kw_only=True)
class CouponForCheckout:
    """Cupom + contagens de uso para validar no checkout."""

    coupon: Coupon
    total_uses: int
    company_uses: int


@dataclass(frozen=True, kw_only=True)
class OrderItemView:
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    base_unit_price: Decimal | None
    tier_min_quantity: int | None
    line_total: Decimal
    content_locale: str


@dataclass(frozen=True, kw_only=True)
class OrderView:
    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[OrderItemView]
    created_at: datetime
    content_locale: str
    coupon_code: str | None = None
    coupon_type: CouponType | None = None
    coupon_percent: Decimal | None = None
    coupon_discount_amount: Decimal = Decimal("0.00")
    shipping_discount_amount: Decimal = Decimal("0.00")


class OrderingRepository(Protocol):
    """Persistencia de pedidos (snapshot + credito atomico)."""

    async def get_product_for_order(
        self, company_id: uuid.UUID, product_id: uuid.UUID, locale: str = "pt-BR"
    ) -> ProductForOrder | None:
        """Le produto + tiers + regras da empresa para validacao/precificacao."""

    async def find_active_offer(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID
    ) -> RecoveryOfferView | None:
        """Oferta nao expirada/nao resgatada do carrinho do comprador."""

    async def get_coupon_for_checkout(
        self, code: str, company_id: uuid.UUID
    ) -> CouponForCheckout | None:
        """Cupom normalizado + usos APPLIED totais/da empresa (somente leitura)."""

    async def create_order(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        items: list[ResolvedItem],
        payment_method: str,
        idempotency_key: str,
        po_number: str | None,
        notes: str | None,
        subtotal: Decimal,
        shipping_total: Decimal,
        total: Decimal,
        content_locale: str,
        discount_total: Decimal = Decimal("0.00"),
        recovery_offer_id: uuid.UUID | None = None,
        coupon_code: str | None = None,
    ) -> OrderView:
        """Cria pedido (snapshot) + reserva credito (boleto) + resgata oferta
        de recuperacao na MESMA transacao (uso unico).

        Com ``coupon_code``, o cupom e bloqueado/revalidado e o resgate e
        inserido na mesma transacao; o total gravado usa o recalculo do
        servidor, nao o valor recebido.
        """

    async def get_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView | None:
        """Consulta um pedido do tenant (com itens)."""

    async def cancel_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        """Cancela o pedido e libera a reserva de credito (se houver)."""


class CheckoutCartReader(Protocol):
    """Leitura do carrinho do comprador para a previa do checkout."""

    async def get_checkout_cart(
        self, company_id: uuid.UUID, user_id: uuid.UUID, locale: str = "pt-BR"
    ) -> CheckoutCartSnapshot | None:
        """Carrinho ativo com itens precificados; None quando nao existir."""
