# UI3.1 步骤级分布式调用链时序甘特图抽屉验收 (2026-10-17)

## 概述与结论

UI3.1（步骤级分布式调用链时序甘特图抽屉 `StepTraceTimelineDrawer.vue`）已全量交付并完成验证，**标志着 ATP v4.9.0 Phase 3（链路追踪诊断控制台与火焰图下钻大盘）正式开启并取得首个关键组件落地**：
1. **核心组件实现 (`frontend/src/views/run/components/StepTraceTimelineDrawer.vue`)**：
   - **交互式甘特时序图 (Gantt Timeline Chart)**：
     - 精准计算调用链各 Span 起止时间在步骤整体耗时中的百分比位移（`left%`）与宽度（`width%`）；
     - 依据通讯协议与组件类型赋予工业级色标：HTTP (蓝色)、gRPC (紫色)、MQ (橙色)、DB (青色)、Cache (火山红)；
     - 标注红斑高亮故障 Span 与金色五角星标注串行耗时关键路径（Critical Path）；
   - **Span 层级树状折叠 (Hierarchical Span Tree)**：
     - 按照 `parent_span_id` 自动形成多叉树，支持层级缩进与单节点展开/折叠；
     - 直观展示总耗时与节点自耗时（Self-Time）；
   - **Span 属性下钻检查器 (Inspector Panel)**：
     - 点击任意 Span 即可展开属性字典（`http.method`, `http.status_code`, `rpc.service`, `db.statement`, 异常堆栈等）；
   - **一键首因下钻诊断 (Root Cause Deep-dive)**：
     - 联动 T2.2 后端 `/observability/trace/deep-dive` 接口，自动在抽屉顶部展开故障根因归因告警条、微服务与排障处置建议；
   - **网络时钟偏差校准模式**：
     - 联动 T2.1 `/observability/trace/skew-compensate` 接口，支持一键切换显示因果单调性校准前后时序。
2. **用例执行详情主视图集成 (`frontend/src/views/run/RunDetail.vue`)**：
   - 在顶部基本信息 `TraceID` 处添加交互动作“查看调用链甘特图”；
   - 在各测试步骤折叠面板的动作区（`<template #extra>`）新增专属 `Trace` 联动按钮，支持一键开启抽屉并精准定位该步骤的关联链路。
3. **前端 API 客户端扩展 (`frontend/src/api/observabilityTrace.ts`)**：
   - 封装 `compensateClockSkew`, `deepDiveAnalysis`, `buildLineage`, `getLineage`, `listLineages`, `getExecutionTrail` 等方法与 TypeScript DTO 接口。

## 质量与测试门禁验证

1. **单元测试验证**：
   - `frontend/src/views/run/components/StepTraceTimelineDrawer.spec.ts`：3 passed；
   - `frontend/src/views/run/RunDetail.spec.ts`：7 passed；
   - 总体通过率：**10 passed across Run & Trace tests (100% PASS)**。
2. **TypeScript 强类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass！
3. **生产环境构建 (`vite build`)**：
   - 4513 个模块编译通过，生产环境打包构建成功。
