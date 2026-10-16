# ATP v3.3.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**集群协同调度、资产拓扑与质量门禁交互控制台全量落地 (Cluster HA Orchestration, Asset Graph & Quality Governance Studio)**
> 承接基准：以 v3.2.0 交付的 12 项集群调度、全景资产拓扑、动态仿真沙箱与质量门禁引擎为底座，打造全功能、高可靠的前端交互控制台与可视化大盘。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1：跨节点 Worker 集群协同调度与故障转移监控台 (Cluster Worker Scheduling & Failover Studio)**
  - 核心目标：提供 Worker 节点容量负载仪表板、任务队列水位与 P0 抢占流水面板、以及失联节点自动故障转移卡片。
- **Phase 2：全域测试资产依赖拓扑与变更影响面控制台 (Global Asset Graph & Impact Studio)**
  - 核心目标：提供全景资产引用有向图谱力导向图、契约变更逆向影响面推导抽屉、以及精准回归套件自动合成弹窗。
- **Phase 3：多协议动态仿真沙箱与流量镜像控制台 (Ephemeral Sandbox & Traffic Mirroring Studio)**
  - 核心目标：提供瞬时沙箱动态端口调度管理抽屉、跨协议数据透传会话总线面板、以及流量镜像写副作用隔离检测卡片。
- **Phase 4：企业级测试质量度量大盘与质量门禁中心 (Quality Metrics Dashboard & Governance Gate Center)**
  - 核心目标：提供四维质量度量全景大盘页面、CI/CD 智能门禁卡点规则配置抽屉、以及附带防伪数字印章的发版准入合格证书弹窗。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：跨节点 Worker 集群协同调度与故障转移监控台 (Cluster Worker Scheduling & Failover Studio)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **跨节点 Worker 负载监控抽屉与容量分级仪表板** | cluster_load_balancer | 落地 `ClusterWorkerMonitorDrawer.vue` 组件与 API 客户端；展示节点 CPU/内存/并发利用率、五级健康状态标签与最优节点择优调度；见 docs/evidence/cluster-worker-monitor-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[x]` | **自适应任务排队水位与 P0 弹性抢占调度控制台** | adaptive_queue_preemptor | 落地 `AdaptiveTaskQueueDrawer.vue` 组件；展示队列排队顺位、预计等待时长 ETA、P0 弹性抢占与任务挂起唤醒流水；见 docs/evidence/adaptive-task-queue-drawer-ui1-2-2026-10-16.md |
| UI1.3 `[x]` | **节点失联超时检测与孤儿任务故障转移卡片** | worker_failover_recovery | 落地 `WorkerFailoverRecoveryCard.vue` 组件；支持心跳超时全网巡检、失联节点自动收割与孤儿任务抢救重调度记录展示；见 docs/evidence/worker-failover-recovery-card-ui1-3-2026-10-16.md |

---

### Phase 2：全域测试资产依赖拓扑与变更影响面控制台 (Global Asset Graph & Impact Studio)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **测试资产全景引用拓扑图谱与孤儿资产看板** | asset_graph_indexer | 落地 `AssetDependencyGraphViewer.vue` 组件；基于 ECharts 力导向图呈现 Plan-Suite-Case-API-Dataset 依赖图谱与孤儿资产标记；见 docs/evidence/asset-dependency-graph-viewer-ui2-1-2026-10-16.md |
| UI2.2 `[x]` | **接口契约变更影响面分析与受损用例抽屉** | contract_change_impact_analyzer | 落地 `ContractChangeImpactDrawer.vue` 组件；支持新旧 OpenAPI 契约 Diff 对比、Breaking 变更逆向推导与受损用例分级标记；见 docs/evidence/contract-change-impact-drawer-ui2-2-2026-10-16.md |
| UI2.3 `[x]` | **变更影响用例自动化精准回归套件合成向导** | targeted_regression_trigger | 落地 `TargetedRegressionWizard.vue` 组件；支持受损用例去重组装、P0 提权抢占与一键持久化落库；见 docs/evidence/targeted-regression-wizard-ui2-3-2026-10-16.md |

---

### Phase 3：多协议动态仿真沙箱与流量镜像控制台 (Ephemeral Sandbox & Traffic Mirroring Studio)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **瞬时轻量级仿真沙箱与端口生命周期管理抽屉** | ephemeral_sandbox_manager | 落地 `EphemeralSandboxManagerDrawer.vue` 组件；展示 20000-29999 端口动态分配、HTTP/gRPC/WS 多协议沙箱拉起、TTL 倒计时与 Mock 路由测试；见 docs/evidence/ephemeral-sandbox-manager-drawer-ui3-1-2026-10-16.md |
| UI3.2 `[x]` | **跨协议数据透传与会话上下文共享总线面板** | cross_protocol_session_bus | 落地 `CrossProtocolSessionBusPanel.vue` 组件；展示 HTTP-gRPC-WS 跨协议变量共享、Token 自动透传与动态模板插值预览；见 docs/evidence/cross-protocol-session-bus-panel-ui3-2-2026-10-16.md |
| UI3.3 `[ ]` | **沙箱网络流量镜像与写操作副作用隔离卡片** | sandbox_traffic_mirror | 落地 `SandboxTrafficMirrorCard.vue` 组件；支持影子流量分流配置、外发敏感写操作拦截检测与零泄露安全验证证明展示。 |

---

### Phase 4：企业级测试质量度量大盘与质量门禁中心 (Quality Metrics Dashboard & Governance Gate Center)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **全生命周期测试质量度量多维评分大盘页面** | quality_metrics_engine | 落地 `QualityMetricsDashboardView.vue` 页面与路由；呈现四维加权雷达图、自动化覆盖率、缺陷逃逸率、执行稳定性与 MTTR 指标总览。 |
| UI4.2 `[ ]` | **CI/CD 智能质量门禁规则配置与卡点决策抽屉** | quality_gate_engine | 落地 `QualityGateRuleConfigDrawer.vue` 组件；支持配置指标比较算子、阻塞性发布卡点规则与在线实时判定结果展示。 |
| UI4.3 `[ ]` | **自动化发版准入合格证书与防伪数字印章弹窗** | release_readiness_certification | 落地 `ReleaseCertificateModal.vue` 组件；展示 ISO 27001 / SOC 2 官方绿盾徽标、HMAC-SHA256 数字印章验签与合格证明导出。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
