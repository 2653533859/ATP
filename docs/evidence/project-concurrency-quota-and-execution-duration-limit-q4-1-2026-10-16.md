# Q4.1 项目级并发配额与执行时长硬限制验收（2026-10-16）

## 概述与结论

Q4.1（项目级并发配额与执行时长硬限制）已完成全量代码演进与自动化质量验证：
1. **多租户项目资源配额数据模型 (`ProjectQuota` & Alembic `20261016_0082`)**：
   - 建立 `project_quotas` 表，为每个项目分配：
     - `max_concurrent_runs`：项目最大并行活跃任务数（默认 5，支持 1-100）；
     - `daily_duration_limit_seconds`：每日执行总时长配额（默认 28800s / 8 小时）；
     - `max_single_run_timeout_seconds`：单任务执行硬超时上限（默认 3600s / 1 小时）；
     - `over_quota_policy`：并发超额控制策略（`reject` 立即拒绝或 `queue` 排队等待）；
     - `is_enabled`：配额管控启用开关。
2. **多租户配额准入与自适应控制引擎 (`project_quota_manager.py`)**：
   - **实时活跃任务聚合计数 (`count_project_active_runs`)**：跨测试套件（SuiteRun）、测试计划（PlanRun）与性能压测（PerformanceRun）统计当前项目并发执行任务；
   - **每日累计运行时长核算 (`calculate_project_daily_duration_seconds`)**：精确汇总今日在执行与已结束任务的 CPU/执行秒数；
   - **调度准入判定 (`evaluate_project_dispatch_quota`)**：
     - 并发达到上限时，依据配置策略执行 `reject`（拒绝）或 `queue`（加入排队）；
     - 每日累计时长耗尽时，安全拒绝调度并给出耗尽明细与次日解冻提示；
   - **僵尸长任务硬超时收割器 (`scan_and_reap_timed_out_runs`)**：实时扫描超过 `max_single_run_timeout_seconds` 的僵尸任务，自动熔断取消并释放占用资源。
3. **REST API 统一扩展 (`api/v1/projects.py`)**：
   - `GET /api/v1/projects/{project_id}/quota`：获取项目资源配额设置；
   - `PUT /api/v1/projects/{project_id}/quota`：管理员动态调优项目配额；
   - `GET /api/v1/projects/{project_id}/quota/evaluation`：实时评估配额占用与调度准许状态；
   - `POST /api/v1/projects/{project_id}/quota/reap-timeouts`：主动清理硬超时任务。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_project_quota_manager.py`：**7 passed in 0.65s**（覆盖默认配额初始化、参数边界校验、正常准入放行、并发饱和拒绝/排队策略、每日时长超额拦截、单任务硬超时判定、僵尸任务自动收割等场景）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 215 source files**；
   - Alembic 迁移链：`20261016_0082` 紧随 `20261015_0081` 成为最新 Head，结构完全对齐。
