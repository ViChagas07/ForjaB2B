# Forja B2B — LGPD (Lei Geral de Proteção de Dados)

Este documento descreve **o que o backend implementa** em relação aos direitos
dos titulares. **Não afirma conformidade jurídica integral** — a adequação legal
final depende de fatores de negócio/processo fora do código.

## Direitos implementados (self-service, tenant-scoped)

| Direito | Endpoint | Comportamento |
| :--- | :--- | :--- |
| Acesso/exportação | `GET /api/v1/privacy/export` | Exporta dados do titular (perfil, papel, consentimentos, auditoria própria). |
| Retificação | `PATCH /api/v1/privacy/me` | Atualiza `full_name` e `phone` (com auditoria). |
| Exclusão | `DELETE /api/v1/privacy/me` | **Anonimiza** dados pessoais, preserva registros financeiros/fiscais/auditoria. |
| Consentimento | `POST /api/v1/privacy/consent` | Registro versionado/append-only (aceite ou revogação). |
| Estado de consentimento | `GET /api/v1/privacy/consent` | Último registro por finalidade. |

## Isolamento

- `company_id`/`user_id` derivam do token autenticado — nunca de parâmetro do
  cliente. Um titular não consegue exportar dados de outro (nem de outro tenant).

## Anonimização (exclusão)

A exclusão não remove a linha do usuário (preservando FKs e integridade), mas
anonimiza: `email` → `deleted+<uuid>@anonymized.forja.local`, `full_name` →
"Usuario Removido", `phone`/`cpf_encrypted` → `NULL`, `status` → `SUSPENDED`.
Registros financeiros (pedidos, faturas, ledger) e trilha de auditoria são
preservados, conforme as regras de retenção do projeto.

## Auditoria

- `audit_log` registra `personal_data.rectify` e `personal_data.delete` na mesma
  transação, com `actor_user_id` do titular.

## Limitações

- Não há fluxo de operador administrativo (exportação/retificação de terceiros do
  mesmo tenant) — apenas self-service. Documentado como pendência.
- Preferências de cookies não são tratadas no backend (sem responsabilidade de
  servidor no fluxo atual).
