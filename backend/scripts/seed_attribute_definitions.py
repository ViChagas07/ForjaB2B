"""Seed idempotente de definições de atributos de produto.

Carrega o JSON versionado em `backend/app/seed_data/attribute_definitions.json`
e aplica `ON CONFLICT (key) DO UPDATE` para manter o estado sincronizado.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Adiciona o diretório backend ao path antes dos imports da aplicação
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.application.product_attributes import load_registry_from_json  # noqa: E402
from app.domain.product_attributes import AttributeDefinition  # noqa: E402

JSON_PATH = BACKEND_DIR / "app" / "seed_data" / "attribute_definitions.json"


async def seed_attribute_definitions(admin_url: str) -> int:
    """Aplica o seed de definições de atributos.

    Retorna o número de linhas inseridas/atualizadas.
    """
    registry = load_registry_from_json(str(JSON_PATH))

    engine = create_async_engine(admin_url)
    try:
        async with engine.begin() as conn:
            count = 0
            for definition in registry.definitions.values():
                await conn.execute(
                    text(
                        """
                        INSERT INTO product_attribute_definitions
                            (key, label, type, unit, options, scope, section,
                             display_order, required, min_value, max_value, max_length,
                             created_at, updated_at)
                        VALUES
                            (:key, :label, :type, :unit, CAST(:options AS jsonb),
                             CAST(:scope AS jsonb), :section, :display_order,
                             :required, :min_value, :max_value, :max_length,
                             now(), now())
                        ON CONFLICT (key) DO UPDATE SET
                            label = EXCLUDED.label,
                            type = EXCLUDED.type,
                            unit = EXCLUDED.unit,
                            options = EXCLUDED.options,
                            scope = EXCLUDED.scope,
                            section = EXCLUDED.section,
                            display_order = EXCLUDED.display_order,
                            required = EXCLUDED.required,
                            min_value = EXCLUDED.min_value,
                            max_value = EXCLUDED.max_value,
                            max_length = EXCLUDED.max_length,
                            updated_at = now()
                        """
                    ),
                    {
                        "key": definition.key,
                        "label": definition.label,
                        "type": definition.type.value,
                        "unit": definition.unit,
                        "options": _options_to_json(definition.options),
                        "scope": _scope_to_json(definition),
                        "section": definition.section,
                        "display_order": definition.display_order,
                        "required": definition.required,
                        "min_value": definition.min_value,
                        "max_value": definition.max_value,
                        "max_length": definition.max_length,
                    },
                )
                count += 1
            return count
    finally:
        await engine.dispose()


def _options_to_json(options: tuple | None) -> str | None:
    if options is None:
        return None
    return json.dumps([{"key": opt.key, "label": opt.label} for opt in options])


def _scope_to_json(definition: AttributeDefinition) -> str:
    if definition.scope_type.value == "global":
        return '["global"]'
    return json.dumps(list(definition.scope_categories))


async def main() -> None:
    admin_url = os.environ.get(
        "DATABASE_ADMIN_URL",
        "postgresql+asyncpg://forja_admin:forja_admin_secret_dev@localhost:5432/forja_db",
    )

    print(f"Carregando definições de: {JSON_PATH}")
    count = await seed_attribute_definitions(admin_url)
    print(f"Seed concluído: {count} definições processadas.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
