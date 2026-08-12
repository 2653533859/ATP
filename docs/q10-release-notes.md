# Q10 Release Notes

> Date: 2026-07-08
> Evidence: `docs/q10-acceptance-summary.md`, `docs/release-evidence-2026-07-06.md`

## Summary

Q10 turns ATP's engineering quality into a repeatable release baseline. It adds backend lint / format / type / coverage gates, frontend unit and E2E coverage, security scanning and dependency remediation, real-infrastructure integration coverage, SLO visibility, and flaky-test governance.

This release should be reviewed in split PRs according to `docs/q11-pr-split-plan.md`, with the Ruff format baseline kept separate from behavioral changes where possible.

## Major Change Groups

### 1. Environment And Dependency Compatibility

- Fixed local Python 3.14 backend setup by pinning `asyncpg==0.31.0`, `psycopg2-binary==2.9.12` and `PyYAML==6.0.3`, which ship Windows cp314 wheels and avoid local C compiler/`pg_config` builds.
- Preserved Python 3.12 deployment compatibility with conditional dependency pins.
- Hardened `make setup` for Homebrew `libpq`, `openssl@3`, `readline`, and `krb5` paths.
- Unified Playwright / pytest-playwright pins so Docker Python 3.12 and local Python 3.14 resolve cleanly.

### 2. Code Quality Gates

- Added Ruff lint and format checks.
- Added `.pre-commit-config.yaml`.
- Added progressive mypy coverage for `core`, `schemas`, and `services`.
- Added backend coverage reporting with a 52% fail-under gate.

### 3. Frontend Test Baseline

- Added Vitest, jsdom, Vue Test Utils, and coverage tooling.
- Added focused tests for auth, HTTP interceptors, permissions, WebSocket behavior, theme utilities, chart theming, and shared UI.
- Added suite / plan Playwright E2E coverage for load, trigger, and history workflows.

### 4. Security And Dependency Hygiene

- Added Bandit, pip-audit, npm audit, Gitleaks, Trivy, and Dependabot automation.
- Remediated configured backend and frontend dependency audit findings to zero known vulnerabilities.

### 5. Real-Infrastructure Integration

- Expanded integration tests for suite-run / plan-trigger and notification / bug-report flows.
- Added Alembic migrations discovered by fresh database integration runs:
  - `test_suites.config`
  - `bug_trackers.tracker_type` enum conversion
- Made integration project setup idempotent with explicit project codes.

### 6. SLO And Flaky Governance

- Added `atp_run_outcomes_total{entity_type,status}` for case / suite / plan terminal outcomes.
- Added Grafana panels for API availability, API P95, run success rate, and API error-budget remaining.
- Added SLO documentation with PromQL and target definitions.
- Added `pytest-rerunfailures`, a project `flaky` marker, and a one-retry integration CI policy.

### 7. Documentation Closure

- Added Q10 acceptance summary.
- Updated README, Task, MEMORY, CONTEXT, release evidence, observability, CI, SLO, flaky, frontend testing, security, and code-quality documentation.
- Added Q11 roadmap and PR split plan for review packaging.

## Verification Snapshot

Latest recorded evidence:

```text
Backend local Python 3.14 regression excluding integration: 825 passed
Docker Python 3.12 target-runtime regression excluding integration: 823 passed
Backend coverage gate: 823 passed, total coverage 53.47%, required 52%
Backend real-infra integration: 10 passed, repeat run 10 passed
Frontend Vitest: 18 passed
Frontend Playwright E2E: 9 passed
Frontend type-check: passed
Frontend build: passed
Ruff lint: passed
Ruff format-check: passed
Mypy: passed in 76 source files
Bandit: medium/high 0, low findings visible
pip-audit: no known vulnerabilities found
npm audit: found 0 vulnerabilities
pre-commit: passed
Grafana dashboard JSON: valid
SLO worker regression: 23 passed
Flaky governance smoke: rerun option accepted, 2 passed
git diff --check: passed
```

## Risk Notes

| Area | Risk | Mitigation |
|------|------|------------|
| Ruff format baseline | Large mechanical diff can hide behavior changes during review. | Keep format-only changes in a dedicated PR / commit and add the final SHA to `.git-blame-ignore-revs`. |
| Dependency upgrades | Runtime behavior can shift across FastAPI / Starlette / pytest / Vite / Vitest / Axios / ECharts upgrades. | Keep Python 3.12 and Python 3.14 verification evidence; retain lockfile / requirements diff for rollback. |
| Python 3.14 conditional pins | Local-only compatibility pins may diverge from deployment behavior. | Docker Python 3.12 regression remains the deployment baseline; do not promote Python 3.14 to runtime without a separate matrix decision. |
| Security workflows | Gitleaks / Trivy can expose latent repository or image findings when first run in CI. | Treat first failures as triage input; only suppress findings with documented rationale. |
| Integration retries | A bounded retry can hide environmental flakes if not monitored. | `docs/flaky-governance.md` requires repeated signatures to be fixed or explicitly marked with an exit condition. |
| SLO panels | Initial thresholds are thin-slice operational defaults, not production-calibrated targets. | Q11 includes SLO production calibration and runbook work. |
| Run outcome metric | Metrics are best-effort and emitted from worker paths; they are not a source of truth for database state. | Use dashboards for operations, and database records for authoritative reports/audits. |

## Rollback Plan

The current detailed dependency, lockfile, image, scanner, and vulnerability rollback procedure is `docs/dependency-security-rollback.md`.

### Dependency / Runtime Changes

1. Revert `backend/requirements.txt`, `frontend/package.json`, and `frontend/package-lock.json` to the previous release.
2. Reinstall dependencies:

   ```bash
   backend/.venv/bin/python -m pip install -r backend/requirements.txt
   npm --prefix frontend ci
   ```

3. Re-run the baseline:

   ```bash
   backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration
   npm --prefix frontend run type-check
   npm --prefix frontend run test
   ```

### Quality Gate / CI Changes

1. If a new gate blocks unrelated emergency work, temporarily bypass the workflow job in branch protection rather than deleting the config.
2. Revert `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `pyproject.toml`, and `backend/requirements-dev.txt` together if the gate config itself is faulty.
3. Keep test/source changes separate from gate rollback so behavior fixes remain reviewable.

### Ruff Format Baseline

1. Revert the format-only PR / commit as a unit if required.
2. Remove the corresponding SHA from `.git-blame-ignore-revs`.
3. Re-run `make format-check PYTHON=backend/.venv/bin/python` to confirm the chosen baseline.

### Security Automation

1. Revert `.github/workflows/security.yml` or `.github/dependabot.yml` independently if automation is misconfigured.
2. Do not roll back dependency vulnerability fixes unless a runtime regression is confirmed.
3. If a specific scanner finding is false-positive, add a scoped suppression with rationale in `docs/security-scanning.md`.

### Integration / Migration Changes

1. If migration issues appear before production deploy, fix forward and re-run an empty database `alembic upgrade head`.
2. If production migration has already run, prefer database backup restore for data rollback.
3. For code rollback, keep migration files in history unless the deployment never applied them.

### SLO / Flaky Governance

1. SLO dashboard changes can be reverted independently via `docker/grafana/dashboards/atp-overview.json`.
2. `atp_run_outcomes_total` metric emission can remain harmless even if dashboard panels are rolled back.
3. To disable integration retries, revert the `--reruns 1 --reruns-delay 2` change in `.github/workflows/test-integration.yml` while keeping the marker documentation.

## Release Checklist

- [ ] Apply the PR split from `docs/q11-pr-split-plan.md`.
- [ ] Confirm Ruff format baseline is isolated or reviewed with whitespace ignored.
- [ ] Re-run main CI after final split.
- [ ] Re-run or collect security workflow evidence.
- [ ] Re-run or collect integration workflow evidence.
- [ ] Re-run or collect frontend E2E workflow evidence.
- [ ] Re-run or collect release-readiness workflow evidence.
- [ ] Confirm `docs/q10-acceptance-summary.md` and this file match the final commit set.
