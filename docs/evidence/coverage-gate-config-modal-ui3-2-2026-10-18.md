# UI3.2 增量覆盖率发布门禁配置与高危分支补测弹窗交付验收 (2026-10-18)

## 概述与交付物

UI3.2（增量覆盖率发布门禁配置与高危分支补测弹窗组件）已全量研发交付并通过各项工程门禁，**达成 ATP v5.9.0 Phase 3 第二个核心交互弹窗交付**：
1. **可视化门禁配置与补测中枢弹窗 (`frontend/src/views/workbench/components/CoverageGateConfigModal.vue`)**：
   - **4 大发布门禁指标概览横幅 (`gate-metrics-banner`)**：实时展示增量行覆盖率门槛（85%）、分支覆盖率门槛（70%）、P0 阻塞级未覆盖分支零容忍状态与最大容许未覆盖代码行；
   - **双 Tab 结构切换**：
     - **Tab 1: 发布门禁准入红线配置**：支持滑块与数值输入双向联动调节行覆盖率与分支覆盖率门槛，提供 P0 强阻断 Switch 开关与豁免路径白名单（`tests/*`、`*.spec.ts`、`alembic/*`）录入；
     - **Tab 2: 缺失高危分支补测用例展示与导出**：清晰展示系统反向推导合成的缺失补测用例草稿（文件路径、目标行号、推荐边界入参、可执行 Python pytest 代码片段），提供“导出补测脚本草稿”功能。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/CoverageGateConfigModal.spec.ts`：5 passed（弹窗头部指标横幅渲染、自定义初始策略反显、导出补测脚本事件发射、保存门禁策略事件发射、恢复默认推荐门禁值功能）；
   - **通过率**：**5 passed in 1.96s (100% PASS)**。
2. **前端工程质量门禁**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (20.95s)**；
   - `npm run build` (`vite build`)：**4608 modules transformed, built in 3.87s, 0 errors!**。
