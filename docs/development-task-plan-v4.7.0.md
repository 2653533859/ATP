# ATP v4.7.0 研发任务规划与执行计划 (2026-10-17)

> 版本定位：**生产级全链路影子流量压测控制台、单元化隔离切流看板、多源资源容量水位监控大盘与全链路压测复盘决策中心 (Full-Link Stress Testing Console, Cell-based Traffic Shunting Dashboard, Multi-source Watermark Guardian & Digital-Twin Drill Review Board)**
> 承接基准：以 v4.6.0 交付的影子流量染色标动态注入、影子库表写防污染隔离、MQ 影子分流、多单元流量调度、跨单元依赖逃逸检测、单元故障自愈 RTO 验证、多源容量水位度量、调用链瓶颈归因、防雪崩自适应熔断大脑、TPS 阶梯拐点拟合与爆炸半径审计 12 大服务引擎与 REST API 为坚实底座，在 Vue 3 前端构建完整、优雅、专业的可视化抽屉、组件面板与全景监控大盘，达成端到端全栈工业级全链路压测体系大闭环。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 全链路影子流量染色、库表防污染与 MQ 隔离控制台 (Shadow Traffic & Data Isolation Console)**
  - 聚焦跨协议影子流量染色透传注入与校验抽屉、影子库表读写防污染安全隔离与拦截抽屉、以及全链路影子数据与 MQ 消息分流隔离全景大盘页面。
- **Phase 2: 单元化架构测试隔离 (Cell-based Testing) 与容灾切流看板 (Cell Isolation & Traffic Shunting Dashboard)**
  - 聚焦多可用区单元化切流权重控制与智能路由抽屉、跨单元服务依赖逃逸与拓扑孤岛检测面板、以及单元故障切换与常态化容灾自愈全景大盘页面。
- **Phase 3: 压测容量水位实时监控与防雪崩自适应熔断控制台 (Capacity Watermark & Avalanche Breaker Console)**
  - 聚焦多源基础设施 (DB池/Redis/MQ) 容量水位监控抽屉、压测调用链热点慢调用与资源争用归因卡片、以及防击穿自适应分级限流与防雪崩熔断大脑控制台。
- **Phase 4: 全链路压测拐点分析、爆炸半径审计与复盘决策大盘 (Stress Drill Review & Blast Radius Dashboard)**
  - 聚焦 TPS 阶梯加压性能曲线与最大吞吐拐点分析抽屉、生产全链路压测安全审计与爆炸半径评估卡片、以及全链路压力演练综合审计与数字孪生复盘大盘页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：全链路影子流量染色、库表防污染与 MQ 隔离控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **跨协议影子流量染色透传注入与校验抽屉** | `shadow_traffic_taint_propagator` | 落地 `ShadowTrafficTaintPropagatorDrawer.vue` 组件与 API 客户端；展示 HTTP/gRPC/MQ 染色头注入、多跳拓扑透传链路追踪与丢标泄漏预警；单测独立通过；见 docs/evidence/shadow-traffic-taint-propagator-drawer-ui1-1-2026-10-17.md |
| UI1.2 `[x]` | **影子库表读写防污染安全隔离与拦截抽屉** | `shadow_database_isolation_inspector` | 落地 `ShadowDatabaseIsolationDrawer.vue` 组件与 API 客户端；展示生产表至影子表映射树、SQL 动态重写审计、高危写操作阻断警告与映射配置；单测独立通过；见 docs/evidence/shadow-database-isolation-drawer-ui1-2-2026-10-17.md |
| UI1.3 `[x]` | **全链路影子数据与 MQ 消息分流隔离全景大盘页面** | `shadow_isolation_dashboard` | 落地 `FullLinkShadowIsolationDashboardView.vue` 视图与路由；汇总全链路影子流量隔离率（100%）、影子库表就绪数、MQ 影子分流数与旁路 Mock/Drop 监控；单测独立通过；见 docs/evidence/full-link-shadow-isolation-dashboard-ui1-3-2026-10-17.md |

---

### Phase 2：单元化架构测试隔离 (Cell-based Testing) 与容灾切流看板

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **多可用区单元化切流权重控制与智能路由抽屉** | `cell_based_testing_traffic_controller` | 落地 `CellBasedTrafficControllerDrawer.vue` 组件与 API 客户端；展示 Cell 状态（ACTIVE_PROD, STRESS_ONLY, DRAINING）、权重调节滑块、用户分片取模路由与压测专用单元隔离；单测独立通过；见 docs/evidence/cell-based-traffic-controller-drawer-ui2-1-2026-10-17.md |
| UI2.2 `[x]` | **跨单元服务依赖逃逸与拓扑孤岛检测面板** | `cell_escape_dependency_detector` | 落地 `CellEscapeDependencyPanel.vue` 组件与 API 客户端；展示跨单元 RPC 调用拦截、共享数据源混用告警、拓扑依赖调用边可视化矩阵；单测独立通过；见 docs/evidence/cell-escape-dependency-panel-ui2-2-2026-10-17.md |
| UI2.3 `[ ]` | **单元故障切换与常态化容灾自愈全景大盘页面** | `cell_failover_dashboard` | 落地 `CellFailoverResilienceDashboardView.vue` 视图与路由；模拟单机房/单元瘫痪、展示 4 阶段时序耗时（心跳超时、DNS 切换、数据追平、路由收敛）、金融级 RTO 实时度量；单测独立通过。 |

---

### Phase 3：压测容量水位实时监控与防雪崩自适应熔断控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **多源基础设施 (DB池/Redis/MQ) 容量水位监控抽屉** | `multisource_capacity_watermark_meter` | 落地 `MultisourceCapacityWatermarkDrawer.vue` 组件与 API 客户端；展示 DB 连接池、Redis 内存、MQ 积压四阶仪表盘（SAFE, WARNING, SATURATED, EXHAUSTED）与木桶短板资源定位；单测独立通过。 |
| UI3.2 `[ ]` | **压测调用链热点慢调用与资源争用归因卡片** | `distributed_bottleneck_root_cause_classifier` | 落地 `DistributedBottleneckClassifierCard.vue` 组件与 API 客户端；展示 P50/P90/P99 响应时间、死锁/慢SQL/线程池打满/CPU饱和智能分类与优化建议；单测独立通过。 |
| UI3.3 `[ ]` | **防击穿自适应分级限流与防雪崩熔断大脑控制台** | `adaptive_avalanche_circuit_breaker` | 落地 `AdaptiveAvalancheBreakerConsoleDrawer.vue` 组件与 API 客户端；展示 4 阶段熔断状态机（正常、一级缓速25%、二级急刹60%、硬核毫秒阻断 ABORT）、实时熔断触发广播与一键紧急重置；单测独立通过。 |

---

### Phase 4：全链路压测拐点分析、爆炸半径审计与复盘决策大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **TPS 阶梯加压性能曲线与最大吞吐拐点分析抽屉** | `step_load_throughput_knee_detector` | 落地 `StepLoadThroughputKneeDrawer.vue` 组件与 API 客户端；展示并发 vs TPS 拟合曲线、Knee Point 最佳拐点、Cliff Point 崩溃点与日常生产最佳并发推荐；单测独立通过。 |
| UI4.2 `[ ]` | **生产全链路压测安全审计与爆炸半径评估卡片** | `stress_blast_radius_safety_evaluator` | 落地 `StressBlastRadiusEvaluatorCard.vue` 组件与 API 客户端；展示 4 级爆炸半径（局域可控到全局失控）、4 大安全护栏准入状态、64 位 SHA-256 审计指纹；单测独立通过。 |
| UI4.3 `[ ]` | **全链路压力演练综合审计与数字孪生复盘大盘页面** | `full_link_stress_drill_reporter` | 落地 `FullLinkStressDrillSummaryDashboardView.vue` 视图与路由；汇聚吞吐指标、容量水位、熔断事件与准入评级，提供全景演练报告 Markdown 一键实时预览与复制导出；单测独立通过。 |

---

## 3. 质量门禁规则

1. **类型检查与前端编译**：前端组件与路由严格执行 `npm run type-check` (`vue-tsc --noEmit`) 零错误；`npm run build` (`vite build`) 成功构建。
2. **组件单元测试**：所有新增组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
3. **路由与导航无缝接入**：所有视图页面接入 `frontend/src/router/index.ts` 并同步至 `frontend/src/layouts/navigation.ts`。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
