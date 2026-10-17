# UI3.2 断言漂移演进对比与语法模拟弹窗前端验收 (2026-10-17)

## 概述与交付物

UI3.2（断言漂移演进对比与语法模拟弹窗）已全量研发交付并通过各项工程门禁，**达成 ATP v5.5.0 Phase 3 第二个前端交互核心里程碑**：
1. **断言演进模拟弹窗组件 (`frontend/src/views/workbench/components/AssertionDriftEvolutionModal.vue`)**：
   - **头部指标栏**：呈现演进健康置信分（如 `94.0`）、风险等级标签（`LOW`、`MEDIUM`、`HIGH`）以及是否允许自动合流状态；
   - **Tab 1: 断言代码 Diff 对比**：
     - 红绿双色对比卡片：原始基线断言 vs 演进后现代断言；
     - Unified Code Diff 区域（行级增删对齐）；
     - 演进推导决策原因便签列表；
   - **Tab 2: 响应结构变迁透视 (Schema Drift Map)**：
     - 表格呈现每一个漂移项（`FIELD_RENAMED`、`ENVELOPE_UNWRAPPED`、`PATH_RELOCATED`、`TYPE_MUTATED`）；
     - 路径变迁流转（`old_path` ➔ `new_path`）、置信度与详细可解释性；
   - **Tab 3: 在线沙箱语法演练 (Dry-Run)**：
     - 在线编辑断言 Python 代码与最新响应 JSON 数据；
     - 执行隔离沙箱试跑，实时呈现试跑反馈状态卡片（`PASS`、`FAIL`、`ERROR`）与耗时；
   - **操作闭环**：一键采纳演进与一键安全回滚至原基线快照。
2. **前后端 REST API 协同**：
   - 后端 `backend/app/api/v1/test_self_healing_api.py` 挂载演进试跑、漂移检测与回滚端点；
   - 前端 `selfHealingCoreApi` 封装完整调用能力。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/AssertionDriftEvolutionModal.spec.ts`：4 passed（得分与风险等级渲染、代码 Diff 与决策标签对比、沙箱在线试跑调用及结果渲染、确认采纳与一键回滚事件闭环）；
   - **通过率**：**4 passed in 3.11s (100% PASS)**。
2. **前端工程质量**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (20.44s)**；
   - `npm run build` (`vite build`)：**4570 modules transformed, built in 4.03s, 0 errors!**。
3. **后端 API 测试回归**：
   - `backend/tests/api/test_test_self_healing_api.py`：**4 passed in 4.83s (100% PASS)**。
