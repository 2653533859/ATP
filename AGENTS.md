# Repository Guidelines

## Project Structure & Module Organization

The platform is implemented and running; `PRD.md` defines product scope, `Task.md` tracks per-module completion, and `docs/` holds design notes, runbooks and quarterly plans. Actual layout:

- `backend/` — FastAPI app (`app/api`, `app/core`, `app/models`, `app/schemas`, `app/services`, `app/middleware`), Celery workers and executors (`app/worker`), Alembic migrations (`alembic/`), tests (`tests/`).
- `frontend/` — Vue 3 + TypeScript UI (`src/views` by feature, `src/api`, `src/stores`, `src/locales`), Playwright specs in `e2e/`.
- `docker/`, `docker-compose*.yml`, `deploy/` — container resources, compose variants and the Helm chart.
- `scripts/` — operational scripts (postgres backup/restore, Android network doctor, evidence tooling, Windows local run).
- `docs/` — architecture, migrations, CI, SLO, security and quarterly acceptance documents.

Keep module boundaries aligned with the PRD domains (case management, scheduling, execution, reporting); see `docs/domain-boundaries.md`.

Executors live in `backend/app/worker/executors/`, one module per test type — there is no top-level `workers/` directory, and backend tests live under `backend/tests/`, not a root `tests/`.

## Build, Test, and Development Commands

`Makefile` is the canonical entry point and wraps exactly what CI runs. Override the interpreter with `make PYTHON=/path/to/python ...` and the compose binary with `make COMPOSE="docker compose" ...`.

- `make setup` — install backend requirements and run `npm ci`.
- `make dev` / `make dev-down` — full stack via Docker Compose.
- `make infra-up` / `make infra-down` — postgres + redis + minio only.
- `make migrate` — `alembic upgrade head`.
- `make backend` / `make worker` / `make beat` / `make frontend` — run each process locally.
- `make test` — `test-backend` + `test-frontend-build`.
- `make lint` / `make format` / `make format-check` / `make mypy` — Python quality gates.
- `make pre-commit` — run all hooks over all files.

Python 3.12 is required. Node 20+ for the frontend.

## Coding Style & Naming Conventions

- Python: 4 spaces, `snake_case` for functions/files, `PascalCase` for classes. Enforced by `ruff` (line length 120, double quotes, `target-version = py312`); `backend/alembic/versions` is excluded. `mypy` runs on a progressive baseline — `app/core`, `app/schemas`, `app/services` only.
- TypeScript/Vue: 2 spaces, `camelCase` for variables/functions, `PascalCase` for components. There is no eslint/prettier config — `vue-tsc --noEmit` plus `vite build` are the gates.
- YAML/JSON/Markdown: 2-space indentation.
- Comments and user-facing copy are predominantly Chinese; match the file being edited. New frontend strings go through `vue-i18n` keys where the surrounding page already does.
- Prefer small, single-responsibility modules by feature area.

## Testing Guidelines

- Backend tests live in `backend/tests/{api,services,worker,migrations,plans,integration,frontend}`, named `test_<behavior>.py`. Frontend unit tests are `*.spec.ts` under `frontend/src` (Vitest); end-to-end specs are `frontend/e2e/*.spec.ts` (Playwright).
- `make test-backend` skips `backend/tests/integration`. Integration tests need real PostgreSQL/Redis/MinIO and run via `make test-integration` (`ATP_INTEGRATION_TESTS=1`, `integration` marker).
- The root `backend/tests/conftest.py` stubs optional heavy dependencies with a fill-missing-only strategy — extend its defaults rather than adding blanket `sys.modules` overwrites. `PytestCollectionWarning` is escalated to an error, so keep collection clean.
- The `flaky` marker requires an entry in `docs/flaky-governance.md` with cause, evidence and exit criteria.
- Coverage gate: `make test-backend-coverage` enforces `--cov-fail-under=70`.
- Cover critical flows from `PRD.md`: case execution, scheduling, reporting, role permissions. Add a regression test for every bug fix.

## Commit & Pull Request Guidelines

The repository follows Conventional Commits:

- `feat: add case scheduling API`
- `fix: handle websocket reconnect timeout`
- `docs: update execution engine design`

PR requirements:

- Clear summary and scope, linked issue or `PRD.md` requirement section.
- Test evidence (`make test` output, or screenshots for UI changes).
- Notes on config, migration or rollout impact. Model changes require an Alembic migration — see `docs/alembic-migration-guidelines.md`.
- CI (`.github/workflows/ci.yml`) runs empty-database migration verification, backend pytest, and frontend type-check + build on push/PR to `main`. Nightly/manual workflows cover integration, E2E, security scanning and release readiness (`docs/ci-workflows.md`).

## Security & Configuration Tips

- Never commit secrets; `.env.example` lists the required variables. Gitleaks runs both as a pre-commit hook and in CI, with the allowlist in `.gitleaks.toml`.
- Keep environment-specific endpoints and keys outside source control. Secrets stored in the database (global variables, notification/bug-tracker/LLM credentials) are encrypted with Fernet.
- Validate API inputs and apply role-based access checks at service boundaries via `app/api/deps.py` (`get_current_user`, `require_roles`, `require_admin`).
- Dependency and code scanning: `make security-bandit`, `make security-deps` (pip-audit + npm audit), plus Trivy and Dependabot in CI — see `docs/security-scanning.md`.
