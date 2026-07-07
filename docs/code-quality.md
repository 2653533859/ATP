# ATP Code Quality Gates

> Last updated: 2026-07-08

## Current Gate

Q10 Phase 1 has started with a narrow, high-signal backend lint gate:

```bash
python -m ruff check backend/app backend/tests
```

The initial rule set is:

- `F821`: undefined name
- `F822`: undefined name in `__all__`
- `F823`: local variable referenced before assignment

The first gate started small so CI could block clear correctness issues before the historical formatting cleanup landed. The Q10 format baseline is now applied across `backend/app` and `backend/tests`.

## Local Commands

Install backend development tools:

```bash
python -m pip install -r backend/requirements-dev.txt
```

Run the lint gate:

```bash
make lint
```

Run the formatter:

```bash
make format
```

Run the format gate:

```bash
make format-check
```

Run the progressive type gate:

```bash
make mypy
```

Run the backend SAST gate:

```bash
make security-bandit
```

Run all local commit hooks:

```bash
make pre-commit
```

## CI

`.github/workflows/ci.yml` now includes a `backend-lint` job on push and pull request events. The job installs `backend/requirements-dev.txt` and runs the same `ruff check` and `ruff format --check` commands.
The same job also runs `python -m mypy`.
The same job also runs Bandit SAST with medium/high severity gating.

## Mypy Gate

Q10 Phase 1 now includes a progressive mypy baseline:

```bash
python -m mypy
```

Scope:

- `backend/app/core`
- `backend/app/schemas`
- `backend/app/services`

Baseline captured on 2026-07-06:

```text
Success: no issues found in 76 source files
```

The initial configuration uses `ignore_missing_imports` and `follow_imports = "silent"` to keep the gate focused on the selected application modules. Stricter options should be enabled module by module after the current Q10 baseline is merged.

## Pre-Commit

`.pre-commit-config.yaml` now runs:

- `check-yaml`, excluding Helm templates under `deploy/helm/atp/templates/`
- `end-of-file-fixer`
- `trailing-whitespace`
- backend ruff check using pinned `ruff==0.8.4`
- backend ruff format check using pinned `ruff==0.8.4`
- backend mypy using the current project environment
- frontend Vitest

Validation on 2026-07-08:

```text
make pre-commit PYTHON=backend/.venv/bin/python
```

Result:

```text
check yaml: passed
fix end of files: passed
trim trailing whitespace: passed
backend ruff check: passed
backend ruff format check: passed
backend mypy: passed
frontend vitest: passed
```

## Baseline Notes

Exploratory full-rule scans on 2026-07-06 showed these historical cleanup areas:

- `ruff format --check backend/app backend/tests`: initially reported a large historical formatting baseline.
- `ruff check backend/app backend/tests --select E,F,I,UP,B,SIM --statistics`: mostly long lines, FastAPI default-argument patterns, import ordering, and delayed imports.

The format baseline was applied on 2026-07-08:

- `ruff format backend/app backend/tests`: 217 files reformatted, 115 left unchanged.
- `ruff format --check backend/app backend/tests`: passes after the baseline.
- `.git-blame-ignore-revs` has been added with instructions. Append the format-only commit SHA after committing the baseline.

Remaining broader-rule cleanup should still be rolled out separately:

1. Add import-order and modernization rules with explicit per-file ignores where needed.
2. Expand ruff beyond F821/F822/F823 once formatting noise is out of the review path.

## Coverage Gate

Q10 Phase 2 has started with backend coverage visibility.

Local command:

```bash
make test-backend-coverage
```

CI command:

```bash
python -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=xml --cov-report=term-missing:skip-covered --cov-fail-under=52
```

Baseline refreshed on 2026-07-08:

- Python: 3.14.5 local venv
- Result: `823 passed, 41 warnings`
- Total backend coverage: `53.47%`
- CI gate: `52%`
- Artifact: `coverage.xml` uploaded as `backend-coverage-xml`

The threshold is intentionally set one point below the current baseline to prevent accidental coverage drops while leaving room for small platform or dependency differences in CI. Future changes should raise this threshold only after the baseline improves.

## Next Target

The next Q10 quality steps are:

- Commit the standalone `ruff format` baseline and append that commit SHA to `.git-blame-ignore-revs`.
- Add Gitleaks, Trivy, and Dependabot/security workflow automation.
- Expand the front-end Vitest suite beyond the first auth/http/websocket/component slice.
- Expand coverage reporting to HTML artifacts if CI review needs line-by-line browsing.

## Frontend Unit Testing

Q10 Phase 3 has started with a minimal Vitest pipeline.

Local commands:

```bash
cd frontend && npm run test
cd frontend && npm run test:coverage
```

Baseline refreshed on 2026-07-08:

- Test result: `18 passed`
- Covered slices: auth store, theme store, HTTP request/401 interceptors, permissions utilities, WebSocket message parsing/reconnect behavior, chart theme utilities, and `BatchOperationBar`
- Full-source coverage visibility: `1.8%`
- CI gate: run `npm run test` before `type-check` and `build`

No frontend coverage threshold is enforced yet because this is the first test slice and most views/components remain intentionally uncovered. Add a threshold only after more reusable components and route-level logic are covered.
