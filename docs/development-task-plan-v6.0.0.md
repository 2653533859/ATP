# ATP v6.0.0 研发任务规划书
## 智能缺陷聚类去重、根因归因与跨平台全生命周期中台 (Intelligent Defect Deduplication, Auto-Root-Cause Aggregation & Bi-directional Ticket Lifecycle Hub)

**规划日期**：2026-10-18
**目标版本**：v6.0.0 (Major Release)
**核心目标**：彻底解决自动化测试大规模并发执行下的“缺陷风暴与海量重复提单”痛点。构建工业级智能缺陷聚类去重、自动责任归属推导与跨平台（Jira/禅道/GitHub）双向状态同步闭环。

---

## 1. 架构拓扑与全景流程

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 失败堆栈指纹提取与智能聚类去重引擎]
        T1_1["T1.1 失败堆栈与异常语义指纹提取器 (defect_failure_fingerprint_extractor)"]
        T1_2["T1.2 缺陷相似度计算与海量失败聚类去重器 (defect_similarity_deduplicator)"]
        T1_3["T1.3 缺陷智能去重与聚合管理 REST API (/api/v1/defect-intelligence/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 责任归属智能推导与双向状态同步网关]
        T2_1["T2.1 故障责任微服务与团队智能归因路由器 (defect_root_cause_router)"]
        T2_2["T2.2 跨平台缺陷工单双向状态同步器 (defect_bidirectional_sync_gateway)"]
        T2_3["T2.3 缺陷 SLA 超时预警与升级看门狗 (defect_sla_escalation_watchdog)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 智能缺陷聚类看板与全生命周期工作台]
        UI3_1["UI3.1 堆栈指纹拓扑与同源缺陷聚类抽屉 (DefectClusterInspectionDrawer)"]
        UI3_2["UI3.2 跨平台同步与 SLA 升级策略配置弹窗 (DefectSyncConfigModal)"]
        UI3_3["UI3.3 智能缺陷治理与全生命周期工作台中枢 (/workbench/defect-intelligence)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产防误提安全沙箱、合规存证与全量发布]
        T4_1["T4.1 偶发抖动缺陷提单防击穿安全沙箱看门狗 (flaky_defect_suppression_guard)"]
        T4_2["T4.2 缺陷归因结论与 SLA 履约 64 位 SHA-256 存证证书器 (defect_evidence_signer)"]
        T4_3["T4.3 v6.0.0 智能缺陷治理中台全域综合验收与发布说明"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：失败堆栈指纹提取与智能聚类去重引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **失败堆栈与异常语义指纹提取器** | `backend/app/services/defect_failure_fingerprint_extractor.py` | 规范化清理堆栈行号与动态地址，生成唯一稳定的 64 位异常指纹；单测独立通过；见 docs/evidence/defect-failure-fingerprint-extractor-t1-1-2026-10-18.md |
| T1.2 `[x]` | **缺陷相似度计算与海量失败聚类去重器** | `backend/app/services/defect_similarity_deduplicator.py` | 基于指纹与文本相似度自动聚合归类同源缺陷，去重避免垃圾重复提单；单测独立通过；见 docs/evidence/defect-similarity-deduplicator-t1-2-2026-10-18.md |
| T1.3 `[x]` | **缺陷智能去重与聚合管理 REST API** | `backend/app/api/v1/defect_intelligence_api.py` | 挂载 `/api/v1/defect-intelligence/*` 路由，提供指纹提取、相似度匹配与批次聚合端点；单测独立通过；见 docs/evidence/defect-intelligence-api-t1-3-2026-10-18.md |

---

### Phase 2：责任归属智能推导与双向状态同步网关

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **故障责任微服务与团队智能归因路由器** | `backend/app/services/defect_root_cause_router.py` | 结合调用链与异常堆栈定位故障根因微服务，智能路由至代码责任人与处理团队；单测独立通过；见 docs/evidence/defect-root-cause-router-t2-1-2026-10-18.md |
| T2.2 `[x]` | **跨平台缺陷工单双向状态同步器** | `backend/app/services/defect_bidirectional_sync_gateway.py` | 支持与 Jira/GitHub Issues 双向同步，回归通过自动关闭、失败自动重新激活 (Reopen)；单测独立通过；见 docs/evidence/defect-bidirectional-sync-gateway-t2-2-2026-10-18.md |
| T2.3 `[x]` | **缺陷 SLA 超时预警与升级看门狗** | `backend/app/services/defect_sla_escalation_watchdog.py` | 针对 P0/P1/P2 各级缺陷监控解决 SLA 倒计时，超时毫秒级触发升级阻断告警；单测独立通过；见 docs/evidence/defect-sla-escalation-watchdog-t2-3-2026-10-18.md |

---

### Phase 3：智能缺陷聚类看板与全生命周期工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **堆栈指纹拓扑与同源缺陷聚类抽屉** | `frontend/src/views/workbench/components/DefectClusterInspectionDrawer.vue` | 呈现同源聚类用例列表、堆栈差异对比与一键合并主缺陷交互；单测独立通过；见 docs/evidence/defect-cluster-inspection-drawer-ui3-1-2026-10-18.md |
| UI3.2 `[x]` | **跨平台同步与 SLA 升级策略配置弹窗** | `frontend/src/views/workbench/components/DefectSyncConfigModal.vue` | 可视化交互配置 Jira/GitHub 集成凭据、SLA 响应与解决时限及广播通道；单测独立通过；见 docs/evidence/defect-sync-config-modal-ui3-2-2026-10-18.md |
| UI3.3 `[x]` | **智能缺陷治理与全生命周期工作台中枢页面** | `frontend/src/views/workbench/DefectIntelligenceWorkbenchView.vue` | 落地路由 `/workbench/defect-intelligence`，集成 4 大 Bento KPI、聚类缺陷流水大盘与组件联动；单测独立通过；见 docs/evidence/defect-intelligence-workbench-view-ui3-3-2026-10-18.md |

---

### Phase 4：生产防误提安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **偶发抖动缺陷提单防击穿安全沙箱看门狗** | `backend/app/services/flaky_defect_suppression_guard.py` | 识别偶发网络抖动与 Flaky 假失败，防范误建无效工单与警报疲劳；单测独立通过；见 docs/evidence/flaky-defect-suppression-guard-t4-1-2026-10-18.md |
| T4.2 `[ ]` | **缺陷归因结论与 SLA 履约 64 位 SHA-256 存证证书器** | `backend/app/services/defect_evidence_signer.py` | 规范化确定性 JSON，签发不可篡改的 64 位 SHA-256 指纹与 HMAC-SHA256 签名存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v6.0.0 智能缺陷治理中台全域综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v6.0.0-release-notes.md` 与专项交付证据。 |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `pytest-standalone-sweep.py` 隔离单跑 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vitest` 前端单测 100% PASS；
   - `vue-tsc --noEmit` 0 错误；
   - `vite build` 生产打包成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
