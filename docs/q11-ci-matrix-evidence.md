# Q11 CI Matrix Evidence

> Date: 2026-07-09
> Status: complete; local and GitHub runner matrix archived
> Scope: Q11-02 final CI matrix replay and evidence collection.

## Findings And Remediations

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

The first post-fix GitHub runner replay exposed CI/security gaps that were not visible in the initial local replay:

- `types-redis` was missing from dev dependencies, and Redis async close calls needed a typed helper because the installed stubs did not expose `Redis.aclose`.
- The Trivy action tag was invalid as `aquasecurity/trivy-action@0.33.1`; it was updated to `aquasecurity/trivy-action@v0.36.0`.
- Gitleaks scanned historical repository content and flagged old virtualenv files plus a documentation placeholder; `.gitleaks.toml` now scopes those historical/documentation allowances.
- Backend pytest expected the exact observability phrase `慢查询、队列积压、接口错误率与 MinIO 使用量`; `docs/observability-guide.md` now keeps the contract wording.
- Worker image scanning found Go stdlib CVEs in the old `grafana/k6:0.52.0` binary; the worker now copies k6 from `grafana/k6:2.1.0`.
- Frontend image scanning found Alpine package CVEs in `nginx:alpine`; the production stage now runs `apk upgrade --no-cache` before copying built assets.

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
Worker image: built; final post-security replay uses k6 v2.1.0.
Worker k6: k6 v2.1.0 (commit/83a87a41e2, go1.26.4, linux/arm64).
Frontend image: built, image id e6ddeb596f3f.
```

Warnings:

- Docker used the legacy builder locally.
- Frontend image build emitted npm deprecation warnings for `vue-i18n@9.14.5` and transitive `glob@10.5.0`.
- `npm audit` during frontend image build reported `found 0 vulnerabilities`.

### Trivy Remediation Local Replays

Worker image replay after the k6 refresh:

```bash
docker build -t atp-worker:q11-k6-fix -f backend/Dockerfile.worker backend/
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 image --severity HIGH,CRITICAL --ignore-unfixed \
  --exit-code 1 atp-worker:q11-k6-fix
```

Result:

```text
Worker k6: k6 v2.1.0 (commit/83a87a41e2, go1.26.4, linux/arm64).
Trivy worker image scan: 0 findings for high/critical fixed vulnerabilities.
```

Frontend image replay after the Alpine package refresh:

```bash
docker build -t atp-frontend:q11-os-fix frontend/
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 image --severity HIGH,CRITICAL --ignore-unfixed \
  --exit-code 1 atp-frontend:q11-os-fix
```

Result:

```text
Production stage upgraded libcrypto3, libssl3, libexpat, libxml2, and related Alpine packages.
Trivy frontend image scan: 0 findings for high/critical fixed vulnerabilities.
```

### GitHub Runner Final Matrix

Final commit under test:

```text
c1ef60cf0dde705423e9315a5f4e67ee235efd8c
```

Workflow results:

| Workflow | Event | Run | Result | Notes |
|----------|-------|-----|--------|-------|
| CI | push | https://github.com/2653533859/ATP/actions/runs/28998360621 | success | Backend lint, empty DB migration, backend pytest, frontend unit/type/build all passed |
| Security | push | https://github.com/2653533859/ATP/actions/runs/28998360606 | success | Dependency audit, Gitleaks, and Trivy backend/worker/frontend scans all passed |
| CI (integration) | workflow_dispatch | https://github.com/2653533859/ATP/actions/runs/28998366738 | success | Real-service integration job passed |
| Release readiness | workflow_dispatch | https://github.com/2653533859/ATP/actions/runs/28998368776 | success | Docker backend/worker/frontend build checks and checklist contract passed |
| CI (e2e) | workflow_dispatch | https://github.com/2653533859/ATP/actions/runs/28998370798 | success | Frontend Playwright E2E passed |

Notes:

- GitHub emitted Node.js 20 deprecation annotations for several actions; these are warnings only and did not fail any job.
- Dependabot PR runs visible near the same time are independent PR checks and are not part of the `main` Q11-02 evidence matrix.

## Next Action

Q11-02 is complete. Continue Q11-10: calibrate API availability and P95 windows in `docs/slo-guide.md` using observed traffic windows and explicit target rationale.
