# T1.3 代码覆盖率与增量染色 REST API 服务验收 (2026-10-18)

## 概述与交付物

T1.3（代码覆盖率与增量染色 REST API 服务）已全量研发交付并通过各项工程门禁，**正式达成 ATP v5.9.0 Phase 1（多源覆盖率数据摄取与增量 Diff 行级染色引擎）100% 全量大闭环**：
1. **完整 RESTful 端点群 (`backend/app/api/v1/code_coverage_api.py`)**：
   - 挂载路由前缀：`/api/v1/code-coverage/*`，统一注册进 `backend/app/api/v1/router.py`；
   - `POST /api/v1/code-coverage/ingest`：多源覆盖率报告上报与解析（支持 Coverage.py JSON、LCOV 与 JaCoCo XML 格式）；
   - `POST /api/v1/code-coverage/diff-staining`：结合 Git Unified Diff 补丁动态计算增量代码覆盖率（`overall_diff_line_coverage_pct` 与 `overall_diff_branch_coverage_pct`）；
   - `GET /api/v1/code-coverage/reports`：列出已归档的统一覆盖率报告；
   - `GET /api/v1/code-coverage/reports/{report_id}`：获取指定覆盖率详情与文件覆盖汇总；
   - `GET /api/v1/code-coverage/files/staining`：查询指定变更源码文件逐行高亮染色（红/黄/绿）数据。
2. **测试隔离与初始种子数据**：
   - 内置 `_load_seed_coverage_data()` 与 `clear_coverage_store()`，保证开箱即用与测试隔离。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/api/test_code_coverage_api.py`：3 passed（报告列表与详情查询及 404 防呆、多格式覆盖率上报解析与 400 校验、增量染色计算与单文件逐行染色详情查询）；
   - **Phase 1 整体套件**：**11 passed in 4.78s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：3/3 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**5 files already formatted.**；
   - `mypy`：**Success: no issues found in 3 source files.**。
