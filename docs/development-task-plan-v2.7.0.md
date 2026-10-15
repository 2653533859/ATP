# ATP v2.7.0 研发任务规划与执行计划 (2026-10-15)

> 规划日期：2026-10-15
> 基线依赖：[`docs/current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md)
> 任务台账：[`Task.md`](../Task.md)

---

## 1. 目标与范围 (Goals & Scope)

在 v2.6.0 实现 Android 真机池化、云原生分布式算力、多模态视觉自愈与外部生态双向协同的基础之上，v2.7.0 聚焦于：
1. **iOS 移动真机与模拟器池化调度 (iOS Device Farm)**：借鉴 AutoDroid 架构，统一 iOS 设备资产、WDA 状态心跳与租约行锁；
2. **全链路分布式 Trace 追踪与微服务下钻 (APM Tracing)**：用例请求自动注入 W3C TraceContext，打通 Jaeger/OpenTelemetry 链路瀑布图与慢 Span 定界；
3. **多端多协议可视化编排画布 (Visual Workflow Canvas)**：支持接口、数据库与端侧测试节点的流程图混合编排与单步断点调试；
4. **企业级风控与合规审计增强 (Security & Compliance)**：敏感数据动态脱敏网关与细粒度 API 凭证治理。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：iOS 移动真机池化与 W3C 自动化调度 (iOS Device Automation)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **iOS 统一设备资产与在线心跳模型** | 设备模块 | 扩展 `devices` 统一模型支持 `platform='ios'`、UDID、iOS 版本与 WDA 状态；实现 iOS 设备注册与心跳刷新；见 docs/evidence/unified-ios-device-asset-and-heartbeat-model-t1-1-2026-10-15.md |
| T1.2 `[x]` | **W3C/Appium 2 XCUITest 会话自愈与租约队列** | T1.1 | 建立 iOS 专用设备租约调度与行锁抢占；实现 WebDriverAgent 会话异常断连自动重连与恢复；见 docs/evidence/w3c-appium-xcuitest-session-healer-and-leases-t1-2-2026-10-15.md |
| T1.3 `[x]` | **IPA 资产解析与低代码步骤执行** | T1.2 | 支持 IPA 签名包 Bundle ID 与版本自动读取；接入点击/输入/滑动/断言与录屏/Syslog 归档；见 docs/evidence/ipa-metadata-parsing-and-ios-lowcode-steps-t1-3-2026-10-15.md |

---

### Phase 2：全链路分布式 Trace 追踪与微服务下钻 (Distributed Tracing & APM)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **W3C TraceContext 与 traceparent 协议自动注入** | 契约执行器 | 用例发出的所有 HTTP / gRPC 流量自动注入 W3C 标准 `traceparent` 上下文请求头；见 docs/evidence/w3c-trace-context-traceparent-auto-injection-t2-1-2026-10-15.md |
| T2.2 `[x]` | **OpenTelemetry / Jaeger 分布式调用链检索** | T2.1 | 根据测试用例的 TraceID 自动检索目标微服务集群调用拓扑与 Span 耗时瀑布图；见 docs/evidence/jaeger-opentelemetry-distributed-trace-waterfall-t2-2-2026-10-15.md |
| T2.3 `[x]` | **失败步骤慢调用瓶颈与异常 Span 自动标红聚类** | T2.2 | 自动将用例失败点精准下钻定位至服务端微服务异常 Span（如慢 SQL、RPC 超时或锁竞争）；见 docs/evidence/trace-anomaly-clustering-and-root-cause-t2-3-2026-10-15.md |

---

### Phase 3：多端多协议混合低代码可视化编排画布 (Visual Workflow Canvas)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[x]` | **多端多协议混合编排流程图引擎** | 用例模块 | 支持 HTTP $\rightarrow$ SQL $\rightarrow$ Redis $\rightarrow$ Android/iOS 节点的流式有向无环图（DAG）混合编排；见 docs/evidence/multi-protocol-mixed-workflow-dag-engine-t3-1-2026-10-15.md |
| T3.2 `[x]` | **节点间上下文变量双向数据流拓扑校验** | T3.1 | 自动分析节点间入参/出参变量拓扑依赖，防止循环依赖与未声明变量引用；见 docs/evidence/workflow-dataflow-topology-validator-t3-2-2026-10-15.md |
| T3.3 `[x]` | **画布单步断点调试与实时数据流观察器** | T3.2 | 支持在任意编排节点设置断点，单步执行并实时观察各节点入参与输出结果；见 docs/evidence/workflow-debugger-step-over-and-watchers-t3-3-2026-10-15.md |

---

### Phase 4：企业级安全风控与合规审计增强 (Security & Compliance Governance)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **敏感测试数据与测试凭据动态脱敏网关** | 审计模块 | 自动识别并脱敏用例出参、响应体与执行证据中包含的个人敏感信息（PII：如 18 位身份证、11 位手机号、16~19 位银行卡号、邮箱及自定义敏感词）；见 docs/evidence/sensitive-test-data-pii-redaction-gateway-t4-1-2026-10-15.md |
| T4.2 `[x]` | **API Key / 租户令牌细粒度权限管控与审计导出** | 认证模块 | 支持项目级/环境级 API Key 有效期与 IP 白名单防护，生成格式化安全审计报表；见 docs/evidence/api-key-tenant-governance-and-audit-export-t4-2-2026-10-15.md |
| T4.3 `[ ]` | **平台核心资产定时快照备份与灾备恢复演练** | 存储模块 | 支持 PostgreSQL + MinIO + SQLite 增量备份与自动恢复演练，保障企业级灾备恢复。 |

---

## 3. 质量门禁规则

1. **零警告零错误**：Ruff / Mypy / Bandit 必须持续通过，不可引入任何未声明或松弛降级。
2. **全覆盖单测证明**：每个任务必须配备专属独立单测文件，且满足 `pytest-standalone-sweep.py` 100% 独立通过。
3. **真实环境取证**：每项任务交付必须具备带日期的专项交付证据文档，落盘在 `docs/evidence/`。
