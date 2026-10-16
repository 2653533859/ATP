# T2.1 Sagas/TCC 分布式事务流转跟踪与悬挂事务探测器验收 (2026-10-16)

## 概述与结论

T2.1（Sagas/TCC 分布式事务流转跟踪与悬挂事务探测器）已完成全量交付与验证，正式开启 **ATP v4.0.0 Phase 2（微服务分布式事务与跨系统数据最终一致性稽核）**：
1. **核心服务实现 (`backend/app/services/saga_transaction_state_tracker.py`)**：
   - 深入建模分布式事务模式：支持 `TCC`（Try - Confirm - Cancel）与 `SAGA`（Forward - Compensate）双模态状态机；
   - 建立全局事务（`GlobalTxRecord`）与子分支事务（`BranchTxRecord`）的级联关联与全生命周期状态流转跟踪；
   - 核心异常模式探测算法：
     - **悬挂事务 (HANGING_TRANSACTION)**：网络重试迟滞导致 Cancel 补偿请求先于 Try 执行，晚到的 Try 产生永久资源冻结；
     - **空补偿 (EMPTY_COMPENSATION)**：未曾执行 Try/Forward 却直接收到 Cancel/Compensate 请求；
     - **超时未决 (TIMEOUT_PENDING)**：分支事务长期处于 PENDING 未决状态且超过全局事务超时阈值；
     - **部分提交失败 (PARTIAL_COMMIT_FAILURE)**：部分分支已确认提交但存在未补偿的失败分支，引发跨服务数据撕裂；
   - 自动化输出一致性状态裁决（COMMITTED / ROLLED_BACK / HANGING / INCONSISTENT / TIMEOUT）与针对性加固指导。
2. **REST API 接入 (`backend/app/api/v1/saga_transaction_tracker.py`)**：
   - 挂载路由前缀 `/consistency/saga`：
     - `POST /consistency/saga/transactions`：注册全局事务上下文；
     - `POST /consistency/saga/branches`：上报微服务分支事务阶段与执行耗时；
     - `GET /consistency/saga/transactions/{global_tx_id}/audit`：审计特定事务一致性与悬挂隐患；
     - `GET /consistency/saga/hanging`：探测全网未决、悬挂或一致性撕裂事务列表；
     - `POST /consistency/saga/simulate`：仿真典型分布式事务场景（hanging / empty_compensation / timeout / normal）；
     - `DELETE /consistency/saga/transactions`：清空事务缓存仓库（需工程师权限）；
   - 并在 `backend/app/api/v1/router.py` 中稳定接入全局 API 路由表。

## 质量与测试门禁验证

1. **自动化单元测试 (`backend/tests/services/test_saga_transaction_state_tracker.py`)**：
   - 6 项测试全部通过（**6 passed in 0.29s**）：
     - `test_normal_tcc_transaction_commit`：验证全部分支 Try/Confirm 正常提交与 COMMITTED 最终一致性；
     - `test_hanging_transaction_detection`：验证 Cancel 先行与晚到 Try 的悬挂异常探测与防悬挂加固指引；
     - `test_empty_compensation_detection`：验证无 Try 记录时的空补偿检测；
     - `test_partial_commit_inconsistency_detection`：验证部分提交失败与数据撕裂判定；
     - `test_rollback_consistency`：验证失败后补偿成功的 ROLLED_BACK 一致性；
     - `test_simulate_saga_scenarios_and_list_hanging`：验证场景仿真与全网悬挂事务列表探测。
2. **独立文件执行**：
   - `python scripts/pytest-standalone-sweep.py` 单文件独立执行 **1 passed, 0 failed (100% PASS)**。
3. **代码规范与格式化**：
   - `ruff check` 与 `ruff format --check` 全部通过，零代码异味。
4. **静态类型安全**：
   - `mypy backend/app/services/saga_transaction_state_tracker.py` **Success: no issues found in 1 source file**。
