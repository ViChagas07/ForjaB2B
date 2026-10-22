# ADR-0011: Idempotência por chave única no banco

- **Status:** aceito e implementado (chave no corpo, não no header `Idempotency-Key`)
- **Data:** 2026-10-09
- **Contexto do código:** `backend/app/modules/ordering/infrastructure/repository.py`,
  `backend/app/modules/payment/infrastructure/repository.py`,
  `backend/app/modules/credit/infrastructure/repository.py`,
  `backend/app/modules/ordering/interface/schemas.py`,
  `backend/app/modules/payment/interface/schemas.py`

## Contexto

Criar pedido, iniciar pagamento e lançar crédito podem ser repetidos por timeout, retry de
rede ou duplo clique. Sem idempotência, o cliente cria dois pedidos ou cobra duas vezes.
O projeto é multi-tenant; a chave de idempotência precisa ser única **por empresa**, não
global.

## Decisão

1. Pedidos, pagamentos e lançamentos de crédito aceitam um `idempotency_key` (string de
   1 a 64 caracteres) **no corpo JSON**, não no header HTTP.
2. Cada tabela tem índice único parcial `(company_id, idempotency_key)` (quando a chave não
   é nula); a inserção usa a constraint e trata conflito.
3. O caso de uso procura a chave antes de criar; se já existe, devolve o recurso existente.
   Se duas requisições concorrem, o banco decide e a perdedora recebe `409` de conflito.
4. O efeito é transacional: pedido, itens, reserva de crédito e evento de outbox commitam
   juntos; um retry não duplica o efeito.
5. O webhook de pagamento tem idempotência adicional por `(provider, event_id)`.

## Alternativas consideradas

- **Header `Idempotency-Key`:** é o padrão de mercado e será adotado em produção, mas o
  contrato atual do frontend/testes usa o corpo. Não foi trocado nesta entrega para não
  quebrar o cliente.
- **Chave só em memória/Redis:** perde a garantia após restart e não cobre concorrência
  entre réplicas.
- **Deduplicação por payload:** frágil; dois pedidos legítimos iguais seriam bloqueados.
- **Sem idempotência, só retry do cliente:** inaceitável para pedido/pagamento.

## Consequências

- O cliente precisa gerar e reenviar a mesma chave em retries; a documentação da API deve
  deixar isso explícito.
- Não há middleware genérico: cada caso de uso implementa a leitura/checagem.
- A chave fica no corpo e aparece em logs se o payload for logado; hoje não se loga o corpo
  inteiro, mas isso deve continuar sendo regra.
- O `409` é usado para conflito de idempotência e para concorrência otimista de produto;
  clientes precisam distinguir pelo `type`/`detail` do Problem Details.

## Em produção real, seria diferente

- Aceitar `Idempotency-Key` no header (com fallback temporário para o corpo) e calcular um
  fingerprint do request; rejeitar a mesma chave com payload diferente (`422`).
- Guardar a resposta original por um TTL (24 h) para replay idempotente, em vez de só
  retornar o recurso existente.
- Limpar chaves antigas com job/partição e monitorar colisões e taxa de replay.
- Padronizar o middleware para todos os POSTs mutáveis, não só pedido/pagamento/crédito.
- Ter testes de concorrência com múltiplas conexões e de payload divergente.
