# Flaky Test Governance

This document defines the Q10 flaky-test policy for ATP integration and E2E tests.

## Goals

- Keep ordinary unit and static tests deterministic.
- Allow one bounded retry only for infrastructure-heavy scheduled suites.
- Make every known flaky test visible, owned, and removable.

## Policy

| Scope | Retry policy | Marker policy | Notes |
|-------|--------------|---------------|-------|
| Backend unit/static tests | No automatic retry | Do not use `flaky` | Failures should be fixed directly. |
| Backend integration workflow | `--reruns 1 --reruns-delay 2` in scheduled/manual CI | Use `@pytest.mark.flaky` only with a documented issue/exit condition | Covers real PostgreSQL / Redis / MinIO startup and network timing. |
| Frontend Playwright E2E | `retries: 1` only when `CI=true` | Prefer test title comment or linked issue; do not hide assertion bugs | Local runs stay retry-free to expose regressions early. |
| Celery worker task behavior tests | No automatic retry | Do not use `flaky` | Task mutation semantics must remain deterministic. |

## Adding A Flaky Marker

Only add `@pytest.mark.flaky` after all of the following are true:

1. The failure has happened at least twice with the same signature.
2. The failure is caused by external timing, browser rendering, service readiness, or network behavior.
3. The test still verifies a valuable user or integration path.
4. The owning issue or TODO states the exit condition for removing the marker.

Example:

```python
@pytest.mark.integration
@pytest.mark.flaky(reason="MinIO startup race on hosted runners; remove after health probe hardening")
async def test_report_export_flow(...):
    ...
```

Do not mark tests flaky for assertion mismatches, data races introduced by application code, permission failures, migration failures, or dependency-resolution failures.

## Triage Workflow

1. Re-run the exact failed command once locally or through `workflow_dispatch`.
2. If the retry passes, inspect logs to confirm the failure was environmental.
3. If the same signature repeats, either fix the root cause or add `flaky` with a linked exit condition.
4. If the retry fails again, treat it as a real regression.
5. Review all `flaky` markers during release readiness; no marker should survive without current evidence.

## Current Known Flaky Inventory

No test is currently marked `flaky`.

The former CaseList `ResizeObserver loop completed with undelivered notifications` warning was resolved in Q11-40 by disabling horizontal table scroll while the table is empty. `case-list.spec.ts` now rejects that exact page error, so recurrence is a regression rather than accepted flaky noise.

`src/utils/chartTheme.spec.ts` failed twice on 2026-07-31 under concurrent load with
`Test timed out in 5000ms` on `await import('@/utils/chartTheme')` — 16.2s under load
versus ~200ms idle. It was **not** registered as flaky, because rule 2 above does not
apply: the cost was inside our own control, not external timing. Both test cases
dynamically re-import the module (`vi.resetModules()` in `beforeEach` requires it, so the
module-load side effects can be asserted after `clearAllMocks`), and while the spec mocked
`echarts/core` it left `echarts/charts`, `echarts/components` and `echarts/renderers` real
— so every import paid for transforming the whole echarts subgraph, for modules that no
assertion in the file touches. Mocking those three entry points (Q15-06) cut the in-test
time from ~196-289ms to ~12-13ms measured over three cold runs, which restores roughly a
400x margin against the 5000ms default. The global `testTimeout` was deliberately left
alone: raising it would have kept the 16s of work and only moved the threshold.

## Commands

Local deterministic runs:

```bash
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration
npm --prefix frontend run e2e
```

Scheduled/manual infrastructure run with bounded retry:

```bash
ATP_INTEGRATION_TESTS=1 backend/.venv/bin/python -m pytest backend/tests/integration -m integration -v --tb=short --reruns 1 --reruns-delay 2
```
