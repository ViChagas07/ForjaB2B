# ADR-0009: Outbox, reconciliação e índice versionado com alias

- **Status:** aceito e implementado (worker/beat com falha local conhecida)
- **Data:** 2026-10-10
- **Contexto do código:** `backend/app/infrastructure/db/outbox.py`,
  `backend/app/modules/search/application/sync.py`,
  `backend/app/modules/catalog/infrastructure/admin_repository.py`,
  `backend/alembic/versions/0011_search_outbox.py`,
  `backend/app/modules/search/interface/cli.py`,
  `backend/app/tasks/celery_app.py`

## Contexto

O catálogo pode ser editado no admin enquanto o Elasticsearch está indisponível. Uma
escrita dupla (PostgreSQL + Elasticsearch) perde eventos se o segundo passo falhar. O
índice também precisa ser reconstruível sem derrubar a busca e sem perder documentos.

## Decisão

1. **Outbox transacional:** toda mutação de catálogo grava o produto e um evento
   `UPSERT`/`DELETE` em `search_outbox` **na mesma transação**. Se o commit falha, o evento
   não existe; se commitou, o evento fica pendente para o worker.
2. **Dispatch assíncrono:** Celery beat roda `dispatch_search_outbox` a cada 15 s e
   `reconcile_search_index` a cada 15 min. Eventos têm `attempts` e limite
   (`SEARCH_OUTBOX_MAX_ATTEMPTS`, padrão 5).
3. **Índice versionado:** a reindexação cria `<alias>_vN` (ex.: `forja_products_v2`),
   indexa em lotes, valida a contagem contra o PostgreSQL e só então troca o alias
   `forja_products` de forma atômica. O índice anterior permanece para rollback.
4. **Falha visível:** qualquer documento rejeitado no `bulk` ou divergência de contagem
   acima de `SEARCH_REINDEX_COUNT_TOLERANCE` (padrão 0) faz o comando sair com código
   diferente de zero e **não troca o alias**.
5. **Reconciliação:** compara `version` (epoch ms de `updated_at`) e presença no índice;
   reaplica documentos desatualizados, remove órfãos e reporta `rejected`.
6. **Versionamento externo:** o documento indexado usa a versão do produto; um evento
   antigo não sobrescreve um documento mais novo.

## Alternativas consideradas

- **Escrita dupla direta no request:** simples, mas perde evento se o ES falhar e aumenta a
  latência do admin. Rejeitado.
- **CDC (Debezium) lendo o WAL:** robusto e desacoplado, mas adiciona Kafka/Connect e
  complexidade operacional desproporcional ao projeto.
- **Índice único recriado no lugar:** janela de indisponibilidade e sem rollback trivial.
  Rejeitado.
- **Índice como fonte de verdade:** não atende preço/autorização. Rejeitado.

## Consequências

- A busca é **eventualmente consistente**; o atraso depende do worker/beat.
- O beat é um ponto único de falha local; nesta máquina ele está em restart por permissão
  de escrita em `celerybeat-schedule`, então a reconciliação automática não roda.
- A reindexação exige espaço para dois índices e um alias; é seguro reverter o alias.
- A outbox é global (sem RLS), pois o catálogo é global; eventos não contêm preço nem dado
  privado.
- O CLI é o caminho de recuperação manual (`bootstrap`, `reindex`, `reconcile`).

## Em produção real, seria diferente

- Usar CDC/Debezium ou um worker dedicado com fila e DLQ, monitorando lag da outbox e
  idade do evento mais antigo.
- Alertar quando `attempts` chega ao limite ou quando `reconcile` encontra órfãos; hoje há
  log e relatório, não alerta.
- Adicionar ILM/rollover ao índice (ver `NON_GOALS.md`) e snapshots do Elasticsearch.
- Fazer a troca de alias com verificação de saúde e manter um período de dupla leitura
  antes de apagar o índice antigo.
- Rodar o beat em alta disponibilidade (duas instâncias com lock) ou usar um scheduler
  gerenciado.
