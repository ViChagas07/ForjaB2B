"""Pacote de mapeadores ORM da Fase 1.

Importar este pacote registra todas as tabelas no ``Base.metadata`` (usado
como ``target_metadata`` do Alembic). Os mapeadores sao centralizados aqui,
e nao por modulo, porque o schema relacional e intrinsecamente transversal
(FKs entre agregados) e os bounded contexts nao podem importar internals uns
dos outros (contrato import-linter).
"""

from __future__ import annotations

from app.infrastructure.db.models.audit import AuditLog
from app.infrastructure.db.models.cart import Cart, CartItem
from app.infrastructure.db.models.catalog import Brand, Category, Product, ProductPriceTier
from app.infrastructure.db.models.companies import Company, CompanyAddress
from app.infrastructure.db.models.credit import CreditAccount, CreditEntry
from app.infrastructure.db.models.external_identity import UserExternalIdentity
from app.infrastructure.db.models.identity import CompanyMember, User
from app.infrastructure.db.models.invoicing import Invoice
from app.infrastructure.db.models.ordering import Order, OrderItem
from app.infrastructure.db.models.privacy import ConsentRecord

__all__ = [
    "AuditLog",
    "Brand",
    "Cart",
    "CartItem",
    "Category",
    "Company",
    "CompanyAddress",
    "CompanyMember",
    "ConsentRecord",
    "CreditAccount",
    "CreditEntry",
    "Invoice",
    "Order",
    "OrderItem",
    "Product",
    "ProductPriceTier",
    "User",
    "UserExternalIdentity",
]
