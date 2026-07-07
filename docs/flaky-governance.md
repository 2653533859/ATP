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

The full Playwright E2E run may log a Vite client `ResizeObserver loop completed with undelivered notifications` warning while still passing. This is tracked as test-environment noise, not a flaky assertion, and does not currently require a marker.

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
