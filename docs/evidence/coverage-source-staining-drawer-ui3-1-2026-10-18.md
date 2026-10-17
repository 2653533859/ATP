# UI3.1 源码文件逐行覆盖率动态高亮染色抽屉交付验收 (2026-10-18)

## 概述与交付物

UI3.1（源码文件逐行覆盖率动态高亮染色抽屉组件）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.9.0 Phase 3（覆盖率全景染色看板与源码级透视工作台）的前端交付**：
1. **可视化源码逐行染色抽屉 (`frontend/src/views/workbench/components/CoverageSourceStainingDrawer.vue`)**：
   - **指标与状态概览横幅 (`staining-hero-bar`)**：实时展示源码文件路径、增量代码行覆盖率徽章、已覆盖行数、部分分支覆盖行数、红色未覆盖高危行数及总变更行数；
   - **视图多模式过滤切换 (`a-radio-group`)**：支持一键切换“全部行 (All)”、“仅变更行 (Diff)”与“仅红黄未覆盖行”，精准排查高危漏测代码；
   - **未覆盖红线快捷定位条 (`quick-jump-bar`)**：聚合红色未覆盖行号标签（`Line N`），点击触发平滑滚动（`scrollIntoView`）与高亮聚焦定位；
   - **四态逐行染色渲染**：
     - 绿色背景与指示条（`COVERED`，完全覆盖）；
     - 黄色背景与指示条（`PARTIAL`，分支部分覆盖，显示 `分支: M/N` 标签）；
     - 红色背景与指示条（`UNCOVERED`，高危未覆盖行，悬浮操作提供“生成补测用例”快捷按钮）；
     - 灰色背景（`NOT_EXECUTABLE`，非执行代码行）。
   - **行号栏与命中计数器 (`hits-badge`)**：左侧 Gutter 栏清晰展示行号、`+` Diff 变更标识及测试执行命中频次（如 `5x`）。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/CoverageSourceStainingDrawer.spec.ts`：4 passed（抽屉头部及覆盖率指标统计渲染、红色未覆盖行快速跳转 pill 点击与定位事件发射、行内生成补测用例事件发射、关闭抽屉事件发射）；
   - **通过率**：**4 passed in 2.04s (100% PASS)**。
2. **前端工程质量门禁**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (21.30s)**；
   - `npm run build` (`vite build`)：**4608 modules transformed, built in 4.12s, 0 errors!**。
