PYTHON ?= python3
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; elif command -v docker-compose >/dev/null 2>&1; then printf 'docker-compose'; else printf 'docker compose'; fi)
# ruff 检查的独立脚本清单：Makefile 的 lint / format / format-check、ci.yml 的两个
# ruff step、.pre-commit-config.yaml 的两个 ruff 钩子必须覆盖同一批脚本，
# backend/tests/test_quality_gate_consistency.py 守住这五处不漂移。
LINT_SCRIPTS = scripts/scaffold-q12-evidence.py scripts/validate-q12-evidence.py scripts/collect-q12-evidence.py scripts/pytest-standalone-sweep.py scripts/validate-deployment-readiness.py scripts/validate-android-worker-config.py scripts/performance-gate.py scripts/performance-environment-smoke.py scripts/performance_acceptance_target.py scripts/notification-channel-smoke.py scripts/notification-channel-acceptance.py scripts/web-recording-worker-smoke.py scripts/minio-dataset-acceptance.py
# $(PYTHON) 既可能是裸命令（默认 python3）也可能是路径（backend/.venv/bin/python）。
# 对裸命令直接 dirname 会得到 "."，把当前目录塞进 PATH 首位——既没把目标解释器的
# bin 目录加进来，又引入 CWD-on-PATH 隐患。先用 command -v 解析成绝对路径；
# 解析不到时保持 PATH 原样，绝不产生空目录项（空项同样等价于当前目录）。
PYTHON_BIN_DIR := $(shell p="$$(command -v $(PYTHON) 2>/dev/null)"; [ -n "$$p" ] && dirname "$$p" || true)
PYTHON_PATH := $(if $(PYTHON_BIN_DIR),$(PYTHON_BIN_DIR):$(PATH),$(PATH))

.PHONY: setup dev dev-down infra-up infra-down migrate backend worker beat frontend lint format format-check mypy security-bandit security-pip-audit security-npm-audit security-deps pre-commit test test-backend test-backend-coverage test-backend-standalone test-integration test-frontend-build test-frontend-e2e scaffold-q12-evidence collect-q12-evidence validate-q12-evidence validate-deployment-readiness validate-android-worker-config performance-environment-smoke web-recording-worker-smoke

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
	$(PYTHON) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci
	@# 放在最后且不致命：钩子环境构建失败（例如 gitleaks 需要 Go 工具链而本机没有）
	@# 不应该连带让依赖安装半途中断。失败时明确告知，而不是静默跳过。
	@PATH="$(PYTHON_PATH)" $(PYTHON) -m pre_commit install --hook-type pre-commit --hook-type pre-push \
		|| echo "warning: pre-commit install 失败，本地 git 钩子未启用；见 docs/ci-workflows.md「门禁强制力现状」"

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
	cd backend && celery -A app.worker.celery_app worker --loglevel=info -Q $${CELERY_QUEUES:-default,android,mobile_special,ios,ai,maintenance,performance}

beat:
	cd backend && celery -A app.worker.celery_app beat --loglevel=info

frontend:
	cd frontend && npm run dev

lint:
	$(PYTHON) -m ruff check backend/app backend/tests $(LINT_SCRIPTS)

format:
	$(PYTHON) -m ruff format backend/app backend/tests $(LINT_SCRIPTS)

format-check:
	$(PYTHON) -m ruff format --check backend/app backend/tests $(LINT_SCRIPTS)

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
	PATH="$(PYTHON_PATH)" $(PYTHON) -m pre_commit run --all-files

test: test-backend test-frontend-build

test-backend:
	$(PYTHON) -m pytest backend/tests -q --ignore=backend/tests/integration

test-backend-coverage:
	$(PYTHON) -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=term-missing:skip-covered --cov-report=xml --cov-fail-under=82

test-backend-standalone:
	$(PYTHON) scripts/pytest-standalone-sweep.py --jobs $(or $(JOBS),4)

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

validate-deployment-readiness:
	$(PYTHON) scripts/validate-deployment-readiness.py $(ARGS)

validate-android-worker-config:
	@if [ -z "$(BACKEND_ENV)" ] || [ -z "$(AGENT_ENV)" ]; then \
		echo "Usage: make validate-android-worker-config BACKEND_ENV=... AGENT_ENV=... [REPORT=...]"; \
		exit 2; \
	fi
	$(PYTHON) scripts/validate-android-worker-config.py --backend-env "$(BACKEND_ENV)" --agent-env "$(AGENT_ENV)" $(if $(REPORT),--report "$(REPORT)",)

performance-environment-smoke:
	@if [ -z "$(ARGS)" ]; then \
		echo "Usage: make performance-environment-smoke ARGS='--api-base-url ... --deployment ... --target ...'"; \
		exit 2; \
	fi
	$(PYTHON) scripts/performance-environment-smoke.py $(ARGS)

web-recording-worker-smoke:
	@if [ -z "$(ARGS)" ]; then \
		echo "Usage: make web-recording-worker-smoke ARGS='--api-base-url ... --project-id ... [--run-recording --start-url ...]'"; \
		exit 2; \
	fi
	$(PYTHON) scripts/web-recording-worker-smoke.py $(ARGS)
