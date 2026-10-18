# UI3.2 分布式压测策略配置与过载熔断围栏弹窗组件验收 (2026-10-18)

## 概述与交付物

UI3.2（分布式压测策略配置与过载熔断围栏弹窗组件）已全量研发交付并通过各项工程门禁，**达成 ATP v6.2.0 Phase 3（全链路压测拓扑透视与容量大盘工作台）的第二个关键前端交互组件**：
1. **弹窗组件交互实现 (`StressConfigModal.vue`)**：
   - **顶部发压概览横幅**：展示目标压测微服务、规划峰值并发（VU）、分布式 Worker 算力节点数（按单 Pod 承载 2000 VU 自动计算推演）与秒级熔断看门狗激活状态；
   - 交互操作：支持“重置为推荐默认值”、“保存配置并生成发压作业”与“取消”操作；
2. **三 Tab 细粒度策略配置表单**：
   - **Tab 1：负载模型与阶梯爬坡 (Load Profile)**：支持 `STEP_RAMP_UP`、`SPIKE_SURGE`、`CONSTANT_STEADY`、`SOAK_LONGEVITY` 4 种模式切换；配置初始并发（50~10000 VU）、阶梯步长（100~5000 VU）、阶段数与稳态持续秒数；
   - **Tab 2：生产防击穿过载熔断 (Circuit Breaker)**：错误率熔断红线（0.1~10.0%）、生产 Pod 核心 CPU 保护上限（50~95%）、P99 时延上限（100~5000ms）与毫秒级自动断路切流泄压总开关；
   - **Tab 3：影子存储隔离与清理 (Shadow Storage)**：影子表识别后缀（`_shadow`）、压测结束自动预演清理开关与生产核心主库防穿透强制锁；
3. **数据响应式驱动与算力自动精算**：
   - 动态计算峰值并发（`calculatedPeakVu = initial_vu + (steps - 1) * step_vu`）并自动向上取整推算分布式 Worker 节点数（`requiredWorkers = ceil(peak_vu / 2000)`）；
   - **设计系统规范严格遵守**：全量使用 CSS 变量，彻底消除硬编码 HEX 色值。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/StressConfigModal.spec.ts`：4 passed（横幅指标与并发/Worker节点自动精算、外部初始配置回填、表单数据携带保存事件触发、一键重置默认配置）；
   - **Phase 3 组件套件**：**8 passed in 2.22s (100% PASS)**。
2. **工程质量门禁**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (22.48s)**；
   - `npm run build` (`vite build`)：**4635 modules transformed, built in 4.70s, 0 errors!**。
