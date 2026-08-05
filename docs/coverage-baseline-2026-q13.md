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
| After lowcode-executor slice (Q14-01 complete) | 1267 passed | 81% | 70% | main run-chains of both lowcode executors behind fake Playwright/ADB seams: `web_lowcode_executor` 51% -> 97% (screenshot-per-step + video record/upload, fail-stop, launch error), `android_lowcode_executor` 53% -> 98% (_adb_cmd four branches, uiautomator-dump text/resourceId click resolution, run orchestration); gate raised 66 -> 70 and the stale Makefile gate (52) synced to 70 |
| After suites API slice (Q14-02 start) | 1279 passed | 81% | 70% | `api/v1/suites.py` 68% -> 100% (CRUD 404 ladder, empty-case-ids validation short-circuit, trigger env-404/empty-cases-400, env-var merge with extra-vars priority, suite-run list/get); run_retention behavior change (Q14-04) landed in the same window taking the service 78 -> 90% |
| After notifications API slice | 1286 passed | 81% | 70% | `api/v1/notifications.py` 62% -> 99% (create encrypt-before-store + audit, list/get sensitive-config masking, update non-config-field path + 404 ladder, delete audit, dingtalk test dispatch with en-US summary) |
| After API-router sweep closeout (Q14-02 complete) | 1310 passed | 82.20% | 70% | Added route-level seams for three remaining high-signal API gaps: `api/v1/ai_healing_stats.py` 0% -> fully covered and skipped (cache hit/miss + Redis failure tolerance), `api/v1/devices.py` 0% -> 95% (list/filter, scan 503/sync, get/update/delete 404 ladders), `api/v1/healing_prompt_examples.py` 0% -> 96% (filter forwarding, create-from-step error map, update marker audit fields, delete 404). |
| After Q14-00 evidence tooling | 1327 passed | 82.19% | 70% | Added publishable Q12 external-evidence templates, scaffold/validator helpers, and an automated Prometheus/API/ADB collector behind `make collect-q12-evidence` with fake-source collector regressions (latency peak, data-gap gating, abort-before-rehearsal, `increase(...[1d])` day attribution, integer count formatting, `ATP_`-prefixed credentials); the remaining SLO/device capture is no longer manual, but still requires live external sources before Q14-00 can close. |
| After service slice 1 (bug_reporter + failure_diagnosis) | 962 passed | 63.35% | 56% | `bug_reporter` 20% -> 95% (four trackers behind one scripted httpx fake), `failure_diagnosis` 12% -> 97% (rule/LLM/fallback three-state) |
| After service slice 2 (ai_healing run-level) | 985 passed | 64.50% | 56% | `ai_healing` 46% -> 89% (run_diagnosis_for_run all states, cache keys, daily limits, vision loading, enqueue hooks) |
| After service slice 3 (exports) | 1003 passed | 65.97% | 56% | `exports` 36% -> 92% (three-level JUnit, aggregate suite/plan HTML builders, cache hit/miss, PDF routes behind a faked renderer) |
| After service slice 4 (mobile_special API, Q13-02 complete) | 1019 passed | 66.98% | 62% | `mobile_special` 45% -> 91%; slice exposed and fixed a live break (create_task 500 on every call: created_by duplicated between schema dump and explicit kwarg) |

## Q15-05 Backend Worker / Maintenance Slice

Measured with the **Python 3.12** toolchain (`/tmp` venv built from
`backend/requirements*.txt`), which is what `ci.yml` runs. See the interpreter
note below before comparing these numbers with a local 3.14 run.

| Stage | Tests | Backend total (3.12) | Gate | Notes |
| --- | ---: | --- | --- | --- |
| Q15-05 start (post-Q14) | 1390 passed | 84.31% | 70% | Five named modules below 60%: `worker/tasks_performance.py` 0%, `services/mobile_special/aggregator.py` 9%, `services/ai_healing_stats.py` 26%, `worker/tasks_db_backup.py` 44%, `services/dashboard_alerts.py` 56% |
| After the five named modules | 1421 passed | 85.15% | 70% | `tasks_performance` 0% -> 100% (five status transitions incl. the `finally` that closes a run after a k6 crash), `aggregator` 9% -> 95% (three task-type summary shapes + no-sample = None not 0), `ai_healing_stats` 26% -> 98% (scripted 8-query FakeDB, fingerprint bucketing, Top-10 truncation, NULL SUM coercion), `tasks_db_backup` 44% -> 93% (script env passing, MinIO outage tolerance, retry-on-non-zero-exit), `dashboard_alerts` service 56% -> 98% (every metric branch, all three notify channels, cross-project config refusal) |
| After auth + scripts routers | 1442 passed | 85.55% | 70% | Two routers that were at **0%**: `api/v1/auth.py` (unknown-user and wrong-password must be indistinguishable 401s; disabled account 403 with no token; refresh rejects an access token) and `api/v1/scripts.py` (1 MB limit, case-type allowlist, `case.config` round-trip, MinIO failure degradation). `backend/tests/api/test_auth.py` — the file CLAUDE.md cited as the single-file example — did not exist |
| After dashboard-alert + performance routers (Q15-05 complete) | 1467 passed | **86.04%** | **82** | `api/v1/dashboard_alerts.py` 49% -> ~100% (the viewer/owner permission ladder, admin-only global listing), `api/v1/performance.py` 68% -> 99% (duration/VUs parsing per unit, stage summing, target-host allowlist, GET/PATCH/LIST routes). Gate raised 70 -> 82 |

### Interpreter note (measured 2026-08-01)

The same command reports **different statement counts** on different Python
minor versions:

| Interpreter | Statements | Missed | Total |
| --- | ---: | ---: | --- |
| Python 3.12 (what `ci.yml` runs) | 13962 | 1619 | 86.04% |
| Python 3.14 (local `backend/.venv`) | 13367 | 1591 | 85.55% |

The 595-statement difference is why the Q15 roadmap's planning input (82.73% /
13962 statements) did not reproduce locally at first. **Set gates against the
3.12 number, then confirm the local 3.14 run still clears them** — the gate must
pass on both, so the binding constraint is whichever reads lower.

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
| After workbench mount-test slice (Q14-03 complete) | 102 passed | 21.48% | 20.5 | Added mount tests for the five Q14 workbench views: `CaseList.vue` 36.01%, `DashboardView.vue` 51.73%, `PlanList.vue` 60.69%, `RunDetail.vue` 45.50%, `SuiteList.vue` 50.29%. Frontend gates raised to statements 20.5 / branches 17.5 / functions 16.5 / lines 21.0. |
| After system-page mount-test slice (Q15-04 complete) | 128 passed | **32.96%** | **31.5** | Added six component mount specs across system, mock, and mobile-special routes, including chart theme/unmount lifecycle assertions. `views/system` statements reached **37.36%**; full coverage is 32.96 / 27.81 / 26.36 / 34.04% for statements / branches / functions / lines. Gates remain 31.5 / 26.5 / 24.5 / 32.5, retaining more than 0.25pt headroom on every metric. |

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
  (TOTAL 60.03%) -> 62% after Q13-02 completed (TOTAL 66.98%) -> 70% after
  Q14-01 -> **82% after Q15-05** (TOTAL 86.04% on 3.12, 85.55% on 3.14, so the
  headroom against the binding number is 3.55 points).
- Every slice records before/after rows in this table; import-only tests that
  inflate line coverage without behavioral assertions do not qualify.
- The gate value is declared in exactly two places (`Makefile` and
  `.github/workflows/ci.yml`) and quoted in `docs/ci-workflows.md`;
  `backend/tests/test_quality_gate_consistency.py` fails if the three drift
  apart. Raising the gate means changing all three in the same commit.
