#!/bin/sh
# One-off: garante o indice de busca (bootstrap + reindex) antes de subir a API.
#
# Uso no Render (servico Docker): campo "Docker Command" = sh /app/scripts/start_with_search_bootstrap.sh
# Multiplos comandos no campo viram UM unico nome para o /bin/sh do container
# (exit 127 "not found"); o script evita qualquer encadeamento no campo.
# Depois de validar nos logs ({"indexed": N, "rejected": 0, "swapped": true}),
# limpe o campo "Docker Command" (vazio = volta ao CMD da imagem).
#
# A versao do indice segue ELASTICSEARCH_INDEX_VERSION (default 2, como no
# .env.example e no DEPLOY_RENDER.md). O numero de workers segue
# WEB_CONCURRENCY (o Render define 1 em instancias de pouca CPU).
set -e

VERSION="${ELASTICSEARCH_INDEX_VERSION:-2}"

python -m app.modules.search.interface.cli bootstrap --version "$VERSION"
python -m app.modules.search.interface.cli reindex --version "$VERSION"

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-4}" \
    --no-server-header \
    --access-log
