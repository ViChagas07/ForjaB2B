# ==============================================================================
# Forja B2B — Development & Operations Makefile
# ==============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Cores para terminal
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

.PHONY: help
help: ## Mostra esta lista de ajuda com todos os comandos disponíveis
	@echo -e "$(CYAN)Forja B2B — Comandos de Desenvolvimento e Infraestrutura:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# Ambiente e Setup
# ------------------------------------------------------------------------------
.PHONY: env
env: ## Copia .env.example para .env caso não exista
	@if [ ! -f .env ]; then cp .env.example .env && echo "Arquivo .env criado com sucesso!"; else echo ".env já existe."; fi

# ------------------------------------------------------------------------------
# Docker Compose & Infraestrutura
# ------------------------------------------------------------------------------
.PHONY: up
up: env ## Inicia todos os serviços do docker-compose em background
	docker compose up -d

.PHONY: down
down: ## Para todos os serviços do docker-compose
	docker compose down

.PHONY: restart
restart: ## Reinicia todos os containers
	docker compose restart

.PHONY: build
build: ## Constrói as imagens dos containers sem cache
	docker compose build --no-cache

.PHONY: ps
ps: ## Exibe status e portas de todos os containers
	docker compose ps

.PHONY: logs
logs: ## Acompanha os logs de todos os containers em tempo real
	docker compose logs -f

.PHONY: logs-backend
logs-backend: ## Acompanha logs do serviço backend
	docker compose logs -f backend

.PHONY: logs-worker
logs-worker: ## Acompanha logs do Celery worker
	docker compose logs -f celery-worker

.PHONY: clean
clean: ## Para todos os serviços e remove volumes e redes órfãs
	docker compose down -v --remove-orphans

# ------------------------------------------------------------------------------
# Shell & Acesso aos Containers
# ------------------------------------------------------------------------------
.PHONY: shell-backend
shell-backend: ## Abre shell interativo no container backend
	docker compose exec backend bash

.PHONY: shell-db
shell-db: ## Conecta ao PostgreSQL com a role de aplicação (forja_app)
	docker compose exec postgres psql -U forja_app -d forja_db

.PHONY: shell-db-admin
shell-db-admin: ## Conecta ao PostgreSQL com a role de admin (forja_admin)
	docker compose exec postgres psql -U forja_admin -d forja_db

.PHONY: shell-redis
shell-redis: ## Abre CLI do Redis
	docker compose exec redis redis-cli

# ------------------------------------------------------------------------------
# Banco de Dados & Migrações
# ------------------------------------------------------------------------------
# Migrations exigem DDL e rodam com a role administrativa restrita
# (forja_admin) via DATABASE_ADMIN_URL, em container ONE-OFF. O container de
# runtime (backend) nunca recebe essa credencial. O alembic/env.py le
# DATABASE_ADMIN_URL e falha explicitamente sem ela.
.PHONY: migrate
migrate: ## Aplica migrações pendentes do Alembic (role admin, container one-off)
	docker compose run --rm --no-deps --env-file .env backend alembic upgrade head

.PHONY: migration-rollback
migration-rollback: ## Reverte a última migração do Alembic (role admin, one-off)
	docker compose run --rm --no-deps --env-file .env backend alembic downgrade -1

# ------------------------------------------------------------------------------
# Qualidade, Linting e Testes (Backend)
# ------------------------------------------------------------------------------
.PHONY: lint-backend
lint-backend: ## Executa o linter ruff no backend
	docker compose exec backend ruff check .

.PHONY: format-backend
format-backend: ## Aplica formatação automática com ruff no backend
	docker compose exec backend ruff format .

.PHONY: typecheck-backend
typecheck-backend: ## Executa checagem de tipos estáticos com mypy
	docker compose exec backend mypy .

.PHONY: arch-backend
arch-backend: ## Verifica contratos de arquitetura (import-linter)
	docker compose exec backend lint-imports

.PHONY: test-backend
test-backend: ## Executa a suíte de testes com pytest e cobertura
	docker compose exec backend pytest --cov=app --cov-report=term-missing

# ------------------------------------------------------------------------------
# Qualidade, Linting e Testes (Frontend)
# ------------------------------------------------------------------------------
.PHONY: lint-frontend
lint-frontend: ## Executa lint no frontend
	docker compose exec frontend npm run lint

.PHONY: typecheck-frontend
typecheck-frontend: ## Executa checagem de tipos TypeScript no frontend
	docker compose exec frontend npm run typecheck

.PHONY: test-frontend
test-frontend: ## Executa testes unitários no frontend
	docker compose exec frontend npm run test
