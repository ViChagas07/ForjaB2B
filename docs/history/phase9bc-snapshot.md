> **Documento histórico (congelado).** Snapshot da Fase 9B-c, substituído pelas
> validações V3 e pelo `docs/STATUS.md` atual. Preservado como registro.

---

## Fase 9B-c — Frontend multilíngue (seletor de idioma, textos traduzidos e RTL em árabe)

**Iniciado:** 2026-10-13  
**Concluído:** 2026-10-13 (testes automatizados passam; validação visual com Docker pendente)

### Resumo

O frontend Next.js (App Router + `next-intl` v3) exibe o catálogo, busca, carrinho e pedidos no idioma escolhido pelo cliente, com layout RTL para árabe e indicadores visuais de `content_locale`/`fallback`. O painel de administração continua em português.

### Implementado

| Componente | Descrição |
|------------|-----------|
| **Infraestrutura de idioma** | `HttpRequest.locale` → header `Accept-Language`; hooks `useCatalogApi`, `useCartApi`, `useOrderingApi`, `useCreditApi`, `useCompanyApi` injetam `useLocale()` |
| **Indicadores `content_locale`/`fallback`** | `ProductDetailView`, `CartView` (por item), `OrderDetailView` (cabeçalho + itens) — Globe + código locale + badge "Fallback" |
| **RTL para árabe** | `html lang` + `dir="rtl"`; font stack `Noto Sans Arabic`; propriedades lógicas (`ms-1`, `text-end`, `text-start`); numerais ocidentais |
| **Admin "Traduções"** | Seção 5 no formulário de produto (modo edição); estados `ausente`/`machine`/`reviewed`/`stale`; edição manual + "Marcar como revisada"; "Retraduzir" oculto (sem provedor) |

### Qualidade

| Verificador | Resultado |
|-------------|----------|
| Typecheck | ✅ passed |
| Lint | ✅ passed (3 warnings `<img>` vs `next/image`) |
| Testes | ✅ 83 passed |
| i18n parity | ✅ 11 locales (356 chaves cada) |

### Testes

```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run (83 testes)
```

### Arquivos criados/modificados

**Frontend (novos):**
- `features/admin/catalog/translation-row.tsx` — componente linha de tradução

**Frontend (modificados):**
- `core/domain/catalog.ts` — tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `core/application/ports/http-client.ts` — `locale` em `HttpRequest`
- `infrastructure/http/api-client.ts` — header `Accept-Language`
- `infrastructure/http/catalog-api.ts` — `locale` param + `useCatalogApi` hook
- `infrastructure/http/cart-api.ts` — `locale` param + `useCartApi` hook
- `infrastructure/http/ordering-api.ts` — `locale` param + `useOrderingApi` hook
- `infrastructure/http/credit-api.ts` — `locale` param + `useCreditApi` hook
- `infrastructure/http/company-api.ts` — `locale` param + `useCompanyApi` hook
- `infrastructure/http/admin-catalog-api.ts` — endpoints de tradução admin
- `infrastructure/http/index.ts` — exports dos hooks `use*Api`
- `features/catalog/product-detail.tsx` — indicador `content_locale`/`fallback`
- `features/cart/cart-view.tsx` — indicador por item
- `features/ordering/order-detail.tsx` — indicador no cabeçalho e itens
- `features/ordering/checkout-view.tsx` — `text-left` → `text-start`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` — seção 5 "Traduções"
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` — chaves de tradução (11 locales)

### NÃO VALIDADO e riscos

- **Validação visual com Docker pendente**: Ambiente sem Docker/ES — não foi possível navegar em `pt-BR`/`en`/`es`/`ar`, conferir `dir="rtl"` e layout árabe, testar seção admin "Traduções"
- **Qualidade árabe não revisada por nativo**: Traduções de máquina/automatizadas
- **Numerais ocidentais**: Não usa árabe-índicos (١, ٢, ٣)
- **Provedor de tradução não adotado**: Porta existe, botão "Retraduzir" oculto
- **Painel admin em português**: Requisito do projeto
- **Moeda fixa BRL**: Sem conversão

### Próximos passos

1. Disponibilizar Docker/Elasticsearch → executar validação visual (Passo 6)
2. Atualizar `docs/I18N.md` (já feito) e `docs/STATUS.md`
3. Checagens finais (RULES.md) — já executadas