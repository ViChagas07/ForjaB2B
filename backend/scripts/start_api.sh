#!/bin/sh
# Start da API com migration fail-fast.
#
# Em planos do Render que nao suportam pre-deploy, aplicar `alembic upgrade
# head` antes de liberar trafego evita o cenario de codigo novo + schema antigo
# (login/onboarding 500). A variavel tambem permanece disponivel para o engine
# administrativo do runtime (catalogo/admin), como no docker-compose.
#
# Se DATABASE_ADMIN_URL nao estiver presente ou a migration falhar, a API sobe
# com o caminho de compatibilidade (login/CNPJ continuam funcionando; cadastro
# CPF responde 503 ate a migration ser aplicada). /health/schema mostra o estado.
set -e

# Se ALLOW_START_WITH_FAILED_MIGRATION nao for "true" (padrao false em prod),
# falha de migration aborta o container (exit != 0). Em dev, defina
# ALLOW_START_WITH_FAILED_MIGRATION=true para permitir compatibilidade.
ALLOW_FAILED="${ALLOW_START_WITH_FAILED_MIGRATION:-false}"

if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ] && [ -n "${DATABASE_ADMIN_URL:-}" ]; then
    echo "[start] aplicando migrations (alembic upgrade head)..."
    if python scripts/predeploy.py; then
        echo "[start] migrations aplicadas/validadas."
    else
        if [ "$ALLOW_FAILED" = "true" ]; then
            echo "[start] AVISO: migration falhou; iniciando em modo de compatibilidade."
            echo "[start] O cadastro CPF responderah 503 ate a migration 0030/0031 ser aplicada."
        else
            echo "[start] ERRO: migration falhou e ALLOW_START_WITH_FAILED_MIGRATION nao e true." >&2
            echo "[start] Deploy abortado. Corrija a migration ou defina ALLOW_START_WITH_FAILED_MIGRATION=true (apenas dev)." >&2
            exit 1
        fi
    fi
elif [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ]; then
    if [ "$ALLOW_FAILED" = "true" ]; then
        echo "[start] AVISO: DATABASE_ADMIN_URL ausente; migration nao aplicada no startup."
        echo "[start] O cadastro CPF responderah 503 ate a migration 0030/0031 ser aplicada."
    else
        echo "[start] ERRO: DATABASE_ADMIN_URL ausente e ALLOW_START_WITH_FAILED_MIGRATION nao e true." >&2
        echo "[start] Deploy abortado. Configure DATABASE_ADMIN_URL ou defina ALLOW_START_WITH_FAILED_MIGRATION=true (apenas dev)." >&2
        exit 1
    fi
fi

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-4}" \
    --no-server-header \
    --access-log
