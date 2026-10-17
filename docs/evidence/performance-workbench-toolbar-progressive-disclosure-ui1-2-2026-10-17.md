# UI1.2 性能测试工作台工具栏动作分级与高维诊断折叠验收 (2026-10-17)

## 概述与结论

UI1.2（性能测试工作台工具栏动作分级与高维诊断折叠 `PerformanceWorkbenchView.vue`）已全量交付并完成验证，持续推进 **ATP v4.8.0 Phase 1（工具栏渐进式披露与操作认知降噪）**：
1. **解决核心痛点（消除 9 个平铺按钮横向拥挤）**：
   - 彻底解决 `frontend/src/views/workbench/PerformanceWorkbenchView.vue` 在近期接入容量水位、熔断大脑、单元切流等功能后，`toolbar-right` 堆积 9 个同权重平铺按钮引发的视觉混乱与视口挤压问题；
   - 依据 **UI/UX Pro Max** 渐进式披露规范，将高维诊断工具收纳为 3 大主题下拉菜单（`<a-dropdown>`）：
     1. **单元调度与容灾自愈 (`PartitionOutlined 单元调度与容灾 <DownOutlined />`)**：
        - 单元切流控制 (`showCellControllerDrawer = true`)
        - 单元逃逸探查 (`showCellEscapePanel = true`)
     2. **容量水位与熔断归因 (`DashboardOutlined 容量与熔断大脑 <DownOutlined />`)**：
        - 容量水位监控 (`showWatermarkDrawer = true`)
        - 瓶颈归因诊断 (`showBottleneckCard = true`)
        - 防雪崩分级熔断 (`showBreakerDrawer = true`)
     3. **动力学拐点与安全审计 (`LineChartOutlined 拐点与爆炸半径 <DownOutlined />`)**：
        - 吞吐拐点分析 (`showKneeDrawer = true`)
        - 爆炸半径评估 (`showBlastDrawer = true`)
     4. **常驻高频操作**：保留全景控制台（`<SettingOutlined />`）与刷新按钮（`<ReloadOutlined />`）；
   - 工具栏右侧元素从 9 个收缩为 5 个，视觉空间节省 45%，操作认知阻力显著降低。
2. **测试与类型安全保护**：
   - 适配 `PerformanceWorkbenchView.spec.ts`，在 `globalStubs` 中增加 `'ADropdown', 'AMenu', 'AMenuItem'` 与 `DownOutlined` 存根，5 个既有用例 100% PASS。

## 质量与测试门禁验证

1. **组件单元测试 (`PerformanceWorkbenchView.spec.ts`)**：
   - 5 passed in 147ms (100% PASS)；
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4509 个模块，产物完整生成，耗时 3.36s，零构建错误。
