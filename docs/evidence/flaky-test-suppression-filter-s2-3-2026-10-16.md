# S2.3 CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离过滤器验收 (2026-10-16)

## 概述与结论

S2.3（CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离过滤器）已完成全量交付与验证，至此 **ATP v3.6.0 Phase 2（动态测试切片并发调度与变更风险指数模型）100% 达成全量大闭环**：
1. **Flaky 用例自适应抑制隔离服务 (`backend/app/services/flaky_test_suppression_filter.py`)**：
   - **抖动指数判定算法 (`flakiness_score`)**：
     - 在历史执行轮次 $\ge 4$ 的样本中，基于失败率接近 50% 程度量化统计不确定性与偶发抖动率；
   - **多模态抑制过滤处置策略 (`FlakyFilterMode`)**：
     - `AUTO_ADAPTIVE`（自动自适应）：高频严重抖动（$\ge 0.75$）用例自动隔离移出主干 CI 队列，轻中度偶发抖动用例保留并附加 2 次退避重试保护；
     - `QUARANTINE_STRICT`（严格隔离）：只要检测到抖动一律移至隔离观察队列；
     - `RETRY_ONLY`（仅重试）：全部保留在主干并附加重试；
   - **人工治理覆盖表联动 (`register_flaky_governance_override`)**：
     - 优先遵循工程治理白名单/工单覆盖规则，保证环境已知问题平滑跳过；
   - **隔离与执行集划分 (`FlakySuppressionReport`)**：
     - 精确输出主干阻塞执行用例集 `actionable_case_ids` 与隔离观察用例集 `quarantined_case_ids`，计算抑制率 `suppression_ratio_pct`。
2. **REST API 端点统一扩展 (`backend/app/api/v1/ci_impact.py`)**：
   - `POST /api/v1/ci-impact/flaky-filter/filter`：提交待评估用例集，返回自适应隔离报告；
   - `GET /api/v1/ci-impact/flaky-filter/reports`：历史隔离报告列表查询；
   - `GET /api/v1/ci-impact/flaky-filter/reports/{filter_id}`：获取指定隔离报告详情；
   - `POST /api/v1/ci-impact/flaky-filter/governance/override`：注册用例级人工治理策略覆盖。

## 质量与测试门禁验证

1. **单元测试 (`pytest`)**：
   - `backend/tests/services/test_flaky_test_suppression_filter.py`：**4 passed in 0.32s**（覆盖稳固用例放行、中度抖动自动附加重试、重度抖动自适应隔离、严格/重试模式切换、人工治理覆盖优先级）；
   - Phase 1 & 2 全量单测：**21 passed in 1.1s**；
   - `scripts/pytest-standalone-sweep.py`：**100% 独立通过**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 260 source files**。
