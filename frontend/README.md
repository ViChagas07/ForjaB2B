# Forja B2B — Frontend (Fase 0 — Fundação)

Fundação arquitetural e visual do frontend do Forja B2B. Next.js (App Router),
TypeScript strict, Tailwind, shadcn/ui, next-intl (11 locales + RTL), TanStack
Query, Zustand e Zod, com boundaries arquiteturais verificáveis via
dependency-cruiser.

> Esta é a **fundação**. Nenhuma funcionalidade de negócio (cadastro, login,
> catálogo, carrinho, checkout, pedidos, pagamentos, etc.) é implementada aqui.

## Stack

| Área               | Ferramenta                                            |
| :----------------- | :---------------------------------------------------- |
| Framework          | Next.js 14 (App Router, RSC, standalone)              |
| UI                 | React 18 + TypeScript strict + Tailwind 3 + shadcn/ui |
| Estado de servidor | TanStack Query v5                                     |
| Estado de cliente  | Zustand v4                                            |
| Validação          | Zod                                                   |
| i18n               | next-intl v3 (11 locales, RTL)                        |
| Testes             | Vitest (unit), Playwright + axe (smoke/a11y)          |
| Arquitetura        | dependency-cruiser                                    |

## Estrutura (Clean Architecture)

```
frontend/
├── app/                 # Next.js: rotas, layouts, rotas de metadados e API
│   ├── [locale]/        # locale routing (layout, page, error, not-found, loading)
│   ├── api/health/      # /api/health
│   ├── sitemap.ts, robots.ts, manifest.ts, llms.txt/, ...
├── core/                # Núcleo independente de frameworks
│   ├── domain/          # Result, DomainError (neutro)
│   └── application/
│       ├── ports/       # HttpClient (porta)
│       └── use-cases/   # (vazio na Fase 0)
├── infrastructure/      # Adapters externos
│   └── http/            # FetchHttpClient, RFC 7807 (ProblemDetails), config
├── features/            # Módulos de negócio (fases futuras)
├── shared/              # Código compartilhado
│   ├── components/      # shell (header, idioma, tema)
│   ├── lib/             # cn, query-client
│   ├── stores/          # Zustand (ui-store)
│   └── ui/              # componentes base shadcn/ui
├── i18n/                # routing, request, navigation, locales
├── messages/            # 11 arquivos de tradução
├── tests/               # unit (Vitest) + e2e (Playwright)
└── public/brand/        # logo, ícone
```

### Regra de dependência (verificada por dependency-cruiser)

```
app → features → core/application → core/domain
                      ↓
                 infrastructure
```

- `core/domain` não depende de application/infrastructure/shared/features/app.
- `core` inteiro é independente de React/Next/TanStack/Zustand.
- `shared/ui` (componentes) não importa core/infrastructure/features/app.
- `infrastructure` não importa UI/rotas/features.
- `features` não importam internals umas das outras.
- Sem ciclos.

Componentes **não** fazem `fetch()` direto; usam a porta `HttpClient` (adapter
em `infrastructure/http`).

## Design tokens

Fonte central: `app/globals.css` (CSS variables, HSL) + `tailwind.config.ts`.

| Token          | Valor (MEGA-PROMPT)      |
| :------------- | :----------------------- |
| `forge-500`    | `#F97316` (primary)      |
| `forge-600`    | `#EA580C` (hover)        |
| `steel-800`    | `#1E293B`                |
| `steel-900`    | `#0F172A`                |
| `platinum-50`  | `#F8FAFC` (background)   |
| `platinum-200` | `#E2E8F0` (border/muted) |

Semânticos: `success`, `info`, `warning`, `danger`. Dark mode via classe `.dark`
(alternância de CSS variables, sem cor fixa espalhada).

> Decisão de contraste: `--primary-foreground` é `steel-900` (texto escuro sobre
> o laranja `forge-500`) porque laranja + texto branco não atinge WCAG AA. O
> `--muted-foreground` em modo claro é `slate-600` pelo mesmo motivo.

## i18n

- Locales: `pt-BR` (padrão), `en`, `zh-CN`, `ja`, `ko`, `ru`, `es`, `de`, `fr`,
  `it`, `ar`.
- `ar` é RTL (`dir="rtl"` no `<html>`). Layout usa logical properties.
- Prefixo de locale sempre presente (`/pt-BR`, `/en`, `/ar`). `localeDetection`
  desativado: a raiz `/` sempre resolve para `pt-BR`.
- Paridade de chaves testada em `tests/unit/i18n-parity.test.ts`.

## Comandos

```bash
npm run dev          # servidor de desenvolvimento
npm run build        # build de produção (standalone)
npm run start        # serve o build
npm run lint         # ESLint (next lint)
npm run typecheck    # tsc --noEmit
npm run format       # prettier --write
npm run format:check # prettier --check
npm run test         # vitest run
npm run test:e2e     # playwright test (porta 3010)
npm run depcruise    # dependency-cruiser (boundaries)
npm run check        # lint + typecheck + format:check + test + depcruise
```

## Variáveis de ambiente

Somente variáveis **públicas** (`NEXT_PUBLIC_*`). Nenhum segredo de backend
(DATABASE_URL, senhas, API secrets, chaves) pode viver no bundle do browser.

| Variável               | Padrão                  | Uso                           |
| :--------------------- | :---------------------- | :---------------------------- |
| `NEXT_PUBLIC_API_URL`  | `http://localhost:8000` | Base da API (`/api/v1`)       |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | canonical/sitemap/OG/llms.txt |

## Health

`GET /api/health` → `200 {"status":"ok","service":"forja-frontend",...}`.
Independe de PostgreSQL/Redis; não expõe detalhes internos.

## Notas / pendências

- **Fonte**: usa um stack de fontes de sistema (cobre CJK/JP/KR e árabe) sem
  dependência de runtime. Uma fonte de marca (via `next/font/google`) deve ser
  aprovada no `DESIGN.md` antes de ser introduzida.
- **Tema**: a troca light/dark aplica a classe após o hydration (`suppressHydrationWarning`),
  com um possível flash no primeiro paint; uma solução com script inline no
  `<head>` pode ser adicionada quando o tema for requisito de produto.
- **Robots/IA**: a decisão de bloquear/liberar crawlers de IA (GPTBot, ClaudeBot,
  etc.) é do dono do produto e ainda não foi tomada.
- **RTL**: componentes próprios usam logical properties; componentes shadcn
  (dialog/dropdown) ainda usam utilitários físicos e podem receber um passe de
  logical properties em fase futura.
