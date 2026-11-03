# Forja B2B

Plataforma de e-commerce B2B para **EPIs e máquinas industriais**, feita para empresas
(CNPJ) que compram em volume. Visitantes veem **preço sob consulta**; empresas
autenticadas veem o **preço negociado** da própria empresa. Catálogo, carrinho,
pedido, administração de catálogo, busca e conteúdo em vários idiomas.

> **Projeto de portfólio.** Todos os dados, marcas, CNPJs, preços, certificados (CA) e
> imagens de demonstração são **fictícios**. Nada aqui é uma oferta comercial real.
> O código não tem licença definida (ver [Licença](#licença)).

**English summary:** Forja B2B is a portfolio e-commerce platform for industrial PPE and
machinery. It pairs a FastAPI/PostgreSQL multi-tenant backend (row-level security) with a
Next.js storefront in 11 UI languages, company-specific pricing, catalog administration and
a lexical search path with a PostgreSQL fallback. All demo data is fictional. The optional
pgvector/RRF semantic path is implemented but **disabled by default**.

[![CI Backend](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-backend.yml/badge.svg?branch=main)](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-backend.yml)
[![CI Frontend](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-frontend.yml/badge.svg?branch=main)](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-frontend.yml)
[![CI Architecture](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-architecture.yml/badge.svg?branch=main)](https://github.com/ViChagas07/ForjaB2B/actions/workflows/ci-architecture.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Node 20+](https://img.shields.io/badge/node-20%2B-339933?logo=node.js&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Next.js 14](https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white)

## O que é o Forja B2B

O fluxo é o de um marketplace B2B: uma empresa se cadastra com CNPJ, é aprovada, recebe
condições comerciais e compra em quantidades de atacado. O catálogo é global; o preço, a
visibilidade e a autorização são resolvidos por empresa no PostgreSQL.

- **Problema:** preço B2B não é preço de vitrine. Cada cliente negocia condição própria,
  e o preço não pode vazar entre empresas nem ser servido por um índice de busca.
- **Solução:** PostgreSQL como fonte de verdade, RLS por `company_id`, preço resolvido no
  servidor, índice de busca apenas com IDs e conteúdo público.
- **Demonstração:** 50 produtos, 11 categorias, 8 marcas fictícias, 4 empresas e 13 usuários
  de demonstração (dados do seed; contagens conferidas no banco em 2026-10-22).

## Funcionalidades

- **Catálogo:** categorias, marcas, produtos, imagens SVG por categoria, disponibilidade,
  estoque configurável por produto, compra direta e estado de CA (EPI vencido ou ausente não
  é vendável).
- **Busca:** lexical no Elasticsearch com prioridade para SKU, tolerância a acento e
  autocomplete; fallback textual no PostgreSQL. Semântica opcional com pgvector + RRF.
- **Preços por empresa:** regra negociada (preço fixo por produto) > desconto percentual
  (por categoria ou global) > preço de lista. Visitante recebe `price_on_request=true`.
- **Carrinho e pedido:** preços revalidados no servidor, snapshot do pedido, reserva de
  crédito e idempotência por chave única no banco.
- **Administração de catálogo:** criar, editar, publicar e despublicar produtos; atributos
  dinâmicos por categoria; imagem; concorrência otimista (409); trilha de auditoria;
  eventos na outbox de busca.
- **Traduções:** conteúdo armazenado em `en`, `es` e `ar` (origem `pt-BR`), com estados
  `machine`, `reviewed` e `stale`; interface em **11 idiomas**, incluindo RTL para árabe.
- **Conta e acesso:** login JWT, refresh com rotação, RBAC (`ADMIN`, `BUYER`, `APPROVER`,
  `FINANCE`), OAuth Google opcional.
- **Recuperacao de conta:** codigo por e-mail ou SMS, Turnstile fail-closed, reset_token de uso unico, revogacao de sessoes e verificacao de telefone na conta.
- **Crédito, faturamento e pagamento:** ledger append-only, fatura/boleto simulado e
  gateway de pagamento **fake local** (PIX/cartão/boleto). Não há adquirente real.
- **LGPD:** exportação, retificação, anonimização e consentimento self-service.
- **Notificações:** outbox transacional + Celery/RabbitMQ + SMTP local (Mailpit).
- **Observabilidade:** logs JSON com `X-Request-ID`, métricas Prometheus, traces OTel e
  endpoints de health. O Compose local inclui OTel Collector, Prometheus e Grafana; há
  falhas conhecidas nessa stack (ver [Limitações](#limitações-conhecidas)).

## Arquitetura

```mermaid
flowchart TB
  subgraph Client["Cliente"]
    WEB["Next.js 14<br/>App Router · 11 idiomas · RTL"]
  end

  subgraph App["Backend FastAPI (Python 3.12)"]
    HTTP["API REST /api/v1<br/>RFC 7807"]
    AUTH["JWT + RBAC<br/>tenant do token"]
    SEARCH["Busca<br/>lexical + fallback<br/>semântica opcional"]
    ADMIN["Admin de catálogo<br/>atributos · traduções"]
  end

  PG[("PostgreSQL 16<br/>fonte de verdade · RLS<br/>pgvector opcional")]
  ES[("Elasticsearch 9.5<br/>índice versionado + alias")]
  REDIS[("Redis<br/>refresh · cache · exchange")]
  RABBIT[("RabbitMQ<br/>Celery")]
  WORKER["Celery worker/beat<br/>outbox · reconcile"]
  OTEL["OTel Collector"]
  PROM["Prometheus"]
  GRAF["Grafana"]

  WEB -->|"JSON / HTTPS"| HTTP
  HTTP --> AUTH
  HTTP --> SEARCH
  HTTP --> ADMIN
  AUTH --> PG
  SEARCH --> ES
  SEARCH --> PG
  ADMIN --> PG
  ADMIN -->|"outbox na mesma transação"| PG
  WORKER --> PG
  WORKER --> ES
  WORKER --> RABBIT
  HTTP --> REDIS
  HTTP -. OTLP .-> OTEL
  OTEL --> PROM --> GRAF
```

A raiz de composição é `backend/app/main.py`. Os módulos seguem Clean Architecture
(`domain → application → infrastructure/interface`) e o import-linter impede dependências
cruzadas entre bounded contexts. PostgreSQL guarda preço, estoque, CA, autorização e
traduções; Elasticsearch e pgvector são **derivados e reconstruíveis**.

### Fluxo de busca

```mermaid
flowchart TD
  Q["q + idioma"] --> V["Validação: tamanho, página, limites"]
  V --> ES["Elasticsearch lexical<br/>status ACTIVE + disponibilidade"]
  V --> SEM["pgvector semântico<br/>somente se EMBEDDINGS_ENABLED=true"]
  ES --> RRF["RRF k=60<br/>quando os dois caminhos respondem"]
  SEM --> RRF
  ES -->|"timeout/erro"| CB["Circuit breaker<br/>3 falhas / 15 s"]
  CB --> PGF["Fallback PostgreSQL<br/>tsvector + unaccent + pg_trgm"]
  RRF --> H["Hidratação no PostgreSQL<br/>preço · autorização · tradução"]
  PGF --> H
  H --> R["Resposta + search_mode"]
```

`search_mode` informa o caminho real: `hybrid`, `lexical`, `semantic_postgres` ou
`postgres_fallback`. Falha de infraestrutura não vira lista vazia silenciosa: o fallback é
usado e, se ambos falharem, a API responde erro. **Preço nunca entra no índice nem no vetor.**

## Decisões de destaque

| Decisão | Por quê | ADR |
| :--- | :--- | :--- |
| PostgreSQL é a fonte de verdade; multi-tenant com RLS | Preço e autorização não podem vazar nem depender de índice | [ADR-0005](docs/ADRs/0005-postgresql-fonte-de-verdade-rls.md) |
| Busca lexical + fallback; semântica opcional com RRF | Robustez com custo proporcional; o modo real é explícito | [ADR-0004](docs/ADRs/0004-busca-hibrida.md) |
| Preços fora do índice e preço consultivo | Isolamento por empresa e ausência de dado comercial no ES | [ADR-0006](docs/ADRs/0006-precos-fora-do-indice.md) |
| Traduções armazenadas, 11 idiomas de UI e 4 de conteúdo | Sem tradução em tempo de request; fallback campo a campo | [ADR-0007](docs/ADRs/0007-traducoes-armazenadas.md) |
| Atributos em JSONB com definições por categoria | Flexibilidade de catálogo sem EAV nem colunas por nicho | [ADR-0008](docs/ADRs/0008-atributos-jsonb.md) |
| Outbox, reconciliação e índice versionado com alias | Indexação não bloqueia o catálogo; rebuild e rollback seguros | [ADR-0009](docs/ADRs/0009-outbox-indice-versionado.md) |
| Rate limiting com Redis e fallback local | Implementado; fail-open no trafego geral e fail-closed na recuperacao de conta | [ADR-0010](docs/ADRs/0010-rate-limiting-redis.md) |
| Idempotência por chave única | Evita pedido/pagamento duplicado em retry | [ADR-0011](docs/ADRs/0011-idempotencia.md) |
| Timeouts curtos e circuit breaker na busca | Degradar em ~2 s, não em ~15 s | [ADR-0012](docs/ADRs/0012-timeouts-circuit-breaker.md) |
| Observabilidade proporcional e segredos fora do Git | Diagnóstico sem acoplar o projeto a um vendor | [ADR-0013](docs/ADRs/0013-observabilidade-segredos.md) |

## Estado de validação

A tabela abaixo separa o que foi **executado e observado** do que é apenas
**implementado**, **validado em outra sessão** ou **não validado**. Datas e comandos são
os desta sessão (2026-10-22), salvo indicação.

| Área | Estado | Evidência |
| :--- | :--- | :--- |
| Backend: unidade + arquitetura + seguranca | ✅ Validado | `pytest tests/unit tests/architecture tests/security` → **1357 passed** (3 falhas antigas de boundaries) |
| Backend: suite sem Docker | ✅ Validado | integracao pulada; baseline de testes antigos |
| Backend: suite completa com Docker | ✅ Validado | `pytest tests/` → **1797 passed, 2 skipped, 5 failed + 1 error antigos** (Testcontainers) |
| Ruff | ✅ Validado | `ruff check` OK; `ruff format --check` → **384 files already formatted** |
| Mypy nos arquivos da feature | ✅ Validado | 18 arquivos, 0 erros; baseline mantem erros antigos de stubs |
| Mypy no repositorio | ❌ Falha conhecida | baseline de tipagem em testes/estubs; nao bloqueia a feature |
| Import-linter | ✅ Validado | **5 contratos mantidos, 0 quebrados** |
| Frontend: tipos e lint | ✅ Validado | `npm run typecheck` OK; `npm run lint` OK com 4 warnings `<img>` |
| Frontend: testes e build | ✅ Validado | **332 passed**; `npm run build` concluiu |
| Docker Compose (sintaxe) | ✅ Validado | `docker compose --env-file .env.example config --quiet` OK |
| Docker Compose (runtime) | ⚠️ Parcial | 9 containers healthy e 2 em restart (`forja-grafana`, `forja-celery-beat`); `forja-frontend` criado, não iniciado (detalhes abaixo) |
| Busca lexical, multilíngue e fallback | ✅ Validado em sessão anterior | Evidência V2 em [PROGRESS](docs/agent/PROGRESS.md): `en`/`es`/`ar`, SKU, `postgres_fallback` com ES parado, latências e recuperação. **Não reexecutado nesta sessão.** |
| Busca semântica (`hybrid`) | ⚠️ Não validado no estado padrão | `EMBEDDINGS_ENABLED=false`; houve validação local na Fase 7, mas não é o padrão nem foi validada em produção |
| i18n visual (11 idiomas, RTL) | ✅ Evidência existente | 16 capturas em [`docs/validation/v3/`](docs/validation/v3/) e spec Playwright com **5 passed** (registro em PROGRESS); **não reexecutado nesta sessão** |
| CI no GitHub | ⚠️ Não verificado | Workflows existem ([backend](.github/workflows/ci-backend.yml), [frontend](.github/workflows/ci-frontend.yml), [arquitetura](.github/workflows/ci-architecture.yml)); nenhum run foi consultado. O mypy local sugere que o job backend falha. |
| Deploy em provedor | ❌ Não executado | Não há `render.yaml`, URL pública nem deploy registrado; ver [DEPLOY_RENDER](docs/DEPLOY_RENDER.md) |
| Teste de carga | ❌ Não executado | Não há k6/Locust nem resultados versionados; ver [LOAD](docs/testing/LOAD.md) |
| Licença | ❌ Ausente | Não há `LICENSE`; sem licença, vale o padrão de todos os direitos reservados |

### O que está deliberadamente desligado

- **Embeddings:** `EMBEDDINGS_ENABLED=false` no `.env.example` e no padrão do código. O
  caminho `hybrid` existe, mas não é o estado de produção deste repositório.
- **Pagamento real:** `FakePaymentGateway` gera referências determinísticas; não há
  adquirente, conciliação ou webhook de terceiro real.
- **OAuth Google:** opcional; sem credenciais, os endpoints retornam 503 e o botão fica
  oculto.
- **Rate limiting:** implementado no Redis com fallback local; os fluxos de recuperacao de conta usam modo fail-closed e baldes dedicados.

## Como rodar localmente

Pré-requisitos: Docker com Compose v2, Python 3.12 (para rodar testes fora do container)
e Node.js 20+ (frontend). O `.env.example` contém **apenas valores fictícios de
desenvolvimento**; não reuse em produção.

```bash
# 1. Ambiente
cp .env.example .env
# Edite .env se quiser; DEMO_USER_PASSWORD habilita os usuários de demonstração.

# 2. Stack (PostgreSQL, Redis, RabbitMQ, Mailpit, Elasticsearch, backend, workers,
#    OTel/Prometheus/Grafana)
docker compose up -d
docker compose ps

# 3. Migrations (role administrativa, container one-off)
make migrate

# 4. Seed idempotente (catálogo, empresas, usuários, preços e traduções)
make seed

# 5. Definições de atributos por categoria (idempotente)
docker compose run --rm --no-deps --env-file .env backend \
  python scripts/seed_attribute_definitions.py

# 6. Índice de busca (ajuste a versão ao mapping atual; hoje v2)
docker compose exec backend python -m app.modules.search.interface.cli bootstrap --version 2
docker compose exec backend python -m app.modules.search.interface.cli reindex --version 2
docker compose exec backend python -m app.modules.search.interface.cli reconcile

# 7. API
# http://localhost:8000/docs (somente fora de produção)
# http://localhost:8000/health/live · /health/ready · /health/search

# 8. Frontend
cd frontend
npm ci
npm run dev   # http://localhost:3000
```

> **Proxy same-origin:** o navegador chama `/api/v1` na própria origem do frontend; o
> Next encaminha para `BACKEND_URL` (variável somente de servidor). O CORS do backend
> continua configurado para chamadas diretas em desenvolvimento. Em produção é preciso
> definir `BACKEND_URL` no painel da Vercel e refazer o deploy, pois os rewrites são
> resolvidos no build.

## IA local com LM Studio (Qwen 3.5 9B)

> **[Espaço reservado para o GIF/vídeo de demonstração]** — gravar o chat respondendo
> nos 11 locales e o e-mail de carrinho abandonado saindo pelo Mailpit/Resend dry-run.

### Por que o LLM é local

O projeto é de portfólio e a IA roda em um modelo pequeno (Qwen 3.5 9B) no LM Studio,
em `http://localhost:1235/v1` (API compatível com OpenAI). A decisão evita custo por
token e mantém catálogo, conversas e dados de clientes fora de provedores de nuvem.

O compromisso é explícito: **a IA é um extra, não uma dependência**. Em produção
(Render) o LM Studio local não está acessível; por isso:

- `GET /health` e o readiness **nunca** consultam o LLM;
- `GET /health/llm` é separado, tem cache de ~30 s e sempre responde HTTP 200 com
  `{available, enabled, model}`;
- sem LLM, o chat mostra uma mensagem traduzida de "modo demonstração local" e ainda
  devolve os cartões determinísticos da busca;
- o e-mail de carrinho abandonado sempre sai: o LLM só redige o parágrafo persuasivo
  e, se estiver indisponível ou citar valor/percentual divergente, o template fixo
  traduzido é usado. Desconto (máx. 3%, só para quem já comprou) e frete grátis são
  decididos exclusivamente pelo código.

### Rodando a IA localmente com LM Studio

1. Instale o [LM Studio](https://lmstudio.ai/) e baixe o modelo **Qwen 3.5 9B**
   (o identificador exato visto em `/v1/models` neste ambiente é `qwen/qwen3.5-9b`).
2. Carregue o modelo e inicie o servidor local na porta **1235** (Developer → Local
   Server). Confirme:
   ```bash
   curl http://localhost:1235/v1/models
   ```
3. No `.env`, habilite a IA e aponte para o endpoint:
   ```dotenv
   AI_AGENTS_ENABLED=true
   LLM_ENABLED=true
   LLM_BASE_URL=http://localhost:1235/v1
   LLM_API_KEY=lm-studio
   LLM_MODEL=qwen/qwen3.5-9b
   LLM_TEMPERATURE=0.3
   LLM_TIMEOUT_SECONDS=60
   LLM_MAX_TOKENS=512
   LLM_REASONING_EFFORT=none
   ```
   `LLM_REASONING_EFFORT=none` desliga o bloco de raciocínio do Qwen no LM Studio
   (respostas rápidas). O cliente também remove qualquer `<think>...</think>` que
   escapar. `LLM_API_KEY` é fictícia: o LM Studio ignora o valor.
4. **Docker:** o backend roda em container, então `localhost` aponta para o próprio
   container. O `docker-compose.yml` já declara
   `extra_hosts: host.docker.internal:host-gateway` e usa
   `LLM_BASE_URL_DOCKER`, cujo padrão é `http://host.docker.internal:1235/v1`.
   Quem roda o backend direto no host usa `LLM_BASE_URL=http://localhost:1235/v1`.
   No Linux, o `extra_hosts` com `host-gateway` é o que torna o host acessível.
5. Suba/rebuilde backend e worker e confira:
   ```bash
   docker compose up -d --build backend celery-worker
   curl http://localhost:8000/health/llm
   ```
   Esperado: `{"available":true,"enabled":true,"model":"qwen/qwen3.5-9b"}`.
6. O endpoint de chat é `POST /api/v1/ai/chat`; o widget consulta `/health/llm`
   (cache de 30 s) e mostra o aviso de demonstração quando o modelo não está
   disponível. Nenhuma rota de catálogo, carrinho, checkout ou login depende do LLM.
7. Para testar o e-mail de carrinho sem enviar mensagens reais:
   ```dotenv
   EMAIL_DRY_RUN=true
   ```
   O worker renderiza o e-mail e registra no log em vez de chamar o Resend.

### Usuários de demonstração

O seed só cria usuários se `DEMO_USER_PASSWORD` estiver definida (o `.env.example` traz um
valor fictício). A senha é a mesma para todos; nunca versione uma senha real.

| Empresa | Usuário | Papel |
| :--- | :--- | :--- |
| Empresa Exemplo | `admin@exemplo.com.br` | ADMIN |
| Empresa Exemplo | `comprador@exemplo.com.br` | BUYER |
| Metalúrgica Demo Alfa | `comprador@metalurgica-alfa.example.com` | BUYER |
| Construções Demo Beta | `comprador@construcoes-beta.example.com` | BUYER |
| Indústria Demo Gama | `comprador@industria-gama.example.com` | BUYER |

As três empresas demo têm condições diferentes: Alfa sem desconto; Beta 10% em proteção da
cabeça; Gama 5% global + preço negociado em `CAP-002` e `BOT-001`. Visitante sempre recebe
preço consultivo.

### O que foi (e não foi) testado em ambiente limpo

`docker compose config` foi validado. A suíte completa foi executada sobre a stack Docker
existente. **Não** foi feito um bootstrap do zero com volumes novos nesta sessão: apagar ou
recriar volumes é proibido pelas regras do projeto (`down -v`/`volume rm`). Portanto, o
roteiro acima é o procedimento documentado, mas a criação de um ambiente totalmente limpo
continua **NÃO VALIDADA**.

## Qualidade

```bash
# Backend (na pasta backend, com .venv Python 3.12)
pytest tests/unit tests/architecture tests/security -q   # 1357 passed
pytest tests/ -q                          # 1797 passed, 2 skipped (Docker/Testcontainers)
DOCKER_HOST=tcp://127.0.0.1:1 pytest tests/ -q  # integracao pulada
ruff check . && ruff format --check .     # OK / 384 files
mypy app/modules/identity/application/password_recovery.py app/modules/identity/application/phone_verification.py app/modules/identity/infrastructure/password_recovery_store.py app/modules/identity/infrastructure/password_recovery_repository.py app/modules/identity/infrastructure/phone_verification_repository.py app/modules/identity/infrastructure/twilio_verify.py app/modules/identity/infrastructure/turnstile.py app/modules/identity/infrastructure/verified_phone_resolver.py app/modules/identity/interface/password_recovery_router.py app/tasks/password_recovery.py app/interface/security_headers.py app/interface/deps.py app/infrastructure/security  # 18 arquivos, 0 erros
mypy .                                    # baseline de erros antigos em testes/estubs
lint-imports --config .import-linter      # 5/5

# Frontend (na pasta frontend)
npm run typecheck && npm run lint
npm run test -- --run                     # 332 passed
npm run build                             # OK (com BACKEND_URL)
```

- **CI:** `.github/workflows/ci-backend.yml`, `ci-frontend.yml` e `ci-architecture.yml`.
  O status real dos runs não foi consultado nesta sessão.
- **Testes de carga:** não executados; ver [`docs/testing/LOAD.md`](docs/testing/LOAD.md).
  Nenhum número de carga é apresentado neste README.
- **Simulações de falha:** o fallback sem Elasticsearch foi validado na V2 (ES parado,
  `search_mode=postgres_fallback`, recuperação após `start` + `reconcile`) e está
  documentado em [`docs/search/RUNBOOK.md`](docs/search/RUNBOOK.md) e no
  [`PROGRESS`](docs/agent/PROGRESS.md). Não foi reexecutado nesta sessão.

## Segurança e privacidade

- **Segredos:** nenhum segredo real no repositório; `.env` é ignorado. O `.env.example` tem
  apenas valores de desenvolvimento.
- **Multi-tenant:** RLS `FORCE ROW LEVEL SECURITY` em tabelas de domínio; `company_id` vem
  do JWT, nunca de parâmetro do cliente. Roles `forja_app`/`forja_admin` sem `BYPASSRLS`.
- **Autenticação:** JWT HS256 curto, refresh com rotação no Redis, Argon2id para senhas,
  OAuth Google com `state` e exchange code de uso único.
- **Pagamento:** webhook HMAC-SHA256 sobre o corpo bruto, `company_id` dentro do payload
  assinado.
- **LGPD:** exportação, retificação, anonimização e consentimento; a exclusão preserva
  registros financeiros/fiscais e auditoria.
- **Limite honesto:** nao ha WAF, Vault, SOC 2 ou ISO 27001. Ver
  [SECURITY.md](docs/SECURITY.md), [LGPD.md](docs/LGPD.md) e
  [NON_GOALS.md](docs/NON_GOALS.md).

## Observabilidade

- Logs estruturados em JSON com `X-Request-ID` e `trace_id`; erros RFC 7807 sem stack trace.
- Métricas Prometheus em `/metrics`: HTTP, pedidos, pagamentos, notificações e busca por
  `search_mode`.
- Traces OTLP para o collector do Compose, com instrumentação FastAPI e SQLAlchemy.
- Health: `/health/live`, `/health/ready`, `/health/search` (a indisponibilidade do
  Elasticsearch não derruba o readiness).
- **Estado local:** `forja-grafana` reinicia por provisioning inválido de datasource
  (dois defaults) e `forja-celery-beat` reinicia por permissão de escrita em
  `celerybeat-schedule`. Os demais containers estão healthy. Isso é uma falha de
  infraestrutura local, não uma validação de produção.

## API

A API é FastAPI e o contrato é versionado em `/api/v1`.

- Contrato versionado: [`docs/api/openapi.json`](docs/api/openapi.json)
- Documentação estática (Redoc): [`docs/api/index.html`](docs/api/index.html)
- Política de versionamento/depreciação: [`docs/API_VERSIONING.md`](docs/API_VERSIONING.md)
- Webhooks: [`docs/WEBHOOKS.md`](docs/WEBHOOKS.md)
- Tipos TypeScript gerados: `frontend/core/domain/api-schema.d.ts`
- Mapa de endpoints por contexto: [`docs/API.md`](docs/API.md)
- Cupons (regras, cálculo, endpoints e admin): [`docs/COUPONS.md`](docs/COUPONS.md)

Localmente:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Regenerar o snapshot: `cd backend && python scripts/export_openapi.py`
- Regenerar os tipos: `cd frontend && npm run openapi:types`

Em produção (`ENVIRONMENT=production`), `/docs` e `/openapi.json` são desligados por
padrão; publique o HTML estático ou sirva o snapshot.

Erros seguem Problem Details (RFC 9457) em `application/problem+json`, com
`request_id` e `errors[]` por campo nas validações. Mutações críticas exigem o
header `Idempotency-Key` (16–128 caracteres): repetição com o mesmo payload
devolve a resposta original e `Idempotent-Replayed: true`; payload diferente
responde 422; requisição em andamento responde 409 com `Retry-After`.

## Deploy

Não há deploy executado nem configuração de provedor versionada. O roteiro e as pendências
para um deploy no Render estão em [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md). O
`docker-compose.prod.yml` cobre apenas o Elasticsearch com TLS/API key e réplicas para uma
VPS; ele **não** é um plano de deploy completo.

## Limitações conhecidas

1. **CORS implementado** e configurável por `CORS_ORIGINS`; o domínio real ainda precisa
   ser definido no deploy.
2. **`mypy .` falha** em 48 erros de tipagem em testes; o job de CI roda `mypy .`. O código
   de aplicação (`mypy app --strict`) está limpo.
3. **Grafana e celery-beat** reiniciam no Compose local (provisioning e permissão de
   arquivo). Isso atrasa a reconciliação automática da busca.
4. **Rate limiting implementado** (Redis com fallback local); ainda não há WAF/edge.
5. **Idempotência no header** `Idempotency-Key` nas rotas críticas; o campo
   `idempotency_key` no corpo continua aceito como fallback depreciado.
6. **Busca semântica desligada** por padrão (`EMBEDDINGS_ENABLED=false`); o modo `hybrid`
   não é o padrão e não foi validado em produção. O fallback PostgreSQL busca apenas
   `pt-BR`.
7. **Traduções não revisadas por falante nativo** (especialmente árabe). São demonstração.
8. **Pagamento fake**, sem adquirente real, conciliação ou estorno.
9. **Deploy e carga não executados**; não há números de produção nem de carga.
10. **Licença indefinida**; sem `LICENSE`, o código está sob todos os direitos reservados
    por padrão.
11. **Três produtos do seed** (`EPI-LUV-002`, `EPI-RES-003`, `MAQ-PAR-004`) têm descrição
    nula; a API admin exige descrição para novos produtos, mas o dado legado permanece.
12. **`.commandcode/` versionado:** arquivos de ferramentas do agente estão no índice do
    Git. Não foram alterados nesta entrega; o responsável deve decidir se devem sair do
    repositório.

## Capturas de tela

As capturas abaixo são reais, geradas na validação visual de i18n (Chromium, 2026-10-22).
Não são mockups. O conjunto completo (16 imagens: pt-BR, en, ar e zh-CN × catálogo, busca,
detalhe e carrinho) está em [`docs/validation/v3/`](docs/validation/v3/).

| Catálogo (pt-BR) | Busca (en) |
| :---: | :---: |
| ![Catálogo em pt-BR](docs/validation/v3/pt-BR-catalog.jpg) | ![Busca em inglês](docs/validation/v3/en-search.jpg) |

| Catálogo (árabe, RTL) | Detalhe (zh-CN) |
| :---: | :---: |
| ![Catálogo em árabe com layout RTL](docs/validation/v3/ar-catalog.jpg) | ![Detalhe em chinês simplificado](docs/validation/v3/zh-CN-detail.jpg) |

> As capturas foram feitas com a checagem de CORS do Chromium desativada porque o backend
> ainda não envia cabeçalhos CORS. Isso está documentado e não esconde a lacuna.

## Licença

**[A DEFINIR pelo responsável]** — não há arquivo `LICENSE` neste repositório. Sem uma
licença explícita, o código tem **todos os direitos reservados** por padrão; não é
open source. A escolha da licença é uma decisão do responsável, não deste projeto.

## Documentação

O mapa completo está em [`docs/INDEX.md`](docs/INDEX.md). Atalhos:

- [Arquitetura](docs/ARCHITECTURE.md) · [Status atual](docs/STATUS.md) · [Não-objetivos](docs/NON_GOALS.md)
- [ADRs](docs/ADRs/) · [Busca (runbook)](docs/search/RUNBOOK.md) · [i18n](docs/I18N.md)
- [Segurança](docs/SECURITY.md) · [LGPD](docs/LGPD.md) · [Catálogo/admin](docs/CATALOG_ADMIN.md)
- [API](docs/API.md) · [Testes de carga](docs/testing/LOAD.md) · [Deploy Render](docs/DEPLOY_RENDER.md) · [Recuperacao de conta](docs/PASSWORD_RECOVERY.md)
- [Relatório final de prontidão](docs/readiness/FINAL_REPORT.md) · [Histórico](docs/history/)
