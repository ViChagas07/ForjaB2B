# API — mapa de endpoints

A API é FastAPI e segue o prefixo `/api/v1`. A documentação OpenAPI é gerada em runtime:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

`/docs` e `/openapi.json` são desligados quando `ENVIRONMENT=production` (ver
`backend/app/main.py`). Não há snapshot versionado do OpenAPI; o contrato executável é o
próprio app. Erros usam `application/problem+json` (RFC 7807), com `type`, `title`,
`status`, `detail` e extensões por campo.

## Saúde

| Método | Rota | Observação |
| :--- | :--- | :--- |
| GET | `/health/live` | Liveness |
| GET | `/health` | Alias de liveness (fora do schema) |
| GET | `/health/ready` | PostgreSQL + Redis |
| GET | `/health/search` | `ok`/`degraded`/`unavailable`/`disabled` |
| GET | `/metrics` | Prometheus (fora do schema) |

## Identidade

| Método | Rota | Observação |
| :--- | :--- | :--- |
| POST | `/api/v1/auth/login` | E-mail + senha; retorna access/refresh |
| POST | `/api/v1/auth/refresh` | Rotação de refresh |
| POST | `/api/v1/auth/logout` | Revoga refresh |
| GET | `/api/v1/auth/google` | 302 para o Google (se configurado) |
| GET | `/api/v1/auth/google/callback` | Callback; exchange code de uso único |
| POST | `/api/v1/auth/oauth/exchange` | Troca o code pelo par de tokens |

## Empresas e crédito

| Método | Rota | Observação |
| :--- | :--- | :--- |
| POST | `/api/v1/companies` | Cadastro de empresa (CNPJ) |
| GET | `/api/v1/companies/me` | Empresa do token |
| POST | `/api/v1/companies/{company_id}/approve` | Admin de plataforma (`ADMIN_API_KEY`) |
| GET | `/api/v1/credit/account` | Conta de crédito do tenant |
| GET | `/api/v1/credit/entries` | Lançamentos do tenant |

## Catálogo público

| Método | Rota | Observação |
| :--- | :--- | :--- |
| GET | `/api/v1/catalog/categories` | Categorias |
| GET | `/api/v1/catalog/categories/{category_id}` | Categoria |
| GET | `/api/v1/catalog/brands` | Marcas |
| GET | `/api/v1/catalog/brands/{brand_id}` | Marca |
| GET | `/api/v1/catalog/products` | Lista com `q`, filtros e paginação |
| GET | `/api/v1/catalog/products/{product_id}` | Detalhe; atributos preenchidos |

`Accept-Language`/`?lang=` negociam o idioma; a resposta inclui `content_locale` e
`fallback`. Visitante recebe `price_on_request=true` e `base_unit_price=null`.

## Busca

| Método | Rota | Observação |
| :--- | :--- | :--- |
| GET | `/api/v1/search/products` | `q`, `page`, `page_size`, filtros; retorna `search_mode` |
| GET | `/api/v1/search/products/autocomplete` | Mínimo de 2 caracteres; máximo 10 sugestões |

## Carrinho, pedidos, faturamento e pagamento

| Método | Rota | Observação |
| :--- | :--- | :--- |
| GET | `/api/v1/cart` | Carrinho do tenant |
| POST | `/api/v1/cart/items` | Adiciona item |
| PUT | `/api/v1/cart/items/{product_id}` | Atualiza quantidade |
| DELETE | `/api/v1/cart/items/{product_id}` | Remove item |
| DELETE | `/api/v1/cart` | Limpa o carrinho |
| POST | `/api/v1/orders` | Cria pedido; exige `idempotency_key` no corpo |
| GET | `/api/v1/orders/{order_id}` | Pedido |
| POST | `/api/v1/orders/{order_id}/cancel` | Cancela |
| POST | `/api/v1/invoices` | Cria fatura/boleto simulado |
| GET | `/api/v1/invoices/{invoice_id}` | Fatura |
| GET | `/api/v1/invoices/order/{order_id}` | Fatura do pedido |
| POST | `/api/v1/payments` | Inicia pagamento fake; `idempotency_key` no corpo |
| GET | `/api/v1/payments/{payment_id}` | Pagamento |
| POST | `/api/v1/payments/webhook` | HMAC `X-Forja-Signature` sobre o corpo bruto |

## Notificações e privacidade

| Método | Rota | Observação |
| :--- | :--- | :--- |
| GET | `/api/v1/notifications` | Notificações do tenant |
| POST | `/api/v1/notifications/{notification_id}/resend` | Reenvio |
| GET | `/api/v1/privacy/export` | Exportação LGPD |
| PATCH | `/api/v1/privacy/me` | Retificação |
| DELETE | `/api/v1/privacy/me` | Anonimização |
| POST | `/api/v1/privacy/consent` | Consentimento |
| GET | `/api/v1/privacy/consent` | Consentimentos |

## Administração de catálogo (RBAC `ADMIN`)

| Método | Rota | Observação |
| :--- | :--- | :--- |
| POST | `/api/v1/admin/catalog/products` | Cria `DRAFT` |
| GET | `/api/v1/admin/catalog/products` | Lista com `q`, categoria e status |
| GET | `/api/v1/admin/catalog/products/{product_id}` | Detalhe admin |
| PATCH | `/api/v1/admin/catalog/products/{product_id}` | Edição com `version` (409) |
| POST | `/api/v1/admin/catalog/products/{product_id}/publish` | `DRAFT` → `ACTIVE` |
| POST | `/api/v1/admin/catalog/products/{product_id}/unpublish` | `ACTIVE` → `DRAFT` |
| GET | `/api/v1/admin/catalog/categories/{category_slug}/attributes` | Definições por categoria |
| GET | `/api/v1/admin/catalog/static-images` | Imagens estáticas disponíveis |
| GET | `/api/v1/admin/catalog/translations/products/{product_id}` | Traduções e staleness |
| PATCH | `/api/v1/admin/catalog/translations/products/{product_id}/{locale}` | Edição/marcação `reviewed` |

## Autenticação e convenções

- Rotas públicas: catálogo, busca, health e webhook (HMAC).
- Rotas de tenant: exigem `Authorization: Bearer <access_token>`; o `company_id` vem do
  token, nunca de parâmetro.
- Rotas admin: exigem papel `ADMIN` no token e `DATABASE_ADMIN_URL` configurada.
- Paginação: `page`/`page_size` (máx. 100 na busca) e limite de profundidade.
- Texto de usuário é texto simples, sem HTML, com limites de tamanho.
- `X-Request-ID` é aceito e devolvido; `Vary: Accept-Language` nas rotas dependentes de
  idioma.

> **CORS:** o backend não envia cabeçalhos CORS. Chamadas de navegador a partir de outra
> origem são bloqueadas. Ver a limitação no `README.md`.
