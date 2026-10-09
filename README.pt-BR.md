# Forja B2B — Backend (README em português)

API FastAPI (Python 3.12) de marketplace B2B multi-tenant, com isolamento via
PostgreSQL RLS. Clean Architecture + SOLID, tipagem estrita (`mypy` strict).

## Requisitos

- Docker (Docker Desktop) + Docker Compose v2
- Python 3.12 (para rodar testes localmente com venv)

## Execução local (Docker Compose)

```bash
cp .env.example .env   # preencher valores (defaults de dev já servem)
make up                # sobe postgres, redis, rabbitmq, mailpit, backend, worker, beat, frontend, etc.
make migrate           # aplica as migrações Alembic (role admin, container one-off)
```

Serviços principais:

| Serviço | Porta | Uso |
| :--- | :--- | :--- |
| backend (API) | 8000 | `/docs`, `/api/v1/*` |
| Mailpit (e-mails) | 8025 | inspecionar e-mails de notificação |
| RabbitMQ | 15672 | management (guest/guest) |
| Grafana | 3001 | dashboards (admin/dev) |

## Testes e qualidade (backend)

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt -r requirements-dev.txt

pytest tests/                 # unidade + integração (Testcontainers)
ruff check . && ruff format --check .
mypy .
lint-imports --config .import-linter
```

> Os testes de integração exigem o daemon Docker (PostgreSQL/Redis descartáveis
> via Testcontainers, usando o bootstrap real de `docker/postgres`).
> **Atenção:** rode a suíte com as variáveis de docker-compose removidas do
> ambiente (`DATABASE_URL`, `DATABASE_ADMIN_URL`, `REDIS_URL`, etc.), pois elas
> sobrescrevem os defaults testados por `tests/unit/test_config.py`.

## Integrações simuladas (sem serviços pagos)

- **Pagamentos**: PIX (com desconto no backend) e cartão via `FakePaymentGateway`;
  webhook autenticado por HMAC (`PAYMENT_WEBHOOK_SECRET`).
- **Notificações**: outbox transacional + Celery/RabbitMQ + SMTP local (Mailpit).
- **Tributação**: simulação ICMS-ST explícita (não é motor fiscal de produção).
- **Frete**: tarifa determinística por peso (sem transportadora).
- **Google OAuth**: fluxo tradicional de redirect (opcional, configurar
  `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URI`).

## Documentação

- `docs/STATUS.md` — estado das fases
- `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/LGPD.md`, `docs/ADRs/`
- `docs/RUNBOOK.md` — operação/troubleshooting

## Para produção

Rotacione todos os segredos (`SECRET_KEY`, `PEPPER`, `ENCRYPTION_KEY`,
`PAYMENT_WEBHOOK_SECRET`) e o **segredo Google anteriormente exposto** via
gerenciador de segredos. Não use os valores de `.env.example` fora de dev.
