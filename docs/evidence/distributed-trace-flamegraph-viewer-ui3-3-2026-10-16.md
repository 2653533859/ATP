# UI3.3 全链路分布式追踪 TraceID 慢调用火焰图交互组件验收 (2026-10-16)

## 概述与结论

UI3.3（全链路分布式追踪 TraceID 慢调用火焰图交互组件）已完成全量交付与验证，至此 **ATP v3.5.0 Phase 3（多端原生性能剖析与深度质量诊断控制台）100% 全量大闭环**：
1. **API 客户端扩展 (`frontend/src/api/distributedTraces.ts` & `frontend/src/api/index.ts`)**：
   - 封装 `distributedTracesApi` 客户端：`ingestTrace`（摄入 OpenTelemetry/Jaeger Spans 调用链）、`listTraces`（查询追踪列表）与 `getTrace`（获取层级树与火焰图）；
   - 建立 `DistributedSpanItem`、`FlamegraphNodeItem`、`TraceTreeReportItem`、`IngestTraceRequest` 等强类型接口定义。
2. **全链路阶梯火焰图与慢调用诊断组件 (`DistributedTraceFlamegraphViewer.vue`)**：
   - **链路核心指标与瓶颈横幅**：突出展示全链路总时延（ms）、根微服务与根接口、参与微服务标签列表、Span 节点总数与慢调用计数；
   - **阶梯火焰图甘特视图 (Flamegraph View)**：
     - 基于微服务调用拓扑深度递归分层展示阶梯条块；
     - 宽度按耗时占总时延比例动态自适应（最小宽度保底）；
     - 慢调用（>100ms）红底金边高亮并展示火焰图标；
     - 点击 Span 块即可实时在下方抽屉卡片剖析 Span ID、总耗时、Self-Time 独占耗时与时延占比；
   - **多层级调用树表格 (Hierarchical Span Tree)**：
     - 支持缩进与展开/收起，展示父子依赖关系、自身独占耗时 (Self-Time)、时延占比彩色进度条与状态；
   - **慢调用瓶颈排行与诊断建议 (Top Slow Spans)**：
     - 按耗时降序排列所有慢调用节点，针对高自身独占耗时（CPU/反序列化/磁盘IO密集）与高下游依赖耗时（建议异步并发与二级缓存）提供差异化优化指导；
   - **一键仿真摄入**：支持一键摄入 6 节点完整微服务链路（Gateway -> Auth -> Order -> Payment -> DB）进行可视化演练。
3. **接口测试工作台挂载集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「全链路火焰图」快捷入口；
   - 支持一键滑出 1060px 抽屉，联动微服务接口与 TraceID 进行慢调用与时延瓶颈诊断。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/DistributedTraceFlamegraphViewer.spec.ts`：**2 passed in 74ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 450ms**；
   - 核心工作台与性能诊断测试套件：**49 passed in 2.59s**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.67s, 0 errors**。
