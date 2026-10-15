# C2.1 测试资产全景引用拓扑图谱与反向索引引擎验收（2026-10-16）

## 概述与结论

C2.1（测试资产全景引用拓扑图谱与反向索引引擎）已完成全量交付与验证，正式拉开 **v3.2.0 Phase 2（全域测试资产依赖拓扑与变更影响面智能分析）** 的研发大幕：
1. **测试资产全景分类模型 (`AssetType` & `RelationType`)**：
   - 资产节点覆盖：`plan`（测试计划）、`suite`（测试套件）、`case`（测试用例）、`dataset`（数据集）、`api_endpoint`（接口契约端点）、`device`（设备）、`env`（环境与变量）；
   - 关联边覆盖：`CONTAINS`（包含关系）、`DRIVEN_BY_DATASET`（数据驱动绑定）、`CALLS_API`（接口调用依赖）、`BINDS_DEVICE`（设备绑定）、`USES_ENV`（环境变量引用）。
2. **双向索引图谱引擎 (`AssetGraphIndexer`)**：
   - **正向依赖索引 (`get_downstream_dependencies`)**：从根资产（如 Plan）向下展开所依赖的所有 Suites、Cases、Datasets 与 API Endpoints；
   - **反向消费索引 (`get_upstream_consumers`)**：从底层原子资产（如 Case 或 API）逆向递归推导全部消费方（如哪些 Suite 或 Plan 在消费该用例）；
   - 严格记录图谱遍历深度（`depth`）并采用 `visited` 集合杜绝环形死循环。
3. **未引用孤儿资产实时探测 (`find_orphan_assets`)**：
   - 自动检测并汇总未被任何测试套件或执行计划消费的孤儿测试用例（`orphan_cases`）；
   - 自动检测并汇总未被绑定的冗余无用数据集（`orphan_datasets`），为资产垃圾回收与瘦身提供精准凭证。
4. **REST API 统一扩展 (`api/v1/asset_graph.py` & `router.py`)**：
   - `GET /api/v1/asset-graph/project/{project_id}`：导出指定项目的完整依赖图谱（节点、有向边、资产分布统计与孤儿清单）；
   - `GET /api/v1/asset-graph/asset/{asset_type}/{asset_id}/lineage`：双向追踪指定资产的全链路血缘消费链路；
   - `GET /api/v1/asset-graph/project/{project_id}/orphans`：检测指定项目内的孤儿用例与废弃数据集；
   - `POST /api/v1/asset-graph/reindex`：全量扫描数据库，重构资产拓扑与双向索引。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_asset_graph_indexer.py`：**5 passed in 0.26s**（覆盖图谱构建与节点检索、反向消费方溯源、正向依赖链路展开、孤儿用例/数据集侦测、项目子图导出与统计分型）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 234 source files**。
