PYTHON ?= python3
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; elif command -v docker-compose >/dev/null 2>&1; then printf 'docker-compose'; else printf 'docker compose'; fi)

.PHONY: setup dev dev-down infra-up infra-down migrate backend worker beat frontend test test-backend test-integration test-frontend-build test-frontend-e2e

setup:
	$(PYTHON) -m pip install -r backend/requirements.txt
	cd frontend && npm ci

dev:
	$(COMPOSE) up --build

dev-down:
	$(COMPOSE) down

infra-up:
	$(COMPOSE) -f docker-compose.dev.yml up -d

infra-down:
	$(COMPOSE) -f docker-compose.dev.yml down

migrate:
	cd backend && alembic upgrade head

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && celery -A app.worker.celery_app worker --loglevel=info -Q $${CELERY_QUEUES:-default,mobile_special,ai,maintenance,performance}

beat:
	cd backend && celery -A app.worker.celery_app beat --loglevel=info

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend-build

test-backend:
	$(PYTHON) -m pytest backend/tests -q --ignore=backend/tests/integration

test-integration:
	ATP_INTEGRATION_TESTS=1 $(PYTHON) -m pytest backend/tests/integration -m integration -v --tb=short

test-frontend-build:
	cd frontend && npm run type-check && npm run build

test-frontend-e2e:
	cd frontend && npm run e2e
