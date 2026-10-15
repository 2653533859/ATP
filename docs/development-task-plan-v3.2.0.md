# ATP v3.2.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**高可用微服务集群协同调度与全景自动化测试资产治理 (HA Cluster Orchestration & Global Asset Governance)**
> 承接基准：以 v3.0.0 企业级底座与 v3.1.0 全景交互控制台为依托，实现跨多节点 Worker 集群的自适应弹性调度、资产全生命周期依赖图谱、轻量级动态仿真沙箱编排与 CI/CD 质量准入门禁。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1：跨节点 Worker 集群自适应负载与动态弹性调度 (Dynamic Cluster Autoscaling & Adaptive Scheduling)**
  - 核心目标：实时采集与评估多 Worker 节点 CPU/内存/并发队列容量，实现基于负载评分的最优任务派发、动态抢占与失联故障转移（Failover）。
- **Phase 2：全域测试资产依赖拓扑与变更影响面智能分析 (Global Asset Dependency & Impact Analysis)**
  - 核心目标：构建全平台测试资产（用例/套件/计划/数据集/环境）全景图谱，自动分析接口契约变更影响面并触发精准回归。
- **Phase 3：多协议测试执行动态沙箱与隔离环境编排 (Multi-Protocol Sandbox Orchestration)**
  - 核心目标：按需拉起瞬时隔离的 Mock 仿真沙箱，打通跨协议（HTTP/gRPC/WebSocket）数据透传与流量镜像。
- **Phase 4：企业级测试质量度量大盘与质量门禁策略中心 (Quality Metrics & Governance Gate Center)**
  - 核心目标：聚合全生命周期测试度量指标，提供基于规则引擎的 CI/CD 发布准入门禁与防伪准入认证报告。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：跨节点 Worker 集群自适应负载与动态弹性调度 (Dynamic Cluster Autoscaling & Adaptive Scheduling)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| C1.1 `[x]` | **跨节点 Worker 节点动态负载监控与容量评分算法** | 调度模块 | 落地 `cluster_load_balancer` 服务与 `/cluster/workers/*` API；支持加权并发、内存与 CPU 负载评分算法，自动选取最优 Worker 节点；见 docs/evidence/cluster-load-balancer-c1-1-2026-10-16.md |
| C1.2 `[x]` | **基于执行队列水位与优先级自适应弹性抢占调度器** | C1.1 | 落地 `adaptive_queue_preemptor` 服务；支持高优先级任务（P0）抢占插队与低优先级自适应挂起，实时计算排队预计等待时长；见 docs/evidence/adaptive-queue-preemptor-c1-2-2026-10-16.md |
| C1.3 `[x]` | **节点失联与心跳超时自动化任务故障转移与断点重试** | C1.2 | 落地 `worker_failover_recovery` 服务；检测心跳超时的僵死 Worker 节点，自动剥离并原子重调度中断的任务，防止执行丢失；见 docs/evidence/worker-failover-recovery-c1-3-2026-10-16.md |

---

### Phase 2：全域测试资产依赖拓扑与变更影响面智能分析 (Global Asset Dependency & Impact Analysis)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| C2.1 `[x]` | **测试资产全景引用拓扑图谱与反向索引引擎** | 资产模块 | 落地 `asset_graph_indexer` 服务；解析用例-套件-计划-环境变量多层依赖链条，输出完整有向引用图谱；见 docs/evidence/asset-graph-indexer-c2-1-2026-10-16.md |
| C2.2 `[x]` | **接口契约变更影响面逆向推导与受影响用例标记** | C2.1 | 落地 `contract_change_impact_analyzer` 服务；对比 OpenAPI / JSON Schema 字段增删变动，自动逆向定位受损用例清单；见 docs/evidence/contract-change-impact-analyzer-c2-2-2026-10-16.md |
| C2.3 `[x]` | **变更影响用例自动化精准回归套件合成与触发** | C2.2 | 落地 `targeted_regression_trigger` 服务；一键将受波及的用例自动重组为精准最小化回归测试套件并下发执行；见 docs/evidence/targeted-regression-trigger-c2-3-2026-10-16.md |

---

### Phase 3：多协议测试执行动态沙箱与隔离环境编排 (Multi-Protocol Sandbox Orchestration)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| C3.1 `[ ]` | **瞬时轻量级仿真沙箱与动态端口生命周期调度** | 调度模块 | 落地 `ephemeral_sandbox_manager` 服务；支持秒级拉起隔离的 Mock 仿真容器/进程与生命周期回收。 |
| C3.2 `[ ]` | **跨协议数据透传与会话级上下文共享总线** | C3.1 | 落地 `cross_protocol_session_bus` 服务；打通 HTTP、gRPC、WebSocket 间统一上下文共享与数据跨协议传递。 |
| C3.3 `[ ]` | **沙箱网络流量镜像与回放实时隔离检测** | C3.2 | 落地 `sandbox_traffic_mirror` 服务；支持将指定测试流量无损镜像至沙箱环境，隔离真实下游副作用。 |

---

### Phase 4：企业级测试质量度量大盘与质量门禁策略中心 (Quality Metrics & Governance Gate Center)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| C4.1 `[ ]` | **全生命周期测试质量度量多维评分大盘** | 报表模块 | 落地 `quality_metrics_engine` 服务；度量缺陷逃逸率、用例覆盖度、用例执行波动方差与 MTTR 指标。 |
| C4.2 `[ ]` | **CI/CD 流水线智能质量门禁规则判定引擎** | C4.1 | 落地 `quality_gate_engine` 服务；支持配置阻塞发布卡点规则（如通过率 < 99%、存在未关闭严重缺陷直接拦截）。 |
| C4.3 `[ ]` | **自动化发布准入认证与防伪合格证书生成** | C4.2 | 落地 `release_readiness_certification` 服务；自动汇总测试证据与门禁达标报告，生成发布准入合格证书。 |

---

## 3. 质量门禁规则

1. **后端质量基线**：`ruff check`、`ruff format --check` 与 `mypy` 保持 100% 零错误。
2. **测试全覆盖与独立性**：每个任务配备对应测试文件，并通过 `scripts/pytest-standalone-sweep.py`。
3. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
