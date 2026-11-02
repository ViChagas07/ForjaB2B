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

A migration `0042_order_item_cnpj_discount` adiciona em `order_items`, de forma nullable e sem backfill:

- `list_unit_price` — preço de tabela antes do CNPJ;
- `cnpj_discount_percent` — 15.00 ou 30.00;
- `cnpj_discount_band` — 15 ou 30.

`unit_price` continua sendo o preço final da linha. Pedidos antigos ficam com `NULL` e não são alterados. Mudanças futuras de regra não recalculam pedidos existentes.

## Testes de referência

- `backend/tests/unit/test_cnpj_discount.py` — faixas 1/29/30/31, 10+20, 30+10, duplicatas, arredondamento, cupom/recovery, total não negativo, payload adulterado e cobrança BRL.
- `backend/tests/integration/test_cnpj_discount_api.py` — fluxo HTTP real CNPJ x CPF, carrinho, preview, pagamento e snapshot.
- `backend/tests/integration/test_cnpj_migration.py` — migration 0042 do zero, banco populado, downgrade e re-upgrade sem perda de dados.
