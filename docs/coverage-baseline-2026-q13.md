# Q13 Coverage Baseline

## Snapshot

Measured with the local Python 3.14 toolchain, branch coverage enabled
(`--cov=backend/app`, integration tests excluded as in CI).

| Stage | Tests | Backend total | Gate | Notes |
| --- | ---: | --- | --- | --- |
| Q13 start (post-Q12) | 844 passed | 53% (5731 missed of 13327) | 52% | `worker/tasks.py` at 35% (362 missed) was the largest single gap |
| After execution-chain slice 1 (tasks.py) | 878 passed | 55.65% (5429 missed) | 52% | `worker/tasks.py` 35% -> 86%; remaining misses concentrated in the auto-bug success path (745-822, owned by the Q13-02 `bug_reporter` slice) |

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=term
```

## Conventions Established (Q13-01 slice 1)

`backend/tests/worker/test_tasks_execution_chain.py` fixes the unit-seam pattern
for Celery task bodies:

- Stub `celery_app`/`redis_client`/`tracing`/`async_runner` in `sys.modules`
  before importing `app.worker.tasks`; `run_async` is replaced with a real
  `asyncio.run` so task bodies execute synchronously inside the test.
- Restore the real modules after import and call `load_all_models()` once so
  ORM instantiation (`TestRun`/`SuiteRun`/`PlanRun`) has complete mappers.
- `AsyncSessionLocal` is monkeypatched on the conftest `app.core.database`
  stub to return a `_FakeDB` (objects keyed by `(model name, pk)`, scripted
  `execute` rows, commit/refresh counters).
- Late-imported collaborators (`notifier`, `exports`, `dashboard_alerts`) are
  injected via `monkeypatch.setitem(sys.modules, ...)`.
- Domain rows are `SimpleNamespace` stand-ins with `None`-defaulting attribute
  access; real enums (`RunStatus`, `SuiteRunStatus`, `PlanRunStatus`) are used
  for status assertions.

Executor slices (Q13-01 slice 2) should follow the same shape: fake the
transport/driver boundary (httpx client, Playwright page, ADB shell), never the
executor's own logic.

## Threshold Policy

- The CI gate stays at 52% until the executor slice lands; raise to 56% when
  TOTAL reaches 60% so the gate keeps roughly 4 points of headroom, mirroring
  the Q12 policy of never gating at the measured value.
- Every slice records before/after rows in this table; import-only tests that
  inflate line coverage without behavioral assertions do not qualify.
