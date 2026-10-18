# ATP v6.2.0 研发任务规划书: 生产全链路影子压测与容量基线推演中台

**版本代号**: `v6.2.0`
**核心方向**: 全链路影子压测标注入与隔离透传、分布式阶梯加压调度、基于 USL 定律的容量拐点智能推导、生产防击穿秒级自动熔断切流、全链路瓶颈拓扑看板与密码学存证证书中枢。
**发布周期**: 2026-10-18 ~ 2026-10-19

---

## 1. 架构总览与价值

在大型微服务架构中，大促与高峰期往往伴随着海量突发流量。由于测试环境配置低、数据量少，无法真实反映生产微服务调用链路与底层存储的真实吞吐极限。
ATP v6.2.0 引入 **全链路影子压测与容量推演中台**，具备四大核心优势：
1. **全链路压测流量标无损透传与数据隔离**：在真实生产环境下，通过 `X-Stress-Test` 与影子标签驱动请求严格路由至影子库表（`t_order_shadow`），绝不污染生产主库；
2. **基于通用可伸缩性定律 (USL) 的容量拐点推演**：自动计算高并发下的系统吞吐极限（Saturation Point）与性能拐点（Knee Point），挖掘隐蔽锁竞争与网络瓶颈；
3. **生产防击穿秒级自动熔断看门狗**：实时监控生产核心 CPU、错误率与 P99 时延，一旦触碰红线毫秒级紧急清零切断压测流（Circuit Breaker），确保生产业务绝对安全；
4. **全生命周期合规存证与可视化工作台**：Bento KPI 压测大盘、调用链瓶颈拓扑抽屉与 64 位 SHA-256 不可篡改存证证书。

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 压测流量标隔离与分布式影子发压引擎]
        T1_1["T1.1 全链路影子压测标注入与上下文透传器"]
        T1_2["T1.2 分布式海量虚拟用户发压调度与阶梯加压器"]
        T1_3["T1.3 全链路影子压测管控与发压作业 REST API"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 架构容量基线拐点推演与自适应限流熔断看门狗]
        T2_1["T2.1 系统容量拐点智能推演与吞吐天花板挖掘器"]
        T2_2["T2.2 生产击穿毫秒级熔断与过载紧急泄压看门狗"]
        T2_3["T2.3 影子数据隔离防污染巡检与影子库表清理器"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 全链路压测拓扑透视与容量大盘工作台]
        UI3_1["UI3.1 微服务全链路发压拓扑与瓶颈链路透视抽屉"]
        UI3_2["UI3.2 分布式压测策略配置与过载熔断围栏弹窗"]
        UI3_3["UI3.3 全链路生产压测与容量基线中枢工作台 (/workbench/stress-testing)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产防击穿安全沙箱、合规存证与全量发布]
        T4_1["T4.1 生产全链路压测特批审批与窗口期强准入看门狗"]
        T4_2["T4.2 容量基线推演结论与压测验收 64 位 SHA-256 存证证书器"]
        T4_3["T4.3 v6.2.0 全链路生产影子压测与容量中台全域综合验收与发布说明"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：压测流量标隔离与分布式影子发压引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **全链路影子压测标注入与上下文透传器** | `backend/app/services/stress_traffic_isolation_engine.py` | 支持 Header、gRPC 与 MQ 压测标透传，强制识别影子库表隔离；单测独立通过；见 docs/evidence/stress-traffic-isolation-engine-t1-1-2026-10-18.md |
| T1.2 `[x]` | **分布式海量虚拟用户发压调度与阶梯加压器** | `backend/app/services/stress_load_profile_stepper.py` | 支持阶梯爬坡、瞬时峰值、稳态压测等负载模型，推演并发与发压节点；单测独立通过；见 docs/evidence/stress-load-profile-stepper-t1-2-2026-10-18.md |
| T1.3 `[x]` | **全链路影子压测管控与发压作业 REST API** | `backend/app/api/v1/stress_testing_api.py` | 挂载 `/api/v1/stress-testing/`，提供压测任务启停、实时监控与报告查询；单测独立通过；见 docs/evidence/stress-testing-api-t1-3-2026-10-18.md |

---

### Phase 2：架构容量基线拐点推演与自适应限流熔断看门狗

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **系统容量拐点智能推演与吞吐天花板挖掘器** | `backend/app/services/capacity_knee_point_deductor.py` | 基于通用可伸缩性定律 (USL)，自动拟合并计算系统 TPS/RT 拐点与饱和极限；单测独立通过；见 docs/evidence/capacity-knee-point-deductor-t2-1-2026-10-18.md |
| T2.2 `[x]` | **生产击穿毫秒级熔断与过载紧急泄压看门狗** | `backend/app/services/stress_safety_overload_guard.py` | 实时监测生产错误率、CPU 与延迟红线，触碰红线毫秒级自动熔断切断压测流；单测独立通过；见 docs/evidence/stress-safety-overload-guard-t2-2-2026-10-18.md |
| T2.3 `[x]` | **影子数据隔离防污染巡检与影子库表清理器** | `backend/app/services/shadow_data_pollution_cleaner.py` | 全量巡检压测期间脏数据隔离状态，并提供影子数据安全归档与清理能力；单测独立通过；见 docs/evidence/shadow-data-pollution-cleaner-t2-3-2026-10-18.md |

---

### Phase 3：全链路压测拓扑透视与容量大盘工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **微服务全链路发压拓扑与瓶颈链路透视抽屉** | `frontend/src/views/workbench/components/StressTopologyInspectionDrawer.vue` | 呈现多微服务节点压测链路、慢服务瓶颈高亮与实时性能曲线；单测独立通过；见 docs/evidence/stress-topology-inspection-drawer-ui3-1-2026-10-18.md |
| UI3.2 `[ ]` | **分布式压测策略配置与过载熔断围栏弹窗** | `frontend/src/views/workbench/components/StressConfigModal.vue` | 可视化交互配置发压梯度、目标并发、熔断红线与影子表映射规则；单测独立通过。 |
| UI3.3 `[ ]` | **全链路生产压测与容量基线中枢工作台页面** | `frontend/src/views/workbench/StressTestingWorkbenchView.vue` | 落地路由 `/workbench/stress-testing`，集成 4 大 Bento KPI 与压测作业大盘；单测独立通过。 |

---

### Phase 4：生产防击穿安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **生产全链路压测特批审批与窗口期强准入看门狗** | `backend/app/services/stress_safety_boundary_guard.py` | 生产压测三要素校验（特批演练工单号、夜间低峰运维窗口与安全令牌）；单测独立通过。 |
| T4.2 `[ ]` | **容量基线推演结论与压测验收 64 位 SHA-256 存证证书器** | `backend/app/services/stress_evidence_signer.py` | 规范化确定性 JSON，签发不可篡改的 64 位 SHA-256 指纹与 HMAC-SHA256 签名存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v6.2.0 全链路生产影子压测与容量中台全域综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v6.2.0-release-notes.md` 与专项交付证据。 |

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
   - `vite build` 生产打包成功；
   - 全面遵循 ATP 设计系统主规范（零硬编码色值，严格 Token 化）。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
