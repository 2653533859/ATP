# ATP v4.0.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**分布式调用链全息追踪、分布式事务一致性稽核、智能缺陷根因推导与 AI 自愈引擎 (Distributed Tracing, Transaction Consistency, Root-Cause Diagnosis & AI Self-Remediation Engine)**
> 承接基准：以 v3.8.0 / v3.9.0 交付的生产流量录制回放、接口黄金基线、动态契约破坏防线与混沌工程韧性监控为基础，进一步向微服务全链路分布式可观测性、数据一致性校验与自动化自愈修复纵深推进，打造完整的企业级智能质量工程底盘。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 分布式调用链全息追踪与拓扑性能瓶颈火焰图 (Distributed Trace Telemetry, Span Hierarchy & Performance Flamegraph)**
  - 聚焦 OpenTelemetry / W3C TraceContext 全链路 Span 追踪数据处理、跨服务关键调用路径耗时量化与火焰图生成、以及分布式链路慢调用智能聚类。
- **Phase 2: 微服务分布式事务与跨系统数据最终一致性稽核 (Distributed Transaction & Cross-System Data Consistency Auditor)**
  - 聚焦 Sagas / TCC 分布式长事务状态追踪与悬挂事务发现、跨微服务异构数据库最终一致性对账稽核、以及消息中间件消息幂等消费与死信队列监控。
- **Phase 3: 自动化测试执行失败智能根因推导与故障图谱 (Automated Test Failure Intelligent Root-Cause Diagnosis)**
  - 聚焦用例失败日志、异常调用栈与系统环境指标多模态根因推导、已知缺陷向量指纹特征匹配、以及缺陷工单自动创建与派发。
- **Phase 4: AI 驱动的用例脚本断言自愈与代码级自动修复补丁 (AI-Driven Case Self-Healing & Code Auto-Remediation Patch)**
  - 聚焦 UI 元素定位失效动态自愈与多策略降级容错、API 响应字段变迁自适应断言修补、以及自愈全生命周期审计追踪与补丁应用。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：分布式调用链全息追踪与拓扑性能瓶颈火焰图

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **OpenTelemetry 全链路 Span 追踪采集中继与调用树重构器** | `distributed_trace_telemetry_relay` | 落地 `distributed_trace_telemetry_relay` 服务与 `/trace/telemetry/*` API；支持 TraceId/SpanId 级联树重构、父子依赖解析与多协议头部透传；见 docs/evidence/distributed-trace-telemetry-relay-t1-1-2026-10-16.md |
| T1.2 `[x]` | **跨服务调用关键路径时延分析与火焰图性能瓶颈定位器** | `critical_path_flamegraph_profiler` | 落地 `critical_path_flamegraph_profiler` 服务与 `/trace/flamegraph/*` API；量化关键路径耗时占比（Critical Path Latency），输出标准化 Flamegraph 数据结构；见 docs/evidence/critical-path-flamegraph-profiler-t1-2-2026-10-16.md |
| T1.3 `[x]` | **分布式调用链路异常波动与高频慢调用智能聚类诊断器** | `trace_anomaly_slow_call_clusterer` | 落地 `trace_anomaly_slow_call_clusterer` 服务与 `/trace/anomaly-cluster/*` API；基于耗时分布与错误码自动识别慢调用簇，量化波动偏离度；见 docs/evidence/trace-anomaly-slow-call-clusterer-t1-3-2026-10-16.md |

---

### Phase 2：微服务分布式事务与跨系统数据最终一致性稽核

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **Sagas/TCC 分布式事务流转跟踪与悬挂事务探测器** | `saga_transaction_state_tracker` | 落地 `saga_transaction_state_tracker` 服务与 `/consistency/saga/*` API；跟踪分布式事务分支 Try/Confirm/Cancel 状态，探测超时未决与悬挂事务；见 docs/evidence/saga-transaction-state-tracker-t2-1-2026-10-16.md |
| T2.2 `[x]` | **跨微服务异构数据源最终一致性双向稽核校验器** | `cross_db_data_consistency_auditor` | 落地 `cross_db_data_consistency_auditor` 服务与 `/consistency/audit/*` API；基于业务主键对齐比对跨库字段数据，输出不一致差分记录与对账达标率；见 docs/evidence/cross-db-data-consistency-auditor-t2-2-2026-10-16.md |
| T2.3 `[x]` | **消息事件总线消费延迟、死信积压与幂等消费验证器** | `event_bus_deadletter_idempotency_guard` | 落地 `event_bus_deadletter_idempotency_guard` 服务与 `/consistency/event-bus/*` API；监控消息消费积压、死信重发判定与重复消息幂等执行校验；见 docs/evidence/event-bus-deadletter-idempotency-guard-t2-3-2026-10-16.md |

---

### Phase 3：自动化测试执行失败智能根因推导与故障图谱

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T3.1 `[x]` | **多模态测试失败日志与异常堆栈智能根因推导器** | `test_failure_root_cause_reasoner` | 落地 `test_failure_root_cause_reasoner` 服务与 `/diagnosis/root-cause/*` API；融合控制台日志、HTTP 状态与 Span 错误栈定位首发异常点；见 docs/evidence/test-failure-root-cause-reasoner-t3-1-2026-10-16.md |
| T3.2 `[x]` | **历史已知缺陷向量指纹特征相似度匹配检索器** | `incident_knowledge_fingerprint_matcher` | 落地 `incident_knowledge_fingerprint_matcher` 服务与 `/diagnosis/fingerprint/*` API；提取失败特征向量，与历史问题知识库相似度匹配与经验推荐；见 docs/evidence/incident-knowledge-fingerprint-matcher-t3-2-2026-10-16.md |
| T3.3 `[x]` | **缺陷严重度智能评级与第三方工单自动指派网关** | `defect_auto_ticket_dispatcher` | 落地 `defect_auto_ticket_dispatcher` 服务与 `/diagnosis/ticket-dispatch/*` API；输出缺陷等级判定，对接 Jira/GitHub/Webhook 自动建单；见 docs/evidence/defect-auto-ticket-dispatcher-t3-3-2026-10-16.md |

---

### Phase 4：AI 驱动的用例脚本断言自愈与代码级自动修复补丁

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **UI 元素定位漂移动态自愈与多策略加权降级重试执行器** | `smart_locator_multistrategy_healer` | 落地 `smart_locator_multistrategy_healer` 服务与 `/healing/locator/*` API；结合文本/ID/XPath/语义距离加权推导备选定位，自愈成功率 ≥90%。 |
| T4.2 `[ ]` | **接口响应格式变迁自适应断言规则推导与自动打补丁器** | `adaptive_assertion_auto_patcher` | 落地 `adaptive_assertion_auto_patcher` 服务与 `/healing/assertion-patch/*` API；针对向下兼容字段变迁自动修正断言表达式与默认值。 |
| T4.3 `[ ]` | **端到端测试自愈审计追踪与修复补丁一键应用流水线** | `self_healing_audit_patch_pipeline` | 落地 `self_healing_audit_patch_pipeline` 服务与 `/healing/pipeline/*` API；提供自愈全流程不可篡改审计记录与补丁应用/回滚控制。 |

---

## 3. 质量门禁规则

1. **单测必配**：每个交付服务均配套独立的 `backend/tests/services/test_<name>.py` 单元测试，测试覆盖核心路径与异常分支。
2. **独立通过**：每个测试文件均必须能够脱离全量测试套件独立运行通过（`pytest <file>` PASS）。
3. **代码规范**：`ruff check` 与 `ruff format --check` 全绿通过，零代码规范违规。
4. **类型安全**：`mypy` 增量通过严格静态类型检查。
5. **交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
