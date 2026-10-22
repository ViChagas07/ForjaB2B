# ADR-0013: Observabilidade proporcional e segredos fora do Git

- **Status:** parcial — OTel/métricas/logs implementados; perfil opt-in e grupos de
  variáveis do Render **não implementados**; Grafana local com falha de provisioning
- **Data:** 2026-10-22
- **Contexto do código:** `backend/app/core/telemetry.py`,
  `backend/app/interface/metrics.py`, `backend/app/core/logging.py`,
  `docker-compose.yml`, `docker/otel/`, `docker/prometheus/`, `docker/grafana/`

## Contexto

O projeto precisa ser diagnosticável sem montar uma plataforma de observabilidade
completa. Ao mesmo tempo, segredos (JWT, pepper, criptografia, webhook, banco) não podem
estar no repositório. O deploy de referência seria no Render, que oferece grupos de
variáveis de ambiente, mas nenhum deploy foi feito.

## Decisão

1. **Logs estruturados em JSON**, com `request_id`/`trace_id`, sem senha, token, corpo de
   pagamento ou PII. Erros saem como Problem Details sem stack trace para o cliente.
2. **Métricas Prometheus** em `/metrics`: HTTP (método/status), pedidos, pagamentos,
   notificações e busca por `search_mode`. Labels de baixa cardinalidade; path não entra.
3. **Traces OTLP** para um collector; instrumentação FastAPI e SQLAlchemy. Se
   `OTEL_EXPORTER_OTLP_ENDPOINT` não existir, o provider sobe sem exportador.
4. **Health:** `/health/live`, `/health/ready` (PostgreSQL + Redis) e `/health/search`
   (Elasticsearch; não derruba o readiness).
5. **Segredos:** `.env` é local e ignorado; `.env.example` contém apenas valores fictícios.
   Em produção, a intenção é usar **grupos de variáveis/secret files do provedor**
   (Render Environment Groups), com rotação e escopo por serviço. As credenciais de
   bootstrap e `DATABASE_ADMIN_URL` não vão para o runtime.
6. **Perfil opt-in:** a intenção é que OTel/Prometheus/Grafana sejam um perfil opcional do
   Compose, para não consumir recursos em dev. Hoje eles estão no Compose base, sem
   `profiles:`.

## Alternativas consideradas

- **Sem observabilidade:** mais simples, mas impossível diagnosticar fallback, outbox e
  erros de integração. Rejeitado.
- **APM SaaS (Datadog/New Relic):** bom em produção, mas custo e vendor lock-in; o OTel
  mantém a porta aberta.
- **ELK completo:** pesado para o escopo; logs JSON + Prometheus bastam para a demonstração.
- **Vault/AWS Secrets Manager:** correto em produção, mas mais um serviço para o projeto;
  ver `NON_GOALS.md`.
- **Perfil opt-in já:** desejável, mas não foi implementado nesta entrega.

## Consequências

- O Compose local sobe OTel/Prometheus/Grafana sempre; em uma máquina modesta isso pesa.
- O Grafana local **não sobe** por um `datasource.yaml` com dois datasources default; é uma
  falha de configuração, não de código de aplicação.
- Não há alertas, SLOs, retenção definida nem dashboards validados.
- O Render não foi deployado; os grupos de variáveis são uma decisão de destino, não um
  fato verificado.
- Métricas de busca ajudam a ver `postgres_fallback`, mas não há alerta quando o modo muda.

## Em produção real, seria diferente

- Criar perfis Compose `observability` (opt-in) e um `render.yaml` com Environment Groups;
  nunca versionar valores.
- Usar um backend gerenciado de métricas/traces (Grafana Cloud, Honeycomb, etc.) com
  amostragem, retenção e alertas de SLO.
- Rotacionar segredos com um secret manager (Vault/AWS Secrets Manager) e auditar acesso.
- Adicionar alertas para: taxa de `postgres_fallback`, breaker aberto, lag da outbox,
  erros 5xx, latência p95 e saturação de conexões.
- Definir dashboards versionados e testar o perfil de observabilidade no CI (subir e
  validar health).
