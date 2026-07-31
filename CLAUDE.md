# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ATP (Automated Testing Platform) — a team-oriented automated testing platform covering API testing (HTTP/GraphQL/gRPC/WebSocket), Web UI testing, Android UI testing and Android special-purpose testing (performance/stability/fluency), plus suite orchestration, scheduled plans, execution reports, HTTP load testing, AI healing/case generation, and notification integrations.

Progress and per-module completion is tracked in `Task.md`; product scope in `PRD.md`. `docs/` holds design notes, runbooks and quarterly plans (`docs/optimization-roadmap-2026-q*.md`, `docs/implementation-plan-2026-Q*.md`).

## Tech Stack

- **Frontend**: Vue 3 + TypeScript + Vite + Ant Design Vue 4.x + Pinia + Vue Router + vue-i18n + ECharts + Monaco
- **Backend**: FastAPI + SQLAlchemy 2.x async (asyncpg) + Alembic + pydantic-settings, Python 3.12
- **Task Queue**: Celery 5.x + Redis (DB0=broker, DB1=result, DB2=pubsub)
- **Storage**: PostgreSQL 16, MinIO (screenshots, reports, scripts, APKs, k6 scripts)
- **Executors**: httpx, Playwright, uiautomator2, grpcio, websockets, k6 — via pytest + pytest-json-report
- **Observability**: structlog, Prometheus (`/metrics`), OpenTelemetry → Jaeger
- **Deployment**: Docker Compose (nginx reverse proxy), Helm chart under `deploy/helm/atp`

## Development Commands

The `Makefile` is the canonical entry point — it wraps the exact commands CI runs. Override the interpreter with `make PYTHON=/path/to/python ...` and the compose binary with `make COMPOSE="docker compose" ...`.

Python 3.12 is required. The repo convention is a gitignored venv at `backend/.venv`, which is what the quarterly evidence docs invoke (`make lint PYTHON=backend/.venv/bin/python`, `backend/.venv/Scripts/python.exe` on Windows).

```bash
make setup            # pip install backend deps + npm ci
make dev / dev-down   # full stack via docker compose
make infra-up         # postgres + redis + minio only (docker-compose.dev.yml)
make migrate          # cd backend && alembic upgrade head
make backend          # uvicorn app.main:app --reload --port 8000
make worker           # celery worker -Q default,mobile_special,ai,maintenance,performance
make beat             # celery beat
make frontend         # vite dev server at :5173
```

### Verification (run these after changes)

```bash
make test-backend            # pytest backend/tests -q, excluding integration
make test-frontend-build     # cd frontend && npm run type-check && npm run build
make lint                    # ruff check backend/app backend/tests scripts/*.py
make format-check            # ruff format --check
make mypy                    # mypy over core/ schemas/ services/ only (progressive baseline)
make pre-commit              # all pre-commit hooks over all files
```

Frontend type-check must be run from `frontend/` (`npm run type-check`). Backend has no single type-check command — `make mypy` covers only the three baselined packages.

### Targeted tests

```bash
python -m pytest backend/tests/api/test_auth.py -q          # single file
python -m pytest backend/tests -q -k "suite and not plan"   # by expression
cd frontend && npm run test                                  # vitest unit tests
cd frontend && npx vitest run src/path/to/Foo.spec.ts        # single vitest file
make test-frontend-e2e                                       # playwright (mock dev server)
make test-integration                                        # needs real PG/Redis/MinIO
```

Test roots: `backend/tests/{api,services,worker,migrations,plans,integration,frontend}`, `frontend/src/**/*.spec.ts` (vitest), `frontend/e2e/*.spec.ts` (playwright).

### Security scans

```bash
make security-bandit     # bandit -c pyproject.toml -r backend/app -ll
make security-deps       # pip-audit + npm audit
```

## Architecture

### Request → execution flow

```
POST /api/v1/cases/{id}/run → TestRun(pending) → Celery task on `default` queue
→ worker: status=running → publish to Redis DB2 → executor runs steps
→ per step: request → assert → extract vars → StepResult row → publish
→ final: passed/failed → publish completed → artifacts to MinIO
→ frontend: WebSocket on atp:run:{run_id}; falls back to GET polling on close
```
`docs/backend-request-flow.md` traces this end to end; `docs/worker-lifecycle.md` covers worker/queue behaviour.

### Backend (`backend/app/`)

- `main.py` — lifespan: `setup_logging` → `verify_alembic_head_or_warn` → OTel init → optional `create_all` → `ensure_bucket` → bootstrap admin. Middleware order matters: CORS → CSRF → Trace, then `enable_metrics_for(app)` **before** `include_router` so the instrumentator sees every endpoint, then `FastAPIInstrumentor` **after** routing so spans carry path templates.
- `core/` — `config.py` (pydantic-settings, all env vars), `database.py` (async engine), `security.py` (JWT/password), `encryption.py` (Fernet for secrets), `redis_client.py`, `minio_client.py`, `rate_limit.py` (slowapi), `cache_decorator.py`, `metrics.py`, `otel.py`/`tracing.py`, `migrations_check.py`, `slow_query.py`
- `middleware/` — `csrf.py`, `trace.py`
- `models/` — SQLAlchemy models; `bootstrap.py:load_all_models()` must import every model module for `create_all`/Alembic autogenerate to see it — add new model modules there
- `api/v1/router.py` — registers all routers under `/api/v1`; `ws.py` mounts `/ws/runs/{run_id}`; `mock_server.py` mounts `/mock/`. `cases/` is split into `crud/runs/batch/workflow/common`
- `api/deps.py` — `get_current_user()`, `require_roles()`, `require_admin`/`require_engineer`
- `services/` — business logic: `adb_service`/`adb_resilience`/`device_sync`, `notifier`, `audit`, `bug_reporter`, `ai_healing*`/`ai_case/`/`ai_governance`, `failure_diagnosis`, `performance`, `dataset_schema`, `storage_cleanup`/`storage_alerts`/`run_retention`, `mobile_special/` (adb_client, parsers, collectors)
- `worker/` — `celery_app.py` (queues, routes, beat schedule), `tasks*.py` split by domain, `dispatch.py`/`case_dispatch.py`/`async_runner.py`, `executors/` (one module per test type)
- `mock_main.py` — standalone Mock server entry (see `docs/mock-standalone.md`)

### Celery queues

Routed in `celery_app.py`; a worker must subscribe explicitly (`-Q`):

| Queue | Tasks |
| --- | --- |
| `default` | `run_test_case`, `run_test_suite`, `run_test_plan`, `check_cron_plans` |
| `mobile_special` | Android special tasks, `scan_adb_devices` (real-device constrained) |
| `ai` | LLM calls (`diagnose_*`, `aggregate_healing_feedback`) — isolated for rate limiting/degradation |
| `performance` | `run_performance_test` (k6) |
| `maintenance` | cleanup, storage/dashboard alerts, postgres backups |

Global limits: `task_time_limit=1800`, soft `1500`, `worker_max_tasks_per_child=50`, `prefetch=1`. Details in `docs/celery-queues.md`.

### Frontend (`frontend/src/`)

- `api/http.ts` — axios + JWT interceptor + 401 redirect; `api/index.ts` — all endpoint wrappers
- `stores/auth.ts` (Pinia), `router/index.ts` (routes + auth guard), `utils/websocket.ts` (auto-reconnect wrapper)
- `views/` by feature: auth, project, case, run, suite, plan, device, apk, mock, dashboard, audit, system, mobile-special
- `locales/` — vue-i18n; new user-facing strings go through i18n keys, not literals (migration is partial — match the surrounding page)
- Path alias `@` → `src/`; components auto-imported via `unplugin-vue-components` (`components.d.ts` is generated)
- `vite.config.ts` uses `manualChunks` to split ant-design-vue / echarts / icons / vuedraggable / monaco; routes are lazy-loaded

## Key Design Decisions

- **Schema is Alembic-owned.** `APP_AUTO_CREATE_TABLES` defaults off; startup only *warns* when the DB is not at head (`verify_alembic_head_or_warn`). Always add a migration for model changes — see `docs/alembic-migration-guidelines.md` and `docs/migrations.md`. Alembic uses a sync psycopg2 URL; `env.py` converts from the asyncpg URL automatically.
- **Redis DB separation**: DB0 broker, DB1 results, DB2 pub/sub.
- **WebSocket auth via `?token=`** — the browser WS API cannot send custom headers.
- **Pub/sub is best-effort**: `_safe_publish_run_event` swallows exceptions; correctness must not depend on a delivered event.
- **TestCase/task config is a JSON column** to absorb per-test-type shape differences. Android special-task configs: performance `{interval_seconds, duration_seconds, auto_start}`, stability adds `operation_interval_ms`, fluency adds `stages: [{name, action, coords?}]`.
- **Secrets encrypted at rest** with Fernet (global variables, notification/bug-tracker/LLM credentials).

## Testing Conventions

- The root `backend/tests/conftest.py` stubs optional heavy deps (`app.core.minio_client`, `app.core.redis_client`, `app.api.deps`, `app.core.database`) using a *fill-missing-only* strategy — it never overwrites attributes a test file hard-set. Do not add blanket `sys.modules` overwrites; extend the conftest defaults instead. Celery is deliberately **not** stubbed there so `pytest.importorskip("celery")` stays honest.
- `ATP_INTEGRATION_TESTS=1` disables all stubs; integration fixtures live in `backend/tests/integration/conftest.py` and tests carry the `integration` marker.
- `pytest_pycollect_makeitem` skips `Test*`-named application classes (`TestCase`, `TestPlan`, …) so they can be imported under their real names. `PytestCollectionWarning` is an error — keep collection warning-free.
- The `flaky` marker requires an entry in `docs/flaky-governance.md` with cause, evidence and exit criteria.
- Session fixtures `repo_root` / `repo_file` exist for contract tests that read repo files.
- Coverage gate: `make test-backend-coverage` enforces `--cov-fail-under=70`.

## Conventions

- Python: `snake_case` functions/files, `PascalCase` classes, 4-space indent, ruff line-length 120, double quotes
- TypeScript/Vue: `camelCase` variables/functions, `PascalCase` components, 2-space indent
- Comments and user-facing copy in this repo are predominantly Chinese — match the file you are editing
- Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)
- Config via `.env` (see `.env.example`), loaded by `backend/app/core/config.py`. Default admin comes from `FIRST_ADMIN_*`, created on first boot
- CI (`.github/workflows/`): `ci.yml` (empty-DB migration check, backend pytest, frontend type-check+build) on push/PR to main; `security.yml`, `test-integration.yml`, `test-e2e.yml`, `release-readiness.yml` are nightly/manual — see `docs/ci-workflows.md`
