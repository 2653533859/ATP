# Q11 PR / Commit Split Plan

> Date: 2026-07-08
> Scope: current large Q10/Q11 working diff

This plan keeps review units small enough to reason about. The main rule is: keep the Ruff format baseline separate from behavior changes whenever practical.

## Recommended Order

### PR 1 — Python 3.14 / Dependency Compatibility

Purpose: make local Python 3.14 setup and Python 3.12 deployment baseline coexist.

Include:

- `backend/requirements.txt`
- `Makefile`
- Python 3.14 compatibility fixes in targeted backend code/tests
- Evidence from Docker Python 3.12 and local Python 3.14 backend runs

Validation:

```bash
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration
make format-check PYTHON=backend/.venv/bin/python
```

### PR 2 — Review Fixes And Runtime Correctness

Purpose: land discrete correctness/security fixes surfaced during review.

Include:

- Manual bug-link project permission enforcement
- Missing AI governance / failure diagnosis module inclusion
- Bug status audit-log fix
- Focused regression tests for those fixes

Validation:

```bash
backend/.venv/bin/python -m pytest backend/tests/frontend/test_bug_link_frontend.py backend/tests/frontend/test_failure_diagnosis_static.py -q
backend/.venv/bin/python -m pytest backend/tests/api/test_bug_trackers.py -q
```

### PR 3 — Q10 Quality Gates

Purpose: introduce quality infrastructure without broad behavioral change.

Include:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `backend/requirements-dev.txt`
- `.github/workflows/ci.yml`
- `.git-blame-ignore-revs`
- `docs/code-quality.md`
- `docs/frontend-testing.md`
- `docs/security-scanning.md`
- `frontend/vitest.config.ts`
- frontend unit specs

Validation:

```bash
make lint PYTHON=backend/.venv/bin/python
make format-check PYTHON=backend/.venv/bin/python
make mypy PYTHON=backend/.venv/bin/python
make test-backend-coverage PYTHON=backend/.venv/bin/python
npm --prefix frontend run test
npm --prefix frontend run test:coverage
make pre-commit PYTHON=backend/.venv/bin/python
```

### PR 4 — Ruff Format Baseline

Purpose: isolate mechanical formatting.

Include:

- Backend files touched only by `ruff format backend/app backend/tests`
- No behavioral edits
- Update `.git-blame-ignore-revs` after the commit SHA exists

Validation:

```bash
make format-check PYTHON=backend/.venv/bin/python
git diff --check
```

Review guidance:

- Reviewers can inspect with whitespace ignored.
- Do not mix this PR with permission, migration, or dependency changes.

### PR 5 — Security Automation And Dependency Remediation

Purpose: land vulnerability remediation and recurring security automation.

Include:

- `.github/workflows/security.yml`
- `.github/dependabot.yml`
- backend/frontend dependency upgrades and lockfile changes
- `docs/security-scanning.md`

Validation:

```bash
make security-bandit PYTHON=backend/.venv/bin/python
make security-pip-audit PYTHON=backend/.venv/bin/python
make security-npm-audit
```

### PR 6 — Integration Expansion And Alembic Gaps

Purpose: land real-infra integration coverage and the migrations discovered by it.

Include:

- `backend/tests/integration/test_suite_plan_flow.py`
- `backend/tests/integration/test_notification_bug_flow.py`
- `backend/alembic/versions/20260529_0039_add_suite_config.py`
- `backend/alembic/versions/20260529_0040_convert_bug_tracker_type_enum.py`
- migration regression tests
- integration fixture project-code idempotency changes

Validation:

```bash
cd backend && alembic upgrade head
ATP_INTEGRATION_TESTS=1 backend/.venv/bin/python -m pytest backend/tests/integration -m integration -v --tb=short
```

### PR 7 — Frontend Suite / Plan E2E

Purpose: expand Playwright coverage without backend behavior changes.

Include:

- `frontend/e2e/suite-plan.spec.ts`
- `frontend/e2e/fixtures/mock-api.ts`
- `frontend/e2e/fixtures/mock-data.ts`

Validation:

```bash
npm --prefix frontend run type-check
npm --prefix frontend run test
npm --prefix frontend run e2e
```

### PR 8 — SLO And Flaky Governance

Purpose: land operational quality closure after test coverage exists.

Include:

- `backend/app/core/metrics.py`
- `backend/app/worker/tasks.py`
- `backend/tests/worker/test_run_outcome_metrics.py`
- `docker/grafana/dashboards/atp-overview.json`
- `.github/workflows/test-integration.yml`
- `docs/slo-guide.md`
- `docs/flaky-governance.md`
- `docs/observability-guide.md`
- `docs/ci-workflows.md`

Validation:

```bash
python3 -m json.tool docker/grafana/dashboards/atp-overview.json >/tmp/atp-overview.json
backend/.venv/bin/python -m pytest backend/tests/worker/test_run_outcome_metrics.py backend/tests/worker/test_dataset_parameterized.py backend/tests/worker/test_plan_execution_config.py backend/tests/worker/test_suite_execution_config.py -q
backend/.venv/bin/python -m pytest backend/tests/worker/test_run_outcome_metrics.py -q --reruns 1 --reruns-delay 1
```

### PR 9 — Documentation Closure And Q11 Roadmap

Purpose: sync the project memory and next roadmap after Q10 lands.

Include:

- `README.md`
- `Task.md`
- `MEMORY.md`
- `CONTEXT.md`
- `docs/q10-acceptance-summary.md`
- `docs/release-evidence-2026-07-06.md`
- `docs/optimization-roadmap-2026-q11.md`
- `docs/q11-pr-split-plan.md`

Validation:

```bash
git diff --check
rg -n "Q10|Q11|SLO|flaky" README.md Task.md MEMORY.md CONTEXT.md docs/q10-acceptance-summary.md docs/optimization-roadmap-2026-q11.md
```

## Notes

- `.genkit/traces_idx/genkit.metadata` should be reviewed before staging. If it is generated local metadata with no product value, leave it out of PRs.
- Keep untracked docs and workflows explicit in `git add` commands; do not rely on broad `git add .` for this split.
- If a file contains both format and behavior changes, prefer staging behavior hunks first, then format-only hunks in PR 4.
