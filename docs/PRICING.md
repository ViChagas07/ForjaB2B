# Precificação e desconto CNPJ

## Regra

Contas com `companies.account_type = 'COMPANY'` (CNPJ) recebem desconto automático por linha:

| Faixa | Quantidade da linha (mesmo produto) | Desconto |
| :--- | :--- | :--- |
| Padrão | 1 a 29 unidades | 15% |
| Volume | 30 unidades ou mais | 30% |

- A quantidade é **por produto**, nunca a soma do carrinho. `10 luvas + 20 óculos` deixa os dois em 15%; `30 luvas + 10 óculos` deixa luvas em 30% e óculos em 15%.
- Contas `PERSON` (CPF) e visitantes não recebem esse desconto; o comportamento anterior é preservado.
- Linhas repetidas do mesmo `product_id` no payload de pedido são somadas antes de precificar, para não burlar a faixa de volume.
- O desconto incide sobre o preço já resolvido para a empresa/tier (preço de tabela efetivo). Cupom e recuperação de carrinho incidem depois, sobre o valor já descontado. O total nunca fica negativo.
- Dinheiro é sempre `Decimal`, com arredondamento `ROUND_HALF_UP` ao centavo (nunca `float`).

## Onde ficam as constantes e a regra

Arquivo único: `backend/app/domain/pricing.py`.

- `CNPJ_ACCOUNT_TYPE = "COMPANY"`
- `CNPJ_STANDARD_DISCOUNT_PERCENT = Decimal("15.00")`
- `CNPJ_VOLUME_DISCOUNT_PERCENT = Decimal("30.00")`
- `CNPJ_VOLUME_MIN_QUANTITY = 30`
- `resolve_cnpj_price(account_type, quantity, list_unit_price)` — função pura, valida quantidade inteira >= 1 e devolve preço de tabela, preço final, percentual, faixa e unidades restantes.
- `resolve_customer_price(...)` — compõe a regra da empresa/tier com o desconto CNPJ. É usada por carrinho e pedido.

O catálogo usa `resolve_cnpj_price` com quantidade 1 para exibir os 15% na listagem/detalhe. O carrinho e o pedido usam a quantidade real da linha (15% ou 30%).

## Fonte de verdade e API

O frontend nunca calcula preço. Ele apenas formata/converte os valores devolvidos pela API para a moeda de exibição; a cobrança é sempre em BRL.

- **Catálogo** (`/api/v1/catalog/products` e `/products/{id}`): `list_unit_price`, `unit_price`, `discount_percent`, `discount_band`.
- **Carrinho** (`/api/v1/cart`): por item, `list_unit_price`, `unit_price`, `list_line_total`, `discount_amount`, `discount_percent`, `discount_band`, `units_to_volume_discount`; no total, `list_subtotal`, `cnpj_discount_total` e `subtotal` (final).
- **Preview de checkout** (`/api/v1/orders/coupon-preview`): `list_subtotal`, `cnpj_discount_total`, `subtotal` e `total`.
- **Pedido** (`/api/v1/orders`): por item, `list_unit_price`, `list_line_total`, `cnpj_discount_percent`, `cnpj_discount_band`, `cnpj_discount_amount` e `unit_price` final; no total, `list_subtotal`, `cnpj_discount_total`, `subtotal` e `total`.

O tipo de conta é lido do banco no carrinho/pedido (`companies.account_type`). No catálogo, a exibição usa o claim assinado do token; checkout e pedido revalidam no servidor.

## Snapshot do pedido

O snapshot fica em uma tabela nova, `order_item_pricing`, com relação 1:1 **lógica** (PK em `order_item_id`), sem FK para tabelas existentes:

- `order_item_id` — PK, mesmo UUID de `order_items.id` (sem FK);
- `list_unit_price` — preço de tabela antes do CNPJ;
- `list_line_total` — preço de tabela × quantidade;
- `cnpj_discount_percent` — 15.00 ou 30.00;
- `cnpj_discount_band` — 15 ou 30;
- `cnpj_discount_amount` — economia CNPJ da linha.

`order_items.unit_price` continua sendo o preço final e **não** foi alterado. A migration `0042_order_item_cnpj_discount` apenas cria a tabela nova (e suas policies RLS); não executa `ALTER TABLE` em nenhuma tabela existente e não cria FK para tabela existente.

Motivo: em produção a role `forja` não é owner de `order_items`/`products` e não tem `REFERENCES` nelas; `ALTER TABLE ... ADD COLUMN` e `CREATE TABLE ... REFERENCES order_items` falham com `InsufficientPrivilegeError`. Criar uma tabela nova não depende de ownership, GRANT ou FK. A integridade é garantida pelo código:

- o repositório grava o item e a linha de `order_item_pricing` na **mesma transação**;
- a leitura usa `LEFT JOIN` e trata a ausência como "sem snapshot" (pedidos antigos);
- nenhum fluxo da aplicação apaga `order_items` (cancelamento muda o status do pedido; retenção/fiscalização preservam o histórico). Se um fluxo futuro apagar itens, ele deve apagar também `order_item_pricing` na mesma transação. Os testes de integração que limpam dados apagam o snapshot antes dos itens.

Mudanças futuras de regra não recalculam pedidos existentes.

## Banco local que aplicou a 0042 antiga

A 0042 antiga adicionava colunas em `order_items`; ela nunca foi aplicada em produção, mas pode existir em um banco local/dev. Para migrar para o formato novo:

1. Antes de puxar o código novo, rode `alembic downgrade 0041` (com a migration antiga) para remover as colunas. O `downgrade` antigo fazia exatamente isso.
2. Atualize o código e rode `alembic upgrade head`; a 0042 nova cria `order_item_pricing`.

Se o código novo já foi baixado e o banco está em 0042 com as colunas antigas:

1. `alembic downgrade 0041` remove a tabela `order_item_pricing` (que talvez nem exista), mas **não** remove as colunas antigas.
2. Como owner do banco local, remova manualmente as colunas antigas de `order_items` (`list_unit_price`, `cnpj_discount_percent`, `cnpj_discount_band`) ou restaure o backup anterior.
3. Confirme `alembic_version = 0041`, rode `alembic upgrade head` e `alembic check`.

Em produção não há nada a limpar: o deploy falhou antes de aplicar a 0042, então a revisão permanece em 0041.

## Testes de referência

- `backend/tests/unit/test_cnpj_discount.py` — faixas 1/29/30/31, 10+20, 30+10, duplicatas, arredondamento, cupom/recovery, total não negativo, payload adulterado e cobrança BRL.
- `backend/tests/integration/test_cnpj_discount_api.py` — fluxo HTTP real CNPJ x CPF, carrinho, preview, pagamento e snapshot.
- `backend/tests/integration/test_cnpj_migration.py` — migration 0042 do zero, banco populado, downgrade, re-upgrade e execução com role que não é owner e **não tem `REFERENCES`** em `order_items`.
