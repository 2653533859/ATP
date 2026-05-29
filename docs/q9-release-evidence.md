# Q9 Release Evidence

> Date: 2026-05-29
> Status: initial release-readiness evidence record.

This file records concrete evidence for the Q9 release-readiness baseline. It is intentionally separate from `docs/q9-release-checklist.md`: the checklist says what must be done, while this file records what was actually run and what still needs a Docker/staging environment.

## Local Evidence

### Q8/Q9 Focused Backend Regression

Command:

```bash
cd backend
python -m pytest \
  tests/api/test_ai_healing_iter5_api.py \
  tests/services/test_ai_healing_iter5.py \
  tests/api/test_ai_case_generation_api.py \
  tests/services/test_dataset_schema.py \
  tests/api/test_datasets_crud.py \
  tests/api/test_user_settings_api.py \
  tests/services/test_performance_summary.py \
  tests/services/test_performance_runner.py \
  tests/api/test_performance_api_behavior.py \
  tests/api/test_performance_api_static.py \
  tests/worker/test_celery_routing.py \
  tests/worker/test_deployment_ops_docs.py \
  tests/worker/test_performance_thin_slice_docs.py \
  tests/migrations/test_migration_policy.py \
  tests/migrations/test_zero_state_upgrade.py \
  -q
```

Result:

```text
83 passed, 3 warnings
```

### Q9 Release Readiness Contract Tests

Command:

```bash
cd backend
python -m pytest \
  tests/worker/test_q9_release_readiness.py \
  tests/worker/test_deployment_ops_docs.py \
  tests/worker/test_performance_thin_slice_docs.py \
  -q
```

Result:

```text
9 passed
```

### Frontend Type Check And Build

Commands:

```bash
cd frontend
npm run type-check
npm run build
```

Result:

```text
type-check passed
production build passed
```

Known build note:

```text
Circular chunk: ant-design-icons -> ant-design -> ant-design-icons.
```

This warning predates Q9 and does not block the release-readiness baseline.

### k6 Smoke Demo

Because the local environment does not have global Docker or k6, a portable `k6 v0.52.0` binary was downloaded to a temporary directory and used to run the Q8 smoke script.

Command shape:

```bash
TARGET_URL=https://test.k6.io/ k6 run --summary-export result.json examples/performance/k6-smoke.js
```

Result:

```text
k6 v0.52.0 smoke run completed
summary fixture updated at docs/fixtures/performance-k6-summary.sample.json
```

## Pending CI/Staging Evidence

These checks require GitHub Actions, Docker, Helm, or a staging namespace:

- Full backend regression from `.github/workflows/ci.yml`.
- Release readiness workflow `.github/workflows/release-readiness.yml`.
- Docker build for backend image.
- Docker build for worker image.
- `docker run --rm --entrypoint k6 atp-worker:release-readiness version`.
- Docker build for frontend image.
- `helm lint deploy/helm/atp/`.
- `helm upgrade --install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml --dry-run`.
- Staging smoke tests listed in `docs/q9-release-checklist.md`.

## Release Note Fields

Fill these before tagging:

| Field | Value |
|-------|-------|
| Git SHA | TBD |
| Backend image | TBD |
| Worker image | TBD |
| Frontend image | TBD |
| Backend full regression | TBD |
| Frontend type-check/build | local pass; CI TBD |
| Worker k6 version | portable local pass; Docker CI TBD |
| Alembic current/head | TBD |
| Helm dry-run | TBD |
| Staging smoke | TBD |
