# ADR-0004: Busca híbrida (Elasticsearch + pgvector) com fusão por RRF

- **Status:** aceito; implementado e **validado localmente em 2026-10-10** (Fase 7). Em produção,
  o padrão do repositório é **lexical + fallback PostgreSQL**; o modo **`hybrid`** foi comprovado
  localmente com o modelo de embeddings habilitado (ver `docs/STATUS.md`).
- **Data:** 2026-10-10

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

## Alternativas consideradas

- **Só PostgreSQL (FTS + trigram):** simples, mas sem ranking lexical robusto nem autocomplete tão bons.
- **Só Elasticsearch (com vetores densos no ES):** acopla embeddings ao ES e dificulta regerar/reverter.
- **Serviço externo de embeddings (API paga):** descartado por decisão do responsável (embeddings
  locais, sem API paga nem serviço externo).
