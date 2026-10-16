# UI1.1 OpenTelemetry Span 追踪中继与层级调用树展开抽屉验收 (2026-10-16)

## 概述与结论

UI1.1（OpenTelemetry Span 追踪中继与层级调用树展开抽屉）已完成全量交付与验证，正式开启 **ATP v4.1.0 Phase 1（分布式链路全息追踪、调用树与性能瓶颈火焰图控制台）**：
1. **API 客户端扩展 (`frontend/src/api/traceObservability.ts` & `frontend/src/api/index.ts`)**：
   - 建立 `TelemetrySpanItem`、`TraceTreeReport`、`TraceSummaryItem`、`TraceFlamegraphNodeItem` 等强类型接口契约；
   - 封装 `traceTelemetryApi` 客户端方法：`ingestSpans`、`listTraces`、`getTraceTree` 与 `clearTraces`；
   - 封装 `traceFlamegraphApi` 与 `traceAnomalyApi` 客户端为后续任务奠定通用底盘。
2. **Span 追踪与层级调用树控制台抽屉 (`DistributedTraceSpanTreeDrawer.vue`)**：
   - **头部 Header & W3C TraceContext 报文框**：
     - 展示标准 `00-{trace_id}-{root_span_id}-01` 报文头部格式，支持一键复制到剪贴板供下游链路串联透传；
   - **调用链场景演练与多维过滤栏**：
     - 内置快捷场景：`电商结账调用链 (含支付下游异常 504)` 与 `用户资料多层级只读链 (全链路正常通过)`；
     - 支持按微服务（api-gateway / order-service / pay-service 等）过滤与仅看异常链路（`filterOnlyError`）；
   - **链路批次选择卡片 (Trace Selector)**：
     - 滚动卡片展示已采集的链路，显示根操作名、服务名、总耗时、Span 节点数与 ERROR/OK 状态徽章；
   - **全链路关键指标横幅 (KPI Banner)**：
     - 全链路总时延（ms）、Span 节点总数、跨越微服务数、链路诊断健康状态指示；
   - **层级调用树表格 (Tree Table)**：
     - 树形折叠展开展示各微服务调用层级（缩进 + 颜色徽章）；
     - 显示操作名、SpanId、Span 类型（SERVER / CLIENT / INTERNAL）；
     - 单节点耗时 + 相对于全链路总时延的相对进度条；
     - 节点状态徽章与下游报错信息（如 `Read timed out (504)`）；
     - 悬停展示属性与事件字典预览。
3. **接口测试工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「调用链追踪」主要入口；
   - 支持一键滑出 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/DistributedTraceSpanTreeDrawer.spec.ts`：**2 passed in 60ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**；
   - 工作台测试套件：**14 passed in 571ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 3.31s, 0 errors**。
