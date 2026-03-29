# Android Special Testing Center Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend ATP from a general automation platform into an Android-specialized testing center with test assets, global variable library, performance/stability/fluency tasks, scheduled execution, report center, and report-detail pages comparable to the reference product.

**Architecture:** Build this as an incremental extension on top of the existing ATP stack instead of creating a second platform. Reuse the current auth, project, device, APK, object storage, WebSocket, and scheduler infrastructure; add a new `mobile_special` domain for task definitions, run records, metric samples, incidents, and artifacts; then expose dedicated APIs and frontend pages for Android专项测试. Keep case execution and special-task execution separate so the current case/suite/plan pipeline remains stable while the Android专项 domain grows independently.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, Celery, Redis, PostgreSQL, MinIO, ADB, `dumpsys`, `logcat`, `uiautomator2`, Vue 3, TypeScript, Ant Design Vue, ECharts, pytest.

---

## Scope and delivery assumptions

- Phase 1 target is Android only. Do not add iOS support in this implementation.
- Reuse existing `Project`, `Device`, `APK`, `TestCase`, `TestSuite`, `TestPlan`, `TestRun` concepts where they are already stable.
- Add a new Android专项任务 domain instead of overloading `TestPlan` for every new scenario.
- Match the reference product in capability layers, not pixel-for-pixel UI.
- The first end-to-end release must cover:
  - 测试资产：设备管理中心、全局变量库、App 包管理
  - UI 自动化：沿用现有用例管理、场景编排
  - 专项测试：性能任务、智能稳定性、流畅度分析
  - 调度与分析：定时任务、报告中心、性能/稳定性/流畅度报告详情

---

## Target module map

### Backend domain additions

- `mobile_special_tasks`: Android 专项任务定义
- `mobile_special_runs`: 专项任务执行记录
- `mobile_metric_samples`: 时序采样点
- `mobile_incidents`: Crash / ANR / fatal log / watchdog 事件
- `mobile_run_artifacts`: CSV / JSON / 截图 / 原始日志 / trace 附件
- `global_variables`: 项目级或平台级共享变量库

### Frontend additions

- 测试资产
  - 设备管理中心
  - 全局变量库
  - App 包管理
- UI 自动化
  - 用例管理（复用现有）
  - 场景编排（复用现有套件）
- 专项测试
  - 性能任务列表/配置
  - 智能稳定性任务列表/配置
  - 流畅度分析任务列表/配置
- 调度与分析
  - 定时任务列表
  - 报告中心
  - 性能报告详情
  - 稳定性报告详情
  - 流畅度报告详情

---

## Data model summary

### `MobileSpecialTask`

- `id`
- `name`
- `project_id`
- `task_type` (`performance`, `stability`, `fluency`)
- `source_type` (`apk_only`, `case`, `suite`, `monkey`)
- `source_id` (nullable)
- `device_scope_type` (`single_device`, `device_group`, `manual_pick`)
- `device_id` / `device_group_tag`
- `apk_id` (nullable)
- `app_package`
- `config_json`
- `schedule_enabled`
- `cron_expression`
- `last_run_at`
- `next_run_at`
- `created_by`
- `updated_by`

### `MobileSpecialRun`

- `id`
- `task_id`
- `task_type`
- `status` (`pending`, `running`, `completed`, `failed`, `stopped`)
- `device_id`
- `device_serial`
- `apk_id`
- `app_package`
- `started_at`
- `finished_at`
- `duration_ms`
- `summary_json`
- `config_snapshot`
- `trigger_type` (`manual`, `schedule`, `webhook`)
- `triggered_by`

### `MobileMetricSample`

- `id`
- `run_id`
- `sample_time`
- `metric_type` (`cpu_pct`, `mem_mb`, `fps`, `jank_count`, `frame_time_ms`, `battery_pct`, `temperature_c`, `network_rx_kb`, `network_tx_kb`)
- `metric_value`
- `source`
- `extra_json`

### `MobileIncident`

- `id`
- `run_id`
- `incident_type` (`crash`, `anr`, `fatal_log`, `watchdog`)
- `event_time`
- `title`
- `detail`
- `process_name`
- `thread_name`
- `artifact_path`

### `GlobalVariable`

- `id`
- `scope_type` (`global`, `project`)
- `project_id` (nullable)
- `key`
- `value_encrypted`
- `is_secret`
- `description`
- `created_by`
- `updated_by`

---

## API summary

### Special task APIs

- `GET /api/v1/mobile-special/tasks`
- `POST /api/v1/mobile-special/tasks`
- `GET /api/v1/mobile-special/tasks/{task_id}`
- `PATCH /api/v1/mobile-special/tasks/{task_id}`
- `DELETE /api/v1/mobile-special/tasks/{task_id}`
- `POST /api/v1/mobile-special/tasks/{task_id}/run`
- `POST /api/v1/mobile-special/runs/{run_id}/stop`

### Report APIs

- `GET /api/v1/mobile-special/runs`
- `GET /api/v1/mobile-special/runs/{run_id}`
- `GET /api/v1/mobile-special/runs/{run_id}/summary`
- `GET /api/v1/mobile-special/runs/{run_id}/samples`
- `GET /api/v1/mobile-special/runs/{run_id}/incidents`
- `GET /api/v1/mobile-special/runs/{run_id}/artifacts`
- `GET /api/v1/mobile-special/runs/{run_id}/export.csv`

### Asset APIs

- `GET /api/v1/global-variables`
- `POST /api/v1/global-variables`
- `PATCH /api/v1/global-variables/{id}`
- `DELETE /api/v1/global-variables/{id}`

---

## Worker architecture summary

- Add a dedicated mobile-special task runner instead of pushing this into `dispatch_case`.
- Create a shared monitoring session abstraction:
  - sampler loop for CPU / memory / battery / temperature / network
  - graphics loop for FPS / jank / frame timing
  - incident loop for crash / ANR detection
  - artifact sink for CSV / JSON / screenshots / raw logs
- Task types differ only by orchestration strategy:
  - `performance`: run app or scripted journey and focus on resource sampling
  - `stability`: long-run exploration, crash/ANR monitoring, optional performance sampling
  - `fluency`: scene-based run with FPS/jank emphasis and timeline markers

---

### Task 1: Define the Android专项 schema and migrations

**Files:**
- Create: `backend/app/models/mobile_special.py`
- Create: `backend/app/models/global_variable.py`
- Modify: `backend/app/models/bootstrap.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260330_0014_add_mobile_special_domain.py`
- Test: `backend/tests/migrations/test_mobile_special_migration.py`

**Step 1: Write the failing test**
- Add migration/schema tests that prove the new tables and enums exist.
- Add tests that prove `task_type`, `status`, and `metric_type` constraints are created.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/migrations/test_mobile_special_migration.py -q`
- Expected: FAIL because the new models and Alembic migration do not exist yet.

**Step 3: Write minimal implementation**
- Create SQLAlchemy models for special tasks, runs, samples, incidents, artifacts, and global variables.
- Add relationships to `Project`, `Device`, `APK`, and `User` only where required.
- Create the migration with indexes on `task_id`, `run_id`, `sample_time`, `metric_type`, and `event_time`.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/migrations/test_mobile_special_migration.py -q`
- Expected: PASS.

### Task 2: Add backend schemas and API contracts

**Files:**
- Create: `backend/app/schemas/mobile_special.py`
- Create: `backend/app/schemas/global_variable.py`
- Modify: `backend/app/schemas/__init__.py` if needed
- Test: `backend/tests/api/test_mobile_special_schema.py`

**Step 1: Write the failing test**
- Add schema tests for task create/update/detail/list payloads.
- Add schema tests for report summary, metric samples, incident list, and global variable payloads.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_mobile_special_schema.py -q`
- Expected: FAIL because the schema module does not exist yet.

**Step 3: Write minimal implementation**
- Create Pydantic models for task config, run summary, sample points, incident rows, artifact rows, and global variables.
- Keep `config_json` strongly typed by task type instead of passing opaque dicts through the API.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_mobile_special_schema.py -q`
- Expected: PASS.

### Task 3: Build shared ADB collectors and parsers

**Files:**
- Create: `backend/app/services/mobile_special/__init__.py`
- Create: `backend/app/services/mobile_special/adb_client.py`
- Create: `backend/app/services/mobile_special/collectors.py`
- Create: `backend/app/services/mobile_special/parsers.py`
- Create: `backend/app/services/mobile_special/aggregator.py`
- Test: `backend/tests/services/test_mobile_special_collectors.py`
- Test: `backend/tests/services/test_mobile_special_parsers.py`

**Step 1: Write the failing test**
- Add parser tests for:
  - `dumpsys meminfo <package>` → memory MB sample
  - `dumpsys gfxinfo <package> framestats` → fps/jank/frame time metrics
  - `logcat` crash/anr fragments → normalized incident rows
- Add collector tests that prove ADB command wrappers build the expected commands.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/services/test_mobile_special_collectors.py backend/tests/services/test_mobile_special_parsers.py -q`
- Expected: FAIL because the collector/parsing helpers do not exist yet.

**Step 3: Write minimal implementation**
- Add small wrappers for `adb shell`, `adb logcat`, `dumpsys cpuinfo`, `dumpsys meminfo`, `dumpsys gfxinfo`, `batterystats`, and `pidof`.
- Add parser helpers that convert raw command output into normalized sample rows and incident rows.
- Add summary helpers that compute average CPU, peak CPU, average memory, peak memory, crash count, ANR count, FPS averages, and jank totals.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/services/test_mobile_special_collectors.py backend/tests/services/test_mobile_special_parsers.py -q`
- Expected: PASS.

### Task 4: Implement the performance executor

**Files:**
- Create: `backend/app/worker/executors/android_perf_executor.py`
- Modify: `backend/app/services/mobile_special/aggregator.py`
- Test: `backend/tests/worker/test_android_perf_executor.py`

**Step 1: Write the failing test**
- Add executor tests that prove a performance run:
  - validates device + package inputs
  - starts sampling loops
  - stores metric samples
  - writes summary JSON with avg/max CPU and memory
- Add failure-path tests for missing package, offline device, and sampling timeout.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/worker/test_android_perf_executor.py -q`
- Expected: FAIL because the performance executor does not exist yet.

**Step 3: Write minimal implementation**
- Implement a run loop that optionally launches the app, samples CPU/memory/battery/network every N seconds, aggregates results, and uploads raw artifacts to MinIO.
- Keep the executor independent from case execution so special-task failures do not affect `TestRun` logic.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/worker/test_android_perf_executor.py -q`
- Expected: PASS.

### Task 5: Implement the stability executor

**Files:**
- Create: `backend/app/worker/executors/android_stability_executor.py`
- Modify: `backend/app/services/mobile_special/collectors.py`
- Test: `backend/tests/worker/test_android_stability_executor.py`

**Step 1: Write the failing test**
- Add tests that prove a stability run can execute in:
  - `monkey` / random exploration mode
  - `case` / `suite` driven mode
- Add tests that prove crash and ANR incidents are captured and summarized.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/worker/test_android_stability_executor.py -q`
- Expected: FAIL because the stability executor does not exist yet.

**Step 3: Write minimal implementation**
- Implement long-run orchestration with configurable duration, operation interval, ignore-crash policy, restart policy, and incident monitoring.
- Emit summary fields such as `explore_duration_seconds`, `operation_interval_ms`, `crash_count`, `anr_count`, `completed_action_count`, and `app_restart_count`.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/worker/test_android_stability_executor.py -q`
- Expected: PASS.

### Task 6: Implement the fluency executor

**Files:**
- Create: `backend/app/worker/executors/android_fluency_executor.py`
- Modify: `backend/app/services/mobile_special/parsers.py`
- Test: `backend/tests/worker/test_android_fluency_executor.py`

**Step 1: Write the failing test**
- Add tests for a scene-based fluency run that proves FPS/jank samples are recorded around named stages.
- Add tests for stage markers such as launch, list scroll, detail open, checkout, and custom steps.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/worker/test_android_fluency_executor.py -q`
- Expected: FAIL because the fluency executor does not exist yet.

**Step 3: Write minimal implementation**
- Implement a timeline-oriented executor that runs scripted scenes, marks stage boundaries, samples framestats, and summarizes stage-level FPS/jank.
- Store stage markers in `summary_json` or a small child table only if strictly needed.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/worker/test_android_fluency_executor.py -q`
- Expected: PASS.

### Task 7: Add Celery task wiring and schedule polling

**Files:**
- Create: `backend/app/worker/tasks_mobile_special.py`
- Modify: `backend/app/worker/celery_app.py`
- Modify: `backend/app/worker/tasks_cleanup.py`
- Test: `backend/tests/worker/test_mobile_special_tasks.py`

**Step 1: Write the failing test**
- Add tests that prove manual run dispatch works for each `task_type`.
- Add tests that prove scheduled tasks with due `next_run_at` are enqueued once and updated correctly.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/worker/test_mobile_special_tasks.py -q`
- Expected: FAIL because the task runner and polling logic do not exist yet.

**Step 3: Write minimal implementation**
- Add Celery tasks for `run_mobile_special_task`, `check_mobile_special_schedules`, and cleanup helpers for stale runs/artifacts.
- Register beat polling without changing the existing `TestPlan` scheduler contract.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/worker/test_mobile_special_tasks.py -q`
- Expected: PASS.

### Task 8: Expose backend APIs for assets, tasks, runs, and reports

**Files:**
- Create: `backend/app/api/v1/mobile_special.py`
- Create: `backend/app/api/v1/global_variables.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/v1/devices.py` if device filters/tags are needed
- Modify: `backend/app/api/v1/apks.py` if APK query fields are needed
- Test: `backend/tests/api/test_mobile_special_tasks_api.py`
- Test: `backend/tests/api/test_mobile_special_reports_api.py`
- Test: `backend/tests/api/test_global_variables_api.py`

**Step 1: Write the failing test**
- Add CRUD tests for special tasks.
- Add run trigger, stop, list, summary, samples, incidents, and artifact tests.
- Add global variable CRUD and secret masking tests.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_mobile_special_tasks_api.py backend/tests/api/test_mobile_special_reports_api.py backend/tests/api/test_global_variables_api.py -q`
- Expected: FAIL because the APIs do not exist yet.

**Step 3: Write minimal implementation**
- Implement task CRUD endpoints with typed validation.
- Implement run/report endpoints with pagination and filters.
- Implement global variable APIs with encryption + masked readback for secrets.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_mobile_special_tasks_api.py backend/tests/api/test_mobile_special_reports_api.py backend/tests/api/test_global_variables_api.py -q`
- Expected: PASS.

### Task 9: Extend frontend API client and app navigation

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Validation: `frontend/package.json`

**Step 1: Define the focused validation target**
- Use `npm run type-check` because no dedicated frontend test harness exists yet.

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: current app has no Android专项 route types, API client types, or grouped menu structure.

**Step 3: Write minimal implementation**
- Add API client modules/types for global variables, special tasks, runs, summaries, samples, incidents, and artifacts.
- Refactor the left nav into grouped menus that align with the target product: 测试资产 / UI 自动化 / 专项测试 / 调度与分析 / 系统管理.
- Add routes for task lists, report center, and report detail pages.

**Step 4: Re-run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

### Task 10: Build the asset pages and task-center pages

**Files:**
- Create: `frontend/src/views/system/GlobalVariableLibrary.vue`
- Create: `frontend/src/views/mobile-special/SpecialTaskListView.vue`
- Create: `frontend/src/views/mobile-special/SpecialTaskDrawer.vue`
- Create: `frontend/src/components/mobile-special/SpecialTaskConfigForm.vue`
- Modify: `frontend/src/views/device/DeviceList.vue` if device tags/groups are added
- Modify: `frontend/src/views/apk/ApkList.vue` if package metadata display is expanded
- Validation: `frontend/package.json`

**Step 1: Define the validation target**
- Validate with `npm run type-check` and route-level smoke checks after implementation.

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: there are no pages for global variable library or Android专项 task definitions.

**Step 3: Write minimal implementation**
- Build the 全局变量库 page with project filter, masked values, create/edit dialog, and secret toggle.
- Build the Android专项任务 page with list filters, enable/disable scheduling, run-now action, and create/edit drawer.
- The task form must support:
  - task type
  - app package / APK
  - device selection
  - source mode (`apk_only`, `case`, `suite`, `monkey`)
  - sampling interval / duration / interval ms / performance monitoring toggles

**Step 4: Re-run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

### Task 11: Build the report center and detail pages

**Files:**
- Create: `frontend/src/views/mobile-special/ReportCenterView.vue`
- Create: `frontend/src/views/mobile-special/PerformanceReportDetailView.vue`
- Create: `frontend/src/views/mobile-special/StabilityReportDetailView.vue`
- Create: `frontend/src/views/mobile-special/FluencyReportDetailView.vue`
- Create: `frontend/src/components/mobile-special/MetricKpiCards.vue`
- Create: `frontend/src/components/mobile-special/MetricTrendChart.vue`
- Create: `frontend/src/components/mobile-special/IncidentTable.vue`
- Create: `frontend/src/components/mobile-special/TaskInfoPanel.vue`
- Validation: `frontend/package.json`

**Step 1: Define the validation target**
- Validate with `npm run type-check` and manual route smoke verification.

**Step 2: Verify current gap**
- Run: `cd frontend && npm run type-check`
- Expected: report center and Android专项 detail pages do not exist yet.

**Step 3: Write minimal implementation**
- Build a report center with filters by project, app package, task type, date range, and status.
- Build report detail pages that render:
  - status card
  - average CPU / peak CPU
  - average memory / peak memory
  - crash count / ANR count
  - metric trend charts with dual axis support
  - task information panel
  - incident table
  - artifact download actions
- Match the reference page structure first; refine styling after data correctness is stable.

**Step 4: Re-run validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

### Task 12: Add export, dashboard aggregation, and runtime UX polish

**Files:**
- Modify: `backend/app/api/v1/statistics.py`
- Modify: `backend/app/api/v1/ws.py` if live progress events are added
- Modify: `frontend/src/views/dashboard/DashboardView.vue`
- Modify: `frontend/src/views/mobile-special/ReportCenterView.vue`
- Test: `backend/tests/api/test_mobile_special_statistics.py`
- Validation: `frontend/package.json`

**Step 1: Write the failing test**
- Add API tests that prove special-run summary data can be aggregated by project and date range.

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/api/test_mobile_special_statistics.py -q`
- Expected: FAIL because Android专项 statistics are not included yet.

**Step 3: Write minimal implementation**
- Add optional Android专项 aggregation endpoints or extend the dashboard with dedicated cards and trend series.
- Add export links for raw metric CSV, incident JSON, and task summary JSON.
- Add WebSocket/live polling hooks for running task progress if it can be delivered without destabilizing current run pages.

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/api/test_mobile_special_statistics.py -q`
- Expected: PASS.

### Task 13: Final verification, docs, and rollout notes

**Files:**
- Modify: `README.md`
- Modify: `Task.md`
- Create: `docs/android-special-testing.md`
- Create if needed: `docs/mobile-special-api.md`

**Step 1: Run focused backend regression suites**
- Run: `pytest backend/tests/migrations/test_mobile_special_migration.py backend/tests/api/test_mobile_special_schema.py backend/tests/services/test_mobile_special_collectors.py backend/tests/services/test_mobile_special_parsers.py backend/tests/worker/test_android_perf_executor.py backend/tests/worker/test_android_stability_executor.py backend/tests/worker/test_android_fluency_executor.py backend/tests/worker/test_mobile_special_tasks.py backend/tests/api/test_mobile_special_tasks_api.py backend/tests/api/test_mobile_special_reports_api.py backend/tests/api/test_global_variables_api.py backend/tests/api/test_mobile_special_statistics.py -q`
- Expected: PASS.

**Step 2: Run adjacent existing regressions**
- Run: `pytest backend/tests/services/test_adb_service.py backend/tests/services/test_device_sync.py backend/tests/worker/test_android_executor.py backend/tests/worker/test_android_lowcode_executor.py backend/tests/api/test_apks_streaming.py backend/tests/api/test_statistics.py -q`
- Expected: PASS.

**Step 3: Run frontend validation**
- Run: `cd frontend && npm run type-check`
- Expected: PASS.

**Step 4: Update docs and rollout notes**
- Document Android专项 task types, required ADB capabilities, permissions, artifact retention, and known limitations.
- Update `Task.md` with the new module checklist.
- Update `README.md` navigation and capability summary.

---

## Recommended implementation order

1. Task 1–3 first: schema + contract + collectors
2. Task 4–8 second: executors + scheduler + APIs
3. Task 9–11 third: navigation + task center + report UI
4. Task 12–13 last: aggregation, exports, docs, final verification

## Recommended release slices

- **Slice A:** 数据模型 + 性能任务 + 性能报告
- **Slice B:** 智能稳定性任务 + incident pipeline + 稳定性报告
- **Slice C:** 流畅度任务 + FPS/Jank timeline + 流畅度报告
- **Slice D:** 全局变量库 + 报告中心 + 定时任务整合 + 看板汇总

## Explicit non-goals for this plan

- iOS 专项测试
- 云真机调度平台
- 视频录制剪辑分析
- 自动生成可维护的 Android 低代码回放脚本
- 全量替换现有 `TestPlan` / `RunDetail` / `Dashboard` 数据模型

