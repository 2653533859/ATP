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
| After WebSocket endpoint slice | 1085 passed | 71.62% | 66% | `api/v1/ws.py` 0% -> 89% (token auth, the run-subscription authz ladder admin/triggerer/creator/member/owner, handshake -> pubsub forward -> completed-close) via faked session/redis/WebSocket seams |
| After mobile-special collectors slice | 1095 passed | 72.26% | 66% | `services/mobile_special/collectors.py` 0% -> 92% (SamplingSession PID resolve + parser routing, PeriodicSampler metric-type filter/skip-None/stop, device/package validators) faking run_adb_shell + parsers |
| After mobile-special dispatch slice | 1110 passed | 72.87% | 66% | `worker/tasks_mobile_special.py` 26% -> 97% (run_mobile_special_task executor routing by type + config-merge/device-resolve/failure, check_schedules trigger+cron-reschedule, cleanup bulk-update) via the tasks.py seam pattern |
| After projects API slice | 1125 passed | 73.41% | 66% | `api/v1/projects.py` 41% -> 79% (project/module CRUD, module-tree build, member add 404/409, role update, and the last-owner-removal-block security invariant) |
| After bug-trackers API slice | 1138 passed | 73.76% | 66% | `api/v1/bug_trackers.py` 55% -> 75% (config encrypt/mask CRUD, the _merge_sensitive_config keep-secret-on-masked-update invariant, test-connection type-mismatch guard + error swallow) |
| After plans API slice | 1154 passed | 74.16% | 66% | `api/v1/plans.py` 55% -> 80% (suite-id/env validation, cron next-run + webhook-secret schedule handling, manual run env-var merge, and the webhook trigger secret-auth ladder 400/403/400) |
| After global-variables API slice | 1168 passed | 75% | 66% | `api/v1/global_variables.py` 24% -> 98% (encrypt-before-store, secret mask/reveal, global-scope admin guard, key uniqueness, created_by/updated_by forge-protection); slice exposed and fixed a live break (create_variable 500 on every call: value_encrypted duplicated between model_dump spread and explicit kwarg — same class of bug as create_task) |
| After android-executor deep slice | 1201 passed | measured only combined with the next slice | 66% | run-chain coverage on the four android executors via fake `create_subprocess_exec`/HeartbeatMonitor/MinIO seams: `android_executor` 23% -> 88%, `android_perf_executor` -> 90%, `android_stability_executor` -> 82%, `android_fluency_executor` -> 93% |
| After parallel fan-out slice (apks + cases/batch + adb_service) | 1242 passed | 79% | 66% | three modules covered in one coordinated fan-out: `api/v1/apks.py` 38% -> 96% (chunked temp-file staging + 413 cleanup, MinIO upload/presign/delete-swallow), `api/v1/cases/batch.py` -> 96% (batch delete/move skipped_ids, CSV BOM/order/400-ladder, ZIP import zip-bomb guard + per-entry validation, template/export roundtrips), `services/adb_service.py` 23% -> 97% (_run_adb five branches, devices -l parsing, getprop fallbacks, scan three-state) |
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
