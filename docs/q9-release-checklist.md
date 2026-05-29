# Q9 Release Checklist

> Status: Q9 Phase 1 release-readiness baseline.
> Scope: staging dry-run and release candidate validation after Q8 feature completion.

## 1. Required Gates

Run these checks before tagging a release candidate:

```bash
cd backend
python -m pytest tests -q

cd ../frontend
npm run type-check
npm run build
```

Docker-enabled CI or a release workstation must also verify image builds:

```bash
docker build -t registry.local/atp/backend:<tag> backend/
docker build -t registry.local/atp/worker:<tag> -f backend/Dockerfile.worker backend/
docker run --rm --entrypoint k6 registry.local/atp/worker:<tag> version
docker build -t registry.local/atp/frontend:<tag> frontend/
```

The worker `k6 version` check is mandatory because Q8 performance runs depend on the k6 binary copied from `grafana/k6:0.52.0`.

## 2. Migration Gate

Before switching traffic:

```bash
cd backend
alembic upgrade head
alembic current
alembic heads
```

Acceptance:

- `alembic current` matches the single Alembic head.
- A zero-state upgrade has passed in CI via `tests/migrations/test_zero_state_upgrade.py`.
- The Helm migrate Job or Compose migrate service completes before backend and worker traffic starts.

## 3. Staging Dry-Run

Prepare values:

```bash
cp deploy/helm/atp/values.yaml my-values.yaml
```

Confirm at minimum:

- Image tags point to the release candidate.
- `config.CELERY_QUEUES` includes `default,mobile_special,ai,maintenance,performance`.
- `worker.queues` includes `performance`, or a separate performance worker release is prepared.
- PostgreSQL, Redis, and MinIO endpoints point to staging services.
- Secrets are injected externally and are not committed in values files.

Render and dry-run:

```bash
helm lint deploy/helm/atp/
helm upgrade --install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml --dry-run
```

Apply to staging:

```bash
helm upgrade --install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml
```

## 4. Smoke Tests

After staging deploy:

- Login succeeds.
- Project list loads.
- One API case can be executed and produces a run detail.
- Dataset upload preview works for valid and invalid rows.
- AI case generation opens, handles validation errors, and can save an edited draft in a test project.
- AI healing iter5 preview can be requested from a failed run fixture.
- Performance Center can upload `examples/performance/k6-smoke.js`, create a test definition, trigger a run, and open raw summary.

## 5. Queue And Worker Checks

Confirm worker separation for long-running queues:

```bash
celery -A app.worker.celery_app inspect active_queues
```

Expected queues:

- `default`
- `mobile_special`
- `ai`
- `maintenance`
- `performance`

Production recommendation:

- Run `performance` workers with low concurrency and resource limits.
- Run `ai` workers separately when LLM traffic grows.
- Keep `beat` single-replica with `Recreate` semantics.

## 6. Rollback Plan

Before production release:

- Confirm latest PostgreSQL, Redis, and MinIO backup objects exist.
- Confirm restore has been tested in a non-production namespace.
- Record current Helm revision:

```bash
helm history atp -n atp-production
```

Rollback command:

```bash
helm rollback atp <REVISION> -n atp-production
```

Data migrations that delete data, rename fields, or change enum semantics must not be downgraded in production without a restored backup validation.

## 7. Release Evidence

Record evidence in `docs/q9-release-evidence.md`, then copy the final values into the release note:

- Git SHA and image tags.
- Backend full regression result.
- Frontend type-check/build result.
- Docker build result and worker `k6 version` output.
- Alembic current/head output.
- Helm dry-run output.
- Staging smoke-test result.
