# Testes de carga — estado e roteiro

> **Status: NÃO EXECUTADO.** Não há k6, Locust, Gatling ou resultados de carga
> versionados neste repositório. Nenhum número de throughput, latência ou erro de carga
> deve ser atribuído a este projeto. Este documento existe para registrar a lacuna e o
> procedimento, não para simular resultados.

## Por que não foi executado

- O projeto não tem ambiente de staging nem SLOs acordados; medir na máquina de
  desenvolvimento não representa o Render nem qualquer provedor.
- O catálogo de demonstração tem 50 produtos; o volume não exercita sharding, cache frio
  ou concorrência realista.
- A stack local tem falhas conhecidas (`forja-grafana` e `forja-celery-beat` reiniciando),
  que contaminariam a medição.
- As regras do projeto proíbem declarar executado o que não foi observado.

## O que existe hoje como evidência de latência (não é teste de carga)

- Medições pontuais da busca na validação V2 (ver `docs/agent/PROGRESS.md`): lexical
  **68–162 ms**; fallback após parar o Elasticsearch **~2,05 s** na primeira chamada e
  **8–15 ms** com o circuit breaker aberto; recuperação **28–61 ms** após `start` +
  `reconcile`.
- Essas medições são de uma sessão local, com dados de demonstração. **Não são** um teste
  de carga e **não** representam o Render.

## Roteiro proposto (quando houver staging)

1. **Ambiente:** staging com a mesma topologia de produção (PostgreSQL gerenciado, Redis,
   Elasticsearch com TLS, backend com o número real de workers) e dados anonimizados.
2. **Ferramenta:** k6 (script versionado em `docs/testing/` ou `scripts/load/`) com
   cenários independentes:
   - catálogo: lista + detalhe;
   - busca lexical: termos com resultado, SKU exato e termo sem resultado;
   - busca com fallback: derrubar o Elasticsearch de forma controlada;
   - carrinho/pedido: criar, adicionar, checkout com idempotência;
   - autenticação: login e refresh (com limite de tentativas).
3. **Carga:** rampa gradual (ex.: 1 → 10 → 50 → 100 VUs), com patamares estáveis e
   duração suficiente para observação; não usar picos sem aquecimento.
4. **Métricas:** p50/p95/p99, throughput, taxa de erro, 429, tempo de conexão, pool de
   banco, CPU/memória do backend, latência e CPU do Elasticsearch, lag da outbox,
   `search_mode` e taxa de fallback.
5. **Critérios:** definir SLOs **antes** (ex.: p95 de busca < 300 ms com ES saudável;
   erro < 0,5%) e registrar desvios.
6. **Segurança:** nunca apontar para produção; usar dados fictícios; não imprimir tokens
   ou corpos com PII nos logs do teste.
7. **Relatório:** versionar o script, o commit, a configuração do ambiente, os gráficos e
   as conclusões. Sem isso, o resultado não é reproduzível.

## O que não fazer

- Não copiar números de latência de uma máquina local para o README como se fossem carga.
- Não comparar Render (ou qualquer provedor) sem executar lá.
- Não usar o teste para “provar” que a busca híbrida é necessária; a semântica está
  desligada por padrão e precisa de avaliação própria (qualidade, custo, memória).
