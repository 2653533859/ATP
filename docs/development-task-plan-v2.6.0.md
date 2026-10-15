# ATP v2.6.0 研发任务与演进规划（2026-10-15）

> 规划起点：`v2.5.0`（提交 `f6e679aa`）
> 基线状态：N0 ~ N6 全量 28 项任务已在本地与生产环境（K3s rev63 / SQLite 13）双侧闭环
> 关联索引：[`docs/evidence-index-2026-10-15.md`](docs/evidence-index-2026-10-15.md) 与 [`docs/v2.5.0-release-notes.md`](docs/v2.5.0-release-notes.md)

---

## 1. 规划目标与演进背景

在 v2.5.0 全面确立了“Windows 独立轻量单机”与“Linux 生产集群”的双模式隔离底座、Scrcpy 60FPS 实时流、多步场景编排与协议执行体系后，**v2.6.0 将重点从“测试底座与模式闭环”迈向“智能化、设备池化与分布式云原生扩展”**：

1. **AI 智能中枢与协议标准化 (Hermes MCP & Multi-modal)**：接入开放标准的 Model Context Protocol (MCP)，将 ATP 核心测试能力以标准 Tools 形式向 Cursor / Claude / 本地大模型暴露；结合视觉模型深化多模态 UI 元素断言与自愈；
2. **移动端真机池化与 AutoDroid 隧道治理 (Device Pool & Remote Tunnel)**：基于 SQLite 13 / PostgreSQL 0079 中的 Agent 隧道协议，实现多品牌 Android 真机池化调度、并发套件分配与拔线自动容灾；
3. **云原生分布式性能压测 (Dynamic K8s Performance Operator)**：突破单节点压测瓶颈，实现基于 Kubernetes 动态 Job 的分布式 k6 / Locust 算力分片调度与实时指标聚合；
4. **企业级协作生态闭环 (Enterprise Notifications & Defect Tracker)**：正式落地钉钉/企业微信/飞书富交互卡片通知，以及 Jira / 禅道 / GitHub Issues 的双向缺陷生命周期同步。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### P1：Hermes AI 智能中枢与 MCP 协议标准 (AI & Tool Protocol)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| P1.1 `[x]` | **ATP 核心工具 MCP Server 标准化暴露** | v2.5.0 底座 | JSON-RPC 2.0 / HTTP / Stdio 适配器落地；开放 7 项标准 Tools；实机与 8 项单测全通过；见 docs/evidence/mcp-server-protocol-standardization-p1-1-2026-10-15.md |
| P1.2 `[x]` | **多模态视觉断言与元素视觉自愈** | P1.1, AI 模块 | 支持 assert_visual_element 相似度与 OCR 文本断言；DOM 定位器失效时自动触发 OCR 与视觉模板物理坐标回退点击自愈；见 docs/evidence/multi-modal-visual-assertion-and-healing-p1-2-2026-10-15.md |
| P1.3 `[x]` | **双向规格同步与测试资产自动对齐** | P1.1 | OpenAPI/Swagger 与既有用例自动比对，生成新增接口补丁草稿与变更废弃提示；实机与 5 项单测全通过；见 docs/evidence/bidirectional-spec-sync-case-alignment-p1-3-2026-10-15.md |

---

### P2：Android 真机池化调度与远程 Agent 治理 (Device Pool & Matrix)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| P2.1 `[x]` | **AutoDroid 远程反向隧道 Agent 注册与心跳** | Schema 13 表 | 完善 remote_agents 与 remote_agent_devices 动态绑定，实现跨网设备自动入池同步至 central devices 表并自动联动在线/离线状态；见 docs/evidence/autodroid-reverse-tunnel-device-pool-p2-1-2026-10-15.md |
| P2.2 `[x]` | **真机矩阵并发执行与智能租约队列** | P2.1 | 支持套件 Android 用例按真机矩阵并发分发展开；设备池智能抢占未占用设备；掉线自动释放租约并收敛在途任务；见 docs/evidence/device-matrix-execution-lease-queue-p2-2-2026-10-15.md |
| P2.3 `[x]` | **Android 录屏分段与 Logcat 故障现场自动归档** | P2.2 | 结合稳定性/Monkey 专项，在发生 ANR / Crash 时自动按时间戳截取前后 30 秒 MP4 视频与对齐的 Logcat 崩溃堆栈；见 docs/evidence/android-incident-video-segment-and-logcat-alignment-p2-3-2026-10-15.md |

---

### P3：云原生 Kubernetes 分布式性能算力池 (Cloud-Native Distributed Performance)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| P3.1 `[x]` | **K8s 动态性能压测 Pod 弹性扩缩容调度** | K3s 集群 | 实现基于 batch/v1 Job 的动态弹性算力分片调度与自动回收（ttlSecondsAfterFinished）；支持 k6/Locust 负载精确拆分；见 docs/evidence/k8s-dynamic-performance-pod-operator-p3-1-2026-10-15.md |
| P3.2 `[x]` | **分布式性能指标实时汇总与基线比对** | P3.1 | 聚合多 Pod 产生的实时 TPS、响应时间分位数与错误率；压测完成自动与历史最佳基线对比并输出判定结论；见 docs/evidence/distributed-performance-metrics-aggregation-and-baseline-p3-2-2026-10-15.md |
| P3.3 `[x]` | **多节点高可用与 Prometheus 报警规则集成** | P3.2, 观测系统 | 压测期间动态采集被测目标与压力机本身的 CPU/内存/网络饱和度，超限自动熔断保护；见 docs/evidence/multi-node-ha-prometheus-alerting-circuit-breaker-p3-3-2026-10-15.md |

---

### P4：企业级通知协同与外部缺陷平台双向同步 (Ecosystem & Integrations)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| P4.1 `[x]` | **企业微信 / 钉钉 / 飞书 富卡片通知模板** | 通知模块 | 统一支持带状态颜色、通过率看板、直达链接与操作按钮的 Interactive Message Card，脱离简单纯文本 Webhook；见 docs/evidence/rich-notification-cards-wechat-dingtalk-feishu-p4-1-2026-10-15.md |
| P4.2 `[x]` | **Jira / 禅道 双向缺陷生命周期状态机同步** | 缺陷模块 | 平台内部缺陷一键推送到外部 Jira / 禅道；外部状态变更为已修复/已关闭时，自动更新平台内缺陷状态；见 docs/evidence/jira-zentao-bidirectional-defect-state-machine-p4-2-2026-10-15.md |
| P4.3 `[x]` | **跨网络环境通知投递重试与安全审计** | P4.1, P4.2 | 投递失败自动指数退避重试，密钥与敏感请求参数完全脱敏并记录审计日志；见 docs/evidence/cross-network-notification-retry-and-security-audit-p4-3-2026-10-15.md |

---

## 3. 质量门禁与实施规则

1. **双模式兼容性铁律**：所有新功能必须保障 Windows 本地单机与 Linux 生产集群双轨兼容；
2. **代码审查与门禁规范**：每个阶段严格执行实现 -> 定向测试 -> 独立代码审查 -> 修复 -> 证据归档 -> Git Commit/Push 闭环；
3. **真实环境取证**：拒绝伪造外部集成证据，每个外部平台与真机必须具备带日期的真实环境验证记录。
