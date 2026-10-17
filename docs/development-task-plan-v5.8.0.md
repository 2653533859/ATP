# ATP v5.8.0 研发任务规划：全链路分布式混沌工程与弹性韧性攻防演练中台 (Full-Link Distributed Chaos Engineering & Resilience Drill Hub)

**规划日期**：2026-10-17
**版本代号**：**Distributed Chaos Engineering & Resilience Drill Hub**
**核心目标**：彻底解决微服务架构与分布式系统在复杂生产异常（网络延迟抖动、丢包、服务挂死、数据库超时、下游雪崩）下缺乏自动化韧性演练验证的痛点。构建细粒度故障注入算子库、稳态探测器、爆炸半径动态收敛看门狗与架构韧性雷达分析中枢，实现系统高可用容灾能力 100% 自动化攻防验证与自愈量化评估。

---

## 1. 架构设计与系统全景拓扑

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 故障注入算子与分布式混沌实验执行引擎]
        T1_1["T1.1 网络损伤与故障注入算子库 (chaos_fault_injector_library)"]
        T1_2["T1.2 分布式混沌实验编排与稳态探测引擎 (chaos_steady_state_evaluator)"]
        T1_3["T1.3 混沌演练实验管理与触发 REST API (/api/v1/chaos-engineering/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 弹性韧性自愈评估与爆炸半径动态收敛器]
        T2_1["T2.1 服务降级与熔断恢复时间 RTO/RPO 评估器 (resilience_rto_evaluator)"]
        T2_2["T2.2 演练爆炸半径实时监控与紧急熔断回滚看门狗 (chaos_blast_radius_controller)"]
        T2_3["T2.3 架构韧性弱点雷达分析与加固建议生成器 (architecture_weakness_radar)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 混沌攻防演练中枢与韧性透视工作台]
        UI3_1["UI3.1 混沌故障注入拓扑与稳态指标透视抽屉 (ChaosExperimentInspectionDrawer.vue)"]
        UI3_2["UI3.2 爆炸半径围栏配置与紧急熔断监控弹窗 (BlastRadiusConfigModal.vue)"]
        UI3_3["UI3.3 分布式混沌工程与弹性韧性演练工作台中枢页面 (/workbench/chaos-engineering)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产防击穿安全沙箱、合规存证与全量发布]
        T4_1["T4.1 混沌演练非生产隔离与绝对安全围栏看门狗 (chaos_safety_boundary_guard)"]
        T4_2["T4.2 混沌实验结论与韧性得分 64 位 SHA-256 存证证书器 (chaos_evidence_signer)"]
        T4_3["T4.3 v5.8.0 混沌工程与弹性韧性中台综合验收与发布说明 (v5.8.0-release-notes)"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：故障注入算子与分布式混沌实验执行引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **网络损伤与故障注入算子库** | `backend/app/services/chaos_fault_injector_library.py` | 支持网络延迟抖动 (Latency/Jitter)、丢包 (Packet Loss)、HTTP 状态码变异 (500/502/504) 与响应超时模拟；单测独立通过；见 docs/evidence/chaos-fault-injector-library-t1-1-2026-10-17.md |
| T1.2 `[x]` | **分布式混沌实验编排与稳态探测引擎** | `backend/app/services/chaos_steady_state_evaluator.py` | 定义演练前系统基线稳态 (Steady State Baseline) 与演练中实时指标波动监控 (成功率、P99延迟、探针健康)；单测独立通过；见 docs/evidence/chaos-steady-state-evaluator-t1-2-2026-10-17.md |
| T1.3 `[x]` | **混沌演练实验管理与触发 REST API** | `backend/app/api/v1/chaos_engineering_api.py` | 挂载 `/api/v1/chaos-engineering/*`，提供故障注入配置、实验触发与停止、稳态指标监控与实时状态查询端点；单测独立通过；见 docs/evidence/chaos-engineering-api-t1-3-2026-10-17.md |

---

### Phase 2：弹性韧性自愈评估与爆炸半径动态收敛器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **服务降级与熔断恢复时间 RTO/RPO 评估器** | `backend/app/services/resilience_rto_evaluator.py` | 精准测量故障注入后系统熔断触发耗时、降级旁路响应与故障恢复时间 (RTO/RPO)；单测独立通过；见 docs/evidence/resilience-rto-evaluator-t2-1-2026-10-17.md |
| T2.2 `[x]` | **演练爆炸半径实时监控与紧急熔断回滚看门狗** | `backend/app/services/chaos_blast_radius_controller.py` | 监控故障波及节点数与错误率阈值，当超出设定的爆炸半径时毫秒级自动触发紧急熔断与故障剥离；单测独立通过；见 docs/evidence/chaos-blast-radius-controller-t2-2-2026-10-17.md |
| T2.3 `[x]` | **架构韧性弱点雷达分析与加固建议生成器** | `backend/app/services/architecture_weakness_radar.py` | 输出多维韧性雷达评分 (0~100) 并生成断路器超时调优、重试退避策略与线程池隔离等架构加固建议；单测独立通过；见 docs/evidence/architecture-weakness-radar-t2-3-2026-10-17.md |

---

### Phase 3：混沌攻防演练中枢与韧性透视工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **混沌故障注入拓扑与稳态指标透视抽屉** | `frontend/src/views/workbench/components/ChaosExperimentInspectionDrawer.vue` | 呈现故障注入实时拓扑流向、稳态偏离曲线图、降级状态与一键注入/恢复控制；单测独立通过；见 docs/evidence/chaos-experiment-inspection-drawer-ui3-1-2026-10-17.md |
| UI3.2 `[x]` | **爆炸半径围栏配置与紧急熔断监控弹窗** | `frontend/src/views/workbench/components/BlastRadiusConfigModal.vue` | 可视化交互配置允许受影响的最大服务数、错误率红线与自动熔断看门狗策略；单测独立通过；见 docs/evidence/blast-radius-config-modal-ui3-2-2026-10-17.md |
| UI3.3 `[x]` | **分布式混沌工程与弹性韧性演练工作台中枢页面** | `frontend/src/views/workbench/ChaosEngineeringWorkbenchView.vue` | 落地路由 `/workbench/chaos-engineering`，集成 4 大 Bento KPI、大盘流水与演练编排操作；单测独立通过；见 docs/evidence/chaos-engineering-workbench-view-ui3-3-2026-10-17.md |

---

### Phase 4：生产防击穿安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **混沌演练非生产隔离与绝对安全围栏看门狗** | `backend/app/services/chaos_safety_boundary_guard.py` | 严防在生产非演练时段或对关键生产数据库执行破坏性故障注入，提供绝对环境强隔离与权限阻断；单测独立通过；见 docs/evidence/chaos-safety-boundary-guard-t4-1-2026-10-17.md |
| T4.2 `[x]` | **混沌实验结论与韧性得分 64 位 SHA-256 存证证书器** | `backend/app/services/chaos_evidence_signer.py` | 为混沌演练实验记录、稳态评估报告与韧性加固证书签发不可篡改 SHA-256 + HMAC 存证证书；单测独立通过；见 docs/evidence/chaos-evidence-signer-t4-2-2026-10-17.md |
| T4.3 `[x]` | **v5.8.0 混沌工程与弹性韧性中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.8.0-release-notes.md` 与专项交付证据；见 docs/evidence/v5-8-0-chaos-engineering-platform-acceptance-2026-10-18.md |

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
