# S3.2 变异体执行检验与捕获/存活状态判定执行器验收 (2026-10-16)

## 概述与结论

S3.2（变异体执行检验与捕获/存活状态判定执行器）已完成全量交付与验证：
1. **安全沙箱动态编译与检验执行引擎 (`backend/app/services/mutation_execution_runner.py`)**：
   - **四态判定模型 (`MutantStatus`)**：
     - `KILLED`（已捕获/被杀死）：测试用例发生 `AssertionError` 断言失败或抛出未预期异常，说明测试用例断言有效，成功阻止了篡改逻辑逃逸；
     - `SURVIVED`（存活/漏过）：变异后测试用例依然全量返回 PASS，暴露测试用例存在**虚假通过、断言缺失**的严重盲区；
     - `TIMED_OUT`（超时）：变异引发死循环，受控中断并标记；
     - `ERROR`（编译损坏）：变异环境损坏；
   - **动态沙箱执行隔离 (`_execute_test_against_mutant_code`)**：
     - 隔离的独立沙箱作用域中动态 `exec` 编译变异体代码，驱动测试用例执行；
     - 精准记录捕获该变异体的测试用例 ID（`killing_test_case_id`）与具体错误消息；
   - **全量执行报告度量 (`MutationExecutionRunReport`)**：
     - 输出测试变异体总数、击毙数、存活数、捕获率（`kill_rate_pct`）以及存活变异体 ID 列表（`survived_mutant_ids`），为研发补充有效断言提供精确定位。
2. **REST API 端点统一扩展 (`backend/app/api/v1/ci_impact.py`)**：
   - `POST /api/v1/ci-impact/mutations/execute/run`：驱动测试集执行变异体检验并返回 Killed / Survived 报告；
   - `GET /api/v1/ci-impact/mutations/execute/reports`：历史变异执行报告列表查询；
   - `GET /api/v1/ci-impact/mutations/execute/reports/{run_id}`：获取指定变异执行报告详情。

## 质量与测试门禁验证

1. **单元测试 (`pytest`)**：
   - `backend/tests/services/test_mutation_execution_runner.py`：**3 passed in 0.25s**（覆盖严密断言成功击毙变异体、无断言用例导致变异体存活、击毙率与报告检索）；
   - Phase 1 ~ Phase 3 联合单测：**28 passed in 1.65s**；
   - `scripts/pytest-standalone-sweep.py`：**100% 独立通过**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 262 source files**。
