# Q11 CI Matrix Evidence

> Date: 2026-07-08
> Status: local matrix complete; GitHub runner archival pending
> Scope: Q11-02 final CI matrix replay and evidence collection.

## Current Finding

The first Q11-02 security replay exposed a new backend dependency audit failure:

```text
ecdsa 0.19.2  PYSEC-2026-1325
```

Root cause: `python-jose[cryptography]==3.5.0` still resolves the vulnerable `ecdsa` dependency, and the latest available `ecdsa` line has no fixed version yet.

Remediation:

- Replaced `python-jose[cryptography]==3.5.0` with `PyJWT[crypto]==2.13.0`.
- Migrated JWT encoding/decoding imports from `jose.jwt` to `jwt`.
- Migrated token error handling from `JWTError` to `InvalidTokenError`.
- Updated local API test stubs to use `jwt.InvalidTokenError`.
- Removed stale local venv packages: `python-jose`, `ecdsa`, `rsa`, and `pyasn1`.

## Evidence Collected

### Security

```bash
make security-pip-audit PYTHON=backend/.venv/bin/python
make security-npm-audit
```

Results:

```text
Backend pip-audit: No known vulnerabilities found.
Frontend npm audit: found 0 vulnerabilities.
```

Local environment check:

```bash
backend/.venv/bin/python -m pip check
backend/.venv/bin/python -m pip show python-jose ecdsa rsa pyasn1 PyJWT
```

Results:

```text
pip check: No broken requirements found.
python-jose / ecdsa / rsa / pyasn1: not found.
PyJWT: 2.13.0 installed.
```

### Backend API Regression

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/api/test_deps_project_access.py \
  backend/tests/api/test_project_access_isolation.py \
  backend/tests/api/test_project_role_boundaries.py -q
```

Result:

```text
37 passed
```

```bash
backend/.venv/bin/python -m pytest backend/tests/api -q \
  --ignore=backend/tests/api/test_project_access_isolation.py \
  --ignore=backend/tests/api/test_deps_project_access.py \
  --ignore=backend/tests/api/test_project_role_boundaries.py
```

Result:

```text
341 passed, 38 warnings
```

### Main CI Local Equivalents

```bash
make lint PYTHON=backend/.venv/bin/python
make format-check PYTHON=backend/.venv/bin/python
make mypy PYTHON=backend/.venv/bin/python
```

Results:

```text
Ruff lint: All checks passed.
Ruff format check: 337 files already formatted.
mypy: Success, no issues found in 76 source files.
```

Previously collected in the same Q11-02 replay:

```text
Frontend Vitest: 7 files / 18 tests passed.
Frontend type-check: passed.
Workflow YAML parse: passed for CI, security, integration, E2E, and release-readiness workflows.
Grafana dashboard JSON parse: passed.
```

### Integration Workflow

Initial GitHub runner status:

```text
Workflow: CI (integration)
Run: https://github.com/2653533859/ATP/actions/runs/28921392320
Head: main @ 1efc10ca5fef7c352d1a6c5a9cb5db5f4721e27a
Result: failed
```

Failure root cause:

```text
AttributeError: '_IncludedRouter' object has no attribute 'path'
```

The failure was caused by `FastAPIInstrumentor.instrument_app(app)` being installed even when `OTEL_EXPORTER_OTLP_ENDPOINT` was empty, and being installed before route registration despite the comment saying otherwise. The fix now installs the OTel FastAPI instrumentation only when an OTel endpoint is configured, and after all routers are included.

Local real-infra replay after the fix:

```bash
POSTGRES_HOST=localhost POSTGRES_PORT=55432 \
REDIS_HOST=localhost REDIS_PORT=6380 \
MINIO_HOST=localhost MINIO_PORT=19000 \
ATP_INTEGRATION_TESTS=1 PYTHONPATH=backend \
backend/.venv/bin/python -m pytest backend/tests/integration -m integration -v --tb=short --reruns 1 --reruns-delay 2
```

Result:

```text
10 passed
```

Python 3.12 target-runtime replay after the fix:

```bash
docker run --rm -v "$PWD":/workspace -w /workspace python:3.12-slim-bookworm bash -lc '... python -m pytest backend/tests/integration -m integration -v --tb=short --reruns 1 --reruns-delay 2'
```

Result:

```text
Python 3.12.13
10 passed
```

### E2E Workflow

GitHub runner status:

```text
Workflow: CI (e2e)
Run: https://github.com/2653533859/ATP/actions/runs/28921816190
Head: main @ 1efc10ca5fef7c352d1a6c5a9cb5db5f4721e27a
Result: success
```

Local replay:

```bash
npm --prefix frontend run e2e
```

Result:

```text
9 passed
```

Notes:

- The known Vite `ResizeObserver loop completed with undelivered notifications` warning still appears.
- `CaseList.vue` still logs a mock-data shape warning (`cases.value.filter is not a function`) during the case-list smoke path, but the current E2E assertion passes. This remains a runtime-polish follow-up under Q11-40 / Q11-41, not a Q11-02 blocker.

### Release Readiness Local Replay

Checklist contract:

```bash
test -f docs/q9-release-checklist.md
grep -q "alembic upgrade head" docs/q9-release-checklist.md
grep -q "helm upgrade --install" docs/q9-release-checklist.md
grep -q "performance" docs/q9-release-checklist.md
```

Result:

```text
passed
```

Docker build checks:

```bash
docker build -t atp-backend:q11-readiness backend/
docker build -t atp-worker:q11-readiness -f backend/Dockerfile.worker backend/
docker run --rm --entrypoint k6 atp-worker:q11-readiness version
docker build -t atp-frontend:q11-readiness frontend/
```

Results:

```text
Backend image: built, image id d2ae63764b4a.
Worker image: built, image id 212947161f85.
Worker k6: k6 v0.52.0 (commit/20f8febb5b, go1.22.4, linux/arm64).
Frontend image: built, image id e6ddeb596f3f.
```

Warnings:

- Docker used the legacy builder locally.
- Frontend image build emitted npm deprecation warnings for `vue-i18n@9.14.5` and transitive `glob@10.5.0`.
- `npm audit` during frontend image build reported `found 0 vulnerabilities`.

## Pending Evidence

Q11-02 is not complete until post-fix GitHub workflow-level results are archived:

- Main CI: GitHub runner result for lint, migration, backend coverage, frontend unit/type/build.
- Security workflow: GitHub runner result for Gitleaks, pip-audit, npm audit, and Trivy image scans after the PyJWT migration.
- Integration workflow: GitHub runner result after the OTel instrumentation fix.
- Release-readiness workflow: GitHub runner result for Docker backend / worker / frontend image build and checklist contract.

## Next Action

Push or otherwise run the current local patch on GitHub, then archive successful main CI, security, integration, and release-readiness workflow links here before marking Q11-02 complete.
