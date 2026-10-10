#!/usr/bin/env bash
# ==============================================================================
# Forja B2B - Bootstrap idempotente da role/usuario de aplicacao no Elasticsearch.
# Fase 6 (busca). Cria (ou atualiza) uma role com privilegios MINIMOS sobre o
# indice/alias de produtos e um usuario de aplicacao. NUNCA usa o superusuario
# `elastic` no backend. Le credenciais administrativas do ambiente; nao grava
# segredos em arquivo e nao imprime senhas.
#
# Uso (VPS ou Elastic Cloud):
#   ES_ADMIN_URL=https://es.exemplo:9200 \
#   ES_ADMIN_USER=elastic ES_ADMIN_PASSWORD=... \
#   ES_APP_PASSWORD=... \
#   [ES_CA_CERTS=/caminho/ca.crt] \
#   bash backend/scripts/elasticsearch_bootstrap_roles.sh
#
# Variaveis opcionais:
#   ES_APP_USER (default: forja_search_app)
#   ES_ROLE     (default: forja_search_app)
#   ES_INDEX_PREFIX (default: forja_products)
#   ES_APP_ROLE_FILE (default: docker/elasticsearch/app-role.json) - se existir, e usado
# ==============================================================================
set -euo pipefail

: "${ES_ADMIN_URL:?defina ES_ADMIN_URL (ex.: https://es.exemplo:9200)}"
: "${ES_ADMIN_USER:?defina ES_ADMIN_USER (usuario administrativo)}"
: "${ES_ADMIN_PASSWORD:?defina ES_ADMIN_PASSWORD (do secret manager)}"
: "${ES_APP_PASSWORD:?defina ES_APP_PASSWORD (do secret manager)}"

ES_APP_USER="${ES_APP_USER:-forja_search_app}"
ES_ROLE="${ES_ROLE:-forja_search_app}"
ES_INDEX_PREFIX="${ES_INDEX_PREFIX:-forja_products}"

CURL_OPTS=(-sS --fail-with-body -u "${ES_ADMIN_USER}:${ES_ADMIN_PASSWORD}" -H 'Content-Type: application/json')
if [[ -n "${ES_CA_CERTS:-}" ]]; then
  CURL_OPTS+=(--cacert "${ES_CA_CERTS}")
fi

ROLE_JSON=$(
  cat <<JSON
{
  "cluster": ["monitor"],
  "indices": [
    {
      "names": ["${ES_INDEX_PREFIX}", "${ES_INDEX_PREFIX}_v*"],
      "privileges": ["read", "write", "create_index", "manage", "view_index_metadata", "maintenance"]
    }
  ]
}
JSON
)

USER_JSON=$(
  cat <<JSON
{ "password": "${ES_APP_PASSWORD}", "roles": ["${ES_ROLE}"] }
JSON
)

echo "-> aplicando role '${ES_ROLE}' (idempotente)"
curl "${CURL_OPTS[@]}" -X PUT "${ES_ADMIN_URL}/_security/role/${ES_ROLE}" -d "${ROLE_JSON}" >/dev/null

echo "-> aplicando usuario '${ES_APP_USER}' (idempotente)"
curl "${CURL_OPTS[@]}" -X PUT "${ES_ADMIN_URL}/_security/user/${ES_APP_USER}" -d "${USER_JSON}" >/dev/null

echo "-> conferindo autenticacao do usuario de aplicacao"
curl -sS --fail-with-body -u "${ES_APP_USER}:${ES_APP_PASSWORD}" ${ES_CA_CERTS:+--cacert "${ES_CA_CERTS}"} \
  "${ES_ADMIN_URL}/_cluster/health?wait_for_status=yellow" >/dev/null

echo "OK: role/usuario de aplicacao prontos (privilegios minimos sobre ${ES_INDEX_PREFIX}*)."
