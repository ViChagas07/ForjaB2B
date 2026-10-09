# ADR-0002: Outbox transacional + Celery beat para notificações

- **Status:** aceito
- **Data:** 2026-10-09

## Contexto

Notificações devem ser publicadas de forma confiável (sem perder eventos entre
commit e publicação) e despachadas de forma assíncrona por Celery/RabbitMQ,
respeitando isolamento multi-tenant (RLS).

## Decisão

1. A tabela `notifications` é a **outbox**: os repositórios de negócio inserem a
   linha na **mesma transação** do evento (commit atômico), via helper
   `app.infrastructure.db.outbox.enqueue_notification`.
2. Um `celery-beat` agenda `dispatch_outbox`, que enumera notificações pendentes
   via função `SECURITY DEFINER` `app.list_due_notifications` (owner
   `forja_notification`, `NOLOGIN`) e despacha **por tenant** no contexto RLS
   correto.
3. Falhas transitorias viram `FAILED` (retry); permanentes viram `DEAD_LETTERED`;
   opt-out vira `SKIPPED`.

## Consequências

- A enumeração cross-tenant não quebra RLS (papel dedicado + política restrita).
- `celery-beat` adicionado ao docker-compose (antes só existia o worker).
