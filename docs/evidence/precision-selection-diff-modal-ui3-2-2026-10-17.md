# UI3.2 增量用例推荐与影响分析对比模拟弹窗前端验收 (2026-10-17)

## 概述与交付物

UI3.2（增量用例推荐与影响分析对比模拟弹窗）已全量研发交付并通过各项工程门禁，**达成 ATP v5.7.0 Phase 3 第二个前端交互核心里程碑**：
1. **精准推荐与影响面模拟弹窗组件 (`frontend/src/views/workbench/components/PrecisionSelectionDiffModal.vue`)**：
   - **头部对比统计看板**：
     - 用例裁剪节省率（`reductionRatio` 如 `97.0%`）；
     - 预估节约回归耗时（`timeSavedMinutes` 如 `16.2m`）；
     - 增量推荐用例数 vs 全量套件规模（如 `3 / 100`）；
     - 符号与接口影响面统计（如 `1 符号 / 2 接口`）；
   - **Tab 1: 增量推荐用例集 (Recommended Cases)**：
     - 表格呈现推荐回归用例列表，展示优先级标签（`P0`、`P1`、`P2`）、预估耗时、波及接口以及端到端调用溯源链（`call_lineage`）；
     - 支持交互式多选与全选/清空选择控制；
   - **Tab 2: AST 变更高危符号树 (Changed Symbols)**：
     - 展示底层变动的 Python 函数/类全限定名、文件路径、变迁类型（`SIGNATURE_CHANGED`、`MODIFIED`）、高危严重度与参数签名定义；
   - **操作闭环**：支持“一键派发增量精准回归”（分发选中的用例 ID 列表并触发执行）。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/PrecisionSelectionDiffModal.spec.ts`：2 passed（指标看板、裁剪率与用例列表渲染核验、一键派发增量精准回归事件分发核验）；
   - **通过率**：**2 passed in 3.08s (100% PASS)**。
2. **前端工程质量**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (21.03s)**；
   - `npm run build` (`vite build`)：**4589 modules transformed, built in 3.88s, 0 errors!**。
