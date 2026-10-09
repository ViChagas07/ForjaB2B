# ADR-0001: Webhook de pagamento autenticado por HMAC com company_id no payload

- **Status:** aceito
- **Data:** 2026-10-09

## Contexto

O endpoint de webhook do provedor de pagamento é um canal sistema-a-sistema
(sem JWT). A tabela `payments` tem `FORCE ROW LEVEL SECURITY`, o que impede ler
o pagamento por `provider_reference` antes de conhecer o `company_id`.

## Decisão

O webhook é autenticado por assinatura **HMAC-SHA256 do corpo** (segredo
compartilhado `payment_webhook_secret`). O `company_id` viaja **dentro do payload
assinado** — portanto autenticado pela assinatura — e é usado para estabelecer o
contexto de tenant (RLS) antes de localizar o pagamento por `provider_reference`.

## Consequências

- Sem função `SECURITY DEFINER` adicional para o webhook; autenticidade provém da
  assinatura, e o `company_id` não é "entrada de cliente não confiável".
- Idempotência por `(provider, event_id)` na tabela `payment_events`, com
  máquina de estados rejeitando transições inválidas/fora de ordem.
