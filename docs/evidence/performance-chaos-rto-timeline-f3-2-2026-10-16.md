# F3.2 压力下混沌故障注入时间线与自愈 RTO 测定曲线验收（2026-10-16）

## 概述与结论

F3.2（压力下混沌故障注入时间线与自愈 RTO 测定曲线）已完成全量前端代码演进、组件封装与自动化测试：
1. **混沌计划与 RTO API 客户端扩展 (`frontend/src/api/index.ts`)**：
   - 增加 `ChaosPlanRequest`、`ChaosPlanResponse`、`ChaosRtoEvaluateRequest` 与 `ChaosRtoEvaluateResponse` 数据模式；
   - 封装 `performanceApi.createChaosPlan`：为指定运行记录编排 4 类故障注入（503 宕机、延迟突增、网络丢包、连接重置）；
   - 封装 `performanceApi.evaluateChaosRto`：基于时序采样数据测定自愈恢复时长（RTO 秒数）与抗压韧性评级。
2. **时序轨迹与自愈 RTO 测定图表组件 (`ChaosRtoTimeline.vue`)**：
   - **核心韧性摘要看板**：
     - 展示 Grade A/B/C/D/F 评级徽章与 0-100 综合韧性得分；
     - 突出呈现自愈恢复时长（RTO，精确到小数点后 2 位秒数），未恢复时红色告警；
     - 清晰展示故障前基线 RPS、故障中最低 RPS、最大跌幅百分比以及防抖持续健康时间窗口（如 3.0s）；
   - **双 Y 轴时序轨迹图 (`VChart` / ECharts)**：
     - 左轴呈现吞吐量（Throughput RPS）平滑折线，右轴呈现响应延迟（P95 Latency ms）；
     - `markArea` 浅红渐变高亮标注故障注入区间（Fault Window，如 10s ~ 30s）；
     - `markLine` 绿色虚线与标注点精准指引**自愈确认点与 RTO 间隔**（如 `自愈恢复点 (32.5s) RTO = 2.50s`）；
   - **交互控制与演练模拟**：
     - 支持动态配置故障类型、起始秒数、持续时长与恢复门槛比例，并支持一键「载入示例混沌演练」。
3. **主系统压测中心无缝集成 (`PerformanceCenterView.vue`)**：
   - 在基线漂移模态窗口中扩充双 Tab 导航（「基线漂移与指标告警」+「混沌故障注入与自愈 RTO 测定」），实现按需懒加载。

---

## 质量门禁与验证

1. **前端自动化测试**：
   - `src/views/system/components/ChaosRtoTimeline.spec.ts`：**3 passed in 2.95s**；
   - `src/views/system/components/BaselineDriftMonitor.spec.ts`：**3 passed in 3.43s**；
   - `src/views/system/PerformanceCenterView.spec.ts`：**13 passed in 2.21s**；
   - 全量 Vitest 测试套件：**92 个测试文件全部通过，共 421 项单测 100% PASS**。
2. **静态质量与类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean pass**；
   - `npm run build`：生产环境打包成功无警告（2.84s）。
