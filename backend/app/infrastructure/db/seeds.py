"""Seeds deterministicos para desenvolvimento e testes (Fase 1).

Dados fixos e reproduziveis, independentes de servicos externos. Idempotentes
(``ON CONFLICT (id) DO NOTHING``) e faceis de resetar (``make down-volumes`` +
``make migrate`` + seed).

Aplicados com a role administrativa (``DATABASE_ADMIN_URL``): o catalogo e
global (sem RLS), e os dados de tenant sao inseridos com o contexto de
empresa definido na mesma transacao (a policy RLS exige ``company_id``).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

# PEPPER de desenvolvimento (mesmo valor publicado em .env.example). NUNCA
# usar em producao: a Fase 2 (backend+security) assume o hash/criptografia.
DEFAULT_DEV_PEPPER = "dev_pepper_secret_for_cpf_hmac_2026"

# ---------------------------------------------------------------------------
# Identificadores deterministicos (UUIDs fixos para reproducao)
# ---------------------------------------------------------------------------
EXAMPLE_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")

ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
BUYER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")
APPROVER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000203")
FINANCE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000204")

ADMIN_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000205")
BUYER_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000206")
APPROVER_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000207")
FINANCE_MEMBER_ID = uuid.UUID("00000000-0000-0000-0000-000000000208")

SHIPPING_ADDRESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000209")
BILLING_ADDRESS_ID = uuid.UUID("00000000-0000-0000-0000-00000000020a")

CREDIT_LIMIT_ENTRY_ID = uuid.UUID("00000000-0000-0000-0000-00000000020b")

CONSENT_TERMS_ID = uuid.UUID("00000000-0000-0000-0000-00000000020c")
CONSENT_PRIVACY_ID = uuid.UUID("00000000-0000-0000-0000-00000000020d")

AUDIT_APPROVED_ID = uuid.UUID("00000000-0000-0000-0000-00000000020e")

CATEGORY_EPI_ID = uuid.UUID("00000000-0000-0000-0000-000000000401")
CATEGORY_MAQUINAS_ID = uuid.UUID("00000000-0000-0000-0000-000000000402")

BRAND_PROTEC_ID = uuid.UUID("00000000-0000-0000-0000-000000000501")
BRAND_NORTON_ID = uuid.UUID("00000000-0000-0000-0000-000000000502")

PRODUCT_CAPACETE_ID = uuid.UUID("00000000-0000-0000-0000-000000000301")
PRODUCT_LUVA_ID = uuid.UUID("00000000-0000-0000-0000-000000000302")
PRODUCT_RESPIRADOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000303")
PRODUCT_PARAFUSADEIRA_ID = uuid.UUID("00000000-0000-0000-0000-000000000304")

TIER_CAPACETE_1_ID = uuid.UUID("00000000-0000-0000-0000-000000000601")
TIER_CAPACETE_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000602")
TIER_PARAFUSADEIRA_1_ID = uuid.UUID("00000000-0000-0000-0000-000000000603")
TIER_PARAFUSADEIRA_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000604")

EXAMPLE_CREDIT_LIMIT = Decimal("50000.00")


def cpf_hash(cpf: str, pepper: str) -> str:
    """HMAC-SHA256(cpf, pepper): o mesmo esquema que a Fase 2 usara.

    Nenhum CPF e armazenado em texto claro; apenas o hash deterministico para
    unicidade ("um CPF, uma conta").
    """
    return hmac.new(pepper.encode("utf-8"), cpf.encode("utf-8"), hashlib.sha256).hexdigest()


async def _seed_global_catalog(conn: AsyncConnection) -> int:
    rows = 0
    rows += await _insert(conn, "categories", _CATEGORIES)
    rows += await _insert(conn, "brands", _BRANDS)
    rows += await _insert(
        conn,
        "products",
        _PRODUCTS,
        casts={"attributes": "jsonb"},
    )
    rows += await _insert(conn, "product_price_tiers", _TIERS)
    return rows


async def _seed_tenant(conn: AsyncConnection, pepper: str) -> int:
    rows = 0
    await conn.execute(
        text("SELECT app.set_tenant_context(:company_id, NULL)"),
        {"company_id": EXAMPLE_COMPANY_ID},
    )
    rows += await _insert(conn, "companies", _COMPANIES)
    rows += await _insert(conn, "company_addresses", _ADDRESSES)
    rows += await _insert(conn, "users", _USERS(pepper))
    rows += await _insert(conn, "company_members", _MEMBERS)
    rows += await _insert(conn, "credit_accounts", _CREDIT_ACCOUNTS, conflict_column="company_id")
    rows += await _insert(conn, "credit_entries", _CREDIT_ENTRIES)
    rows += await _insert(conn, "consent_records", _CONSENTS)
    rows += await _insert(conn, "audit_log", _AUDIT, casts={"details": "jsonb"})
    return rows


async def _insert(
    conn: AsyncConnection,
    table: str,
    rows_data: list[dict[str, object]],
    *,
    conflict_column: str = "id",
    casts: dict[str, str] | None = None,
) -> int:
    casts = casts or {}
    for row in rows_data:
        columns = ", ".join(row)
        placeholders = ", ".join(
            f"CAST(:{col} AS {casts[col]})" if col in casts else f":{col}" for col in row
        )
        await conn.execute(
            text(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_column}) DO NOTHING"
            ),
            row,
        )
    return len(rows_data)


async def seed_database(admin_url: str, pepper: str = DEFAULT_DEV_PEPPER) -> dict[str, int]:
    """Aplica os seeds e devolve um relatorio de linhas tentadas por tabela."""
    engine = create_async_engine(admin_url)
    try:
        async with engine.begin() as conn:
            catalog = await _seed_global_catalog(conn)
            tenant = await _seed_tenant(conn, pepper)
    finally:
        await engine.dispose()
    return {"catalog_rows": catalog, "tenant_rows": tenant}


def main() -> None:
    """Entrypoint CLI: ``python -m app.infrastructure.db.seeds``."""
    admin_url = os.environ.get("DATABASE_ADMIN_URL")
    if not admin_url:
        raise SystemExit("DATABASE_ADMIN_URL ausente: seeds usam a role administrativa.")
    pepper = os.environ.get("PEPPER", DEFAULT_DEV_PEPPER)
    report = asyncio.run(seed_database(admin_url, pepper))
    print(json.dumps(report, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Dados (constantes) - valores deterministicos
# ---------------------------------------------------------------------------
_APPROVED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_COMPANIES = [
    {
        "id": EXAMPLE_COMPANY_ID,
        "cnpj": "11444777000161",
        "legal_name": "Construtora Exemplo Ltda",
        "trade_name": "Construtora Exemplo",
        "state_registration": "123456789",
        "status": "ACTIVE",
        "approved_at": _APPROVED_AT,
    },
]

_ADDRESSES = [
    {
        "id": SHIPPING_ADDRESS_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "address_type": "SHIPPING",
        "street": "Avenida Industrial",
        "number": "1200",
        "complement": "Galpao 3",
        "district": "Distrito Industrial",
        "city": "Sao Paulo",
        "state": "SP",
        "postal_code": "01310100",
        "is_default": True,
    },
    {
        "id": BILLING_ADDRESS_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "address_type": "BILLING",
        "street": "Avenida Industrial",
        "number": "1200",
        "complement": "Sala 10",
        "district": "Distrito Industrial",
        "city": "Sao Paulo",
        "state": "SP",
        "postal_code": "01310100",
        "is_default": False,
    },
]


def _USERS(pepper: str) -> list[dict[str, object]]:
    return [
        {
            "id": ADMIN_USER_ID,
            "company_id": EXAMPLE_COMPANY_ID,
            "email": "admin@exemplo.com.br",
            "full_name": "Administrador Exemplo",
            "phone": "+5511999990001",
            "cpf_hash": cpf_hash("52998224725", pepper),
            "status": "ACTIVE",
            "email_verified_at": _APPROVED_AT,
        },
        {
            "id": BUYER_USER_ID,
            "company_id": EXAMPLE_COMPANY_ID,
            "email": "comprador@exemplo.com.br",
            "full_name": "Comprador Exemplo",
            "phone": "+5511999990002",
            "cpf_hash": cpf_hash("11144477735", pepper),
            "status": "ACTIVE",
            "email_verified_at": _APPROVED_AT,
        },
        {
            "id": APPROVER_USER_ID,
            "company_id": EXAMPLE_COMPANY_ID,
            "email": "aprovador@exemplo.com.br",
            "full_name": "Aprovador Exemplo",
            "phone": "+5511999990003",
            "cpf_hash": cpf_hash("31096288851", pepper),
            "status": "ACTIVE",
            "email_verified_at": _APPROVED_AT,
        },
        {
            "id": FINANCE_USER_ID,
            "company_id": EXAMPLE_COMPANY_ID,
            "email": "financeiro@exemplo.com.br",
            "full_name": "Financeiro Exemplo",
            "phone": "+5511999990004",
            "cpf_hash": cpf_hash("45994494219", pepper),
            "status": "ACTIVE",
            "email_verified_at": _APPROVED_AT,
        },
    ]


_MEMBERS = [
    {
        "id": ADMIN_MEMBER_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": ADMIN_USER_ID,
        "role": "ADMIN",
        "status": "ACTIVE",
    },
    {
        "id": BUYER_MEMBER_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": BUYER_USER_ID,
        "role": "BUYER",
        "status": "ACTIVE",
    },
    {
        "id": APPROVER_MEMBER_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": APPROVER_USER_ID,
        "role": "APPROVER",
        "status": "ACTIVE",
    },
    {
        "id": FINANCE_MEMBER_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": FINANCE_USER_ID,
        "role": "FINANCE",
        "status": "ACTIVE",
    },
]

_CREDIT_ACCOUNTS = [
    {"company_id": EXAMPLE_COMPANY_ID, "credit_limit": EXAMPLE_CREDIT_LIMIT},
]

_CREDIT_ENTRIES = [
    {
        "id": CREDIT_LIMIT_ENTRY_ID,
        "credit_account_id": EXAMPLE_COMPANY_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "entry_type": "LIMIT_SET",
        "amount": EXAMPLE_CREDIT_LIMIT,
        "reference_type": "company",
        "reference_id": EXAMPLE_COMPANY_ID,
        "description": "Limite inicial aprovado pelo backoffice (seed).",
    },
]

_CONSENTS = [
    {
        "id": CONSENT_TERMS_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": ADMIN_USER_ID,
        "purpose": "TERMS",
        "action": "GRANTED",
        "version": "v1.0",
        "document_hash": "a" * 64,
        "ip_address": "127.0.0.1",
        "user_agent": "seed",
    },
    {
        "id": CONSENT_PRIVACY_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "user_id": ADMIN_USER_ID,
        "purpose": "PRIVACY",
        "action": "GRANTED",
        "version": "v1.0",
        "document_hash": "b" * 64,
        "ip_address": "127.0.0.1",
        "user_agent": "seed",
    },
]

_AUDIT = [
    {
        "id": AUDIT_APPROVED_ID,
        "company_id": EXAMPLE_COMPANY_ID,
        "actor_user_id": ADMIN_USER_ID,
        "action": "company.approved",
        "resource": "company",
        "resource_id": EXAMPLE_COMPANY_ID,
        "details": json.dumps({"credit_limit": "50000.00"}),
    },
]

_CATEGORIES = [
    {"id": CATEGORY_EPI_ID, "name": "EPIs", "slug": "epis", "is_active": True},
    {
        "id": CATEGORY_MAQUINAS_ID,
        "name": "Maquinas e Ferramentas",
        "slug": "maquinas-e-ferramentas",
        "is_active": True,
    },
]

_BRANDS = [
    {"id": BRAND_PROTEC_ID, "name": "PROTEC", "slug": "protec"},
    {"id": BRAND_NORTON_ID, "name": "NORTON", "slug": "norton"},
]

_PRODUCTS = [
    {
        "id": PRODUCT_CAPACETE_ID,
        "category_id": CATEGORY_EPI_ID,
        "brand_id": BRAND_PROTEC_ID,
        "sku": "EPI-CAP-001",
        "name": "Capacete de Seguranca Pro",
        "slug": "capacete-de-seguranca-pro",
        "description": "Capacete de seguranca classe B com suspensao ajustavel.",
        "status": "ACTIVE",
        "is_epi": True,
        "ca_number": "CA-12345",
        "ca_valid_until": date(2028, 12, 31),
        "ncm": "65061000",
        "unit_of_measure": "UN",
        "weight_kg": Decimal("0.45"),
        "min_order_qty": 6,
        "base_unit_price": Decimal("24.90"),
        "attributes": json.dumps({"cor": "branco", "material": "abs"}),
    },
    {
        "id": PRODUCT_LUVA_ID,
        "category_id": CATEGORY_EPI_ID,
        "brand_id": BRAND_PROTEC_ID,
        "sku": "EPI-LUV-002",
        "name": "Luva de Raspa Premium",
        "slug": "luva-de-raspa-premium",
        "status": "ACTIVE",
        "is_epi": True,
        "ca_number": "CA-54321",
        "ca_valid_until": date(2027, 6, 30),
        "ncm": "61161000",
        "unit_of_measure": "PAR",
        "weight_kg": Decimal("0.12"),
        "min_order_qty": 12,
        "base_unit_price": Decimal("12.50"),
    },
    {
        "id": PRODUCT_RESPIRADOR_ID,
        "category_id": CATEGORY_EPI_ID,
        "brand_id": BRAND_PROTEC_ID,
        "sku": "EPI-RES-003",
        "name": "Respirador PFF2",
        "slug": "respirador-pff2",
        "status": "ACTIVE",
        "is_epi": True,
        "ca_number": "CA-99999",
        "ca_valid_until": date(2023, 1, 1),
        "ncm": "63079090",
        "unit_of_measure": "UN",
        "weight_kg": Decimal("0.02"),
        "min_order_qty": 10,
        "base_unit_price": Decimal("8.90"),
    },
    {
        "id": PRODUCT_PARAFUSADEIRA_ID,
        "category_id": CATEGORY_MAQUINAS_ID,
        "brand_id": BRAND_NORTON_ID,
        "sku": "MAQ-PAR-004",
        "name": "Parafusadeira de Impacto 20V",
        "slug": "parafusadeira-de-impacto-20v",
        "status": "ACTIVE",
        "is_epi": False,
        "ncm": "84672100",
        "unit_of_measure": "UN",
        "weight_kg": Decimal("1.80"),
        "min_order_qty": 1,
        "base_unit_price": Decimal("899.00"),
    },
]

_TIERS = [
    {
        "id": TIER_CAPACETE_1_ID,
        "product_id": PRODUCT_CAPACETE_ID,
        "min_quantity": 6,
        "max_quantity": 23,
        "unit_price": Decimal("24.90"),
    },
    {
        "id": TIER_CAPACETE_2_ID,
        "product_id": PRODUCT_CAPACETE_ID,
        "min_quantity": 24,
        "max_quantity": None,
        "unit_price": Decimal("21.90"),
    },
    {
        "id": TIER_PARAFUSADEIRA_1_ID,
        "product_id": PRODUCT_PARAFUSADEIRA_ID,
        "min_quantity": 1,
        "max_quantity": 4,
        "unit_price": Decimal("899.00"),
    },
    {
        "id": TIER_PARAFUSADEIRA_2_ID,
        "product_id": PRODUCT_PARAFUSADEIRA_ID,
        "min_quantity": 5,
        "max_quantity": None,
        "unit_price": Decimal("849.00"),
    },
]


if __name__ == "__main__":
    main()
