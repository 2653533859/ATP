# S3.1 代码变更行一阶语法变异算子注入生成引擎验收 (2026-10-16)

## 概述与结论

S3.1（代码变更行一阶语法变异算子注入生成引擎）已完成全量交付与验证，正式启动 **ATP v3.6.0 Phase 3（代码变异测试与断言有效性评分引擎）** 研发建设：
1. **一阶变异算子注入与代码反解析引擎 (`backend/app/services/code_mutation_operator_engine.py`)**：
   - **多算子变异规则库 (`MutationOperatorType`)**：
     1. **关系运算符反转 (`ROR`)**：`==` $\leftrightarrow$ `!=`、`<` $\leftrightarrow$ `>=`、`>` $\leftrightarrow$ `<=`、`in` $\leftrightarrow$ `not in`、`is` $\leftrightarrow$ `is not`；
     2. **逻辑连接符替换 (`LCR`)**：`and` $\leftrightarrow$ `or`；
     3. **算术运算符替换 (`AOR`)**：`+` $\leftrightarrow$ `-`、`*` $\leftrightarrow$ `//`；
     4. **返回值篡改 (`RVO`)**：`return True` $\rightarrow$ `return False`、表达式返回值置为 `None`；
     5. **边界常数偏移 (`BVO`)**：数值边界整型常数注入 `+1` / `-1` 偏移扰动；
   - **单变异体独立隔离**：每次注入仅对 AST 产生单一突变（一阶变异体），利用 Python 标准库 `ast.unparse` 还原生成高质感、可独立执行的变异源码（`mutated_code`）；
   - **精准变更行约束 (`target_lines`)**：支持严格限定仅在 Git Diff 修改涉及的代码行注入变异体，避免无效的全文件漫射；
   - **健壮性容错**：面对语法损坏源码具备容错降级机制，输出结构化变异体元数据（`MutantItem` 与 `MutationGenerationReport`）。
2. **REST API 端点统一扩展 (`backend/app/api/v1/ci_impact.py`)**：
   - `POST /api/v1/ci-impact/mutations/generate`：提交源码与目标行号，批量安全生成一阶变异体；
   - `GET /api/v1/ci-impact/mutations/reports`：历史变异体生成报告列表查询；
   - `GET /api/v1/ci-impact/mutations/reports/{generation_id}`：获取指定生成报告详情；
   - `GET /api/v1/ci-impact/mutations/{mutant_id}`：获取单个变异体差异代码与原始代码比对。

## 质量与测试门禁验证

1. **单元测试 (`pytest`)**：
   - `backend/tests/services/test_code_mutation_operator_engine.py`：**4 passed in 0.27s**（覆盖 ROR/LCR/RVO 算子注入、限定目标行约束验证、语法损坏容错韧性、变异体存取生命周期）；
   - 全链路 CI-Impact 联合单测：**25 passed in 1.4s**；
   - `scripts/pytest-standalone-sweep.py`：**100% 独立通过**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 261 source files**。
