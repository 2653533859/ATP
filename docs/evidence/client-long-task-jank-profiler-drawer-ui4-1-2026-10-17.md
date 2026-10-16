# UI4.1 前端运行时长任务 (Long Task) 堆栈下钻与 60 FPS 掉帧卡顿诊断抽屉验收 (2026-10-17)

## 概述与结论

UI4.1（前端运行时长任务 (Long Task) 堆栈下钻与 60 FPS 掉帧卡顿诊断抽屉 `ClientLongTaskJankProfilerDrawer.vue`）已完成全量交付与验证，正式启动 **ATP v4.5.0 Phase 4（客户端运行时全息性能与 Web Vitals 体验监控大盘）**：
1. **核心组件实现 (`frontend/src/views/workbench/components/ClientLongTaskJankProfilerDrawer.vue`)**：
   - **4 项主线程运行时核心 KPI 卡片**：
     - 总阻塞时间（`Total Blocking Time, TBT`，如 `170.0ms`）；
     - TBT 评级状态徽章（`GOOD 优质` $\le 200\text{ms}$、`NEEDS_IMPROVEMENT`、`POOR`）；
     - 预估有效帧率（如 `58.2 FPS`，贴合 60 帧流畅满帧基准）；
     - 掉帧率（`Jank Rate`，丢帧比例量化）；
   - **长任务采样触发与时间窗口调节工具栏**：
     - 支持调节 3000ms / 5000ms / 10000ms 采样窗口；
   - **W3C Long Tasks 列表与归因下钻大表**：
     - 捕获超过 50ms 的 JavaScript 执行任务，展示 Blocking 阻塞贡献耗时；
     - 自动归因至强制同步布局（`LAYOUT_THRASHING`）、Canvas 图表重绘（`CANVAS_RENDER`）、大 JSON 解析与脚本同步运算；
   - **针对性性能调优指引**：
     - 智能提示 `scheduler.yield()` 长任务打散切片、`requestAnimationFrame` 重绘节流与虚拟滚动方案。
2. **工作台挂载 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 工具栏挂载 `<ThunderboltOutlined /> 长任务诊断` 唤起按钮。
3. **API 客户端对接 (`frontend/src/api/visualRegressionA11y.ts`)**：
   - 联动后端 `/api/v1/client-perf/long-tasks/profile` 与 `reports` REST API。

## 质量与测试门禁验证

1. **组件单元测试 (`ClientLongTaskJankProfilerDrawer.spec.ts` & `ApiWorkbenchView.spec.ts`)**：
   - `ClientLongTaskJankProfilerDrawer.spec.ts`：2 passed in 185ms；
   - `ApiWorkbenchView.spec.ts`：12 passed；
   - 总体 Vitest 套件：**14 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4466 个模块，产物完整生成，耗时 3.71s，零构建错误。
