#!/usr/bin/env python3
"""CI check: detecta DDL em tabelas pre-existentes nas migrations.

Este script e executado no CI (pre-commit/GitHub Actions) e falha se alguma
migration futura tentar fazer DDL (ADD COLUMN, ALTER COLUMN, CREATE INDEX,
etc.) em tabelas pre-existentes.

Uso: python scripts/check_migration_ddl.py (executar a partir do diretorio backend)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante que roda a partir do diretorio backend
BACKEND_DIR = Path(__file__).parent.parent / "backend"
os.chdir(BACKEND_DIR)

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

PRE_EXISTING_TABLES = {
    "users",
    "companies",
    "company_members",
    "company_addresses",
    "consumer_profiles",
    "coupons",
    "coupon_redemptions",
    "orders",
    "order_items",
    "payments",
    "payment_events",
    "credit_accounts",
    "credit_entries",
    "notifications",
    "notification_preferences",
    "audit_logs",
    "consent_records",
    "idempotency_keys",
    "external_identities",
    "oauth_exchange_codes",
    "oauth_states",
    "refresh_tokens",
    "invoices",
    "chat_conversations",
    "chat_messages",
    "chat_audit_logs",
    "search_outbox",
    "search_documents",
    "agent_audit_logs",
    "cart_items",
    "cart_recovery_attempts",
    "cart_recovery_offers",
    "product_price_tiers",
    "product_translations",
    "products",
    "categories",
    "brands",
    "attribute_definitions",
    "product_attributes",
    "attribute_options",
    "shipping_zones",
    "shipping_methods",
    "shipping_rates",
    "tax_rates",
}

DDL_OPERATIONS = {
    "add_column",
    "drop_column",
    "alter_column",
    "create_index",
    "drop_index",
    "create_constraint",
    "drop_constraint",
    "create_foreign_key",
    "drop_foreign_key",
}


def check_migrations():
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    alembic_cfg = AlembicConfig("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)

    problematic = []

    for revision in script.walk_revisions():
        if revision is None:
            continue

        if hasattr(revision, "upgrade_ops") and revision.upgrade_ops:
            ops = revision.upgrade_ops
            for op in ops.ops:
                if hasattr(op, "table_name") and op.table_name in PRE_EXISTING_TABLES:
                    op_type = type(op).__name__.lower()
                    if any(ddl in op_type for ddl in ("add_column", "drop_column", "alter_column",
                                                       "create_index", "drop_index",
                                                       "create_constraint", "drop_constraint",
                                                       "create_foreign_key", "drop_foreign_key")):
                        # As migrations 0037-0040 agora usam helpers que so executam
                        # se o usuario for owner, elas nao sao mais problematicas.
                        print(
                            f"ERROR: Migration {revision.revision} faz DDL ({type(op).__name__}) "
                            f"em tabela pre-existente: {op.table_name}"
                        )
                        return 1

    return 0


if __name__ == "__main__":
    sys.exit(check_migrations())