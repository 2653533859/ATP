# ATP v4.1.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**分布式链路全息追踪火焰图、数据一致性对账大盘、智能根因图谱与 AI 自愈前端控制台 (Distributed Tracing Flamegraph, Consistency Audit Dashboard, Root-Cause Graph & AI Self-Healing Frontend Console)**
> 承接基准：全面承接 v4.0.0 交付的后端四大系统（全链路 OpenTelemetry 追踪与火焰图、Sagas/TCC 分布式事务与异构库对账、多模态失败根因推导与已知缺陷知识库、UI 定位器/API 断言自愈与防篡改流水线），构建兼具极客质感与企业级健壮性的现代化前端控制面板。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 分布式链路全息追踪、调用树与性能瓶颈火焰图控制台 (Distributed Trace Telemetry, Span Tree & Flamegraph Console)**
  - 聚焦 OpenTelemetry Span 追踪中继流水与层级调用树展开抽屉、关键路径火焰图全景大盘、以及慢调用聚类诊断卡片。
- **Phase 2: 微服务分布式事务与跨系统数据最终一致性对账大盘 (Distributed Transaction & Cross-System Data Consistency Dashboard)**
  - 聚焦 Sagas/TCC 状态机跟踪与悬挂事务探测抽屉、跨库数据双向一致性对账稽核全景大盘、以及事件总线死信重放与幂等压测卡片。
- **Phase 3: 自动化测试执行失败智能根因推导与缺陷工单指派控制台 (Automated Test Failure Root-Cause Diagnosis & Defect Ticket Console)**
  - 聚焦多模态失败根因推导与因果链下钻弹窗、已知缺陷向量指纹匹配抽屉、以及第三方缺陷工单自动指派与生命周期流转卡片。
- **Phase 4: AI 驱动的用例脚本断言自愈与代码级自动修复补丁大盘 (AI Case Self-Healing & Patch Application Pipeline Dashboard)**
  - 聚焦 UI 选择器自愈降级重试抽屉、API 响应变迁自适应断言 Diff 弹窗、以及端到端自愈审计追踪与一键原子回滚流水线大盘页面。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：分布式链路全息追踪、调用树与性能瓶颈火焰图控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **OpenTelemetry Span 追踪中继与层级调用树展开抽屉** | `distributed_trace_telemetry_relay` | 落地 `DistributedTraceSpanTreeDrawer.vue` 组件与 API 客户端；支持 W3C TraceContext 解析展示、父子层级深度树展开、状态过滤与耗时统计；见 docs/evidence/distributed-trace-span-tree-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[ ]` | **跨服务关键路径分析与慢调用火焰图性能大盘** | `critical_path_flamegraph_profiler` | 落地 `CriticalPathFlamegraphDashboardView.vue` 视图与路由；基于 ECharts/自定义分层渲染火焰图、关键路径高亮与瓶颈归类。 |
| UI1.3 `[ ]` | **分布式调用链路异常波动与慢调用智能聚类诊断卡片** | `trace_anomaly_slow_call_clusterer` | 落地 `TraceAnomalySlowCallClusterCard.vue` 组件；展示 5 大异常模式聚类簇、Z-score 偏离度标签、P95 耗时与加固建议。 |

---

### Phase 2：微服务分布式事务与跨系统数据最终一致性对账大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[ ]` | **Sagas/TCC 分布式事务状态机流转与悬挂事务探测抽屉** | `saga_transaction_state_tracker` | 落地 `SagaTransactionStateTrackerDrawer.vue` 组件；可视化呈现 Try/Confirm/Cancel 分支流转、悬挂事务警报大横幅与防悬挂建议。 |
| UI2.2 `[ ]` | **跨微服务异构数据源最终一致性双向稽核对账大盘页面** | `cross_db_data_consistency_auditor` | 落地 `CrossDbConsistencyAuditDashboardView.vue` 视图与路由；展示主键对齐比对表、对账达标率仪表环、差异分类与补偿修复 SQL 预览。 |
| UI2.3 `[ ]` | **消息事件总线消费延迟、死信重放与幂等压测卡片** | `event_bus_deadletter_idempotency_guard` | 落地 `EventBusDeadletterIdempotencyCard.vue` 组件；展示 Topic 消费延迟积压指标、死信队列一键重放与多轮投递幂等拦截压测。 |

---

### Phase 3：自动化测试执行失败智能根因推导与缺陷工单指派控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **多模态测试失败根因推导与因果失效链下钻面板** | `test_failure_root_cause_reasoner` | 落地 `TestFailureRootCauseDiagnosisModal.vue` 弹窗；展示多模态证据源、因果失效传播链、首发代码位置高亮与置信度环。 |
| UI3.2 `[ ]` | **历史已知缺陷经验知识库与向量指纹匹配抽屉** | `incident_knowledge_fingerprint_matcher` | 落地 `IncidentKnowledgeFingerprintDrawer.vue` 抽屉；展示抗噪声语义指纹比对、历史相似度分级（EXACT/HIGH/MEDIUM）与已验证方案。 |
| UI3.3 `[ ]` | **缺陷严重度评级与第三方工单自动指派卡片** | `defect_auto_ticket_dispatcher` | 落地 `DefectTicketDispatchCard.vue` 组件；展示 P0~P3 严重度徽章、Jira/GitHub 工单预览与工单状态生命周期流转。 |

---

### Phase 4：AI 驱动的用例脚本断言自愈与代码级自动修复补丁大盘

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **UI 元素定位漂移动态自愈推导与降级重试控制台** | `smart_locator_multistrategy_healer` | 落地 `SmartLocatorHealingConsoleDrawer.vue` 组件；展示五维加权降级得分条、新选择器建议、代码补丁与自愈成功率统计。 |
| UI4.2 `[ ]` | **接口响应格式变迁自适应断言规则推导与代码 Diff 弹窗** | `adaptive_assertion_auto_patcher` | 落地 `AdaptiveAssertionPatchModal.vue` 弹窗；展示 JSONPath 迁移轨迹、外层拆包/重命名模式分类、Python 代码 Diff 与一键应用。 |
| UI4.3 `[ ]` | **端到端测试自愈全流程审计追踪与一键回滚流水线全景大盘** | `self_healing_audit_patch_pipeline` | 落地 `SelfHealingAuditPatchPipelineView.vue` 页面与路由；展示四阶段卡点自愈流程、SHA-256 加密防篡改指纹与一键原子回滚控制台。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
