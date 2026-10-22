# ADR-0005: PostgreSQL como fonte de verdade e multi-tenant com RLS

- **Status:** aceito e implementado
- **Data:** 2026-10-10
- **Contexto do código:** `backend/app/infrastructure/db/unit_of_work.py`,
  `backend/app/application/security.py`, `docker/postgres/init-roles.sql`,
  `backend/alembic/versions/0001_companies_identity.py`

## Contexto

O produto é um marketplace B2B: várias empresas (tenants) compram o mesmo catálogo, mas
têm preços, crédito, pedidos e dados pessoais próprios. O risco central é vazamento de
preço ou de dado entre empresas. Índices de busca são derivados e não podem ser a
autoridade sobre preço, disponibilidade ou autorização.

## Decisão

1. **PostgreSQL é a fonte de verdade** de catálogo, preço, crédito, pedidos, traduções,
   consentimentos e auditoria.
2. O isolamento é feito com **Row Level Security `FORCE`** em todas as tabelas de domínio:
   a política compara `company_id` com `app.current_company_id()`, uma GUC transacional
   definida por `app.set_tenant_context(company_id, user_id)` na mesma transação da UoW.
3. `company_id` vem **sempre do JWT** (`AuthContext`), nunca de header, query ou corpo.
4. O runtime usa a role `forja_app` (DML, `NOBYPASSRLS`); migrations usam `forja_admin`
   (`NOSUPERUSER`, `NOBYPASSRLS`), em container one-off. O bootstrap é o único com
   superusuário e não é injetado nos containers de aplicação.
5. Login e enumeração da outbox usam funções `SECURITY DEFINER` com roles `NOLOGIN` e
   políticas dedicadas — não se abre `BYPASSRLS` para a aplicação.
6. Elasticsearch, pgvector e Redis são **derivados** e reconstruíveis; nenhum deles é
   autoridade de dado comercial.

## Alternativas consideradas

- **Filtro por `company_id` só na aplicação:** simples, mas um `WHERE` esquecido vaza
  dados. Rejeitado.
- **Schema por tenant:** isolamento forte, mas migrations e conexões ficam complexas para
  um catálogo global e muitas empresas.
- **Banco por tenant:** isolamento máximo, custo operacional e de conexões alto demais
  para o escopo.
- **Views com `company_id` fixo:** menos flexível e fácil de contornar.

## Consequências

- O isolamento é imposto pelo banco, inclusive para queries ad-hoc de operadores.
- Toda operação de domínio precisa abrir a UoW com contexto de tenant; sem contexto, a
  política retorna vazio (não vaza).
- Consultas cross-tenant (login, outbox) exigem funções dedicadas e auditoria.
- Há custo de policy por linha e necessidade de testes de integração com PostgreSQL real.
- O admin de catálogo é global e usa uma UoW separada (`DATABASE_ADMIN_URL`), sem RLS de
  tenant; isso é explícito e restrito ao backoffice.

## Em produção real, seria diferente

- Usar PostgreSQL gerenciado com PITR, réplica de leitura para relatórios e pooler
  (PgBouncer) com atenção ao modo de transação: `SET LOCAL` funciona, mas o pooler não pode
  trocar o contexto entre transações.
- Separar roles por serviço (API, worker, migrations, leitura analítica) e rotacionar
  credenciais.
- Adicionar testes de política RLS no CI com uma matriz de tenants e um teste negativo
  tentando acessar `company_id` alheio.
- Monitorar tentativas de acesso negadas e consultas cross-tenant; hoje há teste, mas não
  alerta.
