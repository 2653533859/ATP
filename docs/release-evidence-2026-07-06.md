# ATP Release Evidence - 2026-07-06

> Scope: Python 3.14 local setup compatibility, Python 3.12 deployment baseline verification, review fixes, and release documentation sync.

## Change Groups

### 1. Environment And Dependency Compatibility

- `backend/requirements.txt`
  - Keeps the Python 3.12 deployment baseline on the existing dependency pins.
  - Adds Python 3.14-only pins for SQLAlchemy, grpcio/grpcio-tools, Playwright, and OpenTelemetry packages that need newer compatible releases.
- `Makefile`
  - Detects Homebrew `libpq` and exports `pg_config` through `PATH`.
  - Adds Homebrew include/library/pkg-config paths for `libpq`, `openssl@3`, `readline`, and `krb5` when present.
  - Uses the local Homebrew architecture from `uname -m` when `ARCHFLAGS` is not already set.

### 2. Runtime Compatibility Fixes

- `backend/app/services/device_sync.py`
  - Uses a typed SQLAlchemy `literal()` for the PostgreSQL enum value in the upsert `CASE` expression so SQLAlchemy 2.0.51 compiles the statement correctly on Python 3.14.

### 3. Test Compatibility Fixes

- `backend/tests/api/test_ai_llm_configs_api.py`
  - Updates the expected commit count for the update path that also writes an audit log.
- `backend/tests/worker/test_async_runner.py`
  - Patches the simulated Windows event loop policy through `asyncio.__dict__`, avoiding Python 3.14 module `__getattr__` behavior.
- `backend/tests/worker/test_suite_execution_config.py`
  - Stubs flaky-result marking in suite execution tests that intentionally replace the case model surface.

### 4. Progress And Memory Sync

- `Task.md`
- `MEMORY.md`
- `CONTEXT.md`
- `docs/optimization-roadmap-2026.md`

These files now reflect the latest environment matrix, frontend build verification, remaining PR/release tasks, and Q10 startup sequence.

## Verification Evidence

### Python 3.14 Local Backend

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration
```

Result:

```text
823 passed, 41 warnings
```

Additional checks:

```bash
backend/.venv/bin/python -m pip check
git diff --check
```

Results:

```text
No broken requirements found.
git diff --check passed.
```

### Python 3.12 Docker Target Runtime

Command:

```bash
docker run --rm -v "$PWD":/app -w /app python:3.12-slim-bookworm sh -lc 'python --version && apt-get update >/dev/null && apt-get install -y --no-install-recommends gcc libpq-dev >/dev/null && pip install --no-cache-dir -r backend/requirements.txt >/tmp/pip.log && python -m pytest backend/tests -q --ignore=backend/tests/integration'
```

Result:

```text
Python 3.12.13
823 passed, 41 warnings
```

### Frontend Quality

Commands:

```bash
cd frontend && npm run type-check
cd frontend && npm run build
```

Result:

```text
type-check passed.
build passed.
```

Known warning:

```text
Circular chunk: ant-design-icons -> ant-design -> ant-design-icons
```

### Targeted Regression Set

Commands:

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/services/test_device_sync.py \
  backend/tests/api/test_ai_llm_configs_api.py \
  backend/tests/worker/test_async_runner.py \
  backend/tests/worker/test_suite_execution_config.py \
  -q
```

Result:

```text
18 passed in 0.90s
```

### Q10 Minimal Lint Gate

Command:

```bash
make lint PYTHON=backend/.venv/bin/python
```

Result:

```text
All checks passed.
```

### Q10 Dependency Audit Baseline

Commands:

```bash
backend/.venv/bin/python -m pip_audit -r backend/requirements.txt -f json -o /tmp/atp-pip-audit.json
npm --prefix frontend audit --audit-level=moderate --json > /tmp/atp-npm-audit.json
```

Results:

```text
Backend pip-audit: 6 vulnerable packages, 25 vulnerability records.
Frontend npm audit: 16 vulnerability records (9 moderate, 5 high, 2 critical).
```

Notes:

- Backend upgrade review: `python-jose`, `python-multipart`, `pytest`, `jinja2`, `cryptography`, `starlette`.
- Frontend upgrade review: `vitest` / `@vitest/coverage-v8`, `vite`, `axios`, `echarts`, `vue-i18n`, plus transitive `lodash` / `form-data`.
- Blocking CI for dependency audits is deferred until high/critical upgrades are tested.

### Q10 Dependency Audit Remediation

Follow-up date: 2026-07-08

Commands:

```bash
make security-pip-audit PYTHON=backend/.venv/bin/python
make security-npm-audit
```

Results:

```text
Backend pip-audit: No known vulnerabilities found.
Frontend npm audit: found 0 vulnerabilities.
```

Key upgrades:

- Backend: FastAPI/Starlette, python-multipart, pytest/pytest-asyncio, Jinja2, cryptography, prometheus-fastapi-instrumentator; Q11 replay later migrated JWT handling from python-jose to PyJWT.
- Frontend: Vite/Vitest, Axios, ECharts, vue-i18n, jsdom, vue-tsc, plus npm overrides for `brace-expansion`, `form-data`, `lodash`, and `lodash-es`.

### Q11-02 CI Matrix Replay Started

Follow-up date: 2026-07-08

Changes:

- Replayed local security and main-CI equivalent gates.
- Fixed a new `pip-audit` failure by replacing `python-jose[cryptography]==3.5.0` with `PyJWT[crypto]==2.13.0`.
- Migrated token handling from `jose.JWTError` to `jwt.InvalidTokenError`.
- Recorded detailed Q11-02 evidence in `docs/q11-ci-matrix-evidence.md`.

Primary evidence:

```text
Backend pip-audit: No known vulnerabilities found.
Frontend npm audit: found 0 vulnerabilities.
Targeted project access JWT/API tests: 37 passed.
Remaining API tests: 341 passed, 38 warnings.
Ruff lint / format-check / mypy: passed.
```

Follow-up evidence:

```text
GitHub CI (e2e): success, run 28921816190.
GitHub CI (integration): failed, run 28921392320; root cause was unconditional OTel FastAPI instrumentation when endpoint was empty.
Local integration after OTel fix: 10 passed.
Docker Python 3.12 integration after OTel fix: 10 passed.
Local E2E replay: 9 passed.
Release-readiness initial local replay: backend / worker / frontend images built; worker k6 v0.52.0 was verified before the later security refresh to k6 v2.1.0; checklist contract passed.
```

### Q11-02 CI Matrix Replay Completed

Follow-up date: 2026-07-09

Changes:

- Archived final GitHub runner evidence in `docs/q11-ci-matrix-evidence.md`.
- Fixed post-replay CI/security issues: missing `types-redis`, Redis async close typing, invalid Trivy action tag, scoped Gitleaks historical allowlists, observability static-doc contract wording, worker k6 image CVEs, and frontend Alpine runtime package CVEs.
- Refreshed worker k6 from `grafana/k6:0.52.0` to `grafana/k6:2.1.0`.
- Added `apk upgrade --no-cache` to the frontend runtime stage so the `nginx:alpine` production image picks up fixed Alpine packages before Trivy scanning.

Primary evidence:

```text
Final commit under test: c1ef60cf0dde705423e9315a5f4e67ee235efd8c
GitHub CI: success, run 28998360621.
GitHub Security: success, run 28998360606.
GitHub CI (integration): success, run 28998366738.
GitHub Release readiness: success, run 28998368776.
GitHub CI (e2e): success, run 28998370798.
Local worker Trivy replay: 0 high/critical fixed findings after k6 v2.1.0 refresh.
Local frontend Trivy replay: 0 high/critical fixed findings after Alpine package upgrade.
```

### Q11-10 SLO Production Calibration

Follow-up date: 2026-07-09

Changes:

- Updated `docs/slo-guide.md` from a Q10 thin-slice note into the active ATP SLO guide.
- Recorded the current evidence window as local / CI / release-readiness / short-lived staging-style validation, with no continuous production Prometheus history available in this repository snapshot.
- Kept API availability `>= 99.5%`, API P95 latency `<= 2s`, and run success rate `>= 95%` as pre-production guardrails.
- Added production adoption windows: 7 consecutive days for initial production calibration and 14 consecutive days for stable production calibration.
- Deferred paging-grade alerts, monthly error-budget reporting, release-blocking SLO policy, and endpoint-class SLOs until production data exists.

Primary evidence:

```text
Q11 roadmap: Q11-10 marked complete.
SLO guide: observed traffic window, target rationale, production calibration checklist, and deferred decisions recorded.
Next action: Q11-11 SLO triage runbook.
```

### Q11-11 SLO Triage Runbook

Follow-up date: 2026-07-09

Changes:

- Added a SLO triage runbook to `docs/slo-guide.md`.
- Defined first-five-minute checks for breached SLO panels.
- Mapped API availability, API P95 latency, run success rate, and API error-budget exhaustion to first checks and escalation criteria.
- Added a lightweight incident record template for SLO incidents.

Primary evidence:

```text
Q11 roadmap: Q11-11 marked complete.
SLO guide: triage runbook covers availability, latency, run success, and error-budget breaches.
Next action: Q11-12 alert threshold decision.
```

### Q11-12 SLO Alert Threshold Decision

Follow-up date: 2026-07-09

Changes:

- Added the Q11-12 alert threshold decision to `docs/slo-guide.md`.
- Explicitly deferred paging-grade SLO alerts until continuous production Prometheus history exists.
- Kept the existing platform health alerts in `deploy/grafana/alerts/atp-alerts.yaml` as the active alert layer.
- Recorded draft SLO alert candidates for API availability, API P95 latency, API error-budget exhaustion, and run success rate.

Primary evidence:

```text
Q11 roadmap: Q11-12 marked complete.
SLO guide: paging-grade SLO alerts deferred; draft thresholds and enablement criteria recorded.
Next action: Q11-20 frontend coverage growth.
```

### Q11-20 Frontend Navigation Utility Tests

Follow-up date: 2026-07-09

Changes:

- Added `frontend/src/utils/caseNavigation.ts` for project/module/case navigation helpers.
- Added `frontend/src/utils/caseNavigation.spec.ts`.
- Reused the helpers in `ProjectList.vue` and `CaseList.vue`.

Primary evidence:

```text
Vitest: 8 files / 22 tests passed.
Type-check: passed.
Frontend build: passed.
Q11 roadmap: Q11-20 marked complete.
Follow-up completed by Q11-21 suite / plan list helper tests.
```

### Q11-21 Suite And Plan Helper Tests

Follow-up date: 2026-07-09

Changes:

- Added `frontend/src/utils/suiteList.ts` and `frontend/src/utils/suiteList.spec.ts`.
- Added `frontend/src/utils/planList.ts` and `frontend/src/utils/planList.spec.ts`.
- Reused the helpers in `SuiteList.vue` and `PlanList.vue`.

Primary evidence:

```text
Vitest: 10 files / 30 tests passed.
Type-check: passed.
Frontend build: passed.
Backend static frontend checks: 10 passed.
Q11 roadmap: Q11-21 marked complete.
Next action: Q11-22 system page smoke component test.
```

### Q10 Format And Security Automation

Follow-up date: 2026-07-08

Commands:

```bash
backend/.venv/bin/python -m ruff format backend/app backend/tests
make format-check PYTHON=backend/.venv/bin/python
make pre-commit PYTHON=backend/.venv/bin/python
```

Results:

```text
ruff format: 217 files reformatted, 115 left unchanged.
ruff format --check: 332 files already formatted.
pre-commit: passed, including backend ruff format check.
```

Security automation:

- `.github/workflows/security.yml`: Gitleaks, pip-audit, npm high/critical audit, Trivy image scans.
- `.github/dependabot.yml`: pip, npm, Docker, and GitHub Actions weekly update checks.

### Python 3.12 Target Runtime Recheck

Follow-up date: 2026-07-08

Command:

```bash
docker run --rm -v "$PWD":/workspace -w /workspace python:3.12-slim-bookworm bash -lc 'apt-get update && apt-get install -y gcc libpq-dev && python -m pip install --upgrade pip && python -m pip install -r backend/requirements.txt && python -m pytest backend/tests -q --ignore=backend/tests/integration'
```

Result:

```text
823 passed, 41 warnings
```

Note: the first dependency-resolution attempt exposed the old Python 3.12 `pytest-playwright==0.5.2` pin requiring `pytest<9`; the runtime pin is now unified with the Python 3.14 path at `pytest-playwright==0.8.0` / `playwright==1.61.0`.

### Q10 Coverage Gate

Command:

```bash
make test-backend-coverage PYTHON=backend/.venv/bin/python
```

Result:

```text
823 passed, 41 warnings
Total coverage: 53.47%
Required coverage: 52%
```

### Frontend Vitest Gate

Commands:

```bash
npm --prefix frontend run test
npm --prefix frontend run test:coverage
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Results:

```text
Vitest: 18 passed
Vitest coverage: passed, full-source baseline 1.8%
type-check: passed
build: passed with the known Ant Design circular chunk warning
```

### Pre-Commit Gate

Command:

```bash
make pre-commit PYTHON=backend/.venv/bin/python
```

Result:

```text
check yaml: passed
fix end of files: passed
trim trailing whitespace: passed
backend ruff check: passed
backend mypy: passed
frontend vitest: passed
```

### Mypy Gate

Command:

```bash
make mypy PYTHON=backend/.venv/bin/python
```

Result:

```text
Success: no issues found in 76 source files
```

### Bandit SAST Gate

Command:

```bash
make security-bandit PYTHON=backend/.venv/bin/python
```

Result:

```text
No medium or high issues identified.
Low findings visible: 63
```

### Q10 Phase 5 Integration Expansion

Follow-up date: 2026-07-08

Changes:

- Added `backend/tests/integration/test_suite_plan_flow.py` for the suite-run / plan-trigger chain.
- Added `backend/tests/integration/test_notification_bug_flow.py` for notification config masking/test-send failure handling and bug tracker connection/dedup/create/status/manual-link flows.
- Added `backend/alembic/versions/20260529_0039_add_suite_config.py` after the first real-infra run exposed the missing `test_suites.config` column.
- Added `backend/tests/migrations/test_suite_config_migration.py` to keep that Alembic coverage visible.
- Added `backend/alembic/versions/20260529_0040_convert_bug_tracker_type_enum.py` after the real-infra bug flow exposed `bug_trackers.tracker_type` as varchar in pure Alembic-created databases.
- Added `backend/tests/migrations/test_bug_tracker_type_migration.py` to keep that enum conversion covered.
- Updated integration project creation payloads with explicit unique `project_code` values so the suite can be rerun against the same database.

Environment:

```text
Postgres: localhost:55432
Redis: localhost:6380
MinIO: localhost:19000
```

Commands:

```bash
cd backend && alembic upgrade head
ATP_INTEGRATION_TESTS=1 backend/.venv/bin/python -m pytest backend/tests/integration -m integration -v --tb=short
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration
```

Result:

```text
alembic upgrade head: passed on a fresh Postgres database
backend/tests/integration: 10 passed
backend/tests/integration repeat run against the same database: 10 passed
backend/tests excluding integration: 825 passed, 41 warnings
```

### Q10 Phase 5 Frontend E2E Expansion

Follow-up date: 2026-07-08

Changes:

- Added suite / plan mock data and API fixtures for Playwright.
- Added `frontend/e2e/suite-plan.spec.ts` for suite load -> trigger run -> history drawer and plan load -> manual run -> execution history.
- Added a shared `/api/v1/runs` mock to keep dashboard login setup independent from the real backend proxy.

Commands:

```bash
npm --prefix frontend run type-check
npm --prefix frontend run test
npm --prefix frontend run e2e -- suite-plan.spec.ts
npm --prefix frontend run e2e
```

Results:

```text
type-check: passed
Vitest: 18 passed
suite-plan E2E: 2 passed
full Playwright E2E: 9 passed
```

Note: the full E2E run logged a Vite client `ResizeObserver loop completed with undelivered notifications` warning during one test, but all 9 Playwright tests passed.

### Q10 Phase 5 SLO Thin Slice

Follow-up date: 2026-07-08

Changes:

- Added `atp_run_outcomes_total{entity_type,status}` for terminal case / suite / plan outcomes.
- Recorded run outcome metrics in standalone case, parameterized case, suite, and plan worker paths.
- Added `docs/slo-guide.md` with API availability, API P95 latency, run success rate, and API error-budget PromQL.
- Expanded `docker/grafana/dashboards/atp-overview.json` with four SLO panels.
- Updated `docs/observability-guide.md` with the new metric and panel list.

Commands:

```bash
python3 -m json.tool docker/grafana/dashboards/atp-overview.json >/tmp/atp-overview.json
backend/.venv/bin/python -m ruff check backend/app/core/metrics.py backend/app/worker/tasks.py backend/tests/worker/test_run_outcome_metrics.py
backend/.venv/bin/python -m pytest \
  backend/tests/worker/test_run_outcome_metrics.py \
  backend/tests/worker/test_dataset_parameterized.py \
  backend/tests/worker/test_plan_execution_config.py \
  backend/tests/worker/test_suite_execution_config.py \
  -q
```

Results:

```text
Grafana dashboard JSON: valid
ruff: All checks passed
worker SLO/flow regression: 23 passed, 3 warnings
```

### Q10 Phase 5 Flaky Governance

Follow-up date: 2026-07-08

Changes:

- Added `pytest-rerunfailures==16.4` to backend dev dependencies.
- Registered a project `flaky` pytest marker with documentation requirements.
- Enabled one bounded retry for scheduled/manual backend integration CI: `--reruns 1 --reruns-delay 2`.
- Documented Playwright CI retry boundaries and local zero-retry expectations.
- Added `docs/flaky-governance.md` and updated `docs/ci-workflows.md`.

Commands:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m pytest --markers | rg -n "integration|flaky|reruns"
backend/.venv/bin/python -m pytest backend/tests/worker/test_run_outcome_metrics.py -q --reruns 1 --reruns-delay 1
backend/.venv/bin/python - <<'PY'
import yaml
for path in ['.github/workflows/test-integration.yml', '.github/workflows/test-e2e.yml', '.github/workflows/ci.yml']:
    with open(path, encoding='utf-8') as f:
        yaml.safe_load(f)
    print(f'{path}: ok')
PY
```

Results:

```text
pytest markers: integration, project flaky, and rerunfailures flaky marker visible
rerun option smoke test: 2 passed
workflow YAML parse: ok
```

### Q10 Acceptance Closure

Follow-up date: 2026-07-08

Changes:

- Added `docs/q10-acceptance-summary.md`.
- Updated `README.md` with the Q10 quality and stability closure index.
- Synced Task / MEMORY / CONTEXT with the final Q10 acceptance direction.

Primary evidence:

```text
Q10 acceptance summary: present
README Q10 index: present
Task/MEMORY/CONTEXT: synced
```

### Q11-01 Release Notes And Rollback Plan

Follow-up date: 2026-07-08

Changes:

- Added `docs/q10-release-notes.md`.
- Captured Q10 change groups, risk notes, rollback plan, and release checklist.
- Updated Q11 roadmap and memory docs to point the next step at CI matrix evidence collection.

Primary evidence:

```text
Q10 release notes: present
Risk notes: present
Rollback plan: present
Q11 roadmap: Q11-01 marked complete
```

## Recommended PR Description

### Summary

- Fix Python 3.14 backend setup when `psycopg2-binary==2.9.10` needs a local `pg_config`.
- Preserve the Python 3.12 deployment baseline with environment-marker dependency pins.
- Harden the local `make setup` path for Homebrew `libpq` and optional build dependencies.
- Update compatibility tests and sync release progress documentation.

### Test Evidence

- Python 3.14 backend full regression: `823 passed`.
- Docker Python 3.12 backend full regression: `823 passed`.
- Frontend `type-check`: passed.
- Frontend `build`: passed with the known Ant Design circular chunk warning.
- `pip check`: passed.
- `git diff --check`: passed.

### Risk Notes

- Python 3.12 keeps the existing dependency versions through `python_version < "3.14"` markers.
- Python 3.14 uses newer grpc/OpenTelemetry/Playwright/SQLAlchemy pins to avoid build and runtime incompatibilities.
- Local `make setup` now depends on Homebrew `libpq` only when it is available; non-Homebrew environments keep the existing pip install path.

## Remaining Follow-Up

- Decide whether this should ship as one PR or split into:
  - dependency/setup compatibility,
  - Python 3.14 test/runtime fixes,
  - progress/release documentation.
- Continue with PR split/review packaging, keeping the Ruff format baseline separate from behavioral changes where possible.
