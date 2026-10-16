# S1.2 代码函数/端点与自动化测试用例双向依赖映射索引引擎验收 (2026-10-16)

## 概述与结论

S1.2（代码函数/端点与自动化测试用例双向依赖映射索引引擎）已完成全量交付与验证：
1. **核心倒排索引引擎 (`backend/app/services/code_to_test_mapping_indexer.py`)**：
   - **双向数据结构定义 (`TestCaseRef`)**：定义测试用例 ID、名称、类型（`api` / `web` / `android` / `ios`）、优先级（`P0` - `P3`）、项目归属、目标端点集合与目标代码符号集合；
   - **符号与路由倒排索引 (`CodeToTestMappingIndexer`)**：
     - `symbol_to_cases`：按代码符号（如 `app/api/orders.py:OrderService.checkout`）建立倒排索引；
     - `route_to_cases`：按 HTTP Method + Path 归一化路由键（如 `POST /api/v1/orders/create`，大小写不敏感与斜线清理）建立倒排索引；
     - `file_to_cases`：按文件路径泛化兜底建立倒排索引；
   - **智能用例步骤解析 (`auto_index_from_steps`)**：自动解析用例各步骤中的 HTTP 请求方法与 URL，自动抽取纯路径并完成索引装配；
   - **多维逆向影响面查询 (`query_affected_cases`)**：
     - 支持混合输入变更符号、变更路由或变更文件反查受影响用例；
     - 自动去重并按业务优先级严格升序排序（`P0 > P1 > P2 > P3`）；
     - 支持项目级多租户边界隔离过滤（`project_id`）。
2. **REST API 扩展 (`backend/app/api/v1/ci_impact.py`)**：
   - `POST /api/v1/ci-impact/mapping/bind`：显式注册用例与代码符号、API 端点的依赖映射；
   - `POST /api/v1/ci-impact/mapping/auto-index-steps`：从用例步骤数据中自动提取请求 URL 并建索引；
   - `POST /api/v1/ci-impact/mapping/query-affected`：依据变更符号/路由反查波及用例；
   - `GET /api/v1/ci-impact/mapping/stats`：查询图谱总体统计（用例数、符号数、路由数、文件数）。

## 质量与测试门禁验证

1. **单元测试 (`pytest`)**：
   - `backend/tests/services/test_code_to_test_mapping_indexer.py`：**4 passed in 0.16s**（覆盖代码符号反查、API 路由归一化匹配、用例步骤自动索引、用例去重与优先级排序、项目边界隔离）；
   - Phase 1 联合单测：**8 passed in 0.32s**；
   - `scripts/pytest-standalone-sweep.py`：**100% 独立通过**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 256 source files**。
