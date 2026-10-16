# ATP v3.4.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**云原生弹性调度、AI 智能用例自愈与多端原生性能分析引擎 (Cloud-Native Elastic Orchestration, AI-Driven Autonomous Healing & Multi-Platform Profiling Engine)**
> 承接基准：以 v3.3.0 交付的集群协同调度、资产拓扑与质量门禁交互控制台为交互入口，在后端全面升级云原生动态容器调度、AI 驱动的 UI/接口用例智能自愈、多端性能分析采样以及企业级多渠道协同中心。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 云原生动态容器化弹性 Worker 调度与生命周期编排 (Cloud-Native Worker Autoscaling)**
  - 聚焦 K8s Job / Docker 瞬时动态 Worker 实例拉起、基于背压队列时延的自动扩缩容与环境镜像多版本路由。
- **Phase 2: AI 驱动的测试用例自动化自愈与智能断言引擎 (AI-Driven Autonomous Test Healing & Cognitive Assertions)**
  - 聚焦 DOM / UI 树多模态失效选择器自愈恢复、接口 Schema 动态漂移柔性断言与自愈审计流水。
- **Phase 3: 多端原生性能剖析与深度质量诊断分析 (Multi-Platform Native Performance Profiling & Deep Diagnostics)**
  - 聚焦 Android 移动端性能多维采样（CPU/内存/FPS/流速）、Web Core Web Vitals 自动化诊断与分布式慢链路火焰图。
- **Phase 4: 企业级测试报告归档与多渠道告警协同中心 (Enterprise Reporting Center & Multi-Channel Alerting Hub)**
  - 聚焦多模态报告聚合导出（PDF/HTML5/Excel）、企微/钉钉/飞书交互卡片 Webhook 智能分发与 DORA 效能指标度量。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：云原生动态容器化弹性 Worker 调度与生命周期编排

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| D1.1 `[x]` | **K8s Job / Docker 瞬时动态 Worker 实例拉起与配额管控** | Docker/K8s Client | 落地 `k8s_worker_provisioner` 服务与 `/api/v1/cloud-native/workers/*` API；支持瞬时容器实例拉起、CPU/内存配额限制与生命周期销毁；见 docs/evidence/k8s-worker-provisioner-d1-1-2026-10-16.md |
| D1.2 `[x]` | **基于任务背压与队列等待时延的弹性 HPA 自动扩缩容算法** | queue_backpressure | 落地 `queue_backpressure_autoscaler` 服务与 `/api/v1/cloud-native/autoscaling/*` API；实现队列背压指标采集、目标副本数自适应计算与扩缩容决策；见 docs/evidence/queue-backpressure-autoscaler-d1-2-2026-10-16.md |
| D1.3 `[x]` | **容器执行环境镜像版本矩阵与动态路由分发** | image_matrix_router | 落地 `worker_image_matrix_router` 服务与 `/api/v1/cloud-native/images/*` API；支持 Python/Node/Android SDK 多版本镜像矩阵注册与标签路由；见 docs/evidence/worker-image-matrix-router-d1-3-2026-10-16.md |

---

### Phase 2：AI 驱动的测试用例自动化自愈与智能断言引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| D2.1 `[x]` | **基于 DOM / UI 树差分与语义 Embedding 的失效选择器多模态自愈恢复** | locator_healing | 落地 `smart_locator_healing_engine` 服务与 `/api/v1/ai-healing/locators/*` API；实现失效选择器自动评分、相似度加权匹配与自愈选择器生成；见 docs/evidence/smart-locator-healing-engine-d2-1-2026-10-16.md |
| D2.2 `[x]` | **接口响应 Schema 动态漂移自适应修正与智能柔性断言** | schema_assertion | 落地 `flexible_schema_assertion_engine` 服务与 `/api/v1/ai-healing/assertions/*` API；支持字段冗余/排序/类型兼容的动态柔性匹配与漂移报告；见 docs/evidence/flexible-schema-assertion-engine-d2-2-2026-10-16.md |
| D2.3 `[x]` | **异常失败根因智能聚类与自愈执行流水审计** | healing_audit | 落地 `healing_audit_trail_service` 服务与 `/api/v1/ai-healing/audit/*` API；提供执行错误栈向量聚类、用例自愈历史记录与自愈置信度评估；见 docs/evidence/healing-audit-trail-service-d2-3-2026-10-16.md |

---

### Phase 3：多端原生性能剖析与深度质量诊断分析

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| D3.1 `[ ]` | **移动端 CPU/内存/FPS/网络流量实时采样与卡顿泄露检测** | mobile_profiler | 落地 `mobile_perf_profiler` 服务与 `/api/v1/diagnostics/mobile-perf/*` API；支持多指标时序采样、卡顿帧与内存泄露智能检测。 |
| D3.2 `[ ]` | **Web 性能 Core Web Vitals (LCP, FID/INP, CLS) 自动化深度诊断** | web_vitals | 落地 `web_vitals_profiler` 服务与 `/api/v1/diagnostics/web-vitals/*` API；自动评估三大核心指标并提供渲染阻断优化建议。 |
| D3.3 `[ ]` | **接口服务全链路分布式追踪 TraceID 贯通与慢调用火焰图分析** | trace_flamegraph | 落地 `distributed_trace_flamegraph` 服务与 `/api/v1/diagnostics/traces/*` API；支持 Trace 树多层级解析与火焰图耗时段自动提取。 |

---

### Phase 4：企业级测试报告归档与多渠道告警协同中心

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| D4.1 `[ ]` | **测试报告多模态聚合打包导出 (PDF / HTML5 / Excel 详报)** | report_bundler | 落地 `report_bundler_exporter` 服务与 `/api/v1/reporting/exports/*` API；支持结构化数据组装与多格式归档文件生成。 |
| D4.2 `[ ]` | **企业微信 / 钉钉 / 飞书富文本交互式卡片 Webhook 智能投递** | webhook_dispatcher | 落地 `notification_hub_dispatcher` 服务与 `/api/v1/reporting/notifications/*` API；支持多渠道模板组装、限流重试与发送状态审计。 |
| D4.3 `[ ]` | **测试执行准时率与团队研发效能 DORA 指标量化分析** | dora_calculator | 落地 `dora_metrics_calculator` 服务与 `/api/v1/reporting/dora/*` API；量化部署频率、变更失败率、MTTR 与前置交付时间四维效能指标。 |

---

## 3. 质量门禁规则

1. **类型检查与 Lint 零报错**：`ruff check`、`ruff format --check` 与 `mypy` 保持 100% 通过。
2. **单元测试与集成测试**：所有新增后端模块均配备完整的 pytest 单元测试，独立单测运行与全量回归保持 100% PASS。
3. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
