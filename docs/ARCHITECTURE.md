# Forja B2B — Arquitetura do Backend

## Visão geral

API FastAPI (Python 3.12) em Clean Architecture, com isolamento multi-tenant
obrigatório via PostgreSQL Row Level Security (RLS). Cada domínio de negócio é um
*bounded context* independente (`app.modules.*`), composto por quatro camadas:

```
interface (rotas/schemas)  ─┐
infrastructure (repo/adapters) ─┤ irmãos independentes
application (casos de uso/portas) ─┤
domain (regras puras, sem frameworks) ─┘
```

A raiz de composição (`app/main.py`) liga portas a implementações e as expõe em
`app.state`; os routers são finos e não importam infraestrutura.

## Bounded contexts

| Módulo | Responsabilidade |
| :--- | :--- |
| `identity` | login, JWT, refresh, OAuth Google (redirect + exchange code de uso único) |
| `companies` | onboarding, CNPJ, endereços |
| `catalog` | categorias, marcas, produtos, tiers de preço |
| `credit` | ledger append-only (reserva/liberação/captura/pagamento) |
| `pricing` / `shipping` / `tax` | regras de domínio compartilhadas (pure Python) |
| `cart` | carrinho (preços resolvidos no servidor) |
| `ordering` | pedidos (snapshot + reserva de crédito atômica) |
| `invoicing` | fatura/boleto (captura de crédito net-zero) |
| `payment` | pagamentos (PIX/CARD/BOLETO), webhook idempotente, máquina de estados |
| `notification` | outbox transacional + despacho (Celery/RabbitMQ) + e-mail |
| `privacy` | LGPD: exportação, retificação, exclusão, consentimento |
| `audit` / `search` / `rfq` / `notifications` | scaffolds (fases futuras) |

## Isolamento multi-tenant (RLS)

- `app.set_tenant_context(company_id, user_id)` define GUCs transacionais
  (`SET LOCAL`), aplicadas pela `SqlAlchemyUnitOfWork` na mesma transação.
- Todas as tabelas de domínio têm `FORCE ROW LEVEL SECURITY` com política
  `company_id = app.current_company_id()`.
- Funções `SECURITY DEFINER` (`app.resolve_user_by_email`,
  `app.list_due_notifications`) resolvem casos de leitura sem contexto de tenant
  (login e despacho da outbox), com política dedicada e papel `NOLOGIN`.

## Padrões transversais

- Dinheiro/peso/tributos sempre em `Decimal` (nunca `float`), arredondamento
  `ROUND_HALF_UP`.
- Idempotência via `idempotency_key` única + lock `FOR UPDATE`.
- Erros mapeados para RFC 7807 (`application/problem+json`).
- Outbox transacional para notificações (publicação atômica com o commit).

## Contratos de arquitetura

`backend/.import-linter` valida (CI): Clean Architecture em camadas,
independência dos bounded contexts, pureza do domínio e neutralidade do `core`.
