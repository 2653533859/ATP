# ATP v2.8.0 研发任务规划与执行计划 (2026-10-16)

> 规划日期：2026-10-16
> 基线依赖：[`docs/current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md)
> 任务台账：[`Task.md`](../Task.md)

---

## 1. 目标与范围 (Goals & Scope)

在 v2.7.0 实现 iOS 移动真机池化、全链路分布式 Trace、可视化工作流画布与 API 凭据风控的基础之上，v2.8.0 聚焦于：
1. **移动端弱网与网络仿真自动化 (Mobile Network Simulation & Throttle Engine)**：支持 2G/3G/4G/高延迟/丢包/断网仿真，覆盖 Web CDP 与移动端弱网指标采集；
2. **智能用例自动化冒烟生成与自愈 (AI Autonomous Exploration & Case Synthesis)**：基于页面状态树的有向图探索算法，自动生成可执行的 TestCase 资产；
3. **性能基准自动化持续压测与降级演练 (Continuous Performance Gate & Chaos Injection)**：支持基准打标、故障注入（CPU 压满/下游 503）与 RTO 恢复时长测定；
4. **企业级多租户资源配额与成本分析 (Multi-Tenant Quota & Resource FinOps)**：项目级并发配额硬限制与 MinIO/数据库存储生命周期策略自动清理。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：移动端弱网与网络仿真自动化 (Mobile Network Simulation)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| Q1.1 `[x]` | **弱网仿真配置与延迟丢包模型** | 移动端模块 | 建立标准弱网档案（2G/3G/4G/离线/高丢包）；支持带宽限制计算、丢包概率判定与 CDP/ADB 命令映射；见 docs/evidence/mobile-network-simulation-and-throttling-q1-1-2026-10-16.md |
| Q1.2 `[x]` | **弱网专项任务调度与用例指标采集** | Q1.1 | 建立带弱网配置的用例执行调度；采集弱网状态下的请求耗时、重试次数与超时容错指标；见 docs/evidence/weak-network-simulation-scheduler-and-metrics-q1-2-2026-10-16.md |
| Q1.3 `[x]` | **网络流量抓包与故障注入分析** | Q1.2 | 支持请求流量抓包元数据解析，模拟 DNS 劫持与连接中断故障归档；见 docs/evidence/network-capture-analysis-and-fault-injection-q1-3-2026-10-16.md |

---

### Phase 2：智能用例自动化冒烟生成与自愈 (AI Autonomous Exploration)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| Q2.1 `[x]` | **基于状态树的智能探索遍历引擎** | 探索模块 | 实现基于 DOM / Accessibility Tree 的广度/深度有限状态机探索算法，防循环遍历；见 docs/evidence/state-tree-autonomous-exploration-engine-q2-1-2026-10-16.md |
| Q2.2 `[ ]` | **探索事件序列自动合成为 TestCase** | Q2.1 | 将探索过程中的有效点击/输入事件流自动提炼合并为标准 TestCase 数据资产。 |
| Q2.3 `[ ]` | **异常崩溃与死循环探索熔断保护** | Q2.2 | 在遇到黑屏、反复死循环跳转或连续错误时自动触发熔断降级与探索收敛。 |

---

### Phase 3：性能基准自动化持续压测与降级演练 (Continuous Performance & Chaos)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| Q3.1 `[ ]` | **定时自动化性能基准打标与趋势偏移告警** | 性能模块 | 定时自动触发基线对齐任务，对比 RPS 偏离度并输出基准漂移告警。 |
| Q3.2 `[ ]` | **压力下故障注入与混沌恢复时长测定** | Q3.1 | 支持在压测期间注入模拟下游故障与网络抖动，精准测定系统服务自愈恢复时长（RTO）。 |
| Q3.3 `[ ]` | **多维性能对比与容量预测模型** | Q3.2 | 提供多轮压测报告的横向横截面比对，基于线性/多项式回归预测集群最大承载容量。 |

---

### Phase 4：企业级多租户资源配额与成本分析 (Multi-Tenant Quota & FinOps)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| Q4.1 `[ ]` | **项目级并发配额与执行时长硬限制** | 调度模块 | 支持为项目分配最大并发任务数与每日执行总时长上限，超限自动排队或拒绝。 |
| Q4.2 `[ ]` | **测试资产存储生命周期与自动归档清理** | 存储模块 | 依据保留天数策略定时扫描并清理过期的 MinIO 视频、截图与执行历史日志。 |
| Q4.3 `[ ]` | **平台计算与存储资源成本统计报表导出** | Q4.1, Q4.2 | 统计各项目消耗的 Worker CPU-小时数与存储空间占用，生成企业级 FinOps 成本报表。 |

---

## 3. 质量门禁规则

1. **零警告零错误**：Ruff / Mypy / Bandit 保持 100% 通过。
2. **全覆盖单测证明**：每个任务配备独立单测文件并通过 `pytest-standalone-sweep.py`。
3. **真实环境取证**：每项任务交付必须具备带日期的专项交付证据文档，落盘在 `docs/evidence/`。
