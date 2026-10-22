# ADR-0004: Busca híbrida (Elasticsearch + pgvector) com fusão por RRF

- **Status:** aceito; **semântica opcional, desligada por padrão**. O padrão do repositório é
  **lexical + fallback PostgreSQL** (`EMBEDDINGS_ENABLED=false`). O modo **`hybrid`** foi
  comprovado localmente na Fase 7 (2026-10-10), com o modelo habilitado, mas **não** é o
  estado de produção nem foi validado em provedor/ambiente gerenciado.
- **Data:** 2026-10-10 · **Revisão de estado:** 2026-10-22

## Contexto

A busca do catálogo precisa cobrir correspondência textual (nome/SKU/descrição, com tolerância a
acentos e erros de digitação), autocomplete e, também, consultas por **intenção/uso** que não
compartilham palavras exatas com o catálogo. Ao mesmo tempo, o projeto é B2B multi-tenant e os
dados comerciais (preço, disponibilidade, CA) **não podem** viver em um índice de busca.

## Decisão

1. **PostgreSQL é a fonte de verdade** dos dados comerciais e o **fallback textual**
   (`tsvector('portuguese')` + `unaccent` + `pg_trgm`).
2. **Elasticsearch** é o motor **lexical** (índice versionado `<alias>_vN` + alias estável),
   pesquisando nome, SKU (exato/prefixo), marca, categoria, CA e descrição, com filtros de
   publicação/disponibilidade sempre aplicados.
3. **pgvector** (extensão do PostgreSQL) guarda embeddings (384 dims) em tabela separada
   (`product_embeddings`, hash de conteúdo, índice HNSW cosine) para busca **semântica**.
4. A aplicação **funde** os dois caminhos por **Reciprocal Rank Fusion (RRF, k=60)** e **hidrata**
   do PostgreSQL (preço/visibilidade/autorização). O ES/pgvector devolvem apenas ids.
5. **Degradação explícita e informada** em `search_mode`: `hybrid` (ambos ok), `lexical`
   (vetorial indisponível), `semantic_postgres` (ES fora, vetorial ok),
   `postgres_fallback` (ambos fora). Tudo fora → erro, nunca lista vazia.
6. Consultas que **parecem SKU** dispensam o vetorial; o embed da consulta tem **timeout próprio**.

## Consequências

- O índice e os vetores são **derivados e reconstruíveis** (`bootstrap`/`reindex`/`backfill-embeddings`);
  nenhuma perda de dado comercial se um deles cair.
- Preço/estoque nunca entram no índice nem no texto embutido — reduz risco de vazamento e
  mantém a autorização no PostgreSQL.
- Só é chamada de **"híbrida"** quando os dois caminhos realmente executam; caso contrário, o
  modo real é reportado e registrado em métricas/logs.
- Custo: mais um componente (ES) e, quando habilitado, o modelo de embeddings in-process
  (~0,5–1,0 GB) — o sistema degrada para `lexical` se o backend não comportar o modelo.

## Validação (Fase 7, 2026-10-10)

Evidência real: índice versionado reconstruído (**41/41**), reconciliação corrigindo despublicação,
busca lexical (SKU no topo, acento, autocomplete, filtros) e **fallback real** com o ES parado
(`postgres_fallback`); com o modelo local habilitado, o `search_mode` foi **`hybrid`** em consultas
reais (ES + pgvector + RRF) e degradou para `lexical` sem o provedor. Medições (modelo 448 MB,
+172 MB de imagem, ~7 ms/embed) em `docs/search/RUNBOOK.md` §9.

## Estado real (2026-10-22)

- `EMBEDDINGS_ENABLED=false` no `.env.example` e no padrão de `Settings`. Com isso, o
  caminho semântico não é construído e a resposta é `lexical` ou `postgres_fallback`.
- O Elasticsearch está na versão 9.5.5 e o cliente Python em 9.5.1 (major 9). O índice
  versionado atual do mapping é **v2** (`ELASTICSEARCH_INDEX_VERSION=2`).
- A busca multilíngue (Fase 9B-b) consulta campos `en`/`es`/`ar` além do `pt-BR`. O
  fallback PostgreSQL continua textual em **português** — é uma limitação conhecida.
- Timeout de busca de 2 s, sem retries; circuit breaker de 3 falhas/15 s (ADR-0012).
- A validação de fallback com o Elasticsearch parado foi executada na V2
  (ver `docs/agent/PROGRESS.md`): `search_mode=postgres_fallback`, recuperação após
  `start` + `reconcile`, latências registradas. Não foi reexecutada em 2026-10-22.
- **Não validado:** `hybrid` no estado padrão, em produção, com múltiplas réplicas ou com
  catálogo grande. Não há teste de carga.

## Em produção real, seria diferente

- O modo semântico só entraria com avaliação de qualidade (precision/recall) e custo
  (memória do modelo, CPU, latência) contra o corpus real; não por ser “mais moderno”.
- O circuit breaker seria compartilhado entre réplicas, com backoff e métricas por tenant.
- O fallback PostgreSQL seria avaliado para os idiomas de conteúdo (`en`/`es`/`ar`) ou
  substituído por uma busca lexical degradada no próprio ES secundário.
- Haveria SLOs, alertas por `search_mode` e teste de carga; hoje só há medições pontuais.
- O índice teria ILM/rollover, snapshots e réplicas; o alias continuaria sendo o ponto de
  troca atômica.

## Alternativas consideradas

- **Só PostgreSQL (FTS + trigram):** simples, mas sem ranking lexical robusto nem autocomplete tão bons.
- **Só Elasticsearch (com vetores densos no ES):** acopla embeddings ao ES e dificulta regerar/reverter.
- **Serviço externo de embeddings (API paga):** descartado por decisão do responsável (embeddings
  locais, sem API paga nem serviço externo).
