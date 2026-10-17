# UI4.2 质量大盘图表点击穿透联动表格筛选闭环验收 (2026-10-17)

## 概述与结论

UI4.2（质量大盘图表点击穿透联动表格筛选闭环 `DashboardView.vue`）已全量交付并完成验证，持续推进 **ATP v4.8.0 Phase 4（数据大盘图表可解释性与穿透下钻）**：
1. **解决核心痛点（图表静态孤岛、看见异常无法下钻定位彻底消除）**：
   - 彻底修复 `frontend/src/views/dashboard/DashboardView.vue` 中图表仅作为静态展示、用户无法通过点击直达明细数据的问题；
   - **交互光标与下钻手感提升**：
     - 为 `.dashboard-chart-canvas` 注入 `cursor: pointer`，提供明确的可交互点击意符；
   - **全量图表跨视图穿透下钻 (Chart Cross-Filtering)**：
     - **失败原因排行 (`failure_top`)**：点击特定失败条目或扇区，智能关联用例或下钻前往运行中心（`runs?status=failed&project_id=...`），直达故障现场；
     - **通过率趋势 (`pass_rate_trend`)**：点击趋势数据点，联动前往对应工程项目的运行记录中心；
     - **用例类型分布 (`case_type_distribution`)**：点击接口/Web/移动端扇区，自动下钻至用例管理中心并预置类型筛选（`cases?type=...`）；
     - **计划与套件趋势 (`plan_trend`, `suite_trend`)**：点击直接下钻跳转对应测试计划与用例集管理中心；
   - 彻底实现“**看见异常 ➔ 立即下钻定位**”的工业级操作闭环。

## 质量与测试门禁验证

1. **大盘穿透联动单元测试 (`DashboardView.spec.ts`)**：
   - 11 passed in 323ms (100% PASS)；
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4509 个模块，产物完整生成，耗时 3.48s，零构建错误。
