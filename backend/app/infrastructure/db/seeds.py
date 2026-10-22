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
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import normalize_async_database_url
from app.domain.i18n import TranslationStatus, product_source_hash
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

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


async def _seed_global_catalog(conn: AsyncConnection) -> tuple[int, int]:
    rows = 0
    rows += await _insert(conn, "categories", _ALL_CATEGORIES)
    rows += await _insert(conn, "brands", _ALL_BRANDS)
    rows += await _insert(
        conn,
        "products",
        _ALL_PRODUCTS,
        casts={"attributes": "jsonb"},
    )
    rows += await _insert(conn, "product_price_tiers", _ALL_TIERS)
    # Reexecutar o seed ATUALIZA os precos de demonstracao (sem duplicar): o
    # INSERT acima e ON CONFLICT DO NOTHING, entao um ajuste de preco so entra
    # por aqui, e apenas quando o valor realmente muda.
    await _refresh_demo_prices(conn)
    translations = await _seed_product_translations(conn)
    return rows, translations


async def _refresh_demo_prices(conn: AsyncConnection) -> None:
    """Atualiza os precos de lista/tier de demonstracao quando divergem."""
    for product in _ALL_PRODUCTS:
        await conn.execute(
            text(
                "UPDATE products SET base_unit_price = :price, updated_at = now() "
                "WHERE id = :id AND base_unit_price <> :price"
            ),
            {"price": product["base_unit_price"], "id": product["id"]},
        )
    for tier in _ALL_TIERS:
        await conn.execute(
            text(
                "UPDATE product_price_tiers SET unit_price = :price, updated_at = now() "
                "WHERE id = :id AND unit_price <> :price"
            ),
            {"price": tier["unit_price"], "id": tier["id"]},
        )


async def _seed_product_translations(conn: AsyncConnection) -> int:
    """Carrega as traducoes offline de demonstracao (status=machine, idempotente).

    Le ``seed_data/demo_translations.json`` (origem pt-BR, traduzido offline para
    en/es/ar) e insere/atualiza ``product_translations`` por (product_id, locale).
    O ``source_hash`` e calculado do conteudo de origem pt-BR do produto, mantendo
    o vinculo com a origem: reexecutar o seed mantem os hashes corretos e o status
    em ``machine`` (sem duplicar). Traducoes revisadas manualmente (``reviewed``)
    sao SOBRESCREVIDAS de proposito, já que o seed e fonte unica do demo.
    """
    products_by_sku = {product["sku"]: product for product in _ALL_PRODUCTS}
    locales = _DEMO_TRANSLATIONS["locales"]
    rows = 0
    for sku, product in products_by_sku.items():
        trans = _DEMO_TRANSLATIONS["products"].get(sku)
        if not trans:
            continue
        attrs_raw = product.get("attributes")
        source_attrs = json.loads(cast(str, attrs_raw)) if attrs_raw else None
        source_hash = product_source_hash(
            name=cast(str, product["name"]),
            description=cast("str | None", product.get("description")),
            attributes=source_attrs,
        )
        for locale in locales:
            entry = trans.get(locale)
            if not entry:
                continue
            await conn.execute(
                text(
                    "INSERT INTO product_translations "
                    "(product_id, locale, name, description, attributes, "
                    "source_hash, status, translated_at) "
                    "VALUES (:product_id, :locale, :name, :description, "
                    "CAST(:attributes AS jsonb), :source_hash, :status, "
                    ":translated_at) "
                    "ON CONFLICT (product_id, locale) DO UPDATE SET "
                    "name = EXCLUDED.name, "
                    "description = EXCLUDED.description, "
                    "attributes = EXCLUDED.attributes, "
                    "source_hash = EXCLUDED.source_hash, "
                    "status = EXCLUDED.status, "
                    "translated_at = EXCLUDED.translated_at, "
                    "updated_at = now()"
                ),
                {
                    "product_id": product["id"],
                    "locale": locale,
                    "name": entry["name"],
                    "description": entry.get("description"),
                    "attributes": json.dumps(entry.get("attributes") or {}),
                    "source_hash": source_hash,
                    "status": TranslationStatus.MACHINE.value,
                    "translated_at": datetime.now(UTC),
                },
            )
            rows += 1
    return rows


async def _seed_tenant(conn: AsyncConnection, pepper: str, password_hash: str | None) -> int:
    rows = 0
    await conn.execute(
        text("SELECT app.set_tenant_context(:company_id, NULL)"),
        {"company_id": EXAMPLE_COMPANY_ID},
    )
    rows += await _insert(conn, "companies", _COMPANIES)
    rows += await _insert(conn, "company_addresses", _ADDRESSES)
    rows += await _insert(conn, "users", _USERS(pepper))
    if password_hash is not None:
        # Habilita o login dos usuarios da empresa-exemplo (senha do ambiente).
        for user in _USERS(pepper):
            await conn.execute(
                text(
                    "UPDATE users SET password_hash = :password_hash "
                    "WHERE id = :id AND password_hash IS NULL"
                ),
                {"password_hash": password_hash, "id": user["id"]},
            )
    rows += await _insert(conn, "company_members", _MEMBERS)
    rows += await _insert(conn, "credit_accounts", _CREDIT_ACCOUNTS, conflict_column="company_id")
    rows += await _insert(conn, "credit_entries", _CREDIT_ENTRIES)
    rows += await _insert(conn, "consent_records", _CONSENTS)
    rows += await _insert(conn, "audit_log", _AUDIT, casts={"details": "jsonb"})
    return rows


_UPDATE_PRICE_RULE = text(
    "UPDATE company_price_rules SET rule_type = :rule_type, product_id = :product_id, "
    "category_id = :category_id, percent = :percent, unit_price = :unit_price, "
    "updated_at = now() WHERE id = :id"
)


async def _seed_demo_tenants(conn: AsyncConnection, pepper: str, password_hash: str | None) -> int:
    """Cria as empresas de demonstracao, usuarios (se houver senha) e regras.

    Sem ``password_hash`` (variavel ``DEMO_USER_PASSWORD`` ausente) as empresas e
    regras de preco entram, mas os usuarios NAO sao criados (nao ha como logar).
    Reexecutar atualiza os campos mutaveis das regras (idempotente).
    """
    rows = 0
    for tenant in _build_demo_tenants(pepper, password_hash):
        await conn.execute(
            text("SELECT app.set_tenant_context(CAST(:company_id AS uuid), NULL)"),
            {"company_id": str(tenant.id)},
        )
        rows += await _insert(conn, "companies", [tenant.company])
        rows += await _insert(
            conn, "credit_accounts", [tenant.credit_account], conflict_column="company_id"
        )
        rows += await _insert(conn, "credit_entries", [tenant.credit_entry])
        if password_hash is not None:
            rows += await _insert(conn, "users", tenant.users)
            rows += await _insert(conn, "company_members", tenant.members)
        rows += await _insert(conn, "company_price_rules", tenant.rules)
        for rule in tenant.rules:
            await conn.execute(_UPDATE_PRICE_RULE, rule)
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


async def seed_database(
    admin_url: str,
    pepper: str = DEFAULT_DEV_PEPPER,
    demo_user_password: str | None = None,
) -> dict[str, int]:
    """Aplica os seeds e devolve um relatorio de linhas tentadas por tabela.

    ``demo_user_password`` (tipicamente ``DEMO_USER_PASSWORD``) habilita os
    usuarios das empresas de demonstracao e da empresa-exemplo. Sem ele, os
    usuarios NAO sao criados (somente empresas, regras e catalogo).
    """
    password_hash = Argon2PasswordHasher().hash(demo_user_password) if demo_user_password else None
    engine = create_async_engine(normalize_async_database_url(admin_url))
    try:
        async with engine.begin() as conn:
            catalog, translations = await _seed_global_catalog(conn)
            tenant = await _seed_tenant(conn, pepper, password_hash)
            demo = await _seed_demo_tenants(conn, pepper, password_hash)
    finally:
        await engine.dispose()
    return {
        "catalog_rows": catalog,
        "translation_rows": translations,
        "tenant_rows": tenant,
        "demo_tenant_rows": demo,
        "demo_users_seeded": 1 if password_hash is not None else 0,
    }


def main() -> None:
    """Entrypoint CLI: ``python -m app.infrastructure.db.seeds``.

    Por padrao so roda em desenvolvimento/teste. Em producao exige a flag
    explicita ``SEED_ALLOW_PRODUCTION=true`` (os dados sao ficticios e nao
    devem entrar em ambiente real por acidente). A senha dos usuarios de
    demonstracao vem de ``DEMO_USER_PASSWORD`` (nunca versionada).
    """
    environment = os.environ.get("ENVIRONMENT", "development")
    allow_production = os.environ.get("SEED_ALLOW_PRODUCTION", "false").lower() == "true"
    if environment == "production" and not allow_production:
        raise SystemExit(
            "Seed recusado em producao. Defina SEED_ALLOW_PRODUCTION=true para "
            "executar conscientemente (dados de demonstracao)."
        )
    admin_url = os.environ.get("DATABASE_ADMIN_URL")
    if not admin_url:
        raise SystemExit("DATABASE_ADMIN_URL ausente: seeds usam a role administrativa.")
    pepper = os.environ.get("PEPPER", DEFAULT_DEV_PEPPER)
    demo_user_password = os.environ.get("DEMO_USER_PASSWORD") or None
    if demo_user_password is None:
        print(
            json.dumps(
                {
                    "warning": "DEMO_USER_PASSWORD ausente: os usuarios de "
                    "demonstracao NAO foram criados (somente empresas/regras)."
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
    report = asyncio.run(seed_database(admin_url, pepper, demo_user_password))
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


# ---------------------------------------------------------------------------
# Dados de demonstracao da busca (Fase 3) - FICTICIOS
# ---------------------------------------------------------------------------
# Categorias/marcas/produtos adicionais para exercitar a busca do catalogo:
# acentos e grafias proximas ("Óculos"/"Oculos"), singular/plural
# ("Luva"/"Luvas") e prefixos de autocomplete. As marcas sao INVENTADAS e o CA
# dos EPIs usa o prefixo "DEMO-CA-" (nunca numeros reais de Certificado de
# Aprovacao). Ids deterministicos (uuid5) mantem o seed idempotente com
# ON CONFLICT (id) DO NOTHING: reexecutar nao duplica nem altera nada.

_DEMO_NAMESPACE = uuid.UUID("6d656d6f-0000-4000-8000-0000000000d0")


def _demo_id(kind: str, key: str) -> uuid.UUID:
    """UUID deterministico do catalogo de demonstracao (idempotencia)."""
    return uuid.uuid5(_DEMO_NAMESPACE, f"{kind}:{key}")


def _slugify(value: str) -> str:
    """Slug ASCII deterministico para os itens de demonstracao."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


# (slug, nome, slug_pai|None)
_DEMO_CATEGORY_SPECS: list[tuple[str, str, str | None]] = [
    ("protecao-cabeca", "Proteção da Cabeça", "epis"),
    ("protecao-visual", "Proteção Visual", "epis"),
    ("protecao-maos", "Proteção das Mãos", "epis"),
    ("protecao-respiratoria", "Proteção Respiratória", "epis"),
    ("protecao-auditiva", "Proteção Auditiva", "epis"),
    ("protecao-pes", "Proteção dos Pés", "epis"),
    ("protecao-quedas", "Proteção contra Quedas", "epis"),
    ("ferramentas-eletricas", "Ferramentas Elétricas", "maquinas-e-ferramentas"),
    ("maquinas-estacionarias", "Máquinas Estacionárias", "maquinas-e-ferramentas"),
]

# (slug, nome) - marcas FICTICIAS
_DEMO_BRAND_SPECS: list[tuple[str, str]] = [
    ("vulcano", "VULCANO"),
    ("aegis", "AEGIS"),
    ("guardian", "GUARDIAN"),
    ("ferrum", "FERRUM"),
    ("titan", "TITAN"),
    ("sentinel", "SENTINEL"),
]

_CATEGORY_IDS: dict[str, uuid.UUID] = {
    "epis": CATEGORY_EPI_ID,
    "maquinas-e-ferramentas": CATEGORY_MAQUINAS_ID,
    **{slug: _demo_id("category", slug) for slug, _, _ in _DEMO_CATEGORY_SPECS},
}

_BRAND_IDS: dict[str, uuid.UUID] = {
    "protec": BRAND_PROTEC_ID,
    "norton": BRAND_NORTON_ID,
    **{slug: _demo_id("brand", slug) for slug, _ in _DEMO_BRAND_SPECS},
}

_DEMO_CATEGORIES: list[dict[str, object]] = [
    {
        "id": _CATEGORY_IDS[slug],
        "name": name,
        "slug": slug,
        "parent_id": None if parent is None else _CATEGORY_IDS[parent],
        "is_active": True,
    }
    for slug, name, parent in _DEMO_CATEGORY_SPECS
]

_DEMO_BRANDS: list[dict[str, object]] = [
    {"id": _BRAND_IDS[slug], "name": name, "slug": slug} for slug, name in _DEMO_BRAND_SPECS
]

# ca_mode: "valid" (CA ficticio valido) | "expired" (vencido -> indisponivel)
#          | "missing" (EPI sem CA -> indisponivel) | "na" (nao EPI).
_DEMO_CA_EXPIRED = date(2023, 5, 31)
_DEMO_CA_VALID = date(2029, 12, 31)

# (sku, nome, slug_categoria, slug_marca, preco, ca_mode, status, uom)
_DEMO_PRODUCT_SPECS: list[tuple[str, str, str, str, str, str, str, str]] = [
    (
        "CAP-002",
        "Capacete de Segurança Classe A Aba Frontal",
        "protecao-cabeca",
        "protec",
        "32.90",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "CAP-003",
        "Capacete de Segurança Classe B com Jugular",
        "protecao-cabeca",
        "vulcano",
        "45.50",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "CAP-004",
        "Capacetes de Segurança Conjugados",
        "protecao-cabeca",
        "protec",
        "58.00",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "CAP-005",
        "Capacete de Segurança Descontinuado",
        "protecao-cabeca",
        "protec",
        "20.00",
        "valid",
        "INACTIVE",
        "UN",
    ),
    (
        "OCV-001",
        "Óculos de Proteção Incolor",
        "protecao-visual",
        "aegis",
        "18.90",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "OCV-002",
        "Oculos de Proteção Fumê",
        "protecao-visual",
        "aegis",
        "19.50",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "OCV-003",
        "Óculos de Proteção Ampla Visão",
        "protecao-visual",
        "guardian",
        "27.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "OCV-004",
        "Óculos de Segurança Antiembaçante",
        "protecao-visual",
        "aegis",
        "24.90",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "OCV-005",
        "Óculos de Proteção para Sobrepor",
        "protecao-visual",
        "guardian",
        "31.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "OCV-006",
        "Óculos Infantil Descontinuado",
        "protecao-visual",
        "aegis",
        "15.00",
        "na",
        "INACTIVE",
        "UN",
    ),
    (
        "LUV-003",
        "Luva de Raspa de Couro",
        "protecao-maos",
        "protec",
        "13.90",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "LUV-004",
        "Luvas de Raspa Premium",
        "protecao-maos",
        "protec",
        "15.50",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "LUV-005",
        "Luva Nitrílica Descartável",
        "protecao-maos",
        "ferrum",
        "8.90",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "LUV-006",
        "Luva de Vaqueta Petroleira",
        "protecao-maos",
        "ferrum",
        "22.40",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "LUV-007",
        "Luva Anticorte Nível 5",
        "protecao-maos",
        "titan",
        "38.70",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "LUV-008",
        "Luva de Látex Forrada",
        "protecao-maos",
        "protec",
        "9.80",
        "missing",
        "ACTIVE",
        "PAR",
    ),
    (
        "LUV-009",
        "Luva de Raspa Fora de Linha",
        "protecao-maos",
        "protec",
        "11.00",
        "valid",
        "INACTIVE",
        "PAR",
    ),
    (
        "RES-004",
        "Respirador PFF2 Sem Válvula",
        "protecao-respiratoria",
        "protec",
        "3.50",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "RES-005",
        "Respirador PFF3 com Válvula",
        "protecao-respiratoria",
        "protec",
        "7.90",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "RES-006",
        "Respirador Semifacial Duplo Filtro",
        "protecao-respiratoria",
        "ferrum",
        "119.00",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "RES-007",
        "Máscara de Proteção PFF1",
        "protecao-respiratoria",
        "protec",
        "3.20",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "RES-008",
        "Respirador Panorâmico",
        "protecao-respiratoria",
        "ferrum",
        "89.90",
        "expired",
        "ACTIVE",
        "UN",
    ),
    (
        "AUD-001",
        "Protetor Auricular Plug Silicone",
        "protecao-auditiva",
        "aegis",
        "3.50",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "AUD-002",
        "Protetor Auricular Tipo Concha",
        "protecao-auditiva",
        "aegis",
        "34.50",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "AUD-003",
        "Abafador de Ruído Acoplado ao Capacete",
        "protecao-auditiva",
        "vulcano",
        "29.90",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "AUD-004",
        "Protetor Auricular Plug Moldável",
        "protecao-auditiva",
        "guardian",
        "4.50",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "BOT-001",
        "Botina de Segurança Couro",
        "protecao-pes",
        "titan",
        "99.90",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "BOT-002",
        "Bota de Segurança Bico Composite",
        "protecao-pes",
        "titan",
        "139.00",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "BOT-003",
        "Botas de Segurança Impermeáveis",
        "protecao-pes",
        "ferrum",
        "189.00",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "BOT-004",
        "Botina Eletricista",
        "protecao-pes",
        "titan",
        "159.00",
        "missing",
        "ACTIVE",
        "PAR",
    ),
    (
        "BOT-005",
        "Sapato de Segurança Sport",
        "protecao-pes",
        "ferrum",
        "119.00",
        "valid",
        "ACTIVE",
        "PAR",
    ),
    (
        "QUE-001",
        "Cinto Paraquedista 4 Pontos",
        "protecao-quedas",
        "vulcano",
        "210.00",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "QUE-002",
        "Talabarte Duplo I e Y",
        "protecao-quedas",
        "vulcano",
        "145.00",
        "expired",
        "ACTIVE",
        "UN",
    ),
    (
        "QUE-003",
        "Cinturão de Segurança Abdominal",
        "protecao-quedas",
        "titan",
        "89.00",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "QUE-004",
        "Trava Queda Deslizante",
        "protecao-quedas",
        "vulcano",
        "260.00",
        "valid",
        "ACTIVE",
        "UN",
    ),
    (
        "FUR-001",
        "Furadeira de Impacto 850W",
        "ferramentas-eletricas",
        "norton",
        "349.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "FUR-002",
        "Furadeiras de Bancada 500W",
        "ferramentas-eletricas",
        "norton",
        "899.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "FUR-003",
        "Esmerilhadeira Angular 115mm",
        "ferramentas-eletricas",
        "vulcano",
        "279.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "FUR-004",
        "Serra Circular 7 1/4",
        "ferramentas-eletricas",
        "norton",
        "429.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "FUR-005",
        "Retífica Reta 500W",
        "ferramentas-eletricas",
        "vulcano",
        "319.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-005",
        "Compressor de Ar 100L",
        "maquinas-estacionarias",
        "titan",
        "1899.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-006",
        "Prensa Hidráulica 15T",
        "maquinas-estacionarias",
        "titan",
        "4590.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-007",
        "Politriz de Bancada",
        "maquinas-estacionarias",
        "norton",
        "780.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-008",
        "Serra de Bancada 10",
        "maquinas-estacionarias",
        "norton",
        "1290.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-009",
        "Bomba d'Água Autoaspirante",
        "maquinas-estacionarias",
        "vulcano",
        "960.00",
        "na",
        "ACTIVE",
        "UN",
    ),
    (
        "MAQ-010",
        "Torno de Bancada Descontinuado",
        "maquinas-estacionarias",
        "norton",
        "1450.00",
        "na",
        "INACTIVE",
        "UN",
    ),
]

# Atributos pesquisaveis (JSONB) para alguns itens.
_DEMO_ATTRIBUTES: dict[str, dict[str, str]] = {
    "CAP-002": {"cor": "branco", "material": "abs"},
    "OCV-001": {"cor": "transparente", "tratamento": "antiembacante"},
    "LUV-004": {"material": "raspa", "tamanho": "G"},
    "RES-006": {"filtro": "duplo", "classe": "P2"},
    "BOT-001": {"material": "couro", "bico": "composite"},
    "MAQ-005": {"potencia": "2cv", "volume": "100l"},
}


def _build_demo_products() -> list[dict[str, object]]:
    products: list[dict[str, object]] = []
    for index, spec in enumerate(_DEMO_PRODUCT_SPECS, start=1):
        sku, name, category_slug, brand_slug, price, ca_mode, status, uom = spec
        is_epi = ca_mode != "na"
        row: dict[str, object] = {
            "id": _demo_id("product", sku),
            "category_id": _CATEGORY_IDS[category_slug],
            "brand_id": _BRAND_IDS[brand_slug],
            "sku": sku,
            "name": name,
            "slug": _slugify(name),
            "description": f"{name} (item de demonstracao).",
            "status": status,
            "is_epi": is_epi,
            "unit_of_measure": uom,
            "min_order_qty": 1,
            "base_unit_price": Decimal(price),
        }
        if is_epi:
            row["ca_number"] = f"DEMO-CA-{index:04d}"
            if ca_mode == "valid":
                row["ca_valid_until"] = _DEMO_CA_VALID
            elif ca_mode == "expired":
                row["ca_valid_until"] = _DEMO_CA_EXPIRED
        attributes = _DEMO_ATTRIBUTES.get(sku)
        if attributes is not None:
            row["attributes"] = json.dumps(attributes)
        products.append(row)
    return products


_DEMO_PRODUCTS = _build_demo_products()

# (sku, min_quantity, max_quantity|None, unit_price)
_DEMO_TIER_SPECS: list[tuple[str, int, int | None, str]] = [
    ("CAP-002", 6, 23, "30.90"),
    ("CAP-002", 24, None, "27.50"),
    ("OCV-001", 10, 49, "17.50"),
    ("OCV-001", 50, None, "15.90"),
    ("LUV-004", 12, 59, "14.50"),
    ("LUV-004", 60, None, "12.90"),
    ("BOT-001", 6, 23, "94.90"),
    ("BOT-001", 24, None, "89.90"),
    ("RES-006", 5, None, "109.00"),
    ("FUR-001", 3, None, "329.00"),
]


def _build_demo_tiers() -> list[dict[str, object]]:
    tiers: list[dict[str, object]] = []
    for sku, min_quantity, max_quantity, unit_price in _DEMO_TIER_SPECS:
        tiers.append(
            {
                "id": _demo_id("tier", f"{sku}:{min_quantity}"),
                "product_id": _demo_id("product", sku),
                "min_quantity": min_quantity,
                "max_quantity": max_quantity,
                "unit_price": Decimal(unit_price),
            }
        )
    return tiers


_DEMO_TIERS = _build_demo_tiers()

# Listas efetivamente usadas pelo seed (base + demonstracao).
_ALL_CATEGORIES: list[dict[str, object]] = [*_CATEGORIES, *_DEMO_CATEGORIES]
_ALL_BRANDS: list[dict[str, object]] = [*_BRANDS, *_DEMO_BRANDS]
_ALL_PRODUCTS: list[dict[str, object]] = [*_PRODUCTS, *_DEMO_PRODUCTS]
_ALL_TIERS: list[dict[str, object]] = [*_TIERS, *_DEMO_TIERS]

# Traducoes offline de demonstracao (en/es/ar) - origem pt-BR. Carregadas uma
# unica vez no import (arquivo versionado ao lado do seed), nunca no request.
_DEMO_TRANSLATIONS_PATH = (
    Path(__file__).resolve().parents[3] / "seed_data" / "demo_translations.json"
)
_DEMO_TRANSLATIONS = json.loads(_DEMO_TRANSLATIONS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Empresas de demonstracao e precos por empresa (Fase 9A) - FICTICIOS
# ---------------------------------------------------------------------------
# Tres empresas ficticias com condicoes comerciais distintas para o MESMO
# catalogo, para exibir o diferencial B2B:
#   * metalurgica-alfa: sem desconto (preco de lista);
#   * construcoes-beta: desconto percentual por categoria (EPIs, 10%);
#   * industria-gama: desconto global (5%) + preco negociado em SKUs.
# Os CNPJ sao sinteticos e VALIDOS pelo algoritmo oficial (digito verificador),
# mas NAO pertencem a nenhuma empresa real. As senhas dos usuarios vem de
# DEMO_USER_PASSWORD (nunca versionada); sem ela, os usuarios nao sao criados.

_DEMO_TENANT_NAMESPACE = uuid.UUID("6d656d6f-0000-4000-8000-0000000000e0")

# (slug, cnpj sintetico valido, razao social, nome fantasia)
_DEMO_COMPANY_SPECS: list[tuple[str, str, str, str]] = [
    ("metalurgica-alfa", "11222333000181", "Metalurgica Demo Alfa Ltda", "Metalurgica Demo Alfa"),
    ("construcoes-beta", "44555666000181", "Construcoes Demo Beta Ltda", "Construcoes Demo Beta"),
    ("industria-gama", "77888999000181", "Industria Demo Gama Ltda", "Industria Demo Gama"),
]

# (papel RBAC, prefixo do e-mail ficticio do usuario)
_DEMO_ROLE_SPECS: list[tuple[str, str]] = [
    ("ADMIN", "admin"),
    ("BUYER", "comprador"),
    ("APPROVER", "aprovador"),
]

_DEMO_COMPANY_CREDIT_LIMIT = Decimal("25000.00")


@dataclass(frozen=True)
class _DemoTenant:
    """Agregado de dados de uma empresa de demonstracao (ficticia)."""

    id: uuid.UUID
    slug: str
    company: dict[str, object]
    users: list[dict[str, object]]
    members: list[dict[str, object]]
    credit_account: dict[str, object]
    credit_entry: dict[str, object]
    rules: list[dict[str, object]]


def _tenant_id(kind: str, key: str) -> uuid.UUID:
    """UUID deterministico dos dados de tenant de demonstracao (idempotencia)."""
    return uuid.uuid5(_DEMO_TENANT_NAMESPACE, f"{kind}:{key}")


def _rule(
    company_id: uuid.UUID,
    key: str,
    *,
    rule_type: str,
    product_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    percent: Decimal | None = None,
    unit_price: Decimal | None = None,
) -> dict[str, object]:
    """Regra de preco com TODAS as colunas (facilita o upsert idempotente)."""
    return {
        "id": _tenant_id("rule", f"{key}"),
        "company_id": company_id,
        "rule_type": rule_type,
        "product_id": product_id,
        "category_id": category_id,
        "percent": percent,
        "unit_price": unit_price,
    }


def _demo_price_rules(company_id: uuid.UUID, slug: str) -> list[dict[str, object]]:
    # Os produtos de EPI do catalogo demo estao em SUBCATEGORIAS (ex.: "Proteção
    # da Cabeça"), entao o desconto por categoria aponta para a subcategoria real.
    if slug == "construcoes-beta":
        return [
            _rule(
                company_id,
                f"{slug}:desconto-cabeca",
                rule_type="PERCENT_DISCOUNT",
                category_id=_CATEGORY_IDS["protecao-cabeca"],
                percent=Decimal("10.00"),
            )
        ]
    if slug == "industria-gama":
        return [
            _rule(
                company_id,
                f"{slug}:desconto-global",
                rule_type="PERCENT_DISCOUNT",
                percent=Decimal("5.00"),
            ),
            _rule(
                company_id,
                f"{slug}:negociado-cap-002",
                rule_type="FIXED_PRICE",
                product_id=_demo_id("product", "CAP-002"),
                unit_price=Decimal("27.90"),
            ),
            _rule(
                company_id,
                f"{slug}:negociado-bot-001",
                rule_type="FIXED_PRICE",
                product_id=_demo_id("product", "BOT-001"),
                unit_price=Decimal("89.90"),
            ),
        ]
    return []


def _build_demo_tenants(pepper: str, password_hash: str | None) -> list[_DemoTenant]:
    """Empresas demo com usuarios (se houver senha) e regras de preco."""
    tenants: list[_DemoTenant] = []
    for slug, cnpj, legal_name, trade_name in _DEMO_COMPANY_SPECS:
        company_id = _tenant_id("company", slug)
        users: list[dict[str, object]] = []
        members: list[dict[str, object]] = []
        for role, prefix in _DEMO_ROLE_SPECS:
            user_id = _tenant_id("user", f"{slug}:{role}")
            user: dict[str, object] = {
                "id": user_id,
                "company_id": company_id,
                "email": f"{prefix}@{slug}.example.com",
                "full_name": f"{prefix.title()} Demo {trade_name}",
                "cpf_hash": cpf_hash(f"demo-{slug}-{role}", pepper),
                "status": "ACTIVE",
                "email_verified_at": _APPROVED_AT,
            }
            if password_hash is not None:
                user["password_hash"] = password_hash
            users.append(user)
            members.append(
                {
                    "id": _tenant_id("member", f"{slug}:{role}"),
                    "company_id": company_id,
                    "user_id": user_id,
                    "role": role,
                    "status": "ACTIVE",
                }
            )
        tenants.append(
            _DemoTenant(
                id=company_id,
                slug=slug,
                company={
                    "id": company_id,
                    "cnpj": cnpj,
                    "legal_name": legal_name,
                    "trade_name": trade_name,
                    "status": "ACTIVE",
                    "approved_at": _APPROVED_AT,
                },
                users=users,
                members=members,
                credit_account={
                    "company_id": company_id,
                    "credit_limit": _DEMO_COMPANY_CREDIT_LIMIT,
                },
                credit_entry={
                    "id": _tenant_id("credit", slug),
                    "credit_account_id": company_id,
                    "company_id": company_id,
                    "entry_type": "LIMIT_SET",
                    "amount": _DEMO_COMPANY_CREDIT_LIMIT,
                    "reference_type": "company",
                    "reference_id": company_id,
                    "description": "Limite inicial do cliente de demonstracao (seed).",
                },
                rules=_demo_price_rules(company_id, slug),
            )
        )
    return tenants


if __name__ == "__main__":
    main()
