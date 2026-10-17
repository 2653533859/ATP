# T1.2 接口-函数-用例三维调用链拓扑映射引擎服务验收 (2026-10-17)

## 概述与交付物

T1.2（接口-函数-用例三维调用链拓扑映射引擎服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.7.0 Phase 1 第二个核心符号血缘拓扑映射里程碑**：
1. **三维调用拓扑图谱核心引擎 (`backend/app/services/symbol_call_graph_mapper.py`)**：
   - 建立代码符号（`Symbols`）➔ 服务接口（`Endpoints`）➔ 测试用例（`Test Cases`）三维网状可达性拓扑图；
   - **正向拓扑扩散推导 (`trace_impacted_cases`)**：
     - 当输入变更高危符号列表（如 `calculate_discount`、`UserService.authenticate`）时，通过广度优先拓扑扩散，毫秒级定位受影响接口端点与下游测试用例集；
     - 自动组装完整的端到端调用溯源链（`call_lineage`，如 `discount.calculate_discount ➔ POST /api/v1/orders/checkout ➔ case_order_checkout_flow`）；
     - 自动计算增量用例精准裁剪率（`regression_reduction_ratio`）与估算节省回归耗时；
   - **反向覆盖追溯 (`trace_case_symbol_coverage`)**：
     - 支持反向查询任意单个测试用例底层覆盖的所有接口端点与底层代码符号清单。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_symbol_call_graph_mapper.py`：5 passed（种子血缘与自定义注册、优惠券多接口多用例拓扑扩散演练、用户认证单接口多用例扩散、反向用例代码符号覆盖追溯、分析报告字典序列化）；
   - **通过率**：**5 passed in 0.29s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
