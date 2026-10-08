#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Forja B2B: wrapper de bootstrap - roles e hardening base.
# Executado pelo entrypoint oficial do PostgreSQL (initdb) como o superuser de
# bootstrap ($POSTGRES_USER). Injeta credenciais do ambiente no init-roles.sql
# via variaveis psql; nenhuma senha fica gravada em arquivo SQL.
# -----------------------------------------------------------------------------
set -euo pipefail

: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"
: "${POSTGRES_ADMIN_USER:?POSTGRES_ADMIN_USER is required}"
: "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v app_user="$POSTGRES_APP_USER" \
    -v app_password="$POSTGRES_APP_PASSWORD" \
    -v admin_user="$POSTGRES_ADMIN_USER" \
    -v admin_password="$POSTGRES_ADMIN_PASSWORD" \
    -v db_name="$POSTGRES_DB" \
    -f /docker-entrypoint-initdb.d/sql/init-roles.sql
