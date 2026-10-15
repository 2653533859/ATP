# ATP 平台全量功能与架构能力基线（2026-10-15 · v2.6.0）

## 1. 来源与版本状态

本文档作为 ATP 平台在 **2026-10-15** 完成 **v2.6.0** 重大版本研发、双模式割接与生产现场实测后的**权威全量能力基准线**。

- **Git 源码基线**：分支 `main`（提交 `027ae8f7`）；
- **版本发布说明**：[`docs/v2.6.0-release-notes.md`](v2.6.0-release-notes.md)；
- **任务跟踪台账**：[`Task.md`](../Task.md)（v2.6.0 全部 12 项重大特性已 100% 全量闭环）；
- **生产双端运行状态**：
  - **Linux 生产级云原生集群**：运行于 `192.168.3.196:8000`，Helm Revision 64，Alembic 迁移版本 `20261015_0080 (head)`，6 个核心 Pod（backend, beat, flower, performance-worker, web-recorder, worker）稳定处于 1/1 Running 且 0 重启；生产割接后真实业务 Canary（Run 172/173）100% 通过；
  - **Windows 单机轻量模式**：运行于 `127.0.0.1:8001`，基于 SQLite Schema 13 + 本地持久队列 + 本地存储，支持免配置单机便携包（2.22 MB ZIP，SHA-256 清单零漂移）。

---

## 2. 全量核心功能支持矩阵

| 业务领域 / 模块 | Windows 本地单机实现 | Linux 生产级集群实现 | 验收状态与证据 |
|---|---|---|:---:|
| **双模式架构与隔离** | 独立本地 Cookie (`atp_local_access_token`)，中间件校验 `X-ATP-Client-Mode`，模式冲突 409 拦截 | 独立集群 Cookie (`atp_access_token`)，支持多租户、多项目与细粒度 RBAC 权限控制 | **闭环**<br/>[`linux-site-production-cutover-v2-6-0-2026-10-15.md`](evidence/linux-site-production-cutover-v2-6-0-2026-10-15.md) |
| **Hermes AI 与 MCP 协议** | 本地支持 `python -m app.mcp` Stdio 与 `/api/v1/mcp/rpc` HTTP 双模暴露 7 项标准核心工具；支持 8 类面板持久草稿 | 具备相同的标准 MCP Server 能力，支持外部 LLM 智能体跨网络安全调用与会话追踪 | **闭环**<br/>[`mcp-server-protocol-standardization-p1-1-2026-10-15.md`](evidence/mcp-server-protocol-standardization-p1-1-2026-10-15.md) |
| **多模态断言与视觉自愈** | 本地执行器集成 `assert_visual_element`，DOM 选择器失效时通过滑动窗口与 OCR 物理点击自动回退自愈 | Worker 执行器具备相同的视觉相似度比对与视觉物理定位自愈能力 | **闭环**<br/>[`multi-modal-visual-assertion-and-healing-p1-2-2026-10-15.md`](evidence/multi-modal-visual-assertion-and-healing-p1-2-2026-10-15.md) |
| **接口自动化与契约同步** | 支持 HTTP / WebSocket / GraphQL / gRPC 执行与多协议流水线编排；支持 OpenAPI/Swagger 增量用例双向对齐 | 相同的多协议支持与后台任务派发，空步骤防御拦截 | **闭环**<br/>[`bidirectional-spec-sync-case-alignment-p1-3-2026-10-15.md`](evidence/bidirectional-spec-sync-case-alignment-p1-3-2026-10-15.md) |
| **Android 真机与 AutoDroid** | 本地 ADB直连；Scrcpy 60FPS 硬件直解与毫秒触控；工作台就地用例闭环与 422 校验修复 | 支持 AutoDroid 反向隧道远程设备入池、真机矩阵并发分发、行锁智能租约调度与拔线自动收敛 | **闭环**<br/>[`autodroid-reverse-tunnel-device-pool-p2-1-2026-10-15.md`](evidence/autodroid-reverse-tunnel-device-pool-p2-1-2026-10-15.md) |
| **故障现场音视频归档** | 支持 MP4 录屏与截图存储 | Crash/ANR 异常自动触发 `[T-30s, T+30s]` MP4 短视频与 Logcat 故障现场切片归档 | **闭环**<br/>[`android-incident-video-segment-and-logcat-alignment-p2-3-2026-10-15.md`](evidence/android-incident-video-segment-and-logcat-alignment-p2-3-2026-10-15.md) |
| **云原生弹性性能算力池** | 本地单机 k6 / Locust / JMeter 进程调度与快速指标采集 | K8s 动态 `batch/v1` Job 弹性扩缩容、300s TTL 自动清理、时序指标多 Pod 聚合与基线门禁判定 | **闭环**<br/>[`k8s-dynamic-performance-pod-operator-p3-1-2026-10-15.md`](evidence/k8s-dynamic-performance-pod-operator-p3-1-2026-10-15.md) |
| **性能熔断与高可用** | 本地进程级取消信号 | 动态构建 Prometheus 告警规则组，压力机/被测目标饱和度（>=90%）自动熔断防雪崩；HA 节点优选 | **闭环**<br/>[`multi-node-ha-prometheus-alerting-circuit-breaker-p3-3-2026-10-15.md`](evidence/multi-node-ha-prometheus-alerting-circuit-breaker-p3-3-2026-10-15.md) |
| **企业级协同与通知** | 支持邮件、企微 template_card、钉钉 actionCard 与飞书 interactive 卡片预览与发送 | 全渠道交互式富卡片通知支持，带状态色彩徽标、通过率大号看板与直达测试报告 Action 按钮 | **闭环**<br/>[`rich-notification-cards-wechat-dingtalk-feishu-p4-1-2026-10-15.md`](evidence/rich-notification-cards-wechat-dingtalk-feishu-p4-1-2026-10-15.md) |
| **外部缺陷生命周期对齐** | 本地缺陷增删改查与关联执行记录 | 支持 Jira / 禅道 Webhook 自动接收外部状态变更并收敛内部缺陷状态；支持一键反向推送到外部 Issue | **闭环**<br/>[`jira-zentao-bidirectional-defect-state-machine-p4-2-2026-10-15.md`](evidence/jira-zentao-bidirectional-defect-state-machine-p4-2-2026-10-15.md) |
| **重试策略与安全审计** | 本地记录基本执行事件 | 瞬时错误与 HTTP 502/503/429 智能重试，指数退避与 Jitter 防惊群；Webhook URL 与凭证深度脱敏并记录审计日志 | **闭环**<br/>[`cross-network-notification-retry-and-security-audit-p4-3-2026-10-15.md`](evidence/cross-network-notification-retry-and-security-audit-p4-3-2026-10-15.md) |
| **观测体系与稳定性** | 本地日志落盘与健康检查探针 | Prometheus 5/5 采集目标全量 up；Flower 持续在线；14 日连续 0 违约高精度 SLO 监测 | **闭环**<br/>[`linux-site-14day-slo-flower-trend-n5-2-2026-10-15.md`](evidence/linux-site-14day-slo-flower-trend-n5-2-2026-10-15.md) |

---

## 3. 架构演进与全景拓扑

```mermaid
graph TD
  User([用户 / 测试工程师 / LLM Agent])

  subgraph Client[前端与外部调用层]
    WebUI[Vue 3 + TypeScript 生产 SPA]
    MCPClient[Cursor / Claude Desktop / Hermes MCP Client]
    WebhookSource[Jira / 禅道 Webhook 回调]
  end

  subgraph Core[ATP 核心业务层 (FastAPI)]
    Auth[多模式认证 & 租户隔离]
    MCPServer[MCP Server 7项标准工具]
    CaseEngine[用例编排 & 契约同步]
    DeviceMgr[AutoDroid 真机池化 & 租约管理]
    PerfMgr[K8s 弹性算力调度 & 熔断器]
    NotifyEngine[富卡片模板 & 抖动退避重试]
    DefectEngine[双向缺陷状态机]
  end

  subgraph Storage[存储与消息基座]
    PostgreSQL[(PostgreSQL 16 · 迁移头 0080)]
    SQLiteLocal[(SQLite 13 · 本地轻量模式)]
    Redis[(Redis 缓存 & 任务队列)]
    MinIO[(MinIO 对象存储)]
  end

  subgraph Workers[执行器集群]
    CeleryWorkers[异步执行 Worker]
    K8sJobs[K8s 动态算力 Pod (k6 / Locust)]
    AndroidAgents[AutoDroid 反向隧道真机 Agent]
  end

  User --> Client
  Client --> Core
  Core --> Storage
  Core --> Workers
```

---

## 4. 结论与后续演进建议

ATP 平台自此已完成从**单一单体测试脚本管理工具**向**双架构支持、真机池化、云原生算力调度与企业级生态协同的全功能自动化测试平台**的彻底蜕变。

**后续演进建议（v2.7.0 规划重点）**：
1. **iOS 设备真机池化调度支持**：借鉴 AutoDroid 反向隧道与租约行锁成熟架构，引入 go-ios / WDA 反向隧道与真机池化；
2. **测试结果全链路分布式追踪 (Distributed Trace Alignment)**：将用例执行各步骤与被测系统的 OpenTelemetry / Jaeger TraceID 自动贯通，实现从测试用例一键跳转至后端微服务调用链的下钻排查；
3. **低代码可视化编排画布体验升级**：引入更直观的拖拽式多协议与多端用例混合编排流图，提升业务测试人员协作效率。
