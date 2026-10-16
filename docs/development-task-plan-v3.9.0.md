# ATP v3.9.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**微服务网关生产流量镜像录制、影子回放比对、契约动态漂移防线与韧性演练前端控制台全量落地 (Traffic Mirroring, Shadow Replay, Contract Drift Guard & Resilience Studio)**
> 承接基准：以 v3.8.0 交付的 12 项网关旁路捕获、脱敏清洗、聚类合成用例、影子回放、智能去噪差分、黄金基线、契约动态推导、Breaking 评级、级联拓扑、故障注入与 RTO 量化引擎为底座，打造现代 SaaS 科技质感的前端全景工作台、交互抽屉与可视化大盘。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 生产流量网关镜像捕获、智能脱敏与用例聚类合成控制台 (Traffic Capture & Case Synthesis Studio)**
  - 聚焦网关旁路流量镜像监控、动态采样与过滤配置抽屉、敏感数据自适应规则脱敏弹窗、以及流量特征聚类转用例卡片。
- **Phase 2: 影子流量无副作用沙箱回放、动态去噪差分与黄金基线大盘 (Shadow Replay & Golden Baseline Console)**
  - 聚焦影子流量安全沙箱回放控制台、动态噪声智能过滤字段级 Diff 比对器、以及黄金响应基线版本化大盘页面。
- **Phase 3: 实时接口契约动态逆向提取与 Breaking 变更级联防线面板 (Live Contract Guard & Impact Topology)**
  - 聚焦生产流量 OpenAPI/Protobuf 逆向推导与代码预览抽屉、契约破坏性变更 Breaking 仲裁卡片、以及微服务级联依赖拓扑图谱视图。
- **Phase 4: 流量驱动的混沌工程故障注入编排与系统韧性监控中心 (Traffic Chaos & Resilience Studio)**
  - 聚焦流量特征匹配故障注入编排抽屉、断路器生效时延与 RTO 自愈时序分析看板、以及生产流量防线端到端流水线监控页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：生产流量网关镜像捕获、智能脱敏与用例聚类合成控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **微服务网关旁路流量捕获与动态采样过滤抽屉** | `traffic_capture_gateway` | 落地 `TrafficCaptureGatewayDrawer.vue` 组件与 API 客户端；支持 HTTP/gRPC 协议切换、路径/方法正则过滤、动态采样率调节与实时捕获记录流展示；见 docs/evidence/traffic-capture-gateway-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[x]` | **生产敏感数据自适应脱敏规则配置与实时清洗弹窗** | `traffic_data_masker` | 落地 `TrafficDataMaskerModal.vue` 组件；支持 MASK 掩码 / HASH 伪名化 / REDACT 策略切换、敏感字段关键词配置与文本/JSON 在线清洗演练；见 docs/evidence/traffic-data-masker-modal-ui1-2-2026-10-16.md |
| UI1.3 `[x]` | **真实流量特征聚类归一与自动化测试用例合成卡片** | `traffic_to_test_case_synthesizer` | 落地 `TrafficToTestCaseSynthesizerCard.vue` 组件；展示动态路径归一化、聚类去重率 KPI（50%~90%+ 削减冗余）、以及参数化测试数据集抽取与一键生成用例；见 docs/evidence/traffic-to-test-case-synthesizer-card-ui1-3-2026-10-16.md |

---

### Phase 2：影子流量无副作用沙箱回放、动态去噪差分与黄金基线大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **影子流量无副作用沙箱隔离回放与外部 Mock 代理控制台** | `shadow_traffic_replay_engine` | 落地 `ShadowTrafficReplayConsoleDrawer.vue` 组件与 API 客户端；展示 BLOCK_WRITES 安全写拦截（0 脏数据）、第三方支付/短信 Mock 拦截代理、QPS 节流与回放流水；见 docs/evidence/shadow-traffic-replay-console-drawer-ui2-1-2026-10-16.md |
| UI2.2 `[x]` | **响应体动态字段智能去噪与字段级精确差分比对视图** | `traffic_diff_comparator` | 落地 `TrafficDiffComparatorViewer.vue` 组件；展示时间戳/UUID/Token 噪声自动过滤（消除 95%+ 误报）、红绿行级字段差分树与相似度得分 (0~100%)；见 docs/evidence/traffic-diff-comparator-viewer-ui2-2-2026-10-16.md |
| UI2.3 `[x]` | **接口黄金响应基线版本化管理与回归偏离大盘页面** | `golden_response_baseline_manager` | 落地 `GoldenResponseBaselineDashboardView.vue` 视图与路由；呈现多版本基线快照列表、自适应最低相似度阈值（≥95%）、回归偏离三级报警评级与批量校验；见 docs/evidence/golden-response-baseline-dashboard-view-ui2-3-2026-10-16.md |

---

### Phase 3：实时接口契约动态逆向提取与 Breaking 变更级联防线面板

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **生产流量 OpenAPI 3.0 / Protobuf 3 动态逆向推导与代码预览抽屉** | `live_contract_schema_extractor` | 落地 `LiveContractSchemaExtractorDrawer.vue` 组件与 API 客户端；展示多样本归纳推导的必填项、枚举、OpenAPI JSON 树与 Protobuf IDL 代码高亮及一键复制；见 docs/evidence/live-contract-schema-extractor-drawer-ui3-1-2026-10-16.md |
| UI3.2 `[x]` | **接口契约非对称破坏性变更 Breaking 评级仲裁卡片** | `contract_drift_breaking_evaluator` | 落地 `ContractDriftBreakingEvaluatorCard.vue` 组件与 API 客户端；展示双向非对称破坏性规则比对（请求新增必填/响应删除字段判定为 BREAKING）、兼容性得分与阻断行动项；见 docs/evidence/contract-drift-breaking-evaluator-card-ui3-2-2026-10-16.md |
| UI3.3 `[x]` | **契约漂移微服务级联依赖拓扑图谱与爆炸半径告警大盘** | `contract_drift_impact_topology_router` | 落地 `ContractDriftImpactTopologyView.vue` 视图与路由；基于 ECharts 关系拓扑图呈现微服务节点、消费字段碰撞、多跳级联波及服务与爆炸半径告警；见 docs/evidence/contract-drift-impact-topology-view-ui3-3-2026-10-16.md |

---

### Phase 4：流量驱动的混沌工程故障注入编排与系统韧性监控中心

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[x]` | **基于流量特征匹配的应用层混沌故障注入编排抽屉** | `traffic_chaos_fault_injector` | 落地 `TrafficChaosFaultInjectorDrawer.vue` 组件与 API 客户端；支持针对流量特征精准注入时延/503错误/数据截断/丢包四大模式，带最大触发次数安全熔断保护；见 docs/evidence/traffic-chaos-fault-injector-drawer-ui4-1-2026-10-16.md |
| UI4.2 `[x]` | **服务断路器熔断跳闸时延与 RTO 自愈时序分析看板** | `resilience_rto_recovery_evaluator` | 落地 `ResilienceRtoRecoveryDashboardCard.vue` 组件与 API 客户端；可视化呈现演练时序点、跳闸时延（ms）、降级成功率（%）、RTO 自愈时长与四级韧性评级；见 docs/evidence/resilience-rto-recovery-dashboard-card-ui4-2-2026-10-16.md |
| UI4.3 `[x]` | **生产流量防线 Checkpoint 检查点端到端全景监控看板页面** | `traffic_guard_pipeline_api` | 落地 `TrafficGuardPipelineMonitorView.vue` 页面与路由；展示端到端四阶段卡点流、Exit Code 0/1/2 裁决大横幅与高对比度 ANSI 终端控制台日志输出；见 docs/evidence/traffic-guard-pipeline-monitor-view-ui4-3-2026-10-16.md |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
