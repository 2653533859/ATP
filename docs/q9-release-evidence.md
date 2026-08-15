# Q9/Q18 Release Evidence

> Date: 2026-08-12
> Status: historical Q9 record retained; the Q18 extension below is the active release-evidence section.

This file records concrete evidence for the Q9 release-readiness baseline. It is intentionally separate from `docs/q9-release-checklist.md`: the checklist says what must be done, while this file records what was actually run and what still needs a Docker/staging environment.

## Windows/Performance Evidence Refresh (2026-08-15)

This refresh supersedes the older 2026-08-13 reachability snapshot for the current running profile. It records fresh Windows-side evidence and does not close the real Android-device or Linux/Kubernetes Worker gates.

| Gate | Command / evidence | Result |
|---|---|---|
| Windows Worker doctor | `scripts/windows-android-worker.ps1 doctor -EnvFile .env` | passed; Python/Celery/Redis/ADB and PostgreSQL/Redis/MinIO endpoint checks passed; no Android device online |
| Remote dependency TCP | Windows `Test-NetConnection` to `172.31.27.133:5432`, `:6379`, `:9000` | all reachable |
| Live dependency API | authenticated `scripts/windows-local-smoke.ps1` | PostgreSQL, Redis and MinIO `status=ok` |
| Windows API/Web smoke | `scripts/windows-local-smoke.ps1 -SkipPlaywright -SkipReports` | passed; login, project read, Web Worker status, file upload/cleanup passed |
| Browser matrix | same smoke command with local Chromium | passed; no failed requests or error responses |
| Performance API/Prometheus | `scripts/performance-environment-smoke.py` with API and Prometheus URLs | passed; API health, k6/Locust/gRPC executors and Prometheus readiness/query passed |
| Performance node/readiness | `perf-node-local-01` with `performance.worker-local` | passed; node online, executor/allowlist/target/Prometheus checks passed |
| Performance real smoke | Locust test `1`, 1 user / 3 seconds | passed; run `1`, 957 requests, error rate 0, 2 `performance-worker` samples |
| Performance cancellation | Locust test `1`, temporary 60-second duration | passed; run `2` entered `cancelled` after the 2-second cancellation request |
| Android Worker registry | authenticated `GET /api/v1/devices/workers` | passed; `android-win-HPS` online with `mobile_special` and `adb/android` capabilities |
| Android single-device acceptance | `scripts/windows-android-acceptance.ps1` | blocked; `adb devices -l` has no authorized online device; report is local-only at `.local-run/android-acceptance-20260815.json` |

The smoke reports under `.local-run/` are local runtime artifacts and contain no credentials. They are not treated as a substitute for external device, Worker, TLS target, cancellation or multi-node evidence.

## Linux Docker Performance Evidence (2026-08-15)

The Linux MCP connection to `172.31.27.133` was restored. The isolated Docker Compose acceptance stack passed health checks for PostgreSQL, Redis, MinIO, Backend, the dedicated performance Worker, Prometheus metrics and the HTTP/gRPC targets.

| Gate | Evidence | Result |
|---|---|---|
| Locust smoke | `docs/evidence/performance-linux-locust-smoke-2026-08-15.json` | passed; run `1`, 36 iterations, error rate 0, node `worker-a` / queue `performance.worker-a` |
| gRPC TLS smoke | `docs/evidence/performance-linux-grpc-smoke-2026-08-15.json` | passed; run `2`, 5 iterations, TLS certificate/SNI validation passed, error rate 0 |
| Cancellation | `docs/evidence/performance-linux-locust-cancel-2026-08-15.json` | passed; run `3` changed from running to `cancelled` after 2 seconds |

This closes only the Linux Docker Compose single-node acceptance slice. Kubernetes rollout, real multi-node sharding, production Prometheus, external notification, backup/restore and Android-device gates remain open.

## Web Worker Control Plane and Backup/Restore Drill (2026-08-15)

The following checks were completed after restoring the isolated Linux acceptance stack and exercising the Windows Worker mode. They are dated, redacted evidence only; they do not close Kubernetes or production disaster-recovery gates.

| Gate | Evidence | Result |
|---|---|---|
| Redis blocking-read timeout fix | `backend/tests/core/test_database_connection_timeout.py` and `backend/tests/services/test_web_recording_transport.py` | passed; `18 passed`; API command and Worker heartbeat clients now use read timeouts longer than their blocking wait windows |
| Windows Web Recording Worker | `docs/evidence/web-recording-worker-local-2026-08-15.json` | passed; Worker registered/available, Chromium recording started, 2 steps captured, PNG screenshot returned, recording stopped |
| PostgreSQL backup/restore | `docs/evidence/backup-restore-linux-docker-2026-08-15.json` | passed in the isolated Docker stack; temporary database restored and migration row verified, then removed |
| MinIO object mirror/restore | `docs/evidence/backup-restore-linux-docker-2026-08-15.json` | passed in the isolated Docker stack; source/restored SHA-256 matched and temporary objects were removed |

The backup/restore drill does not prove production retention, MinIO lifecycle configuration, scheduled backups, cross-host recovery, Kubernetes rollout or external notification delivery. Those gates remain open.

## MinIO Lifecycle Deployment Contract (2026-08-15)

| Gate | Evidence | Result |
|---|---|---|
| Explicit reconciler | `backend/app/ops_minio_lifecycle.py` | implemented; execution requires `MINIO_LIFECYCLE_APPLY=true` and preserves rules outside the `atp-managed-*` namespace |
| Helm deployment hook | `deploy/helm/atp/templates/minio-lifecycle-job.yaml` | implemented but default disabled; uses the ATP backend image and external Secret values |
| Docker Compose operator profile | `docker-compose.yml` profile `storage-lifecycle` | implemented but default disabled; can be run explicitly with `docker compose --profile storage-lifecycle run --rm minio-lifecycle` |
| Lifecycle safety regression | `backend/tests/services/test_minio_lifecycle.py` and deployment contract tests | passed; `23 passed`; scoped-prefix and rule-preservation checks included |

This is a deployment/code contract, not production acceptance. Before enabling it, export and review the target bucket rules, verify database references and backup prefixes, and record the approved retention period.

## External Notification Readiness Audit (2026-08-15)

The target `atp` database currently has no notification configurations and no
delivery records. This is recorded in
`docs/evidence/notification-readiness-audit-2026-08-15.json`; real SMTP, WeCom,
and DingTalk delivery remains an external acceptance gate and was not simulated
with fabricated credentials.

## MinIO Target Audit (2026-08-15)

The read-only audit of `172.31.27.133` found no lifecycle rules on the `atp`
bucket. Versioning, object locking, and replication were also not configured.
The bucket contains referenced APK, mobile-run, performance, screenshot, trace,
and web-file objects, while the database has active retention policies for
screenshots, reports, APKs, and scripts. The sanitized snapshot is recorded in
`docs/evidence/minio-lifecycle-audit-2026-08-15.json`; no expiration rule was
enabled as part of this audit.

## Q18 Local Gate Snapshot (2026-08-12)

This section records repository-local evidence only. It does not close the real MinIO, external notification, Android device, Linux/Kubernetes, Web Worker or macOS/iOS gates.

| Gate | Command / evidence | Result |
|---|---|---|
| Backend non-integration | `backend\.venv\Scripts\python.exe -m pytest backend/tests -q --ignore=backend/tests/integration` | `1944 passed` |
| Standalone isolation | `backend\.venv\Scripts\python.exe scripts/pytest-standalone-sweep.py --jobs 4` | `264 passed, 0 failed` |
| Frontend | `npm --prefix frontend run test` | `45 files / 183 tests passed` |
| Frontend type/build | `npm --prefix frontend run type-check` and `npm --prefix frontend run build` | passed |
| Python quality | Ruff check/format and mypy progressive scope | passed |
| Performance notification formatting | `backend/tests/services/test_notifier.py` and `test_performance_notifications.py` | `12 passed` |
| Performance early-terminal notification | `backend/tests/worker/test_tasks_performance.py` and `backend/tests/services/test_performance_notifications.py` | `14 passed` |
| Diff hygiene | `git diff --check` | passed |

## Q18 Local Gate Continuation (2026-08-13)

This continuation records the current repository-local evidence after notification reliability, delivery history, retention audit, error redaction and test-isolation updates. It does not close the real notification-provider or external-worker gates.

| Gate | Command / evidence | Result |
|---|---|---|
| Backend non-integration | `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests -q --ignore=backend/tests/integration` | `2012 passed` |
| Backend coverage gate | `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-fail-under=82` | `82.13%, 2012 passed` |
| Standalone isolation | `backend\\.venv\\Scripts\\python.exe scripts/pytest-standalone-sweep.py` by test domain | `267 files passed, 0 failed` |
| Frontend | `npm --prefix frontend run test` | `46 files / 195 tests passed` |
| Frontend type/build | `npm --prefix frontend run type-check` and `npm --prefix frontend run build` | passed |
| Python quality | Ruff check/format and mypy progressive scope | passed |
| Notification smoke contract | `backend/tests/scripts/test_notification_channel_smoke.py` | `3 passed` |
| Notification config response masking | `backend/tests/api/test_notifications.py` | `14 passed`; create/update responses mask sensitive fields |
| Notification config validation | `backend/tests/api/test_notifications.py`, `backend/tests/services/test_notifier.py` | `32 passed`; empty delivery targets rejected |
| Web Worker heartbeat resilience | `backend/tests/services/test_web_recording_transport.py`, `backend/tests/api/test_web_recordings.py` and deployment contract tests | `55 passed` |
| Web Worker acceptance contract | `backend/tests/scripts/test_web_recording_worker_smoke.py` and quality-gate consistency tests | `14 passed` |
| Diff hygiene | `git diff --check` | passed |

The run-retention preview now returns `estimated_objects_sampled` and the UI labels the object count when it is based on the first cleanup batch. This keeps the preview bounded while making the estimate scope explicit.
The per-project retention table now exposes all four run categories and the corresponding project-scoped object estimate, matching the service cleanup scope.
The per-project preview route now applies `RunRetentionPerProjectOut`, including the `global_` → `global` response alias, so OpenAPI and runtime response validation match the frontend contract.

## Q18 External Gate Check (2026-08-13)

This is an external-environment status check, not a passing acceptance result.

| Gate | Check | Result |
|---|---|---|
| Linux target read-only connectivity | MCP system overview for the configured Linux target | blocked: transport closed; no external evidence collected |

The Linux/Kubernetes, external notification-provider, Web Worker, MinIO and Android gates remain open until the target connection is restored and their dated, redacted evidence is collected.

The notification smoke command is ready for target environments, but no provider credentials or external delivery evidence is stored in this repository. The external gate remains open until the report is paired with SMTP/WeCom/DingTalk provider-side evidence.

## Windows Current Profile Check (2026-08-13)

| Check | Result |
|---|---|
| Runtime profile | root `.env`, PostgreSQL/Redis/MinIO configured for `172.31.27.133` |
| Authenticated application checks | login, `/auth/me`, project list and `/web-recordings/workers` passed after restart |
| Dependency reachability | PostgreSQL `5432` reachable; Redis `6379` and MinIO `9000` unreachable from Windows |
| Acceptance status | incomplete; restore Redis/MinIO reachability before full Windows smoke |

| Windows/UI check | Evidence | Result |
|---|---|---|
| Browser Mock E2E | `npm run e2e -- --reporter=line` | `10 passed` after project selector isolation fix |
| Startup dependency check | `GET /api/v1/health/dependencies` on the current root `.env` | PostgreSQL `ok`; Redis/MinIO `unreachable`; no sensitive fields returned |
| Dependency endpoint authorization | Unauthenticated request plus authenticated Windows smoke | Unauthenticated `401`; administrator session can read the sanitized response |
| Windows smoke dependency gate | `scripts/windows-local-smoke.ps1` after authenticated login | Implemented; current rerun remains blocked by Redis/MinIO reachability and must not be marked passed |

The result above is environment evidence only. It does not prove Redis/MinIO availability or external-worker readiness.

### Q18 external evidence still required

- Real MinIO large-object upload, reconciliation, purge authorization and restore drill.
- Real SMTP, WeCom and DingTalk delivery, including metric/reason text and provider failure observability.
- Authorized Android device and Windows Android Worker low-code execution.
- Linux/Kubernetes performance Worker, Prometheus, real TLS target, cancellation, allowlist and multi-node evidence.
- Linux/Xvfb Web Worker and macOS/iOS/Appium target evidence.

Use the Q18 extension in [`docs/q9-release-checklist.md`](q9-release-checklist.md) to fill these fields; do not promote local test results to external acceptance.

## Local Evidence

### Full Backend Regression (2026-05-30, Q9 Phase 5)

Command:

```bash
python -m pytest backend/tests --ignore=backend/tests/integration -q
```

Result:

```text
726 passed, 2 skipped, 41 warnings in 11.84s
```

The 41 warnings are `PytestCollectionWarning` for `Test*`-named SQLAlchemy/Pydantic classes and are not failures. Phase 5 also fixed the router guard to enforce `meta.requireAdmin` and to restore `user` after a page refresh; frontend `npm run type-check` passed.

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
