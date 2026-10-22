# Changelog

Formato inspirado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Datas são as do histórico Git local (51 commits até a base `7ee3265`, antes dos commits
desta entrega), não datas de release.
Não há versões/tags publicadas; o projeto é um monorepo de portfólio.

## [Não lançado] — 2026-10-22

### Documentação

- README reescrito para o estado real, com resumo em inglês, diagramas Mermaid, tabela de
  validação, limitações e capturas de tela existentes.
- ADRs 0005–0013 (RLS, preços, i18n, atributos, outbox, rate limiting proposto,
  idempotência, timeouts/breaker, observabilidade/segredos); ADR-0004 revisado.
- `docs/NON_GOALS.md`, `docs/INDEX.md`, `docs/API.md`, `docs/DEPLOY_RENDER.md`,
  `docs/testing/LOAD.md`, `docs/readiness/GAP_AUDIT.md` e
  `docs/readiness/FINAL_REPORT.md`.
- `docs/STATUS.md` reescrito; log antigo preservado em `docs/history/`.
- Verificador de links internos em `scripts/check_markdown_links.py`.
- `.env.example`: versão do índice alinhada ao mapping atual (v2).

### Correções de documentação

- `docs/ARCHITECTURE.md`: busca padrão lexical + fallback; semântica opcional; seção de
  preços/catálogo/i18n.
- `docs/search/RUNBOOK.md`: removida a contradição sobre o circuit breaker e a frescura do
  índice; estado multilíngue explicitado.
- `docs/RUNBOOK.md`: target `make clean` no lugar de `make down-volumes`.
- `docs/CATALOG_ADMIN.md`: `DRAFT` incluído no `CHECK` de status.

## 2026-10-22

### i18n / frontend

- 1.037 chaves traduzidas no Passo 1; paridade obrigatória contra `pt-BR` em 11 dicionários.
- Seletor de idioma nativo com cookie `NEXT_LOCALE`, `aria-current` e primeira visita por
  `Accept-Language`.
- RTL para árabe derivado de `rtlLocales`; 18 classes físicas trocadas por lógicas e 3
  ícones espelhados.
- Nota discreta de conteúdo exibido em outro idioma apenas no detalhe do produto; selos de
  fallback removidos de carrinho/pedido.
- Chaves de cache do TanStack Query passaram a incluir o locale.
- 16 capturas de validação visual em `docs/validation/v3/` e spec Playwright.

## 2026-10-21

### Validação V2

- API admin ponta a ponta: CRUD, atributos opcionais, RBAC 401/403, 409, SKU imutável,
  auditoria, outbox, despublicar e remover do índice.
- Traduções: 4 locales de conteúdo, cadeia de fallback, `stale` servido, `reviewed`,
  preços idênticos por idioma.
- Busca multilíngue e fallback real com o Elasticsearch parado; correções de concorrência,
  migration `0019` (`orders.content_locale`), `DRAFT`, slug, outbox e auditoria.
- Suíte completa e `mypy --strict` do app registrados no `PROGRESS`.

## 2026-10-14

### Validação V1

- Ambiente, migrations 0001–0017, seeds idempotentes, manifesto de fotos e índice
  Elasticsearch v2 (41/41), `reconcile` e busca `en`/`es`/`ar` validados com Docker.
- Limitações registradas: embeddings desligados, árabe não revisado por nativo, deploy não
  executado.

## 2026-10-13

### Busca multilíngue e preparação da V3

- Índice v2 com campos `name_{en,es,ar}`, `description_{...}` e `attributes_text_{...}`;
  consulta prioriza SKU e combina campos do idioma com `pt-BR`.
- Documentação de i18n e runbook atualizados.
- Preparação da validação visual de 11 idiomas e RTL.

## 2026-10-12

### Catálogo, administração e traduções

- Modelo de atributos por categoria (JSONB + definições versionadas).
- API admin de catálogo: criar/editar/publicar/despublicar, concorrência otimista,
  auditoria e outbox.
- Frontend admin com formulário dinâmico, preview, validação e imagens.
- Traduções armazenadas (`product_translations`), resolução campo a campo, endpoints admin
  e seed de demonstração.
- Busca multilíngue no Elasticsearch (fase 9B-b).

## 2026-10-10

### Busca, preços e robustez

- Elasticsearch 9.5.5 com segurança, cliente 9.5.1, índice versionado e alias.
- Outbox de busca, reindexação, reconciliação e CLI.
- Busca lexical com fallback PostgreSQL; autocomplete; filtros; hidratação autoritativa.
- pgvector, embeddings ONNX opcionais e fusão RRF (desligados por padrão).
- Preços por empresa (`company_price_rules`), precedência negociado > desconto > lista,
  preço consultivo para visitante.
- Imagens por categoria e correções de `.pyc`, credenciais vazias do ES e preço no
  catálogo público.
- Timeouts curtos na busca, circuit breaker e falha visível no bulk/reindex.
- Validação real com Docker, medições e correções de migrations/ES.

## 2026-10-09

### Plataforma e segurança

- Pagamentos, notificações (outbox/Celery) e direitos LGPD.
- Endurecimento de pagamentos, aprovação de empresas e observabilidade (métricas,
  dashboard, healthchecks).
- Auditoria e plano da busca híbrida (Fase 1).

## 2026-10-08

### Fundação

- Commit inicial da plataforma B2B: identidade, empresas, catálogo, crédito, carrinho,
  pedidos, faturamento, frete e impostos.
- Correções iniciais de OAuth, crédito e cálculo tributário.
