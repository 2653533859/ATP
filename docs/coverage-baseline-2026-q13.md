# Q13 Coverage Baseline

## Snapshot

Measured with the local Python 3.14 toolchain, branch coverage enabled
(`--cov=backend/app`, integration tests excluded as in CI).

| Stage | Tests | Backend total | Gate | Notes |
| --- | ---: | --- | --- | --- |
| Q13 start (post-Q12) | 844 passed | 53% (5731 missed of 13327) | 52% | `worker/tasks.py` at 35% (362 missed) was the largest single gap |
| After execution-chain slice 1 (tasks.py) | 878 passed | 55.65% (5429 missed) | 52% | `worker/tasks.py` 35% -> 86%; remaining misses concentrated in the auto-bug success path (745-822, owned by the Q13-02 `bug_reporter` slice) |
| After execution-chain slice 2 (HTTP-family executors) | 924 passed | 60.03% (4864 missed) | 56% | `api_executor` 3% -> 94%, `grpc_executor` 8% -> 88%, `websocket_executor` 3% -> 89%, `graphql_executor` 3% -> 90%; slice exposed and fixed a real production break (`message_factory.GetPrototype` removed in protobuf 5+, grpc executor was failing on every run) |
| After execution-chain slice 3 (web-family executors) | 1045 passed | 69.29% | 62% | `web_executor` 13% -> 84% (faked subprocess pytest+Playwright + MinIO boundary), `web_lowcode_executor` 15% -> 51% (fake Page action dispatch + var replacement); added minio-symbol import guards to survive cross-file stub pollution |
| After execution-chain slice 4 (android-family executors) | 1059 passed | 70.23% | 62% | `android_lowcode_executor` 15% -> 53% (fake `_adb_cmd` over the full action dispatch), `android_executor` 12% -> 23% (run_android_case guard branches); all nine executors now behaviorally covered, TOTAL past 70% |
| After environments API slice | 1070 passed | 70.92% | 66% | `api/v1/environments.py` 0% -> 100% (CRUD routes + secret masking + batch-save encrypt/replace via route-fn seams); a fully-untested API closed, gate 62 -> 66 |
| After service slice 1 (bug_reporter + failure_diagnosis) | 962 passed | 63.35% | 56% | `bug_reporter` 20% -> 95% (four trackers behind one scripted httpx fake), `failure_diagnosis` 12% -> 97% (rule/LLM/fallback three-state) |
| After service slice 2 (ai_healing run-level) | 985 passed | 64.50% | 56% | `ai_healing` 46% -> 89% (run_diagnosis_for_run all states, cache keys, daily limits, vision loading, enqueue hooks) |
| After service slice 3 (exports) | 1003 passed | 65.97% | 56% | `exports` 36% -> 92% (three-level JUnit, aggregate suite/plan HTML builders, cache hit/miss, PDF routes behind a faked renderer) |
| After service slice 4 (mobile_special API, Q13-02 complete) | 1019 passed | 66.98% | 62% | `mobile_special` 45% -> 91%; slice exposed and fixed a live break (create_task 500 on every call: created_by duplicated between schema dump and explicit kwarg) |

## Frontend (Q13-03)

| Stage | Tests | Frontend statements | Gate | Notes |
| --- | ---: | --- | --- | --- |
| Q13-03 start (post-Q12) | 46 passed | 4.38% | 4.1 | workbench tier zero-covered |
| After CaseList slice | 51 passed | 4.65% | 4.4 | extracted utils/caseList (filter/count/workflow-guard/flaky/flatten); CaseList.vue rewired to the tested helpers, e2e still green |
| After RunDetail slice | 58 passed | 5.10% | 4.85 | extracted utils/runDetail (step stats, expand keys, iteration/healing/diagnosis normalizers, error truncation); RunDetail.vue rewired, run-detail e2e still green |
| After SuiteList slice | 62 passed | 5.54% | 5.3 | extended utils/suiteList (module descendant map, tree-select pruning, case execution-blocker classifier, structural case filter); SuiteList.vue dropped its local copies, suite-plan e2e still green |
| After DashboardView slice (Q13-03 workbench tier complete) | 68 passed | 5.95% | 5.7 | extracted utils/dashboardView (date-range gen, generic trend gap-fill, layout normalizer); a test pinned a subtle present-but-invalid layout-key contract |
| After CaseFormDrawer slice | 74 passed | 6.33% | 6.05 | extracted utils/caseFormConfig (config-step parse, form-body/graphql-var/ws-message/request-body normalizers); branch coverage crossed 8% |
| After PlanList cron slice | 77 passed | 6.40% | 6.15 | extended utils/planList (buildCronExpression, formatCronTime); statement gains now marginal per helper slice |
| After mount-test slice (ApkList + DeviceList) | 86 passed | 8.51% | 8.2 | two @vue/test-utils mount tests (ApkList 0->56%, DeviceList 0->62%); statements crossed the 8% Q13-03 acceptance line — mount tests moved +1pt each vs +0.07pt per helper slice |

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

- The gate follows TOTAL with roughly 4-5 points of headroom (Q12 policy of
  never gating at the measured value): 52% -> 56% after the executor slice
  (TOTAL 60.03%) -> 62% after Q13-02 completed (TOTAL 66.98%).
- Every slice records before/after rows in this table; import-only tests that
  inflate line coverage without behavioral assertions do not qualify.
