# ATP Release-Readiness Runbook

## 发布前部署校验

```bash
make validate-deployment-readiness
make validate-deployment-readiness ARGS=--strict
```

普通模式允许本机缺少 Docker/Compose、Helm、`.env` 或 POSIX shell，但必须明确显示 `SKIP`；严格模式用于实际发布前，任一环境依赖缺失都必须失败。仓库契约通过不能替代真实集群、备份恢复或 smoke 证据。

> Updated: 2026-08-13
> Status: Q18 release-readiness extension, retaining the historical filename used by CI and release evidence.
> Scope: release candidate validation for the quality, security, integration, E2E, SLO, data-governance, performance and external-worker gates.

## 1. Release Candidate And Evidence Window

Record the candidate before running any gate:

```bash
export RELEASE_SHA="$(git rev-parse HEAD)"
export RELEASE_TAG="<tag>"
git status --short
git show --no-patch --format='%H %cI %s' "$RELEASE_SHA"
```

Acceptance:

- The worktree is clean and `RELEASE_SHA` is the exact commit used by every workflow and image build.
- CI, Security, Integration, E2E, and Release readiness runs for this SHA are successful or their fresh manual replays are archived.
- Results, workflow URLs, image tags, warnings, and deviations are recorded in the active release-evidence document.

## 2. Code Quality And Test Gates

Install the locked dependencies before local replay:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm --prefix frontend ci
```

Run the Q10 code-quality gates from the repository root:

```bash
make lint PYTHON=backend/.venv/bin/python
make format-check PYTHON=backend/.venv/bin/python
make mypy PYTHON=backend/.venv/bin/python
make test-backend-coverage PYTHON=backend/.venv/bin/python
npm --prefix frontend run test
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Acceptance:

- Ruff lint and format checks pass with no changed files.
- Mypy passes for its configured progressive scope.
- Backend tests pass with total coverage at or above the configured `82%` gate and `coverage.xml` is retained by CI.
- Frontend Vitest, type-check, and production build pass.
- New warnings are investigated; known warnings are linked to a tracked follow-up and recorded in release evidence.

## 3. Security Gates

Run the local security checks:

```bash
make security-bandit PYTHON=backend/.venv/bin/python
make security-pip-audit PYTHON=backend/.venv/bin/python
make security-npm-audit
```

Confirm the Security workflow for `RELEASE_SHA` also passed:

- Gitleaks secret scan.
- Backend `pip-audit` and frontend high/critical `npm audit`.
- Trivy HIGH/CRITICAL scans for backend, worker, and frontend images.

Acceptance:

- Bandit has no medium/high finding.
- Dependency audits have no blocking vulnerability.
- Gitleaks and all three Trivy image scans are green.
- Any scoped suppression has a rationale in `docs/security-scanning.md`; unreviewed suppressions block release.

## 4. Migration And Real-Infrastructure Integration

Start PostgreSQL, Redis, and MinIO, then migrate from the repository root:

```bash
make infra-up
PATH="$PWD/backend/.venv/bin:$PATH" make migrate
make test-integration PYTHON=backend/.venv/bin/python
```

Verify migration state before switching traffic:

```bash
cd backend
.venv/bin/alembic current
.venv/bin/alembic heads
```

Acceptance:

- `alembic upgrade head` succeeds against an empty PostgreSQL database in CI.
- `alembic current` matches the single Alembic head.
- The real-infrastructure integration suite passes against PostgreSQL, Redis, and MinIO.
- Integration retries remain bounded by `docs/flaky-governance.md`; a repeated failure signature is not accepted as green merely because a retry passed.
- The Helm migrate Job or Compose migration step finishes before backend and worker traffic starts.

Stop local infrastructure after evidence is collected:

```bash
make infra-down
```

## 5. Frontend E2E And SLO Contract

Run the complete Playwright suite:

```bash
npm --prefix frontend run e2e
```

Validate the Grafana SLO dashboard JSON:

```bash
python3 -m json.tool docker/grafana/dashboards/atp-overview.json >/dev/null
```

Acceptance:

- Login, dashboard, case execution, run detail, suite, and plan E2E paths pass.
- The dashboard JSON parses and still contains API availability, API P95, run success rate, and API error-budget panels.
- Paging-grade SLO alerts remain governed by the production-history enablement criteria in `docs/slo-guide.md`; their current deferred status is not treated as a missing release gate.
- The CaseList E2E emits no ResizeObserver loop error; `case-list.spec.ts` protects this runtime contract.

## 6. Docker Image Gate

Build the exact release candidate images:

```bash
docker build -t registry.local/atp/backend:<tag> backend/
docker build -t registry.local/atp/worker:<tag> -f backend/Dockerfile.worker backend/
docker run --rm --entrypoint k6 registry.local/atp/worker:<tag> version
docker build -t registry.local/atp/frontend:<tag> frontend/
```

Acceptance:

- All images build from `RELEASE_SHA` without an uncommitted build context.
- The worker image exposes a working `k6` binary because performance runs depend on it.
- The same image digests promoted through staging are used for production; do not rebuild between environments.
- Security workflow Trivy results correspond to the promoted image contents.

## 7. Helm Staging Dry-Run

Prepare release-specific values outside the repository:

```bash
cp deploy/helm/atp/values.yaml my-values.yaml
helm lint deploy/helm/atp/
helm upgrade --install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml --dry-run
helm upgrade --install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml
```

Confirm before applying:

- Image tags and digests match the release candidate.
- `config.CELERY_QUEUES` and `worker.queues` include `default,ios,ai,maintenance,performance`; Android queues are reserved for the Windows Android Worker.
- Long-running `performance` and growing `ai` traffic have the intended worker separation and resource limits.
- PostgreSQL, Redis, MinIO, Prometheus, and notification/bug-tracker endpoints point to staging services.
- Secrets are injected externally and do not appear in values files or rendered manifests.
- Beat remains a single replica.

## 8. Staging Smoke Tests

After deployment, verify:

- Login and project/case navigation.
- One API case execution through run detail and report generation.
- Suite execution and plan manual trigger/history.
- Dataset upload preview with valid and invalid rows.
- Notification test-send failure handling and secret masking.
- Bug tracker connection, deduplication, creation, refresh, and manual link permissions.
- AI case generation and AI healing preview on controlled fixtures.
- Performance Center upload, run, and raw-summary access.
- Prometheus scrape health and all four SLO panels in `ATP Overview`.

### Q18 productization extension

Run these checks on the same release SHA when the corresponding capability is enabled:

- Dataset storage: run migration `20260812_0055`, upload database-mode and MinIO-mode datasets, create a version snapshot and rollback, then run the administrator reconciliation endpoint in dry-run mode. Only after a verified object backup may staging repeat it with `{ "purge": true }`; retain the response and audit-event evidence.
- Run retention: preview global and project-level scopes, confirm that projects with retention overrides are excluded from the global fallback, execute the cleanup in staging, and retain the returned per-project deletion details.
- Performance notification: configure an enabled project channel, use `scripts/notification-channel-smoke.py` with `ATP_TOKEN` or `ATP_USERNAME`/`ATP_PASSWORD`, execute a performance run that produces metrics or a terminal failure, and verify that the delivered message includes RPS/P95/P99/error rate, threshold status and event reasons. Archive the script's redacted JSON report together with provider-side delivery/message evidence. SMTP/WeCom/DingTalk delivery is external evidence; unit tests and a successful API response do not replace it.
- Windows Android Worker: on a Windows host with an authorized device, run `scripts/windows-android-acceptance.ps1` and the required Android low-code smoke. A missing device must remain `BLOCKED`, not be recorded as a pass.
- Linux/Kubernetes performance stack: run `scripts/performance-environment-smoke.py` with the real API, node, target, Prometheus, TLS and metrics arguments; retain JSON evidence for the worker queue, allowlist, cancellation and target metrics.
- Web/iOS external workers: run browser-matrix/recording or Appium acceptance commands only on target worker hosts; local Windows status-only checks cannot close Linux/Xvfb or macOS/iOS gates.

The commands and reports above must be attached to the active release evidence file. If a target environment or notification provider is not part of the release, record the explicit scope exclusion and owner rather than silently skipping it.

Queue inspection:

```bash
celery -A app.worker.celery_app inspect active_queues
```

Expected queues: `default`, `mobile_special`, `ai`, `maintenance`, and `performance`.

## 9. Rollback Readiness

Before production release:

- Confirm current PostgreSQL and MinIO backup objects exist and the latest restore drill is valid.
- Record database migration head, image digests, configuration revision, and current Helm revision.
- Review and assign an owner for `docs/dependency-security-rollback.md`.

```bash
helm history atp -n atp-production
helm rollback atp <REVISION> -n atp-production
```

Data-destructive migrations, enum changes, and field removals must not be downgraded in production without a restore rehearsal. Application rollback must remain compatible with the migrated schema, or traffic must stay stopped while the validated backup is restored.

## 10. Release Decision Record

Record the following in `docs/q9-release-evidence.md` or the active release evidence file:

- `RELEASE_SHA`, release tag, image tags, and immutable image digests.
- CI, Security, Integration, E2E, and Release readiness workflow URLs.
- Ruff, format, mypy, coverage, Vitest, type-check, and build results.
- Bandit, dependency audit, Gitleaks, and Trivy results.
- Alembic current/head output and real-infrastructure integration result.
- Grafana SLO JSON validation and staging SLO panel checks.
- Helm lint/dry-run output and staging smoke-test result.
- Q18 dataset storage/reconciliation, run-retention and performance-notification evidence, including the redacted notification-channel smoke report and provider-side delivery evidence.
- Windows Android, Linux/Kubernetes performance, Web Worker and iOS/Appium evidence or an explicit scope exclusion.
- Accepted warnings, open risks, rollback owner, and final go/no-go decision.

Release is blocked when any required gate is missing, failed, tied to a different SHA, or supported only by stale evidence.
