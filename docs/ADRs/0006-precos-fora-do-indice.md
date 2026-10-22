# ADR-0006: Preços fora do índice e preço consultivo para visitante

- **Status:** aceito e implementado
- **Data:** 2026-10-10
- **Contexto do código:** `backend/app/domain/pricing.py`,
  `backend/app/infrastructure/db/company_pricing.py`,
  `backend/alembic/versions/0014_company_pricing.py`,
  `backend/app/modules/search/application/search.py`

## Contexto

Preço B2B é negociado por empresa e pode ser considerado informação sensível. O catálogo é
global e a busca é servida por um índice derivado (Elasticsearch) e, opcionalmente, por
vetores (pgvector). Se o preço entrar no índice, ele pode vazar para outro tenant, ficar
desatualizado e criar cardinalidade alto no mapping. O visitante não deve ver preço de
nenhuma empresa.

## Decisão

1. **Nenhum preço, desconto, tier, crédito ou dado privado entra no Elasticsearch ou nos
   embeddings.** O índice guarda apenas conteúdo público e IDs.
2. O preço é resolvido no PostgreSQL, por empresa, na seguinte precedência:
   **preço negociado (`FIXED_PRICE`) > desconto percentual (`PERCENT_DISCOUNT`, por
   categoria ou global) > preço de lista (tier por quantidade ou `base_unit_price`)**.
3. As regras vivem em `company_price_rules`, com RLS por `company_id`; a leitura é feita
   dentro da UoW já aberta com o tenant.
4. Visitante (sem JWT) recebe `price_on_request=true` e `base_unit_price=null`; empresa
   autenticada recebe o preço resolvido. O tenant vem do token.
5. Busca, carrinho e pedido **revalidam** o preço no PostgreSQL. A hidratação acontece
   depois da busca; IDs que não existem mais ou não são vendáveis são descartados.
6. Dinheiro é `Decimal`, arredondamento `ROUND_HALF_UP` ao centavo.

## Alternativas consideradas

- **Preço no índice para ordenar/filtrar:** rejeitado por vazamento, staleness e
  cardinalidade. A ordenação por preço fica fora do escopo.
- **Preço no JWT:** reduz uma consulta, mas o token fica grande, não reflete mudanças e
  aumenta a superfície de exposição.
- **Preço calculado no cliente:** inaceitável em B2B; o servidor é a autoridade.
- **Materialized view global de preços:** não resolve o isolamento por tenant.

## Consequências

- A busca não ordena por preço; ordena por relevância/nome.
- Cada resultado exige hidratação e leitura de regras no PostgreSQL — custo aceitável no
  volume de demonstração, mas um ponto de atenção em escala.
- O snapshot do pedido guarda o preço efetivo; mudanças posteriores de regra não reescrevem
  o passado.
- O catálogo público de visitante não expõe `base_unit_price` (corrigido na Fase 9A-2).

## Em produção real, seria diferente

- Cachear o preço resolvido por `(company_id, product_id, quantity)` com TTL curto e
  invalidação por evento de regra; hoje não há cache.
- Criar uma view/materialização por tenant para relatórios, nunca para a resposta pública.
- Auditar alterações de regra de preço (quem, quando, valor anterior) e permitir vigência.
- Ter testes de contrato garantindo que nenhum campo de preço aparece no documento
  indexado ou no texto do embedding.
- Se ordenação por preço for necessária, fazer a ordenação após a hidratação, com limite
  de candidatos e uma métrica de custo — não colocando preço no índice.
