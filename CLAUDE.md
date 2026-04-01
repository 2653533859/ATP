# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ATP (Automated Testing Platform) — a team-oriented automated testing platform covering API testing, Web UI testing, Android UI testing, with suite orchestration, scheduled plans, execution reports, and notification integrations.

## Tech Stack

- **Frontend**: Vue 3 + TypeScript + Vite + Ant Design Vue 4.x + Pinia + Vue Router
- **Backend**: FastAPI 0.115 + SQLAlchemy 2.x async (asyncpg) + Alembic + Pydantic Settings
- **Task Queue**: Celery 5.x + Redis (DB0=broker, DB1=result, DB2=pubsub)
- **Database**: PostgreSQL 16
- **Object Storage**: MinIO (screenshots, reports, scripts, APKs)
- **Executors**: httpx, Playwright, uiautomator2, grpcio, websockets — all via pytest + pytest-json-report
- **Real-time**: Redis Pub/Sub → WebSocket (channel pattern: `atp:run:{run_id}`)
- **Deployment**: Docker Compose (nginx reverse proxy)
- **Python**: 3.12

## Development Commands

### Frontend (`cd frontend`)

```bash
npm install          # install dependencies
npm run dev          # dev server at http://localhost:5173
npm run type-check   # vue-tsc --noEmit
npm run build        # vue-tsc && vite build
```

### Backend (`cd backend`)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000    # API server
celery -A app.worker.celery_app worker --loglevel=info   # worker
celery -A app.worker.celery_app beat --loglevel=info     # scheduler
```

### Type Checking

When running type checks after modifications, specify the subdirectory:
- Frontend: `cd frontend && npm run type-check`
- Backend: uses Python type hints with Pydantic; no separate type-check command

### Tests

```bash
python -m pytest backend/tests -q                    # all backend tests
python -m pytest backend/tests/api -q                # API tests only
python -m pytest backend/tests/api/test_auth.py -q   # single test file
```

Test subdirectories: `api/`, `services/`, `worker/`, `migrations/`, `plans/`, `frontend/`.

### Infrastructure (dev mode)

```bash
docker compose -f docker-compose.dev.yml up -d   # postgres + redis + minio only
```

### Full stack (production)

```bash
docker compose up --build        # all 7 services
docker compose -f docker-compose.app.yml up --build -d  # app only (external infra)
```

## Architecture

### Backend Structure (`backend/app/`)

- `main.py` — FastAPI entry: lifespan creates tables + bootstraps admin, registers routes
- `core/` — config (pydantic-settings), database (async engine), security (JWT/password), redis client
- `models/` — SQLAlchemy models: User, Project, Module (self-referential tree), TestCase, TestRun, StepResult, Environment, Suite, Plan, Device, Notification, Mock, etc.
- `schemas/` — Pydantic request/response schemas
- `api/v1/` — route modules registered in `router.py` (prefix `/api/v1`). WebSocket endpoint at `/ws/runs/{run_id}`
- `api/deps.py` — `get_current_user()`, `require_roles()`, `require_admin` dependency injection
- `services/` — business logic: ADB device sync, notifications, audit, bug reporter
- `models/global_variable.py` — `GlobalVariable` model (scope: global/project, Fernet encryption for secret values)
- `api/v1/global_variables.py` — REST endpoints for global variable CRUD
- `worker/celery_app.py` — Celery instance
- `worker/tasks.py` — `run_test_case` task dispatches to executors
- `worker/executors/` — one executor per test type: `api_executor`, `web_executor`, `web_lowcode_executor`, `android_executor`, `android_lowcode_executor`, `graphql_executor`, `grpc_executor`, `websocket_executor`, `android_perf_executor`, `android_stability_executor`, `android_fluency_executor`

### Frontend Structure (`frontend/src/`)

- `api/http.ts` — axios with JWT interceptor + 401 redirect
- `api/index.ts` — all API method wrappers
- `router/index.ts` — route definitions + auth guard
- `stores/auth.ts` — Pinia auth store (token/user/login/logout)
- `utils/websocket.ts` — WebSocket wrapper with auto-reconnect
- `layouts/MainLayout.vue` — sidebar + header + RouterView
- `views/` — page components organized by feature: auth, project, case, run, suite, plan, device, apk, mock, dashboard, system, mobile-special
- `views/system/GlobalVariableLibrary.vue` — 全局变量库（项目级/全局变量，加密存储，查看/隐藏）
- `components/common/` — shared components (ModuleTree, KvEditor, CaseFormDrawer, etc.)
- Path alias: `@` maps to `src/`

### Execution Flow

```
POST /api/v1/cases/{id}/run → create TestRun(pending) → Celery task
→ Worker: status=running → Redis publish → executor runs steps
→ each step: request → assert → extract vars → write StepResult → Redis publish
→ final: status=passed/failed → Redis publish completed
→ Frontend: WebSocket listens on atp:run:{run_id}, fallback GET on close
```

### Key Design Decisions

- **Redis DB separation**: DB0=Celery broker, DB1=Celery results, DB2=Pub/Sub events
- **WebSocket auth**: via URL query `?token=xxx` (browser WS API doesn't support custom headers)
- **Alembic migration**: uses sync psycopg2 URL (Alembic doesn't support asyncpg); `env.py` converts automatically
- **Database init**: `create_all` in lifespan as fallback + Alembic for incremental migrations
- **TestCase config**: stored as JSON column to accommodate varying structures across test types
- **Pub/Sub failures**: `_safe_publish_run_event` swallows exceptions — real-time push is best-effort

### Docker Compose Services

Full stack (`docker-compose.yml`): frontend, backend, worker, beat, flower, postgres, redis, minio
- Nginx in frontend container reverse-proxies `/api/` → backend:8000, `/ws/` → backend WebSocket
- `docker-compose.dev.yml`: postgres + redis + minio only (for local dev)
- `docker-compose.app.yml`: app services only (when infra is external)

## Android 专项测试中心

### Backend Structure

- **Models**: `backend/app/models/mobile_special.py` — `MobileSpecialTask`, `MobileSpecialRun`, `MobileMetricSample`, `MobileIncident`, `MobileRunArtifact`
- **Enums**: `TaskType` (performance/stability/fluency), `SourceType`, `DeviceScopeType`, `RunStatus`, `TriggerType`, `IncidentType`, `MetricType`, `ArtifactType`
- **Schemas**: `backend/app/schemas/mobile_special.py` — Pydantic request/response schemas
- **Executors**: `backend/app/worker/executors/android_perf_executor.py`, `android_stability_executor.py`, `android_fluency_executor.py`
- **Tasks**: `backend/app/worker/tasks_mobile_special.py` — Celery task dispatch + schedule checker
- **API**: `backend/app/api/v1/mobile_special.py` — REST endpoints (tasks CRUD, runs, samples, incidents, artifacts, export CSV/JSON, statistics)
- **ADB Client**: `backend/app/services/mobile_special/adb_client.py` — ADB command builders
- **Parsers**: `backend/app/services/mobile_special/parsers.py` — `parse_meminfo`, `parse_gfxinfo_framestats`, `parse_cpuinfo`, `parse_batterystats`, `parse_logcat_crash/anr`
- **Collectors**: `backend/app/services/mobile_special/collectors.py` — `SamplingSession`, `PeriodicSampler`

### Frontend Structure

- `SpecialTaskListView.vue` — 专项任务列表页（项目/类型筛选、创建/编辑抽屉、触发执行）
- `ReportCenterView.vue` — 报告中心（KPI卡片、趋势图、运行记录表、导出CSV/JSON）
- `ReportDetailView.vue` — 报告详情（任务信息、KPI卡片、指标趋势图、异常事件表、报告文件表）

### Task Config JSON Structure

- **performance**: `{interval_seconds, duration_seconds, auto_start}`
- **stability**: `{interval_seconds, duration_seconds, auto_start, operation_interval_ms}`
- **fluency**: `{interval_seconds, duration_seconds, auto_start, stages: [{name, action, coords?}]}`

## Conventions

- Python: `snake_case` functions/files, `PascalCase` classes, 4-space indent
- TypeScript/Vue: `camelCase` variables/functions, `PascalCase` components, 2-space indent
- Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)
- API prefix: `/api/v1/`
- Config via `.env` file, loaded by pydantic-settings (`backend/app/core/config.py`)
- Default admin: username/password from `FIRST_ADMIN_*` env vars, auto-created on first boot
