# UI4.2 页面内存泄漏监控与 Detached DOM 幽灵引用探测卡片验收 (2026-10-17)

## 概述与结论

UI4.2（页面内存泄漏监控与 Detached DOM 幽灵引用探测卡片 `ClientMemoryLeakDetectorCard.vue`）已完成全量交付与验证，持续推进 **ATP v4.5.0 Phase 4（客户端运行时全息性能与 Web Vitals 体验监控大盘）**：
1. **核心组件实现 (`frontend/src/views/workbench/components/ClientMemoryLeakDetectorCard.vue`)**：
   - **4 项内存健康生命周期核心 KPI 卡片**：
     - 内存健康综合评分（`memory_health_score_pct`，如 `95.0%`）；
     - 高危内存泄露状态（`CRITICAL_LEAK 泄露` / `STABLE 稳定`）；
     - JS 堆净增长率（`heap_growth_percentage`，监控多轮 GC 后堆底是否持续上升）；
     - 脱落 DOM 树节点数与残留监听器计数（`total_detached_dom_count / total_unreleased_listeners_count`）；
   - **场景诊断工具栏与时序采样**：
     - 输入测试场景名称（如 `drawer_open_close_test`），一键触发内存泄漏全息评估；
   - **内存缺陷发现大表与脱落 DOM 样本剖析**：
     - 识别 `PROGRESSIVE_HEAP_LEAK`、`DETACHED_DOM_TREE_LEAK`（如未销毁的 ECharts 实例闭包持有）；
     - 展示脱落 DOM 节点 ID、保留内存大小（KB）、持有闭包符号与代码修复建议（在 `onUnmounted` 中 `dispose()` 与注销）。
2. **工作台挂载 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 工具栏挂载 `<SlidersOutlined /> 内存泄漏探测` 唤起按钮。
3. **API 客户端对接 (`frontend/src/api/visualRegressionA11y.ts`)**：
   - 联动后端 `/api/v1/client-perf/memory-leak/analyze` 与 `reports` REST API。

## 质量与测试门禁验证

1. **组件单元测试 (`ClientMemoryLeakDetectorCard.spec.ts` & `ApiWorkbenchView.spec.ts`)**：
   - `ClientMemoryLeakDetectorCard.spec.ts`：2 passed in 185ms；
   - `ApiWorkbenchView.spec.ts`：12 passed；
   - 总体 Vitest 套件：**14 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4469 个模块，产物完整生成，耗时 4.83s，零构建错误。
