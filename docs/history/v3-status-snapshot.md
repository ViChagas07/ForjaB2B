> **Documento histórico (congelado).** Snapshot intermediário da validação V3,
> substituído pelo `docs/STATUS.md` atual. Preservado como registro.

---

## Validação V3 — Frontend: 11 idiomas, RTL, selo fallback, checagem visual

**Iniciado:** 2026-10-14  
**Concluído:** 2026-10-14 (testes automatizados passam; validação visual com Docker pendente)

### Resumo

O frontend Next.js (App Router + `next-intl` v3) exibe o **site inteiro do cliente** (catálogo, busca, carrinho, pedido, login, cadastro, conta) em **11 idiomas** com layout RTL para árabe. O painel de administração permanece em português.

### Implementado (V3)

| Componente | Descrição |
|------------|-----------|
| **11 idiomas de interface** | pt-BR, en, zh-CN, ja, ko, ru, es, de, fr, it, ar — nomes nativos no seletor |
| **RTL derivado de lista única** | `isRtlLocale()` → apenas `ar`; `dir="rtl"` + `lang` no HTML |
| **Fontes por escrita** | Noto Sans Arabic, CJK SC, JP, KR, cirílica, latina |
| **Fallback badge removido** | Substituído por nota discreta "Conteúdo exibido em {locale}" só no detalhe do produto |
| **Carrinho/Pedido limpos** | Sem indicadores de locale/fallback |
| **Propriedades lógicas CSS** | `ms-1`, `text-end`, `text-start` nas telas do cliente (4 trocadas) |
| **Seletor de idioma** | Nomes nativos, `aria-label`, teclado, cookie, detecção `Accept-Language` na primeira visita |
| **Admin "Traduções"** | Estados `ausente`/`machine`/`reviewed`/`stale`, edição manual, marcar revisada |

### Qualidade

| Verificador | Resultado |
|-------------|----------|
| Typecheck | ✅ passed |
| Lint | ✅ passed (4 warnings `<img>` admin) |
| Testes unitários | ✅ 86 passed (+3 i18n-parity) |
| i18n parity | ✅ 11 locales (356 chaves cada) |

### Testes

```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run (86 testes)
cd frontend && npx playwright test  # E2E (requer backend)
```

### Arquivos criados/modificados (V3)

**Frontend (novos):**
- `features/admin/catalog/translation-row.tsx`

**Frontend (modificados):**
- `core/domain/catalog.ts` — tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `core/application/ports/http-client.ts` — `locale` em `HttpRequest`
- `infrastructure/http/api-client.ts` — header `Accept-Language`
- `infrastructure/http/{catalog,cart,ordering,credit,company,admin-catalog}-api.ts` — `locale` param + hooks
- `features/catalog/product-detail.tsx` — nota discreta `contentDisplayedIn`, sem badge fallback
- `features/cart/cart-view.tsx` — sem indicadores de locale/fallback
- `features/ordering/order-detail.tsx` — sem indicadores de locale/fallback
- `features/ordering/checkout-view.tsx` — `text-left` → `text-start`
- `features/credit/credit-view.tsx` — `text-right` → `text-end`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` — seção 5 "Traduções"
- `app/[locale]/admin/catalog/products/admin-product-list-client.tsx` — status badges via translations
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` — chaves de tradução (11 locales)

### NÃO VALIDADO e riscos

- **Validação visual com Docker pendente**: Ambiente sem Docker/ES — não foi possível navegar em `pt-BR`/`en`/`ar`/`zh-CN`, conferir `dir="rtl"` e layout árabe, testar seção admin "Traduções"
- **Qualidade árabe não revisada por nativo**: Traduções de máquina/automatizadas
- **Numerais ocidentais**: Não usa árabe-índicos (١, ٢, ٣)
- **Provedor de tradução não adotado**: Porta existe, botão "Retraduzir" oculto
- **Painel admin em português**: Requisito do projeto
- **Moeda fixa BRL**: Sem conversão
- **Fallback PG busca textual apenas pt-BR**

### Próximos passos

1. Disponibilizar Docker/Elasticsearch → executar validação visual
2. Checagens finais (RULES.md) — executadas