# UI2.1 多可用区单元化切流权重控制与智能路由抽屉验收 (2026-10-17)

## 概述与结论

UI2.1（多可用区单元化切流权重控制与智能路由抽屉 `CellBasedTrafficControllerDrawer.vue`）已全量交付并完成验证，正式开启 **ATP v4.7.0 Phase 2（单元化架构测试隔离 Cell-based Testing 与容灾切流看板）**：
1. **核心抽屉实现 (`frontend/src/views/workbench/components/CellBasedTrafficControllerDrawer.vue`)**：
   - **4 大单元拓扑核心 KPI 统计卡片**：
     - 活跃生产单元数（`ACTIVE_PROD`，绿色）；
     - 专属压测单元数（`STRESS_ONLY`，蓝色）；
     - 排空/隔离单元数（`DRAINING` / `ISOLATED_FAILSAFE`，橙色）；
     - 单元拓扑总数（多可用区物理单元数，青色）；
   - **用户分片路由演算沙箱 (Cell Routing Sandbox)**：
     - 支持在线输入任意 `user_id`（如 `user_8866`）与压测影子染色标切换；
     - 实时输出决策 ID、分配单元、归属可用区 (Zone) 与哈希取模/染色隔离裁决原因；
   - **单元拓扑矩阵与切流权重调节大表 (Cell Topology Matrix)**：
     - 展示单元名称、可用区 Tag、运行状态胶囊、权重调节滑块 (Slider 0~100%)、用户分片 Tags (`#0`, `#1`, ...) 以及压测专用靶标状态；
     - 底部集成“保存并下发切流权重”与“登记新物理单元”Modal 对话框。
2. **工作台挂载 (`frontend/src/views/workbench/PerformanceWorkbenchView.vue`)**：
   - 在性能测试工作台工具栏新增 `<a-button size="small" class="toolbar-btn" @click="showCellControllerDrawer = true"><PartitionOutlined /> 单元切流控制</a-button>` 唤起抽屉。
3. **API 客户端对接 (`frontend/src/api/fullLinkStressTesting.ts`)**：
   - 联动后端 `/api/v1/stress/cell-isolation/routing/decide`、`/cells` 与 `/weights` REST API。

## 质量与测试门禁验证

1. **组件单元测试 (`CellBasedTrafficControllerDrawer.spec.ts` & `PerformanceWorkbenchView.spec.ts`)**：
   - `CellBasedTrafficControllerDrawer.spec.ts`：2 passed；
   - `PerformanceWorkbenchView.spec.ts`：5 passed；
   - 总体 Vitest 套件：**7 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4485 个模块，产物完整生成，耗时 3.71s，零构建错误。
