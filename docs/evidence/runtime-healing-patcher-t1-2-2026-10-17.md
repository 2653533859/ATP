# T1.2 运行时失败拦截与自愈补丁应用器服务验收 (2026-10-17)

## 概述与交付物

T1.2（运行时失败拦截与自愈补丁应用器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.5.0 Phase 1 第二个核心自愈里程碑**：
1. **运行时失败拦截与现场热替换引擎 (`backend/app/services/runtime_healing_patcher.py`)**：
   - `intercept_and_heal_step()`：在用例步骤执行抛出定位器未找到异常时拦截执行线程；
   - 提取现场失败上下文，实时调用多模态定位器自愈推导引擎；
   - 若最优候选置信度达到门限（默认 `0.65`），现场热替换新定位器，生成 `SelfHealingPatchRecord` 补丁记录，裁决为 `HEALED_AND_RESUMED`；
   - 若无法高置信度自愈，保持原状快速失败，裁决为 `HEALING_FAILED`；
   - 自动建立步骤自愈索引缓存（`_STEP_PATCH_INDEX`），同一步骤再次执行时实现零延迟复用放行。
2. **自愈补丁全生命周期状态机 (`PatchStatus`)**：
   - `PROPOSED`（推导生成待审）➔ `APPLIED_IN_FLIGHT`（运行时现场热生效）➔ `COMMITTED_PERMANENT`（永久固化回写用例库）或 `REJECTED`（人工/策略否决回滚）。
3. **补丁采纳与回滚管理**：
   - `commit_healing_patch()`：一键将补丁固化至永久库并更新采纳时间戳；
   - `reject_healing_patch()`：回滚补丁并清除步骤索引缓存。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_runtime_healing_patcher.py`：3 passed（运行时现场自愈成功与缓存快速命中、无候选控件时自愈终止安全降级、补丁确认采纳与否决回滚生命周期验证）；
   - **通过率**：**3/3 passed in 0.27s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
