PYTHON ?= python3
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; elif command -v docker-compose >/dev/null 2>&1; then printf 'docker-compose'; else printf 'docker compose'; fi)

.PHONY: setup dev dev-down infra-up infra-down migrate backend worker beat frontend lint format format-check mypy security-bandit security-pip-audit security-npm-audit security-deps pre-commit test test-backend test-backend-coverage test-integration test-frontend-build test-frontend-e2e scaffold-q12-evidence collect-q12-evidence validate-q12-evidence

setup:
	@if command -v brew >/dev/null 2>&1 && brew --prefix libpq >/dev/null 2>&1; then \
		LIBPQ_PREFIX=$$(brew --prefix libpq); \
		OPENSSL_PREFIX=$$(brew --prefix openssl@3 2>/dev/null || true); \
		READLINE_PREFIX=$$(brew --prefix readline 2>/dev/null || true); \
		KRB5_PREFIX=$$(brew --prefix krb5 2>/dev/null || true); \
		BREW_ARCH=$$(uname -m); \
		CPPFLAGS_EXTRA="-I$$LIBPQ_PREFIX/include"; \
		LDFLAGS_EXTRA="-L$$LIBPQ_PREFIX/lib"; \
		PKG_CONFIG_PATH_EXTRA="$$LIBPQ_PREFIX/lib/pkgconfig"; \
		for PREFIX in "$$OPENSSL_PREFIX" "$$READLINE_PREFIX" "$$KRB5_PREFIX"; do \
			if [ -n "$$PREFIX" ]; then \
				CPPFLAGS_EXTRA="$$CPPFLAGS_EXTRA -I$$PREFIX/include"; \
				LDFLAGS_EXTRA="$$LDFLAGS_EXTRA -L$$PREFIX/lib"; \
				PKG_CONFIG_PATH_EXTRA="$$PKG_CONFIG_PATH_EXTRA:$$PREFIX/lib/pkgconfig"; \
			fi; \
		done; \
		PATH="$$LIBPQ_PREFIX/bin:$$PATH" \
		CPPFLAGS="$$CPPFLAGS_EXTRA $$CPPFLAGS" \
		LDFLAGS="$$LDFLAGS_EXTRA $$LDFLAGS" \
		PKG_CONFIG_PATH="$$PKG_CONFIG_PATH_EXTRA:$$PKG_CONFIG_PATH" \
		ARCHFLAGS="$${ARCHFLAGS:--arch $$BREW_ARCH}" \
		$(PYTHON) -m pip install -r backend/requirements.txt; \
	else \
		$(PYTHON) -m pip install -r backend/requirements.txt; \
	fi
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

lint:
	$(PYTHON) -m ruff check backend/app backend/tests scripts/scaffold-q12-evidence.py scripts/validate-q12-evidence.py scripts/collect-q12-evidence.py

format:
	$(PYTHON) -m ruff format backend/app backend/tests scripts/scaffold-q12-evidence.py scripts/validate-q12-evidence.py scripts/collect-q12-evidence.py

format-check:
	$(PYTHON) -m ruff format --check backend/app backend/tests scripts/scaffold-q12-evidence.py scripts/validate-q12-evidence.py scripts/collect-q12-evidence.py

mypy:
	$(PYTHON) -m mypy

security-bandit:
	$(PYTHON) -m bandit -c pyproject.toml -r backend/app -ll

security-pip-audit:
	$(PYTHON) -m pip_audit -r backend/requirements.txt

security-npm-audit:
	cd frontend && npm audit --audit-level=moderate

security-deps: security-pip-audit security-npm-audit

pre-commit:
	PATH="$$(dirname "$(PYTHON)"):$$PATH" $(PYTHON) -m pre_commit run --all-files

test: test-backend test-frontend-build

test-backend:
	$(PYTHON) -m pytest backend/tests -q --ignore=backend/tests/integration

test-backend-coverage:
	$(PYTHON) -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=term-missing:skip-covered --cov-report=xml --cov-fail-under=70

test-integration:
	ATP_INTEGRATION_TESTS=1 $(PYTHON) -m pytest backend/tests/integration -m integration -v --tb=short

test-frontend-build:
	cd frontend && npm run type-check && npm run build

test-frontend-e2e:
	cd frontend && npm run e2e

scaffold-q12-evidence:
	@if [ -z "$(START)" ] || [ -z "$(END)" ] || [ -z "$(ANDROID_DATE)" ]; then \
		echo "Usage: make scaffold-q12-evidence START=YYYY-MM-DD END=YYYY-MM-DD ANDROID_DATE=YYYY-MM-DD [FORCE=1]"; \
		exit 2; \
	fi
	$(PYTHON) scripts/scaffold-q12-evidence.py --start "$(START)" --end "$(END)" --android-date "$(ANDROID_DATE)" $(if $(FORCE),--force,)

collect-q12-evidence:
	@if [ -z "$(START)" ] || [ -z "$(END)" ] || [ -z "$(ANDROID_DATE)" ] || [ -z "$(PROMETHEUS_URL)" ] || [ -z "$(API_BASE_URL)" ] || [ -z "$(TASK_ID)" ] || [ -z "$(DEVICE_SERIAL)" ] || [ -z "$(APP_PACKAGE)" ]; then \
		echo "Usage: make collect-q12-evidence START=YYYY-MM-DD END=YYYY-MM-DD ANDROID_DATE=YYYY-MM-DD PROMETHEUS_URL=http://... API_BASE_URL=http://... TASK_ID=... DEVICE_SERIAL=... APP_PACKAGE=... ATP_TOKEN=... [FORCE=1]"; \
		echo "       authenticate with ATP_TOKEN=... or ATP_USERNAME=... ATP_PASSWORD=..."; \
		exit 2; \
	fi
	@if [ -z "$(ATP_TOKEN)" ] && { [ -z "$(ATP_USERNAME)" ] || [ -z "$(ATP_PASSWORD)" ]; }; then \
		echo "Usage: make collect-q12-evidence ... ATP_TOKEN=... (or ATP_USERNAME=... ATP_PASSWORD=...)"; \
		exit 2; \
	fi
	$(PYTHON) scripts/collect-q12-evidence.py

validate-q12-evidence:
	@if [ -z "$(SLO)" ] || [ -z "$(ANDROID)" ] || [ -z "$(ACCEPTANCE)" ]; then \
		echo "Usage: make validate-q12-evidence SLO=docs/slo-history-YYYY-MM-DD-YYYY-MM-DD.md ANDROID=docs/android-device-rehearsal-YYYY-MM-DD.md ACCEPTANCE=docs/q12-acceptance-summary.md"; \
		exit 2; \
	fi
	$(PYTHON) scripts/validate-q12-evidence.py --slo "$(SLO)" --android "$(ANDROID)" --acceptance "$(ACCEPTANCE)"
