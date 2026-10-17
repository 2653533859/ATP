# T1.3 增量影响面计算与精准用例推荐 REST API 服务验收 (2026-10-17)

## 概述与交付物

T1.3（增量影响面计算与精准用例推荐 REST API 服务）已全量研发交付并通过各项工程门禁，**标志着 ATP v5.7.0 Phase 1（代码变更 AST 影响面追踪与符号依赖映射器）全量大闭环**：
1. **API 模块设计与路由挂载 (`backend/app/api/v1/precision_regression_api.py`)**：
   - 挂载路由前缀 `/api/v1/precision-regression/*` 至系统核心路由树；
   - `POST /api/v1/precision-regression/diff/analyze`：在线解析代码补丁，基于 Python AST 识别受影响符号；
   - `POST /api/v1/precision-regression/recommend`：根据变更高危符号列表正向拓扑扩散，输出最小推荐回归用例集与节省耗时估算；
   - `POST /api/v1/precision-regression/analyze-and-recommend`：端到端一站式直连：从 Git Diff 到最小受影响用例集；
   - `GET /api/v1/precision-regression/coverage/{case_id}`：反向追溯查询单个用例底层覆盖的接口端点与代码符号；
   - `POST /api/v1/precision-regression/lineage/register`：动态注册符号-接口-用例血缘拓扑节点。
2. **中枢架构打通**：
   - 为后续 Phase 3 抽屉组件（`CaseDagTopologyDrawer.vue`）与中枢页面（`PrecisionRegressionWorkbenchView.vue`）提供标准强类型 REST API 数据契约。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_code_diff_symbol_extractor.py`：3 passed；
   - `backend/tests/services/test_symbol_call_graph_mapper.py`：5 passed；
   - `backend/tests/api/test_precision_regression_api.py`：4 passed（Diff 分析、用例推荐与裁剪率计算、端到端一站式推荐、血缘反向覆盖与动态注册）；
   - **Phase 1 后端测试总通过率**：**12 passed across 3 test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：3/3 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**7 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
