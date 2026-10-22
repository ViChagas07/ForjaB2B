# Não-objetivos do Forja B2B

Este documento registra o que **não** foi adotado no projeto e por quê. Não é uma lista de
desculpas: é uma decisão de escopo. O que é lacuna (e não escolha) está marcado como
**lacuna** e aparece também em [`docs/readiness/FINAL_REPORT.md`](readiness/FINAL_REPORT.md).

| Item | Por que não foi adotado | O que foi feito no lugar | Em produção real |
| :--- | :--- | :--- | :--- |
| **WAF próprio** | Um WAF caseiro é fácil de errar e caro de manter; o ganho real vem de regras gerenciadas e bot detection na borda. | API com validação de entrada, limites de tamanho, RFC 7807 e RLS. Não há rate limiting de aplicação (lacuna). | Cloudflare/AWS WAF + rate limit de borda + regras gerenciadas; a aplicação mantém validação e limites por tenant. |
| **Vault / AWS Secrets Manager** | Adiciona um serviço e um modelo operacional que o projeto não tem; o `.env` local é suficiente para demonstração e não versiona segredo real. | `.env` ignorado, `.env.example` só com valores fictícios, roles de banco separadas e segredos fora do runtime quando possível. | Secret manager gerenciado, rotação automática, escopo por serviço e auditoria de acesso; no Render, Environment Groups/Secret Files. |
| **Imagem distroless** | O Dockerfile atual usa `python:3.12-slim` com usuário não-root, `tini` e healthcheck; distroless exige repensar shell/healthcheck e não era o gargalo. | Multi-stage build, usuário não-root, dependências fixadas e healthcheck. | Distroless ou Chainguard, SBOM, assinatura de imagem, scan contínuo e política de admissão. |
| **SOC 2 / ISO 27001** | São processos de auditoria organizacional, não uma feature de código; o projeto não tem empresa, escopo legal ou evidências operacionais para certificar. | Controles técnicos proporcionais: RLS, RBAC, HMAC, LGPD, logs sem PII, CI com secret scan e dependências auditadas. | Programa de compliance, gestão de riscos, políticas, auditoria independente, evidências contínuas e treinamento. |
| **Chaos engineering completo** | Requer ambiente estável, hipóteses e automação de experimentos; o projeto ainda não tem SLOs nem carga reproduzível. | Simulações pontuais e documentadas: Elasticsearch parado → `postgres_fallback`; breaker; reindex com falha visível; `reconcile`. | Chaos Toolkit/Litmus em staging, com hipóteses, blast radius, SLOs e postmortems. |
| **Pact (contract testing)** | O frontend e a API evoluem juntos; um broker Pact adicionaria infraestrutura sem consumidores independentes. | Testes de contrato leves no frontend (Vitest sobre o cliente HTTP), testes de API no backend e OpenAPI gerado em runtime. | Pact Broker/consumer-driven contracts se houver times/consumidores independentes; verificação no CI. |
| **Feature flags** | Não há experimentos nem rollout gradual de features; uma flag sem governança vira dívida. | Configuração por ambiente (`Settings`) para busca, embeddings, OAuth e limites. | LaunchDarkly/Unleash/Flagsmith com targeting, kill switch, auditoria e limpeza de flags. |
| **Testes A/B** | O produto não tem tráfego real nem hipótese de conversão; medir A/B sem usuários seria teatro. | Medição de latência da busca e modo (`lexical`/fallback) via métricas. | Experimentação com amostragem, métricas de negócio, guardrails e análise estatística. |
| **Réplicas de leitura** | O volume de demonstração não justifica; réplica adiciona lag e complexidade de conexão. | Uma instância PostgreSQL com pool e índices; leitura e escrita no mesmo banco. | Réplica para relatórios/analytics, com lag monitorado e roteamento explícito; PgBouncer. |
| **CDN** | O frontend é servido localmente; não há domínio público, cache de assets nem tráfego geográfico. | Assets estáticos versionados no repositório e servidos pelo Next.js/API. | CDN para assets e cache de borda, com invalidação por deploy e compressão. |
| **Elasticsearch ILM** | O catálogo é pequeno e o índice é reconstruível; ILM é operação de cluster, não de aplicação. | Índice versionado + alias, `bootstrap`/`reindex`/`reconcile` e retenção do índice anterior para rollback. | ILM/rollover, snapshots, réplicas, monitoramento de cluster e política de retenção. |
| **Integração de pagamento real** | Exigiria adquirente, credenciais, conciliação, PCI e webhook real; o escopo é demonstrar o fluxo. **Lacuna de produto**, não escolha de arquitetura. | `FakePaymentGateway` determinístico, máquina de estados, webhook HMAC e idempotência. | Stripe/Pagar.me/Asaas ou PIX via PSP, conciliação, estorno, PCI-DSS e segredos gerenciados. |
| **Tradução automática em tempo real** | Latência, custo, dependência externa e risco de traduzir SKU/marca/preço; o request não deve chamar um provedor. | Traduções armazenadas, `source_hash`, status `machine`/`reviewed`/`stale` e edição manual no admin. | TMS assíncrono + revisão humana; provedor só no pipeline, nunca no request. |
| **Idiomas de conteúdo além dos 4** | Cada idioma exige traduções reais, analisador/stopwords no Elasticsearch e revisão; não é só configuração. | `pt-BR` (origem), `en`, `es`, `ar`; interface em 11 idiomas com fallback para `en`/`pt-BR`. | Novos mercados com TMS, analisador dedicado, revisão nativa e testes de busca por idioma. |
| **Painel de administração multilíngue** | O admin é operado por uma equipe interna em português; traduzir o backoffice não era prioridade. | Admin em português; o site do cliente tem 11 idiomas. | Admin i18n com preferência por usuário, auditoria e revisão de termos. |
| **Rate limiting de aplicação** | **Lacuna:** não foi implementado; o Redis existe, mas não há limitador. | Nada no lugar; a limitação está documentada e o ADR-0010 registra a decisão proposta. | WAF/edge + limitador distribuído por IP/tenant, com fail-open monitorado. |
| **Teste de carga** | **Lacuna:** não há k6/Locust nem resultados; medir sem ambiente de staging e SLO seria enganoso. | Testes de integração e medições pontuais de latência da busca (V2/runbook). | Cenários de carga em staging, SLOs, capacity planning e relatório versionado. |
| **Deploy em provedor** | **Lacuna:** não há `render.yaml`, URL ou deploy executado. | `docker-compose.prod.yml` para Elasticsearch em VPS e documentação de deploy. | Blueprint no Render (ou outro provedor), CI/CD, migrations como job, healthchecks e rollback. |

## O que este documento não significa

- Não significa que esses itens sejam impossíveis ou indesejáveis; significa que o custo
  não cabia no escopo de um projeto de portfólio.
- Não substitui a lista de riscos e pendências do responsável em
  [`docs/readiness/FINAL_REPORT.md`](readiness/FINAL_REPORT.md).
- Não autoriza afirmar que o projeto está pronto para produção. Ele não está.
