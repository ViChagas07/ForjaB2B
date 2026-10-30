#!/bin/sh
# One-off: garante o indice de busca (bootstrap + reindex), atualiza o seed de
# demonstracao (imagens/precos/traducoes por SKU) e sobe a API.
#
# Uso no Render (servico Docker): campo "Docker Command" = sh /app/scripts/start_with_search_bootstrap.sh
# Multiplos comandos no campo viram UM unico nome para o /bin/sh do container
# (exit 127 "not found"); o script evita qualquer encadeamento no campo.
# Depois de validar nos logs (seed + {"indexed": N, "rejected": 0, "swapped":
# true}), limpe o campo "Docker Command" (vazio = volta ao CMD da imagem).
#
# A versao do indice segue ELASTICSEARCH_INDEX_VERSION (default 2, como no
# .env.example e no DEPLOY_RENDER.md). O numero de workers segue
# WEB_CONCURRENCY (o Render define 1 em instancias de pouca CPU).
#
# O seed exige no ambiente: SEED_ALLOW_PRODUCTION=true e DATABASE_ADMIN_URL
# (role administrativa; no Render, a Internal Database URL serve). O passo e
# NAO-FATAL: se faltar algo, o aviso aparece no log e a API sobe do mesmo jeito
# (o image_url defasado no banco persiste ate o seed rodar de verdade).
set -e

if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ] && [ -n "${DATABASE_ADMIN_URL:-}" ]; then
    echo "[start] aplicando migrations antes do bootstrap de busca..."
    if python scripts/predeploy.py; then
        echo "[start] migrations aplicadas/validadas."
    else
        echo "[start] AVISO: migration falhou; seguindo para o bootstrap/API em modo de compatibilidade."
    fi
fi

VERSION="${ELASTICSEARCH_INDEX_VERSION:-2}"

python -m app.modules.search.interface.cli bootstrap --version "$VERSION"

if python -m app.infrastructure.db.seeds; then
    echo "seed_demo: OK"
else
    echo "AVISO: seed_demo falhou (veja o erro acima); a API sobe sem atualizar o banco."
fi

python -m app.modules.search.interface.cli reindex --version "$VERSION"

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-4}" \
    --no-server-header \
    --access-log
