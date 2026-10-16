# T3.2 接口契约字段级兼容性差分与 Breaking 破坏性评级引擎验收 (2026-10-16)

## 概述与结论

T3.2（接口契约字段级兼容性差分与 Breaking 破坏性评级引擎）已完成全量交付与验证：
1. **服务层落地 (`backend/app/services/contract_drift_breaking_evaluator.py`)**：
   - 建立非对称破坏性评级规则模型：
     - `BreakingLevel`（`BREAKING` 阻断性破坏变更 | `WARNING` 潜在风险告警 | `COMPATIBLE` 完全兼容）；
     - `DriftChangeType`（`FIELD_REMOVED`、`FIELD_ADDED`、`TYPE_CHANGED`、`REQUIRED_ADDED`、`REQUIRED_REMOVED`、`ENUM_RESTRICTED`、`ENUM_EXPANDED`）；
   - 请求体与响应体双向非对称差异判定：
     - 请求体：新增必填字段（`REQUIRED_ADDED`）、字段类型改变（`TYPE_CHANGED`）、枚举值缩减（`ENUM_RESTRICTED`）判定为 `BREAKING`；新增可选字段为 `COMPATIBLE`；
     - 响应体：删除任何既有字段（`FIELD_REMOVED`）、类型漂移判定为 `BREAKING`；新增字段判定为 `WARNING`；
   - 契约兼容性得分算法（`compatibility_score_pct` 0.0 ~ 100.0%）：
     - 满分 100 分，按破坏性差异项扣减权重，输出结构化报告 `ContractDriftEvaluationReport`。
2. **REST API 端点落地 (`backend/app/api/v1/live_contract_evaluator.py` & `backend/app/api/v1/router.py`)**：
   - `POST /api/v1/contract-guard/evaluate/compare`：提交两份契约对象或 Schema 直接比对兼容性；
   - `POST /api/v1/contract-guard/evaluate/by-contract-ids`：根据两个已提取或录入的契约 ID 执行破坏性变更评级；
   - `GET /api/v1/contract-guard/evaluate/reports`：查询历史契约破坏性变更评估报告列表；
   - `GET /api/v1/contract-guard/evaluate/reports/{evaluation_id}`：获取指定契约破坏性评估报告详情；
   - `DELETE /api/v1/contract-guard/evaluate/reports`：清空报告缓存。

## 质量与测试门禁验证

1. **后端单元测试 (`pytest`)**：
   - `backend/tests/services/test_contract_drift_breaking_evaluator.py`：**4 passed in 0.33s**；
   - 涵盖请求体必填项新增/类型改变/枚举缩减破坏性判定、响应体字段删除阻断/新增告警判定、完全一致契约 100 分裁决与报告持久化。
2. **单测独立运行验证**：
   - `scripts/pytest-standalone-sweep.py`：**1/1 passed standalone (100%)**。
3. **代码规范与格式化**：
   - `ruff check`：**All checks passed**；
   - `ruff format --check`：**All checks passed**。
4. **静态强类型检查**：
   - `mypy`：**Success: no issues found in 2 source files**。
