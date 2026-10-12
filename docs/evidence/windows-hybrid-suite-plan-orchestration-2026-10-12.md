# N2.3 混合串行套件与手动计划编排证据（2026-10-12）

## 概述与结论

N2.3（混合串行套件与手动计划，串联父子运行和报告）已完成代码检查与定向回归验证。
覆盖：
1. **API / Web 混合套件串行执行**：
   - 在本地单机模式（`settings.ATP_LOCAL_MODE=True`）下，套件执行模式强制收敛为 `sequential`，依次执行 API 与 Web 用例；
   - 子用例运行记录完整保留在 `SuiteRun.case_run_ids` 中，父套件正确生成综合 `result_summary`。
2. **计划与套件失败策略（fast-fail vs continue）**：
   - 在 `fast-fail` 策略下，首个子用例或子套件失败后，立即安全中断执行并将后续未执行项标记为 `skipped`；
   - 在 `continue` 策略下，允许后续用例继续执行并完成综合统计。
3. **单线程执行取消与防死锁**：
   - 本地单机队列模式下，父计划（Plan）调用子套件（Suite）、子套件调用子用例（Case）全程在单工作线程中**内联串行推进**（`execute_suite_inline` 与 `execute_case_fn`），避免将子任务作为独立任务重新入队导致与父任务争抢单工作线程发生父子等待死锁；
   - 收到取消信号（`is_group_cancelled`）时，当前与后续子项平稳收敛为 `skipped`，父运行立即退出，无死锁、无挂起。
4. **服务器原并发路由保留**：
   - 在服务器模式（`settings.ATP_LOCAL_MODE=False`）下，用户配置的 `execution_mode="parallel"` 及 `max_workers` 得到完整保留，异构队列（如 Android/维护队列）正常通过 Celery Worker 路由。

## 测试与代码清单

- `backend/tests/services/test_n2_3_hybrid_suite_and_plan.py`：新建 N2.3 专用 5 项自动化回归，涵盖混合套件串行执行、fast-fail 截断、计划编排、单线程取消防死锁以及服务器并发保留，5 passed in 0.75s。
- `backend/tests/worker/test_suite_execution_config.py` 与 `test_plan_execution_config.py`：共 18 项配置契约回归全量通过。

## 质量门禁与验证

1. **定向测试**：5 passed in 0.75s，零报警，独立运行通过。
2. **静态质量**：`ruff check`、`ruff format`、`mypy` 188 个源文件全部通过。
