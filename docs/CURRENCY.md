# Moeda de exibicao

O Forja B2B armazena, calcula e cobra tudo em **BRL**. A moeda escolhida em
Configuracoes e apenas uma preferencia de **exibicao**: o backend continua
enviando os valores em reais para o Stripe, para os pedidos e para os totais.
Nenhum payload de criacao de pedido/pagamento aceita campo de moeda (os schemas
usam `extra="forbid"`).

## Lista fechada

Moedas aceitas: `BRL`, `USD`, `EUR`, `GBP`, `CAD`, `AUD`, `JPY`, `CNY`.
Padrao: `BRL`. Qualquer valor desconhecido (cookie, perfil, query ou payload
interno) cai em `BRL`. A lista compartilhada fica em:

- backend: `backend/app/domain/currency.py` e no check da migration `0038`;
- frontend: `frontend/core/domain/currency.ts`;
- request de preferencias: normalizado pelo caso de uso `UpdateAccountCurrency`
  (valor invalido vira `BRL`, nao e persistido).

## Taxas

- Provedor: **Frankfurter**, endpoint fixo
  `https://api.frankfurter.dev/v2/providers/ecb/rates`.
- Fonte efetiva: **Banco Central Europeu (ECB)**; o rotulo exibido e
  `Frankfurter / European Central Bank`.
- A URL e constante no servidor. Nenhuma entrada do usuario entra nela.
- Resposta: lista de linhas `{date, base, quote, rate}`. O campo `date` e a
  **data de referencia da taxa** (publicacao do BCE), nao a data da consulta.
  Em fim de semana/feriado ela e anterior ao dia atual.
- Timeout de 5s e no maximo 1 retry.
- Taxas zero, negativas, `NaN`, infinitas, ausentes ou de moeda fora da lista
  sao rejeitadas; nada invalido e gravado no cache.
- A conversao e `valor_brl x taxa(BRL -> moeda)`. O arredondamento acontece
  somente no `Intl.NumberFormat`, no frontend. JPY nao tem centavos por padrao.

## Cache e fallback

- Redis fresco: chave `fx:rates:brl:v1:fresh`, TTL de **12 horas**.
- Ultima conhecida: chave `fx:rates:brl:v1:last-known`, TTL de **7 dias**.
- Lock de refresh: `fx:rates:brl:v1:refresh-lock`, TTL de 15s, para apenas uma
  requisicao consultar a Frankfurter quando o cache expira (anti-stampede).
- Se o provedor falhar e houver ultima conhecida, a resposta traz
  `stale: true` e a data/fonte originais. Se nunca houve taxa, a API responde
  `503` com `fx_rates_unavailable` e o app segue em BRL sem quebrar.
- O frontend busca `GET /api/v1/fx/rates` no layout com `revalidate` de 12h e
  tag `fx:rates`; nao ha polling. Em falha, o bootstrap fica em BRL.

## Frontend

- `CurrencyProvider` recebe o estado pronto do servidor (cookie + taxas), sem
  leitura de cookie no cliente e sem hydration mismatch.
- `setCurrency` grava o cookie `forja_currency` (Path=/, SameSite=Lax, 1 ano)
  e atualiza o estado na hora. Se autenticado, `CurrencyProfileSync` persiste a
  preferencia em `PATCH /api/v1/account/preferences` (best-effort).
- `formatMoney(valorBrl, opcoes)` converte e prefixa `aprox.` (`≈`); `formatBrl`
  sempre mostra reais; `formatRateDate` usa `Intl.DateTimeFormat` em UTC;
  nomes de moeda usam `Intl.DisplayNames`.
- `RateDisclosure` mostra fonte, data de referencia e aviso de taxa
  desatualizada em produto, carrinho e checkout. Permanece oculto em BRL.

## Como adicionar uma moeda

1. Inclua o codigo ISO na lista compartilhada do backend
   (`app/domain/currency.py`) e no `DisplayCurrency` de
   `modules/identity/interface/schemas.py`.
2. Crie uma migration para trocar o check `display_currency` da tabela `users`.
3. Inclua o codigo em `frontend/core/domain/currency.ts` (o tipo e os testes
   derivam da lista).
4. Confirme que a Frankfurter/ECB publica a moeda em
   `/v2/providers/ecb/rates`; se nao publicar, o adaptador deve ser revisto.
5. Atualize os testes de paridade/formatacao; os textos de UI nao precisam de
   traducao manual porque o nome vem do `Intl.DisplayNames`.
6. Rode `pytest tests/unit`, `npm run check` e os testes de integracao de
   conta/pedido/pagamento.

Observacao: adicionar moeda **nao** altera a cobranca. Se um dia a cobranca
multi-moeda for necessaria, ela sera outro fluxo, com regras fiscais e de
precificacao proprias.
