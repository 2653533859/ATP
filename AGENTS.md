# Repository Guidelines

## Project Structure & Module Organization
This repository is currently in planning stage and contains `PRD.md` as the source of truth for scope and architecture. As implementation starts, keep a predictable layout:

- `backend/`: API services, task orchestration, and integrations (Celery/Redis, CI hooks).
- `frontend/`: web UI (case management, execution, reporting).
- `workers/`: execution runners for Web/API/Android tests.
- `tests/`: automated tests mirroring the runtime modules.
- `docs/`: design notes, ADRs, API contracts.

Keep module boundaries aligned with PRD domains (case management, scheduling, execution, reporting).

## Build, Test, and Development Commands
No build tooling is committed yet. Standardize early and document commands in the root `README.md`. Typical commands to support:

- `make setup`: install dependencies and local tooling.
- `make dev`: run backend/frontend/workers locally.
- `make test`: run full automated test suite.
- `make lint`: run formatters and linters.

If `make` is not used, provide equivalent `npm`, `poetry`, or `pytest` commands.

## Coding Style & Naming Conventions
- Use 4 spaces for Python, 2 spaces for YAML/JSON/Markdown indentation.
- Python: `snake_case` for functions/files, `PascalCase` for classes.
- TypeScript/JS (if added): `camelCase` for variables/functions, `PascalCase` for components.
- Prefer small, single-responsibility modules by feature area.

Adopt and enforce tooling once code exists (for example: `ruff` + `black` for Python, `eslint` + `prettier` for frontend).

## Testing Guidelines
- Place tests under `tests/` with feature-based subfolders (example: `tests/api/test_auth.py`).
- Name tests as `test_<behavior>.py` (or `*.spec.ts` for frontend).
- Cover critical flows from `PRD.md`: case execution, scheduling, reporting, and role permissions.
- Add regression tests for every bug fix.

## Commit & Pull Request Guidelines
This repo has no commit history yet; use Conventional Commits from day one:

- `feat: add case scheduling API`
- `fix: handle websocket reconnect timeout`
- `docs: update execution engine design`

PR requirements:
- Clear summary and scope.
- Linked issue or requirement section from `PRD.md`.
- Test evidence (`make test` output or screenshots for UI changes).
- Notes on config, migration, or rollout impact.

## Security & Configuration Tips
- Never commit secrets; use `.env.example` for required variables.
- Keep environment-specific endpoints and keys outside source control.
- Validate API inputs and apply role-based access checks at service boundaries.
