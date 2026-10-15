# F3.3 回归容量预测、饱和拐点与并发上限预测图验收（2026-10-16）

## 概述与结论

F3.3（回归容量预测、饱和拐点与并发上限预测图）已完成全量前端代码演进、组件封装与自动化测试，**正式标志着 v2.9.0 Phase 3（持续性能混沌与容量预测图表视图）的 100% 全量大闭环！**

1. **容量预测与横向比对 API 扩展 (`frontend/src/api/index.ts`)**：
   - 增加 `ComparisonMatrixItem`、`PerformanceCompareResponse`、`PerformanceCapacityForecastRequest` 与 `PerformanceCapacityForecastResponse` 完整数据类型；
   - 封装 `performanceApi.compareRuns`：获取多轮压测横向横截面对比矩阵与扩展效能比（RPS/VU）；
   - 封装 `performanceApi.forecastCapacity`：基于 SLA 阈值与多项式/线性回归计算集群并发上限与预估吞吐量。
2. **容量回归拟合与拐点图表组件 (`CapacityRegressionChart.vue`)**：
   - **核心容量指标 KPI 看板**：
     - 展示最大安全承载并发上限（VU），标注置信度等级徽章（High / Medium / Low）与平均 $R^2$ 拟合优度；
     - 呈现预估峰值吞吐量（RPS）与性能饱和拐点（Knee Point，如 `600 VU @ 4800 RPS`）；
     - 输出智能架构容量规划与瓶颈规避建议横幅；
   - **双轴双拟合回归曲线图 (`VChart` / ECharts)**：
     - 散点（Scatter）清晰呈现各轮实测负载 $(VU, RPS)$ 与 $(VU, P95)$；
     - 拟合线 1：蓝色虚线呈现并发-吞吐量一阶线性扩展回归趋势；
     - 拟合线 2：橙色虚线呈现并发-延迟二阶多项式恶化曲线；
     - `markLine` 标红指示 SLA 延迟红线（如 $P95 = 500\text{ms}$）；
     - `markPoint` 紫色高亮锁定饱和拐点（Knee Point）；
   - **横向多轮压测比对矩阵表格**：
     - 清晰列出每轮测试的并发（VU）、吞吐量（RPS）、P95 延迟（ms）、错误率与单机扩展效能比（RPS/VU）。
3. **主系统压测中心深度集成 (`PerformanceCenterView.vue`)**：
   - 在基线与压测监控模态框中扩充第 3 个 Tab（「回归容量预测与饱和拐点」），实现性能分析一站式工作台。

---

## 质量门禁与验证

1. **前端自动化测试**：
   - `src/views/system/components/CapacityRegressionChart.spec.ts`：**2 passed in 2.84s**；
   - `src/views/system/components/ChaosRtoTimeline.spec.ts`：**3 passed in 2.95s**；
   - `src/views/system/components/BaselineDriftMonitor.spec.ts`：**3 passed in 3.43s**；
   - `src/views/system/PerformanceCenterView.spec.ts`：**13 passed in 2.21s**；
   - 全量 Vitest 测试套件：**93 个测试文件全部通过，共 423 项单测 100% PASS**。
2. **静态质量与类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean pass**；
   - `npm run build`：生产环境打包成功无警告（2.33s）。
