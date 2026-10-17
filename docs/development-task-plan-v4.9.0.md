# ATP v4.9.0 研发任务规划与执行计划 (2026-10-17)

## 1. 版本定位与目标

**ATP v4.9.0** 聚焦于自动化测试平台在**测试全链路分布式链路追踪贯通 (Distributed Trace Alignment) 与 OpenTelemetry 观测中台集成**的彻底突破。

传统自动化测试平台最大的痛点在于**黑盒测试与后端微服务观测体系孤立脱节**：测试用例报错仅能看到 HTTP 500、超时或断言不匹配，排查时测试工程师必须联系后端在茫茫日志海中手工检索，排障成本极高。

ATP v4.9.0 彻底打通这一壁垒：
1. **W3C TraceContext 标准协议注入**：每个用例执行、每个步骤调用自动注入标准 `traceparent` 与 `tracestate`，贯通被测微服务系统的 OpenTelemetry / Jaeger 链路；
2. **测试步骤与微服务 Span 精准对齐**：时钟偏移补偿（Clock Skew Compensation）与 TraceID 自动绑定，用例断言失败时自动捕获对应后端微服务的首因 Span、慢 SQL 查询与异常堆栈；
3. **时序甘特图与火焰图可视化控制台**：在用例执行详情与运行中心中一键展开全链路微服务调用甘特图（Gantt）与下钻火焰图；
4. **全景追踪贯通大盘与审计存证**：提供全站用例链路对齐率、慢跨度下钻、采样率动态治理与 64 位 SHA-256 审计凭证签名。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：W3C TraceContext 与 OpenTelemetry 注入透传引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **W3C TraceContext 标准协议注入与提取服务** | `backend/app/services/w3c_trace_context_injector.py` | 实现 W3C `traceparent` (version-trace_id-parent_id-flags) 与 `tracestate` 格式生成、解析与上下文注入；单测独立通过；见 docs/evidence/w3c-trace-context-injector-t1-1-2026-10-17.md |
| T1.2 `[x]` | **异步任务与执行器链路上下文传播拦截器** | `backend/app/services/test_execution_trace_propagator.py` | 确保 Celery Worker 与多步测试执行会话（REST/gRPC/WebSocket）跨线程/进程透明透传 TraceContext；单测独立通过；见 docs/evidence/test-execution-trace-propagator-t1-2-2026-10-17.md |
| T1.3 `[x]` | **OTLP / Jaeger 追踪数据协议导出适配器** | `backend/app/services/otlp_trace_exporter.py` | 实现标准 OTLP JSON / Protobuf 格式 Span 数据打包与异步导出通道，支持内存模拟器与外接 OpenTelemetry Collector；单测独立通过；见 docs/evidence/otlp-trace-exporter-t1-3-2026-10-17.md |

---

### Phase 2：用例步骤与微服务分布式调用链精准对齐

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **测试步骤与服务端调用链跨网络时钟对齐器** | `backend/app/services/trace_timestamp_clock_skew_aligner.py` | 实现前后端与跨机房网络时钟偏移补偿算法，将毫秒级测试步骤与服务端 Span 时间戳精确校准；单测独立通过；见 docs/evidence/trace-timestamp-clock-skew-aligner-t2-1-2026-10-17.md |
| T2.2 `[x]` | **异常步骤调用链深潜下钻与首因归因器** | `backend/app/services/step_trace_deep_dive_analyzer.py` | 当测试步骤失败（4xx/5xx/断言未通过）时，根据 TraceID 自动检索关联调用链，定位首个报错 Span、慢 SQL 查询及堆栈；单测独立通过；见 docs/evidence/step-trace-deep-dive-analyzer-t2-2-2026-10-17.md |
| T2.3 `[x]` | **跨协议多跳调用链拓扑血缘重构器** | `backend/app/services/cross_protocol_trace_lineage_builder.py` | 解析包含 HTTP、gRPC、Kafka/RocketMQ 及 DB 访问的多跳 Span 树，构建可视化调用图谱与依赖关系；单测独立通过；见 docs/evidence/cross-protocol-trace-lineage-builder-t2-3-2026-10-17.md |

---

### Phase 3：链路追踪诊断控制台与火焰图下钻大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[x]` | **步骤级分布式调用链时序甘特图抽屉** | `frontend/src/views/run/components/StepTraceTimelineDrawer.vue` | 落地甘特图展示服务耗时条、Span 树状折叠、状态色彩徽标与点击查看请求/响应/SQL属性；单测独立通过；见 docs/evidence/step-trace-timeline-drawer-ui3-1-2026-10-17.md |
| T3.2 `[x]` | **慢跨度与服务依赖下钻火焰图卡片** | `frontend/src/views/run/components/SpanFlamegraphInspectorCard.vue` | 落地微服务调用火焰图卡片，支持放大/缩小、高耗时跨度红色高亮与一键筛选；单测独立通过；见 docs/evidence/span-flamegraph-inspector-card-ui3-2-2026-10-17.md |
| T3.3 `[x]` | **全局测试执行分布式追踪贯通全景大盘页面** | `frontend/src/views/quality/DistributedTraceAlignmentDashboardView.vue` | 落地路由 `/quality/trace-alignment`；汇总全站用例 Trace 对齐率（100%）、微服务平均跳数、慢跨度分布与拓扑列表；单测独立通过；见 docs/evidence/distributed-trace-alignment-dashboard-ui3-3-2026-10-17.md |

---

### Phase 4：追踪数据防篡改签名、容量治理与发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **Trace 采样率动态调谐与敏感数据脱敏过滤器** | `backend/app/services/trace_sampler_and_sanitizer.py` | 支持基于概率与失败优先的自适应采样（Adaptive Sampling），自动对 URL、Header 与 SQL 参数中的 Token/密码进行脱敏；单测独立通过；见 docs/evidence/trace-sampler-and-sanitizer-t4-1-2026-10-17.md |
| T4.2 `[x]` | **追踪审计凭据 64 位 SHA-256 防篡改存证器** | `backend/app/services/trace_evidence_fingerprint_signer.py` | 为全链路 Span 与用例步骤对齐记录生成不可篡改 SHA-256 签名，支持合规审计验签；单测独立通过；见 docs/evidence/trace-evidence-fingerprint-signer-t4-2-2026-10-17.md |
| T4.3 `[ ]` | **v4.9.0 全链路分布式追踪中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v4.9.0-release-notes.md` 与专项交付证据。 |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式化完全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vue-tsc --noEmit` 严格类型零错误；
   - `vitest run` 单测 100% PASS；
   - `vite build` 生产构建成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
