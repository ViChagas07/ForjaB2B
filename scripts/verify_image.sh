#!/bin/bash
# verify_image.sh - Valida se a imagem Docker consegue importar migrations e rodar alembic heads
# Uso: ./verify_image.sh [dockerfile] [context_dir]
# Exemplo: ./verify_image.sh Dockerfile .

set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"
CONTEXT_DIR="${2:-.}"
IMAGE_TAG="forja-b2b-verify:latest"

echo "=== Building Docker image ==="
docker build -f "$DOCKERFILE" -t "$IMAGE_TAG" "$CONTEXT_DIR"

echo "=== Testing alembic heads inside container ==="
docker run --rm "$IMAGE_TAG" \
    sh -c "cd /app && python -c \"from alembic.config import Config; from alembic.script import ScriptDirectory; cfg = Config('alembic.ini'); print(ScriptDirectory.from_config(cfg).get_current_head())\""

echo "=== Testing migration imports ==="
docker run --rm "$IMAGE_TAG" \
    sh -c "cd /app && python -c \"from app.core.migration_helpers import add_column_if_owner, create_check_constraint_if_owner, is_owner; print('migration_helpers OK')\""

echo "=== Testing alembic heads via cli ==="
docker run --rm "$IMAGE_TAG" \
    sh -c "cd /app && alembic heads"

echo "=== All checks passed ==="