#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Forja B2B: wrapper de bootstrap - helpers de contexto tenant (RLS).
# Executa como forja_admin (owner do database) para que o schema "app" e as
# funcoes fiquem owned pela role administrativa restrita, e nao pelo superuser
# de bootstrap. No initdb a conexao local e trust (sem senha necessaria).
# -----------------------------------------------------------------------------
set -euo pipefail

: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_ADMIN_USER:?POSTGRES_ADMIN_USER is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_ADMIN_USER" --dbname "$POSTGRES_DB" \
    -v app_user="$POSTGRES_APP_USER" \
    -v admin_user="$POSTGRES_ADMIN_USER" \
    -f /docker-entrypoint-initdb.d/sql/02-rls-setup.sql
