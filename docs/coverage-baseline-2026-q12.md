# Q12 Coverage Baseline

## Snapshot

Captured on 2026-07-10 from the local Python 3.14.5 and Node 20-compatible toolchains.

| Surface | Tests | Coverage | Gate |
| --- | ---: | --- | --- |
| Backend | 840 passed | 53.46% total | 52% total |
| Frontend baseline | 11 files / 33 passed | statements 3.66%, branches 4.06%, functions 2.26%, lines 3.92% | statements/branches/lines 3%, functions 2% |
| Frontend after auth slice | 12 files / 37 passed | statements 4.07%, branches 4.22%, functions 2.60%, lines 4.33% | statements/branches 3.75%, functions 2.25%, lines 4% |
| Frontend after case execution slice | 13 files / 41 passed | statements 4.13%, branches 4.26%, functions 2.73%, lines 4.40% | statements 3.85%, branches 4%, functions 2.45%, lines 4.1% |
| Frontend after scheduling slice | 13 files / 43 passed | statements 4.23%, branches 4.49%, functions 2.81%, lines 4.47% | statements 3.95%, branches 4.2%, functions 2.55%, lines 4.2% |
| Frontend after reporting slice | 14 files / 47 passed | statements 4.44%, branches 4.88%, functions 3.01%, lines 4.66% | statements 4.15%, branches 4.55%, functions 2.75%, lines 4.35% |
| Frontend after q12 review cleanup | 14 files / 46 passed | statements 4.38%, branches 4.81%, functions 2.96%, lines 4.61% | statements 4.1%, branches 4.55%, functions 2.7%, lines 4.35% |

Commands:

```bash
make test-backend-coverage PYTHON=backend/.venv/bin/python
npm --prefix frontend run test:coverage
```

The backend report is written to `coverage.xml`. Frontend HTML and JSON reports are written to `frontend/coverage`; both are retained by the main CI workflow.

## Decision

The backend threshold remains 52% because the measured baseline is stable but only 1.46 points above the gate. The frontend gate was raised after the auth slice and retains at least 0.25 percentage points of local headroom. Neither threshold should be raised by percentage-only tests.

After the q12 review cleanup simplified the case-execution helpers, statements and functions gates were nudged down (4.15→4.1, 2.75→2.7) to restore the required 0.25-point headroom. `frontend/vitest.config.ts` must always mirror the latest gate row in this document.

## Priority Gaps

1. Authentication: complete; LoginView now covers success, required rules, API failure, loading, redirect query, and default redirect behavior.
2. Case execution: complete at the shared-service boundary; CaseList, CaseDetail, and SuiteList reuse tested environment mapping, optional run payload, and named-route run navigation helpers (the `executeCaseRun` API-wrapper indirection was removed in the q12 review, slightly lowering measured coverage).
3. Scheduling: complete; tested save validation order and deterministic create/update payloads complement existing cron helpers and manual-trigger Playwright coverage.
4. Reporting: complete at the data boundary; tested query filters, date-picker values, half-open date limits, missing task-name fallback, and trend summaries. Chart-library internals remain outside unit scope.

Large hardware/browser executors and infrastructure bootstrap modules should stay behind unit seams or integration/E2E tests. Import-only tests that inflate line coverage without checking behavior do not qualify for raising a gate.

## Threshold Policy

- Every critical-flow batch records before/after coverage and its behavioral scenarios.
- Raise a threshold only when the new baseline leaves at least 0.25 percentage points of local headroom.
- A coverage increase does not replace type-check, production build, Playwright, or real-infrastructure integration gates.
