# ATP v6.1.0 研发任务规划书
## 全链路分布式灰度发布与金丝雀流量染色校验中台 (Full-Link Canary Progressive Delivery & Traffic Coloration Verification Hub)

**规划日期**：2026-10-18
**目标版本**：v6.1.0
**核心目标**：构建企业级全链路分布式金丝雀发布与流量染色校验中台。实现“流量染色标定义与上下文透传 ➔ 金丝雀 vs 基线双轨指标实时对比 ➔ 自适应阶梯步进 ➔ 异常击穿毫秒级自动回滚 ➔ 全景拓扑分流透视 ➔ 影子存储防污染校验 ➔ 生产安全沙箱与 64 位 SHA-256 不可篡改存证”的全链路闭环。

---

## 1. 架构拓扑与全景流程

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 流量染色标透传与金丝雀路由分流引擎]
        T1_1["T1.1 全链路流量染色标规则配置与上下文透传器 (canary_traffic_coloration_engine)"]
        T1_2["T1.2 金丝雀与基线双轨指标实时对比推演器 (canary_baseline_metric_comparator)"]
        T1_3["T1.3 金丝雀演进与染色管理 REST API (/api/v1/canary-verification/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 自适应灰度步进调度与自动熔断回滚看门狗]
        T2_1["T2.1 智能金丝雀健康度评分与多阶步进调度器 (canary_health_scoring_stepper)"]
        T2_2["T2.2 灰度击穿自动熔断与秒级一键回滚看门狗 (canary_auto_rollback_guard)"]
        T2_3["T2.3 灰度流量数据隔离与影子存储防污染校验器 (canary_data_isolation_inspector)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 金丝雀双轨流向透视与灰度控制工作台]
        UI3_1["UI3.1 金丝雀全链路染色拓扑与流量分流透视抽屉 (CanaryTopologyInspectionDrawer)"]
        UI3_2["UI3.2 灰度步进策略配置与自动回滚围栏弹窗 (CanarySteppingConfigModal)"]
        UI3_3["UI3.3 全链路金丝雀灰度校验工作台中枢页面 (/workbench/canary-verification)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产防误割安全沙箱、合规存证与全量发布]
        T4_1["T4.1 生产环境灰度强准入与金丝雀发布审批看门狗 (canary_safety_boundary_guard)"]
        T4_2["T4.2 金丝雀健康度结论与放行准入 64 位 SHA-256 存证证书器 (canary_evidence_signer)"]
        T4_3["T4.3 v6.1.0 全链路金丝雀中台全域综合验收与发布说明"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：流量染色标透传与金丝雀路由分流引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **全链路流量染色标规则配置与上下文透传器** | `backend/app/services/canary_traffic_coloration_engine.py` | 支持基于 Header/Cookie/租户/权重的染色标记及跨服务透明透传；单测独立通过；见 docs/evidence/canary-traffic-coloration-engine-t1-1-2026-10-18.md |
| T1.2 `[x]` | **金丝雀与基线双轨指标实时对比推演器** | `backend/app/services/canary_baseline_metric_comparator.py` | 毫秒级对比 Canary 与 Baseline 的错误率、P99 延迟及业务成功率偏离；单测独立通过；见 docs/evidence/canary-baseline-metric-comparator-t1-2-2026-10-18.md |
| T1.3 `[x]` | **金丝雀演进与染色管理 REST API** | `backend/app/api/v1/canary_verification_api.py` | 挂载 `/api/v1/canary-verification/*` 路由，提供染色规则配置、双轨对比查询与回滚端点；单测独立通过；见 docs/evidence/canary-verification-api-t1-3-2026-10-18.md |

---

### Phase 2：自适应灰度步进调度与自动熔断回滚看门狗

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **智能金丝雀健康度评分与多阶步进调度器** | `backend/app/services/canary_health_scoring_stepper.py` | 综合评估五维健康度得分（0~100），驱动流量自适应阶梯步进（5%~100%）；单测独立通过；见 docs/evidence/canary-health-scoring-stepper-t2-1-2026-10-18.md |
| T2.2 `[ ]` | **灰度击穿自动熔断与秒级一键回滚看门狗** | `backend/app/services/canary_auto_rollback_guard.py` | 监控金丝雀相对基线指标偏离红线，超标毫秒级自动触发切流与版本回滚；单测独立通过。 |
| T2.3 `[ ]` | **灰度流量数据隔离与影子存储防污染校验器** | `backend/app/services/canary_data_isolation_inspector.py` | 校验染色流量写操作是否严格路由至影子库表，防止生产脏数据污染；单测独立通过。 |

---

### Phase 3：金丝雀双轨流向透视与灰度控制工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **金丝雀全链路染色拓扑与流量分流透视抽屉** | `frontend/src/views/workbench/components/CanaryTopologyInspectionDrawer.vue` | 呈现多微服务节点分流拓扑、实时权重百分比与双轨指标对比曲线；单测独立通过。 |
| UI3.2 `[ ]` | **灰度步进策略配置与自动回滚围栏弹窗** | `frontend/src/views/workbench/components/CanarySteppingConfigModal.vue` | 可视化交互配置多阶段步进计划、错误率容忍阈值与看门狗自动回滚；单测独立通过。 |
| UI3.3 `[ ]` | **全链路金丝雀灰度校验工作台中枢页面** | `frontend/src/views/workbench/CanaryVerificationWorkbenchView.vue` | 落地路由 `/workbench/canary-verification`，集成 4 大 Bento KPI、灰度版本流水大盘与组件联动；单测独立通过。 |

---

### Phase 4：生产防误割安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **生产环境灰度强准入与金丝雀发布审批看门狗** | `backend/app/services/canary_safety_boundary_guard.py` | 生产灰度发布三要素校验（特批发布工单号、维护时段窗口与安全令牌）；单测独立通过。 |
| T4.2 `[ ]` | **金丝雀健康度结论与放行准入 64 位 SHA-256 存证证书器** | `backend/app/services/canary_evidence_signer.py` | 规范化确定性 JSON，签发不可篡改的 64 位 SHA-256 指纹与 HMAC-SHA256 签名存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v6.1.0 全链路金丝雀中台全域综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v6.1.0-release-notes.md` 与专项交付证据。 |

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
