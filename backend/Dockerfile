# ============================================================
# Forja B2B — Backend Dockerfile (multi-stage)
# Base: Python 3.12.5-slim-bookworm
# ============================================================

# ---------- Stage 1: builder ----------
FROM python:3.12.5-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Instala dependências de build (gcc, libpq-dev para psycopg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copia apenas os arquivos de dependências primeiro (cache layer)
COPY requirements.txt requirements-dev.txt* ./

# Cria virtualenv isolado e instala dependências
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12.5-slim-bookworm AS runtime

# Metadados
LABEL maintainer="ForjaB2B Team" \
      description="Forja B2B Backend API" \
      version="0.1.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000

# Dependências de runtime mínimas
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini && \
    rm -rf /var/lib/apt/lists/*

# Usuário não-root
RUN groupadd --gid 1000 forja && \
    useradd --uid 1000 --gid forja --shell /bin/bash --create-home forja

# Copia virtualenv do builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copia código da aplicação
COPY --chown=forja:forja . .

# Troca para usuário não-root
USER forja

EXPOSE ${PORT}

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Usa tini como init para gerenciar sinais corretamente
ENTRYPOINT ["tini", "--"]

# Uvicorn com workers calculados automaticamente
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--access-log"]
