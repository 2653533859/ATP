# UI4.1 质量大盘与报表折线图通过率/安全阈值基线接入验收 (2026-10-17)

## 概述与结论

UI4.1（质量大盘与报表折线图通过率/安全阈值基线接入 `DashboardView.vue`, `ReportCenterView.vue`）已全量交付并完成验证，正式开启 **ATP v4.8.0 Phase 4（数据大盘图表可解释性与穿透下钻）**：
1. **解决核心痛点（图表缺少工业级基线、好坏难辨的盲目性彻底消除）**：
   - 彻底修复 `frontend/src/views/dashboard/DashboardView.vue` 与 `frontend/src/views/report/ReportCenterView.vue` 中通过率历史趋势折线图缺少参考基准的问题；
   - **双阈值安全基线架构**：
     - **合格基线（90% Target Baseline）**：在折线图中注入绿色虚线 MarkLine（`#52c41a`），标明“合格 90%”，让工程团队与管理者直观辨识健康水位；
     - **警戒红线（75% Warning Baseline）**：在折线图中注入红色虚线 MarkLine（`#f5222d`），标明“警戒 75%”，直观预警跌破容灾底线；
   - 结合半透明区域阴影与数值提示，大幅提升数据大盘的可解释性与决策效率。

## 质量与测试门禁验证

1. **图表大盘单元测试 (`DashboardView.spec.ts` & `ReportCenterView.spec.ts`)**：
   - `DashboardView.spec.ts`：10 passed in 199ms；
   - `ReportCenterView.spec.ts`：4 passed in 121ms；
   - 总体 Vitest 套件：**14 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4509 个模块，产物完整生成，耗时 10.00s，零构建错误。
