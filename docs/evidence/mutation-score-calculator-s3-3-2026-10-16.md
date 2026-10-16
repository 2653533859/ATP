# S3.3 用例断言有效性量化与变异得分计算器验收 (2026-10-16)

## 概述与结论

S3.3（用例断言有效性量化与变异得分计算器）已完成全量交付与验证，至此 **ATP v3.6.0 Phase 3（代码变异测试与断言有效性评分引擎）100% 达成全量大闭环**：
1. **断言有效性量化与盲区定位核心服务 (`backend/app/services/mutation_score_calculator.py`)**：
   - **变异得分标准计算公式 (`calculate_mutation_score`)**：
     $$\text{Mutation Score} = \frac{\text{Killed Mutants} + \text{TimedOut Mutants}}{\text{Total Mutants}} \times 100\%$$
   - **四级断言充分性成熟度等级 (`AssertionAdequacyLevel`)**：
     - `EXCELLENT`（卓越断言，$\ge 85\%$）：测试集具备深度断言，能有效拦截绝大多数篡改；
     - `ADEQUATE`（充分合格，$70\% \sim 84.9\%$）：满足常规发版准入要求；
     - `INSUFFICIENT`（欠缺改进，$50\% \sim 69.9\%$）：半数代码变异未被发现；
     - `WEAK`（脆弱虚设，$< 50\%$）：大量变异体存活，存在“只调用、无断言”的严重虚假通过盲区；
   - **算子细分捕获率度量 (`OperatorScoreBreakdown`)**：
     - 分别统计 ROR（关系反转）、LCR（逻辑替换）、AOR（算术变异）、RVO（返回值篡改）、BVO（边界偏移）的各自变异得分；
   - **断言盲区精准归因与修复指引 (`AssertionBlindspotItem`)**：
     - 罗列所有存活变异体对应的文件、代码行号、原代码与篡改代码；
     - 自动输出针对性断言修复建议（如：`针对返回值篡改建议增加 assert res == expected`）。
2. **REST API 端点统一扩展 (`backend/app/api/v1/ci_impact.py`)**：
   - `POST /api/v1/ci-impact/mutations/score/calculate`：提交变异执行 Run ID，计算变异得分并输出断言盲区报告（`MutationScoreReport`）；
   - `GET /api/v1/ci-impact/mutations/score/reports`：历史变异得分报告列表查询；
   - `GET /api/v1/ci-impact/mutations/score/reports/{score_id}`：获取指定变异得分报告详情。

## 质量与测试门禁验证

1. **单元测试 (`pytest`)**：
   - `backend/tests/services/test_mutation_score_calculator.py`：**4 passed in 0.26s**（覆盖卓越断言 100% 得分、脆弱断言 25% 识别与盲区修复建议提取、端到端变异体执行到得分计算串联、报告检索）；
   - Phase 1 ~ Phase 3 全量单测：**32 passed in 0.58s**；
   - `scripts/pytest-standalone-sweep.py`：**100% 独立通过**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 263 source files**。
