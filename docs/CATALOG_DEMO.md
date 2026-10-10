# Forja B2B — Catálogo de demonstração: preços e clientes demo (Fase 9A)

> Última atualização: 2026-10-10. Documento da Fase 9A (preços de demonstração e
> clientes demo). Ele reúne (1) a auditoria do modelo de preços tal como estava
> antes desta fase e (2) o que foi implementado. **Todos os dados são fictícios.**

## 1. Auditoria (estado antes da Fase 9A)

### 1.1 Modelo de preços

- **Preço de lista**: `products.base_unit_price` (`NUMERIC(12,2)`) + `currency`
  (`BRL` padrão). O catálogo é **global** (sem `company_id`, sem RLS); a escrita
  é revogada de `forja_app` (só `forja_admin`/seed escrevem).
- **Preço progressivo por quantidade**: `product_price_tiers`
  (`min_quantity`, `max_quantity`, `unit_price`), também global. Sem empresa.
- **Resolução**: `app/domain/pricing.py::resolve_unit_price` (tier mais
  específico aplicável; senão `base_unit_price`). O docstring já previa, como
  passo 1, uma "tabela de preço negociado por cliente" que **não existia**.
- **Descontos**: o único desconto no código era o do PIX
  (`pix_discount_amount`, taxa única da plataforma). `orders.discount_total` e
  `order_items.discount_amount` existem, mas sempre `0` (nunca populados).
- **Limite de crédito / moeda / arredondamento**: crédito em
  `credit_accounts.credit_limit` (`NUMERIC(14,2)`); dinheiro sempre `Decimal`
  (nunca `float`); arredondamento `ROUND_HALF_UP` ao centavo (aplicado no
  pagamento; a precificação por tier não arredondava).
- **Preço por empresa**: **não existia** nenhuma tabela, coluna, módulo ou
  endpoint. Confirmado por varredura (`company_price`, `negotiated`, `price_list`,
  `customer_price`, `contract_price`, `discount`): zero ocorrências de domínio.

### 1.2 Onde a regra de preço é aplicada

- **Busca** (`app/modules/search/application/search.py`): o índice/vetor devolve
  apenas **ids**; os dados são **hidratados do PostgreSQL**. Visitante recebe
  `price_on_request=true` e `base_unit_price=null`; autenticado recebia o
  `base_unit_price`. **Nenhum preço vem do Elasticsearch.**
- **Carrinho** (`app/modules/cart/**`): o preço é **resolvido no servidor** na
  leitura (`resolve_unit_price`); nenhum preço enviado pelo cliente é aceito.
- **Pedido/checkout** (`app/modules/ordering/**`): os preços são recalculados e
  gravados como **snapshot** em `order_items`.
- **Catálogo público** (`app/modules/catalog/**`): rotas `/catalog/*` são
  públicas e devolvem `base_unit_price` a qualquer visitante. O frontend
  (`catalog-price.tsx`) mascara a exibição para visitante; **a API não mascara**
  (ver limitações).
- **Índice/embedding**: o documento de busca (`ProductDocument.to_source`) e o
  texto de embedding (`build_embedding_text`) **não contêm preço** (testes
  unitários garantem).

### 1.3 Seed atual (antes desta fase)

- `app/infrastructure/db/seeds.py`, idempotente (`INSERT ... ON CONFLICT (id) DO
  NOTHING`), protegido em produção (`SEED_ALLOW_PRODUCTION`).
- 50 produtos (41 vendáveis), 9 categorias demo, 6 marcas fictícias, tiers demo.
- 1 empresa-exemplo (`Construtora Exemplo`) com 4 usuários (ADMIN, BUYER,
  APPROVER, FINANCE), sem senha (não logavam).

### 1.4 RBAC e isolamento

- Papéis: `ADMIN`, `BUYER`, `APPROVER`, `FINANCE` (`MemberRole`).
- `users.company_id` fixa a empresa "casa"; o login resolve a empresa via
  `app.resolve_user_by_email` (SECURITY DEFINER) e assina `company_id`/`role` no
  JWT. **O tenant nunca vem do cliente.**
- Tabelas de domínio usam `FORCE ROW LEVEL SECURITY` com
  `company_id = app.current_company_id()` (GUC transacional via
  `app.set_tenant_context`).
- CNPJ é validado no domínio (`companies/domain/cnpj.py::is_valid_cnpj`, com
  dígitos verificadores).

### 1.5 Solução mínima adotada

Como não havia preço por empresa, criou-se a estrutura **mínima** compatível:

- **Migration `0014_company_pricing`**: tabela `company_price_rules`
  (tenant-scoped, RLS por `company_id`, escrita revogada de `forja_app`).
- **Modelo ORM** `app/infrastructure/db/models/pricing.py`.
- **Leitor compartilhado** `app/infrastructure/db/company_pricing.py`
  (`load_company_price_rules`, dentro de UoW com tenant).
- **Domínio** `app/domain/pricing.py::resolve_company_price` (precedência).
- Ligação em **busca**, **carrinho** e **pedido** (revalidação no PostgreSQL).

---

## 2. O que é fictício e por quê

- **Nenhum dado, preço ou imagem de loja real foi copiado.** Marcas, produtos,
  descrições, CA (`DEMO-CA-*`), empresas, CNPJ e e-mails são inventados.
- Os **CNPJ** das empresas demo são **sintéticos e válidos pelo algoritmo oficial
  do dígito verificador**, mas não pertencem a nenhuma empresa real.
- Os **preços** são fictícios e só servem para demonstrar a regra B2B; não têm
  relação com preços de mercado.

---

## 3. Preços de lista (BRL) do catálogo de demonstração

- Todo produto **vendável** tem preço de lista em BRL, arredondado como no
  varejo (ex.: `18,90`, `42,50`).
- Faixas plausíveis por categoria (referência, ajustadas ao catálogo):
  capacetes 25–90; luvas 5–60; óculos 8–45; botas 70–220; protetores auriculares
  3–35; respiradores descartáveis 3–15 e semifaciais 90–250; cintos/talabartes
  80–350; máquinas estacionárias 600–9.000. Ferramentas elétricas têm faixa
  livre (200–1.000).
- Variação coerente: modelos básicos mais baratos, premium mais caros.
- **Produtos publicados como INACTIVE ou não vendáveis (CA vencido/ausente)
  mantêm o seed como estava** (servem a testes) e não entram na regra de preço.
- **Reexecutar o seed atualiza os preços** de demonstração (upsert por id, só
  quando o valor muda), sem duplicar linhas.

> Nota: os 4 produtos da Fase 1 (`_PRODUCTS`, ex.: capacete `R$ 24,90`)
> mantêm os valores originais (já coerentes com as faixas); a normalização
> aplicou-se aos 46 produtos do catálogo de demonstração da busca.

---

## 4. Empresas e usuários de demonstração

Três empresas fictícias, cada uma com **1 comprador (BUYER)**, **1 administrador
(ADMIN)** e **1 aprovador (APPROVER)**. As senhas **nunca** ficam no repositório:
vêm de `DEMO_USER_PASSWORD` no momento do seed.

| Empresa (slug) | CNPJ (sintético, válido) | Condição comercial |
| :--- | :--- | :--- |
| `metalurgica-alfa` | 11222333000181 | **sem desconto** (preço de lista) |
| `construcoes-beta` | 44555666000181 | **desconto de 10%** na categoria Proteção da Cabeça |
| `industria-gama` | 77888999000181 | **desconto global de 5%** + **preço negociado** em `CAP-002` (R$ 27,90) e `BOT-001` (R$ 89,90) |

E-mails (fictícios, domínio reservado `example.com`):

| Empresa | ADMIN | BUYER | APPROVER |
| :--- | :--- | :--- | :--- |
| alfa | admin@metalurgica-alfa.example.com | comprador@metalurgica-alfa.example.com | aprovador@metalurgica-alfa.example.com |
| beta | admin@construcoes-beta.example.com | comprador@construcoes-beta.example.com | aprovador@construcoes-beta.example.com |
| gama | admin@industria-gama.example.com | comprador@industria-gama.example.com | aprovador@industria-gama.example.com |

A empresa-exemplo (`admin@exemplo.com.br`, etc.) também passa a ter senha quando
`DEMO_USER_PASSWORD` está definido.

### Como definir a senha

No `.env` local (fora do Git), copie a chave de `.env.example` e troque o valor:

```
DEMO_USER_PASSWORD=<senha local de demonstracao>
```

Sem essa variável, o seed **não cria os usuários demo** e imprime um aviso
(somente empresas, crédito e regras de preço entram). Nenhuma senha real é
versionada.

---

## 5. Regra de precedência de preço

Precedência (testada): **preço negociado da empresa > desconto da empresa sobre a
lista > preço de lista**. O preço de lista é o tier aplicável à quantidade ou,
sem tier, o `base_unit_price`. O desconto percentual é arredondado ao centavo
(`ROUND_HALF_UP`).

- **Visitante** (sem empresa): sempre **preço consultivo** (`price_on_request`),
  nenhum valor exposto.
- Cada empresa só vê o **próprio** preço (RLS); tentativas de acesso cruzado são
  negadas.

### Exemplo numérico (produto `CAP-002`, lista `R$ 32,90`, tier 6–23 = `R$ 30,90`)

| Perfil | Regra aplicada | Preço unitário (qtd. 1) |
| :--- | :--- | :--- |
| Visitante | consultivo | sob consulta (sem valor) |
| alfa | lista | R$ 32,90 |
| beta | 10% (Proteção da Cabeça) sobre a lista | R$ 29,61 |
| gama | negociado `CAP-002` (vence o desconto de 5%) | R$ 27,90 |

Quantidade 10 em `CAP-002` para a empresa **beta**: lista = tier `R$ 30,90`;
com 10% = `R$ 27,81`.

---

## 6. Como rodar e reexecutar o seed

Pré-requisitos: stack de pé (`make up`) e migrations aplicadas (`make migrate`).

```bash
# aplica os dados de demonstração (idempotente; usa DEMO_USER_PASSWORD do .env)
make seed
```

Equivalente manual (role administrativa, container one-off):

```bash
docker compose run --rm --no-deps --env-file .env backend \
  python -m app.infrastructure.db.seeds
```

- Reexecutar é **idempotente**: nada é duplicado; os preços de demonstração são
  atualizados quando divergem.
- Se o seed alterar dados indexados, reconcilie/reindexe a busca:
  `docker compose exec backend python -m app.modules.search.interface.cli reindex`.

---

## 7. Testes e garantias

- **Unitários** (`tests/unit/test_pricing.py`): precedência negociado > desconto
  > lista, desconto por categoria vs global, arredondamento, tier + desconto.
- **Unitários** (`tests/unit/test_seed_demo_pricing.py`): faixas de preço,
  CNPJ válidos, determinismo, sem `password_hash` sem senha.
- **Unitários** (`tests/unit/test_search_documents.py`,
  `test_search_embeddings.py`): documento e texto de embedding **sem preço**.
- **Integração** (`tests/integration/test_company_pricing.py`): visitante
  consultivo; empresa A (negociado) e B (desconto) com valores distintos;
  carrinho revalida no PostgreSQL; RLS isola `company_price_rules`.
- **Integração** (`tests/integration/test_persistence_seeds.py`): seed
  idempotente; sem senha não cria usuários demo; com senha cria 3 empresas x 3
  usuários; preço atualizado na reexecução.

---

## 8. Limitações conhecidas

- (Corrigido na Fase 9A-2, item 0a) o catálogo público devolvia `base_unit_price`
  a visitantes; agora segue a mesma regra da busca (ver seção 10).
- O desconto da empresa vira o próprio `unit_price` do snapshot; **não** há
  coluna dedicada de desconto por item/empresa (o `discount_total` segue `0`).
- Apenas **dois tipos** de regra (preço fixo por produto e desconto percentual
  por categoria/global); não há desconto por quantidade por empresa nem vigência
  (`valid_from`/`valid_until`).
- Apenas os 4 produtos da Fase 1 mantêm preço "de borda" (`R$ 24,90`).

---

## 9. Imagens por categoria (Fase 9A-2)

- Campo opcional `products.image_url` (migration `0015`), validado no domínio
  (`app/domain/catalog_image.py`): aceita `https://...` ou caminho relativo
  iniciado por `/`; rejeita `javascript:`, `data:`, `http:`, protocol-relative
  (`//host`) e acima de 500 caracteres. Pronto para o admin e a importação CSV.
- **Resolução (única e testável):** imagem do produto > imagem padrão da
  categoria (por slug) > placeholder genérico.
- **Onde ficam as ilustrações:** `backend/app/static/catalog/*.svg` (12 SVGs
  originais: 11 categorias do seed + `generic.svg`), **servidas pela própria API**
  em `/static`. Decisão: a API é a dona do contrato de imagem; servir do backend
  mantém a URL diretamente acessível (HTTP 200) e cacheável (ETag/Last-Modified),
  sem depender do frontend. O frontend resolve o caminho relativo com
  `NEXT_PUBLIC_API_URL`.
- **Sem base de URL obrigatória:** como as imagens são servidas pela API (mesma
  origem do backend), **não** há `CATALOG_IMAGE_BASE_URL` nesta fase; consumidores
  externos resolvem o caminho relativo contra a origem da API (uma `image_url`
  absoluta `https://` é devolvida como está).
- **API:** `image_url` (resolvida, nunca nula) e `image_alt` (= nome do produto)
  no catálogo (lista/detalhe), na busca e no carrinho. A imagem é **hidratada do
  PostgreSQL** (nada no Elasticsearch) e nada é gravado em disco em runtime.
- **Seed:** mantém `image_url` nulo (as imagens padrão cobrem tudo) e continua
  idempotente.
- As ilustrações são **originais deste projeto** (sem marcas/terceiros), ~0,5 KB
  cada; podem ser substituídas por fotos reais na **Fase 9A-3** (basta preencher
  `image_url`).

### Como definir a imagem de um produto

```sql
-- admin/backoffice (Fase 9A-3); precedência: produto > categoria
UPDATE products SET image_url = 'https://cdn.exemplo/produto.jpg' WHERE sku = 'CAP-002';
-- ou caminho relativo servido pela própria API:
UPDATE products SET image_url = '/static/catalog/custom.svg' WHERE sku = 'CAP-002';
```

---

## 10. Contrato de preço do catálogo (item 0a da Fase 9A-2)

`GET /catalog/products` e `GET /catalog/products/{id}` passaram a seguir a
**mesma regra** da busca (reutilizando o serviço de preços compartilhado):

- **visitante:** `price_on_request=true` e `base_unit_price=null` (nenhum valor);
- **autenticado:** preço resolvido pela precedência (negociado > desconto > lista).

Mudança de contrato para o frontend: `base_unit_price` passou a ser **opcional**
(`string | null`) e surgiu o campo booleano `price_on_request` (a UI já exibe
"sob consulta"). Endpoints que expõem preço: `/catalog/products`,
`/catalog/products/{id}` e `/search/products` (todos agora mascarados para
visitante); `/cart` e `/orders` exigem autenticação.

---

## 11. Correções correlatas (Fase 9A-2)

- **0b — credenciais vazias do Elasticsearch:** `ELASTICSEARCH_API_KEY=` (vazio)
  no `.env.example` fazia o cliente tratar a chave como definida e ignorar
  usuário/senha (HTTP 401). Agora string vazia (ou só espaços) vira `None` nos
  campos opcionais de credencial do ES, mantendo a regra "API key vence".
- **0c — `.pyc` versionados:** 212 arquivos `__pycache__/*.pyc` estavam no
  índice do Git (anteriores às regras de ignore); foram removidos **do índice
  apenas** (`git rm --cached`), sem apagar do disco. O `.gitignore` já cobre
  `__pycache__/` e `*.pyc`.
