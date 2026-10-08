# ============================================================
# Forja B2B — Frontend Dockerfile (multi-stage standalone Next.js)
# Base: Node 20.17.0-alpine
# ============================================================

# ---------- Stage 1: base ----------
FROM node:20.17.0-alpine AS base
RUN apk add --no-cache libc6-compat
WORKDIR /app

# ---------- Stage 2: dependencies ----------
FROM base AS deps
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
  else npm i; \
  fi

# ---------- Stage 3: builder ----------
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Variáveis de build para o Next.js
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm build; \
  else npm run build; \
  fi

# ---------- Stage 4: runner ----------
FROM base AS runner
WORKDIR /app

LABEL maintainer="ForjaB2B Team" \
      description="Forja B2B Next.js Frontend" \
      version="0.1.0"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Instala curl para healthcheck
RUN apk add --no-cache curl

# Usuário não-root seguro
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Cria diretório de cache e ajusta permissões
RUN mkdir .next && chown nextjs:nodejs .next

# Copia arquivos estáticos públicos e saída de build standalone
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || curl -f http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
