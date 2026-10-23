# Webhooks: auditoria, contrato e operacao

## 1. Auditoria de endpoints que recebem terceiros

| Rota | Origem | Autenticacao | Situacao |
| :--- | :--- | :--- | :--- |
| `POST /api/v1/payments/stripe/webhook` | Stripe | `Stripe-Signature` (HMAC-SHA256 do Stripe) | **Implementado** com tolerancia, dois segredos e limite de corpo |
| `POST /api/v1/payments/webhook` | Provedor PIX/ERP legado | `X-Forja-Signature` (HMAC-SHA256) | **Implementado** (rota **depreciada**; ver `API_VERSIONING.md`) |
| `GET /api/v1/auth/google/callback` | Google (redirect de navegador) | `state` OAuth + code de uso unico | **Nao e webhook**: callback interativo, sem assinatura HMAC; nao processa eventos de negocio |
| ERP inbound | — | — | **Nao se aplica**: nao existe endpoint de ERP recebendo chamadas |
| E-mail inbound (bounce/complaint) | — | — | **Nao se aplica**: provedor de e-mail e somente saida (Mailpit/SMTP) |

Nao foram criados endpoints novos. O padrao descrito abaixo e o adotado para
qualquer webhook futuro (ERP, e-mail, outro PSP): corpo bruto, HMAC com dois
segredos, timestamp, idempotencia por `event_id`, limite de corpo e rate limit
proprio.

## 2. Contrato do webhook legado

```http
POST /api/v1/payments/webhook
Content-Type: application/json
X-Forja-Signature: sha256=<hex>
X-Forja-Timestamp: <unix-seconds>   # recomendado; obrigatorio para anti-replay
```

- **Assinatura com timestamp**: HMAC-SHA256 de `"<timestamp>.<corpo-bruto>"`,
  usando `PAYMENT_WEBHOOK_SECRET` (ou `PAYMENT_WEBHOOK_SECRET_PREVIOUS` durante
  rotacao). A comparacao usa `hmac.compare_digest` e testa **todos** os segredos
  ativos, sem curto-circuito.
- **Sem timestamp**: aceita a assinatura legada do corpo puro apenas durante a
  janela de depreciacao (a rota esta marcada com `Deprecation`/`Sunset`). O
  evento e registrado em log como `webhook_legacy_without_timestamp`.
- **Tolerancia**: `WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS` (padrao **300 s**).
  Timestamp fora da janela responde 401 `webhook_timestamp_invalid`.
- **Corpo bruto**: lido antes de qualquer parse; a assinatura cobre os bytes
  originais. Limite `WEBHOOK_MAX_BODY_BYTES` (padrao **1 MiB**) -> 413.
- **Idempotencia de evento**: `payment_events` tem unique
  `(provider, event_id)`; repeticao devolve `DUPLICATE` e nao reaplica o efeito.
- **Resposta**: 200 somente depois do registro duravel do evento/efeito.
  Assinatura ausente/invalida -> 401 com Problem Details generico, sem detalhes
  de criptografia. Payload invalido -> 422. Corpo grande -> 413.
- **Rate limit**: classe `WEBHOOK` (por IP, sem JWT), configuravel por
  `RATE_LIMIT_WEBHOOK_CAPACITY` / `RATE_LIMIT_WEBHOOK_REFILL_PER_MINUTE`.
- **Logs**: registram rota, status, `event_id` e `provider`; **nunca** o corpo
  completo, a assinatura ou os segredos.

## 3. Stripe

```http
POST /api/v1/payments/stripe/webhook
Stripe-Signature: t=<unix>,v1=<hex>
```

- Verificacao via SDK `stripe.Webhook.construct_event`, com
  `tolerance=WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS`.
- Dois segredos ativos: `STRIPE_WEBHOOK_SECRET` e
  `STRIPE_WEBHOOK_SECRET_PREVIOUS`; a verificacao tenta ambos e so falha se
  nenhum corresponder.
- Corpo bruto limitado por `WEBHOOK_MAX_BODY_BYTES`.
- Eventos irrelevantes ou de ambiente nao mapeado respondem 200
  (`{"received": true, "outcome": null}`) para o Stripe nao retentar.
- Assinatura invalida/expirada/ausente -> 401 sem detalhes.
- Eventos mapeados usam `ConfirmPayment` com `event_id`, garantindo
  processamento idempotente.

## 4. Rotacao de segredo sem janela de falha

1. Gere o segredo novo no provedor e configure-o como **atual**
   (`PAYMENT_WEBHOOK_SECRET` / `STRIPE_WEBHOOK_SECRET`).
2. Mova o antigo para `*_PREVIOUS` e reinicie a API (os dois sao aceitos).
3. Atualize os produtores para assinar com o novo.
4. Confirme `forja_payments_confirmed_total{method,outcome}`/logs sem falhas de assinatura.
5. Remova o `*_PREVIOUS` e reinicie.

O helper `verify_hmac_signature` percorre a lista inteira de segredos e combina
os resultados com `|=`, evitando retorno antecipado que revelaria qual segredo
casou.

## 5. Testes

`backend/tests/integration/test_payment_api.py` cobre:

- assinatura valida (timestamp e legado sem timestamp);
- assinatura invalida, ausente e timestamp expirado;
- corpo acima do limite (413);
- rotacao de segredo (assinatura com o segredo anterior);
- evento repetido (`DUPLICATE`) e concorrencia;
- Stripe: assinatura atual, anterior (rotacao), invalida, expirada e ausente.

## 6. Checklist para um webhook futuro

- [ ] Ler o corpo bruto antes do parse e limitar o tamanho.
- [ ] HMAC do provedor com comparacao em tempo constante.
- [ ] Timestamp assinado + tolerancia (padrao 5 min).
- [ ] Tabela de eventos com unique `(provider, event_id)`.
- [ ] Efeito de negocio e registro do evento na mesma transacao.
- [ ] Dois segredos ativos em variaveis de ambiente.
- [ ] Rate limit por IP/provedor e logs sem corpo/segredo.
- [ ] Testes de assinatura valida/invalida/ausente/expirada/repetida/rotacao.
