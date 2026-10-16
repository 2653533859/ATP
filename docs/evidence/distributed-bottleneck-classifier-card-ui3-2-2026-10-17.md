# UI3.2 压测调用链热点慢调用与资源争用归因卡片验收 (2026-10-17)

## 概述与结论

UI3.2（压测调用链热点慢调用与资源争用归因卡片 `DistributedBottleneckClassifierCard.vue`）已全量交付并完成验证，持续推进 **ATP v4.7.0 Phase 3（压测容量水位实时监控与防雪崩自适应熔断控制台）**：
1. **核心卡片/抽屉实现 (`frontend/src/views/workbench/components/DistributedBottleneckClassifierCard.vue`)**：
   - **4 大时延与系统健康度核心 KPI 卡片**：
     - 压测系统综合健康分（`system_stress_health_score`，如 `86.5`）；
     - P50 中位响应延迟（`p50_latency_ms`，如 `45ms`）；
     - P90 分位响应延迟（`p90_latency_ms`，如 `180ms`）；
     - P99 尾部尖刺延迟（`p99_latency_ms`，如 `680ms`）；
   - **主要核心性能瓶颈根因诊断 Banner (Root Cause Banner)**：
     - 醒目高亮展示 `primary_root_cause`（如 `LOCK_CONTENTION_DEADLOCK`, `SLOW_DATABASE_QUERY`, `THREAD_POOL_EXHAUSTION`, `CPU_SATURATION`）；
     - 呈现智能化根因详细业务影响说明；
   - **调用链瓶颈明细与整改方案大表 (Tracing Bottleneck Findings)**：
     - 责任服务名与慢调用端点/SQL（`culprit_service` / `culprit_endpoint_or_sql`）；
     - 归因类型与严重度级别 Tag（`CRITICAL`, `HIGH`, `MEDIUM`）；
     - 测得耗时（`measured_duration_ms`）；
     - 性能影响与架构优化方案（`optimization_recommendation`）；
   - **即时分析动作**：
     - 提供“即时调用链争用归因分析”与“刷新归因报告”动作，联动后端实时评估。
2. **工作台挂载 (`frontend/src/views/workbench/PerformanceWorkbenchView.vue`)**：
   - 在性能测试工作台工具栏新增 `<a-button size="small" class="toolbar-btn" @click="showBottleneckCard = true"><BugOutlined /> 瓶颈归因诊断</a-button>` 唤起抽屉。
3. **API 客户端对接 (`frontend/src/api/fullLinkStressTesting.ts`)**：
   - 联动后端 `/api/v1/stress/bottleneck-guardian/bottlenecks/classify` 与 `/reports` REST API。

## 质量与测试门禁验证

1. **组件单元测试 (`DistributedBottleneckClassifierCard.spec.ts` & `PerformanceWorkbenchView.spec.ts`)**：
   - `DistributedBottleneckClassifierCard.spec.ts`：2 passed；
   - `PerformanceWorkbenchView.spec.ts`：5 passed；
   - 总体 Vitest 套件：**7 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4497 个模块，产物完整生成，耗时 3.77s，零构建错误。
