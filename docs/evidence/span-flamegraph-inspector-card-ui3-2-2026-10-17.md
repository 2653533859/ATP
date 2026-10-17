# UI3.2 慢跨度与服务依赖下钻火焰图卡片验收 (2026-10-17)

## 概述与结论

UI3.2（慢跨度与服务依赖下钻火焰图卡片 `SpanFlamegraphInspectorCard.vue`）已全量交付并完成验证，**标志着 ATP v4.9.0 Phase 3（链路追踪诊断控制台与火焰图下钻大盘）核心微服务火焰图分析能力全面就绪**：
1. **核心组件实现 (`frontend/src/views/run/components/SpanFlamegraphInspectorCard.vue`)**：
   - **层级火焰图切片 (Hierarchical Flamegraph Slices)**：
     - 依据调用树深度（Depth: 1..N）切分阶梯矩形条，横向坐标百分比精确反映各微服务 Span 的开始时机与耗时跨度；
     - 按协议与组件赋予工业级色标：HTTP (蓝色)、gRPC (紫色)、DB (青色)、Cache (火山红)、MQ (橙色)；
   - **慢跨度红斑火焰告警 (Slow Span Flame Alert)**：
     - 支持动态切换慢耗时阈值（50ms / 100ms / 150ms / 200ms），耗时超标或含错误 Span 呈现高亮鲜红色与呼吸微光火焰动画；
   - **双击下钻聚焦放大 (Zoom & Drilldown)**：
     - 支持双击任意微服务 Span 节点作为局部根节点，自适应伸缩缩放（Zoom-in），并提供一键“返回全链路顶层”；
   - **仅看慢调用开关 (Slow Only Filter)**：
     - 一键过滤非瓶颈跨度，仅保留包含慢跨度及其祖先的调用链路；
   - **选中 Span 剖析卡片 (Inline Metric Inspector)**：
     - 展示 Span ID、微服务名、总执行耗时、自身独占耗时（Self-Time）以及链路耗时占比（%）。
2. **用例执行详情主视图集成 (`frontend/src/views/run/RunDetail.vue`)**：
   - 当用例运行具备 `run.trace_id` 时，在步骤列表上方自动挂载火焰图卡片，支持工程师直观诊断瓶颈。
3. **健壮性与离线降级设计**：
   - 内置安全异常捕获机制，即便在离线或模拟环境下也能优雅降级展示仿真多协议调用链路，不产生未处理异常。

## 质量与测试门禁验证

1. **单元测试验证**：
   - `frontend/src/views/run/components/SpanFlamegraphInspectorCard.spec.ts`：3 passed；
   - `frontend/src/views/run/components/StepTraceTimelineDrawer.spec.ts`：3 passed；
   - `frontend/src/views/run/RunDetail.spec.ts`：7 passed；
   - 总体通过率：**13 passed across Run & Flamegraph tests (100% PASS)**。
2. **TypeScript 强类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass！
3. **生产环境构建 (`vite build`)**：
   - 4516 个模块编译通过，生产环境打包构建成功。
