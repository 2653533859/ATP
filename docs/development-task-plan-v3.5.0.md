# ATP v3.5.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**云原生弹性调度、AI 智能自愈与多端原生性能分析控制台全量落地 (Cloud-Native Autoscaling, AI Healing Studio & Multi-Platform Profiling Console)**
> 承接基准：以 v3.4.0 交付的 12 项云原生容器调度、AI 智能用例自愈、多端性能分析与 DORA 效能引擎为底座，打造全功能、高保真、直观交互的前端控制台与分析大盘。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 云原生动态容器化弹性 Worker 调度与镜像版本控制台 (Cloud-Native Worker & Image Matrix Studio)**
  - 聚焦 K8s/Docker 容器实例拉起配额管理、HPA 队列背压自动扩缩容看板与镜像版本矩阵路由。
- **Phase 2: AI 驱动的用例自愈与契约响应柔性断言控制台 (AI Autonomous Healing & Flexible Assertion Studio)**
  - 聚焦失效选择器多模态自愈恢复推导、接口 Schema 动态漂移自适应修正与自愈执行流水审计。
- **Phase 3: 多端原生性能剖析与深度质量诊断控制台 (Multi-Platform Profiling & Deep Diagnostics Console)**
  - 聚焦移动端性能多维时序图表、Web Core Web Vitals 诊断视图与全链路分布式火焰图交互组件。
- **Phase 4: 企业级报告归档多模态导出与研发效能 DORA 罗盘中心 (Enterprise Reporting Center & DORA Metrics Compass)**
  - 聚焦多模态报告聚合导出弹窗、多渠道富文本卡片 Webhook 广播抽屉与 DORA 研发效能罗盘页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：云原生动态容器化弹性 Worker 调度与镜像版本控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **云原生弹性 Worker 容器 Pod 调度与配额管理抽屉** | k8s_worker_provisioner | 落地 `CloudNativeWorkerManagerDrawer.vue` 组件与 API 客户端；展示容器 Pod 实例运行流水、CPU/内存配额消耗与生命周期下线；见 docs/evidence/cloud-native-worker-manager-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[x]` | **队列背压自适应 HPA 自动扩缩容策略与决策看板** | queue_backpressure_autoscaler | 落地 `HpaAutoscalingDashboardCard.vue` 组件；展示队列积压深度、时延 SLO 惩罚因子计算、副本数自适应调节与防抖冷却；见 docs/evidence/hpa-autoscaling-dashboard-card-ui1-2-2026-10-16.md |
| UI1.3 `[x]` | **容器执行环境镜像版本矩阵与标签路由解析抽屉** | worker_image_matrix_router | 落地 `WorkerImageMatrixDrawer.vue` 组件；展示多版本镜像矩阵（Python/Node/Android/Perf）、标签交集打分匹配推演与回退兜底；见 docs/evidence/worker-image-matrix-drawer-ui1-3-2026-10-16.md |

---

### Phase 2：AI 驱动的用例自愈与契约响应柔性断言控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **失效选择器 DOM/UI 树多模态自愈推导抽屉** | smart_locator_healing_engine | 落地 `SmartLocatorHealingDrawer.vue` 组件与 API 客户端；展示四维加权相似度打分（标识/语义/拓扑/属性）、稳固定位器生成与置信度；见 docs/evidence/smart-locator-healing-drawer-ui2-1-2026-10-16.md |
| UI2.2 `[x]` | **接口响应 Schema 动态漂移自适应修正与柔性断言调试器** | flexible_schema_assertion_engine | 落地 `FlexibleSchemaAssertionDebugger.vue` 组件；支持 STRICT/COMPATIBLE/LENIENT 模式调试、多余字段放行与自愈 Schema 实时导出；见 docs/evidence/flexible-schema-assertion-debugger-ui2-2-2026-10-16.md |
| UI2.3 `[x]` | **异常故障簇智能聚合看板与自愈执行流水审计面板** | healing_audit_trail_service | 落地 `HealingAuditTrailPanel.vue` 组件与 API 客户端；展示错误栈特征聚合故障簇、用例自愈动作历史流水与节省工时成效量化；见 docs/evidence/healing-audit-trail-panel-ui2-3-2026-10-16.md |

---

### Phase 3：多端原生性能剖析与深度质量诊断控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **移动端性能时序曲线与卡顿/内存泄露体检报告看板** | mobile_perf_profiler | 落地 `MobilePerfDiagnosticsViewer.vue` 组件与 API 客户端；支持 CPU/内存/FPS/网络流量多维时序图、线性回归内存泄露告警与 Jank 掉帧分析；见 docs/evidence/mobile-perf-diagnostics-viewer-ui3-1-2026-10-16.md |
| UI3.2 `[x]` | **Web 性能 Core Web Vitals (LCP, INP, CLS) 雷达图与阻断资源分析视图** | web_vitals_profiler | 落地 `WebVitalsDiagnosticsView.vue` 页面与路由；呈现 Google 官方三维核心与辅助体验指标、加权性能综合分与关键渲染阻断资源；见 docs/evidence/web-vitals-diagnostics-view-ui3-2-2026-10-16.md |
| UI3.3 `[ ]` | **全链路分布式追踪 TraceID 慢调用火焰图交互组件** | distributed_trace_flamegraph | 落地 `DistributedTraceFlamegraphViewer.vue` 组件；展示多层级 Span 调用树、独占耗时 (Self-Time) 阶梯图、慢调用高亮与瓶颈摘要。 |

---

### Phase 4：企业级报告归档多模态导出与研发效能 DORA 罗盘中心

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **测试报告多模态聚合打包导出弹窗** | report_bundler_exporter | 落地 `ReportBundlerExportModal.vue` 组件与 API 客户端；支持一键生成并直接下载 HTML5 离线单文件报告、Excel 详报、PDF 凭据与全模态 ZIP 包。 |
| UI4.2 `[ ]` | **企微 / 钉钉 / 飞书富文本交互式卡片 Webhook 智能广播抽屉** | notification_hub_dispatcher | 落地 `NotificationHubBroadcastDrawer.vue` 组件；支持企微 template_card、钉钉 actionCard、飞书卡片实时预览、Webhook 密钥脱敏与一键广播。 |
| UI4.3 `[ ]` | **团队研发效能 DORA 罗盘看板与成熟度评估页面** | dora_metrics_calculator | 落地 `DoraMetricsCompassView.vue` 页面与路由；量化部署频率、变更前置耗时、失败率、MTTR 四维效能指标与团队成熟度等级评定。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
