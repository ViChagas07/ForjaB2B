# ADR-0003: Exclusão LGPD como anonimização (preservando registros)

- **Status:** aceito
- **Data:** 2026-10-09

## Contexto

O direito de exclusão (LGPD) conflita com a obrigação de preservar registros
financeiros/fiscais e de auditoria (ledger, faturas, pedidos, trilhas).

## Decisão

A exclusão do titular é implementada como **anonimização**: a linha do usuário é
mantida (preservando FKs e integridade referencial), mas `email`, `full_name`,
`phone` e `cpf_encrypted` são anonimizados e `status` vira `SUSPENDED`. Registros
financeiros/fiscais/auditoria permanecem intactos, com trilha de auditoria
`personal_data.delete`.

## Consequências

- Integridade referencial e unicidade de `email` preservadas (email anonimizado
  determinístico `deleted+<uuid>@...`).
- Não elimina silenciosamente faturas/ledger/auditoria.
