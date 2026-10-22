# ADR-0012: Timeouts curtos e circuit breaker na busca

- **Status:** aceito e implementado; validado localmente (medições de 2026-10-10)
- **Data:** 2026-10-10
- **Contexto do código:** `backend/app/core/config.py`,
  `backend/app/modules/search/application/search.py`,
  `backend/app/modules/search/infrastructure/elasticsearch.py`,
  `backend/app/core/metrics.py`

## Contexto

Com o Elasticsearch indisponível, a primeira versão da busca esperava ~15 s por request
antes de cair no fallback. Isso derruba a experiência e ocupa conexões. Indexação e busca
têm perfis diferentes: a busca precisa responder rápido; a indexação pode esperar e
retentar.

## Decisão

1. **Timeouts separados por uso:**
   - busca interativa: `ELASTICSEARCH_SEARCH_TIMEOUT_SECONDS=2` e
     `SEARCH_MAX_RETRIES=0`;
   - indexação/reindex/reconcile: `30 s` e `3` retries.
2. **Circuit breaker simples no processo:** após `SEARCH_CIRCUIT_BREAKER_FAILURES=3`
   falhas consecutivas, o caminho lexical é ignorado por
   `SEARCH_CIRCUIT_BREAKER_COOLDOWN_SECONDS=15`; depois o próximo request tenta de novo
   (meia-abertura implícita). Sucesso zera as falhas.
3. **Fallback explícito:** com o breaker aberto ou o ES fora, a busca usa
   `PostgresSearchReader` (`tsvector('portuguese')` + `unaccent` + `pg_trgm`) e reporta
   `search_mode=postgres_fallback`.
4. **Semântica opcional:** o embed da consulta tem timeout próprio
   (`EMBEDDING_QUERY_TIMEOUT_SECONDS=2`); se falhar, a busca continua lexical.
5. **Observabilidade:** cada resultado registra `search_completed` com `search_mode` e
   duração; há métricas `forja_search_requests_total`/`forja_search_duration_seconds`.
6. **Indexação não é afetada:** falha de busca não bloqueia o catálogo; falha de indexação
   fica na outbox e é reprocessável.

## Alternativas consideradas

- **Timeout global único:** simples, mas ou é curto demais para indexar ou longo demais
  para buscar.
- **Retries na busca:** piora a latência em indisponibilidade; rejeitado.
- **Breaker compartilhado no Redis/Envoy:** melhor em múltiplas réplicas, mas adiciona
  dependência; o breaker atual é por processo.
- **Sem breaker, só timeout:** cada request paga 2 s; o breaker reduz para ~10 ms depois
  das falhas.

## Consequências

- Medição local (ES parado): ~15,4–15,7 s antes; ~1,8–2,0 s com timeout; ~10 ms com o
  breaker aberto; recuperação automática ao voltar o ES.
- O breaker é **por worker/processo**; com várias réplicas, cada uma aprende separado.
- O cooldown fixo não tem backoff exponencial nem jitter.
- Uma falha isolada de rede pode abrir o breaker para todos os tenants daquele processo.
- O fallback PostgreSQL não usa traduções (busca apenas `pt-BR`).

## Em produção real, seria diferente

- Usar um breaker compartilhado (Envoy/Istio, Redis ou biblioteca com estado distribuído) e
  backoff exponencial com jitter.
- Definir SLOs (p95/p99) e alertas por `search_mode`, taxa de fallback e latência.
- Fazer teste de carga (ver `docs/testing/LOAD.md`) para calibrar timeouts com o volume real.
- Ter um pool de conexões dedicado e limites por tenant para evitar que um cliente consuma
  todas as conexões do ES.
- Considerar cache de resultados para consultas repetidas e degradação para lexical antes
  de abrir o breaker.
