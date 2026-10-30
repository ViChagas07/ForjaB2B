# Cupons de desconto

Sistema de cupons do Forja B2B: cadastro pelo admin, validação no checkout e
resgate atômico no pedido. Dinheiro usa `Decimal`/`Numeric` de ponta a ponta;
o backend é a fonte de verdade e o front apenas exibe os valores calculados.

## Regras

- Dois tipos:
  - `PRODUCT_TOTAL`: abate um percentual do subtotal dos produtos.
  - `SHIPPING`: abate um percentual do frete; `100` equivale a frete grátis.
- Um único cupom por pedido.
- Percentual entre `0,01` e `100`.
- Código normalizado (`trim` + maiúsculas), único, `A-Z`, `0-9`, hífen e
  underscore, de 4 a 32 caracteres.
- Opcionais: início/fim de validade, limite total de usos, limite por empresa,
  pedido mínimo, teto de desconto e restrição a uma empresa.
- Cupom `PRODUCT_TOTAL` e oferta de recuperação não acumulam; o cupom prevalece.
- O desconto PIX (5%) continua valendo sobre o valor já abatido pelo cupom.

## Ordem de cálculo

1. Preço unitário da empresa e regras de quantidade geram o subtotal.
2. Oferta de recuperação entra somente se não houver cupom `PRODUCT_TOTAL`.
3. Cupom `PRODUCT_TOTAL` sobre o subtotal, limitado pelo teto e pelo subtotal.
4. Frete; cupom `SHIPPING` sobre o frete, limitado pelo teto e pelo frete.
5. PIX opcional sobre o valor restante (produtos + frete após descontos).
6. Total nunca negativo; arredondamento em centavos com `ROUND_HALF_UP`.

`orders.discount_total` continua representando somente a oferta de recuperação.
O cupom é persistido separadamente em `coupon_discount_amount` e
`shipping_discount_amount`, e `shipping_total` guarda o frete líquido.

## Snapshot do pedido

O pedido guarda, no momento da criação:

- `coupon_code`, `coupon_type`, `coupon_percent`;
- `coupon_discount_amount`, `shipping_discount_amount`;
- `total` recalculado pelo backend.

Editar ou desativar o cupom depois não altera pedidos existentes.

## Endpoints

### Admin (`ADMIN`)

- `POST /api/v1/admin/coupons` cria o cupom; `code` omitido gera `FORJA-XXXXXX`.
- `POST /api/v1/admin/coupons/generate-code` sugere um código.
- `GET /api/v1/admin/coupons` lista com busca, status (`ACTIVE`, `EXPIRED`,
  `EXHAUSTED`), paginação e agregados de uso.
- `GET /api/v1/admin/coupons/{id}` detalha com total de usos, valor descontado
  e últimos resgates.
- `PATCH /api/v1/admin/coupons/{id}` edita; `code`/`type` ficam imutáveis depois
  do primeiro resgate.
- `DELETE /api/v1/admin/coupons/{id}` só funciona sem resgates; com resgates,
  retorna 409 e orienta desativar.

Erros de duplicidade/immutabilidade usam 409; validação usa 422.

### Checkout

- `POST /api/v1/orders/coupon-preview` valida e simula sem gravar. Corpo:
  `{ "code": "CUPOM10", "payment_method": "PIX" }`. `code` nulo devolve o resumo
  base sem cupom. Cupom inválido responde 200 com `valid: false` e `reason`.
- `POST /api/v1/orders` aceita `coupon_code` opcional. O cupom é revalidado e
  reservado na mesma transação do pedido, com advisory lock por cupom e
  `coupon_redemptions` único por pedido.
- `POST /api/v1/orders/{id}/cancel` marca o resgate como `RELEASED`.
- Falha/expiração definitiva de PIX/cartão também cancela o pedido e libera o
  resgate. Boleto segue o ciclo da fatura e não libera automaticamente.

Motivos tipados da prévia: `NOT_FOUND`, `INACTIVE`, `NOT_STARTED`, `EXPIRED`,
`EXHAUSTED`, `COMPANY_LIMIT_REACHED`, `MIN_ORDER_NOT_MET` (com
`missing_amount`). `NOT_ALLOWED_FOR_COMPANY` existe na elegibilidade interna,
mas a resposta pública usa `NOT_FOUND` para não revelar a existência de cupom
restrito a outra empresa.

O preview tem dois token buckets: 10 de burst e 30/min por usuário
(`RATE_LIMIT_COUPON_PREVIEW_*`) e 30 de burst e 60/min por IP
(`RATE_LIMIT_COUPON_PREVIEW_IP_*`).

## Como criar um cupom no admin

1. Acesse `/admin/cupons` e clique em **Novo cupom**.
2. Informe o código (ou use **Gerar código**), escolha **Desconto nos produtos**
   ou **Desconto no frete** e o percentual.
3. Opcionalmente abra **Condições avançadas** para validade, limites, pedido
   mínimo, teto e empresa específica (UUID).
4. Confira o resumo em linguagem natural e salve.
5. Na listagem/detalhe é possível ativar/desativar e acompanhar usos, valor
   descontado e últimos resgates.

## Onde o cupom aparece

- Resumo do checkout: cupom aplicado, linhas de desconto, frete/grátis, PIX e
  total.
- Detalhe do pedido do comprador: código do cupom e valores de desconto
  persistidos no snapshot.
- Notificações `order.created` (e-mail/WhatsApp): resumo de valores e cupom
  quando aplicável.
- Admin: detalhe do cupom com agregados de uso.
- Não existem, no código atual, uma tela de histórico de pedidos nem um detalhe
  de pedido específico do admin. Os contratos já expõem os campos de cupom para
  quando essas telas forem criadas.

## Testes

- Backend: domínio, elegibilidade, cálculo, API admin, checkout, concorrência,
  liberação e notificações.
- Frontend: schemas, API, formulário admin, bloco do checkout, revalidação,
  i18n dos 11 locales e detalhe do pedido.
- E2E Playwright: admin cria/listar/desativar, checkout aplica/remove e fluxo
  completo com dois cupons (produtos e frete 100%) e cancelamento.

## Segurança

- Schemas usam `extra="forbid"`; descontos, percentual e total enviados pelo
  cliente são rejeitados. O servidor recalcula tudo em `Decimal`.
- Código é normalizado e limitado a `A-Z`, `0-9`, hífen e underscore (4–32);
  entrada hostil/unicode é rejeitada e a exibição React/HTML escapa o valor.
- Resgates são serializados por advisory lock e contagem global; o resgate é
  único por pedido e a liberação só altera `APPLIED -> RELEASED`.
- `NOT_ALLOWED_FOR_COMPANY` é interno; publicamente vira `NOT_FOUND` para não
  revelar cupons de outras empresas.
- Preview tem limite por usuário **e** por IP. Admin exige papel `ADMIN` em
  todos os métodos; escrita usa `forja_admin` e o runtime lê cupons apenas.
- Alterações de `code`/`type` no admin adquirem o mesmo advisory lock dos
  resgates antes de recontar, fechando a corrida com o primeiro uso.
- Auditoria registra criação/edição/exclusão apenas com código, tipo e campos
  alterados; resgates ficam em `coupon_redemptions`, sem PII.

## Limitações conhecidas

- A validação de frete por endereço não existe no checkout atual; o frete é
  derivado do carrinho. A revalidação cobre itens/carrinho e pagamento.
- Boleto com falha definitiva não libera o cupom automaticamente.
- O rate limiter é fail-open se o Redis falhar e o IP real depende da
  configuração correta de proxies confiáveis (`TRUSTED_PROXY_COUNT`).
- Uma vez conhecido um código válido, os estados `INACTIVE`/`EXPIRED`/etc.
  ainda são distinguíveis de `NOT_FOUND`; o limite por usuário/IP reduz
  enumeração, mas não a elimina.
- E2E e integração com Docker dependem de ambiente com seed e
  `DEMO_USER_PASSWORD`; consulte o relatório de cada fase no
  [PROGRESS](agent/PROGRESS.md).
