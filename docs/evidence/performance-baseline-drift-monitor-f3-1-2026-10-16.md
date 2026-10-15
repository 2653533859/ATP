# F3.1 基线自动打标、漂移偏离度比对与指标告警验收（2026-10-16）

## 概述与结论

F3.1（基线自动打标、漂移偏离度比对与指标告警）已完成全量前端代码演进、组件封装与自动化测试：
1. **性能基线与漂移检测 API 客户端 (`frontend/src/api/index.ts`)**：
   - 增加 `PerformanceDriftAlertResponse` 与 `PerformanceAlignBaselineResponse` 响应契约模型；
   - 扩展 `performanceApi.getDriftAlert`：根据指定压测运行记录 ID 获取吞吐量、延迟与错误率的偏离度及告警评级；
   - 扩展 `performanceApi.alignBaseline`：基于历史最佳运行候选执行原子打标晋升（`auto_promote`）。
2. **基线漂移监控与智能晋升组件 (`BaselineDriftMonitor.vue`)**：
   - **自适应健康与告警横幅**：
     - 根据漂移严重度动态呈现 `none`（绿色稳定）、`warning`（橙色轻微漂移）与 `critical`（红色严重恶化）；
     - 清晰列出具体违约原因列表（如吞吐量下跌超过 15%、P95 延迟恶化超过 20%）；
   - **三核心指标偏离对比卡片 (Delta Cards)**：
     - 吞吐量 (Throughput RPS)：基线目标 vs 当前实测，带偏离百分比与劣化标红标记；
     - P95 响应延迟 (Latency ms)：基线目标 vs 当前实测，延迟增加自动警示；
     - 接口错误率 (Error Rate %)：基线目标 vs 当前实测，错误率跳变增量检测；
   - **基准晋升建议与自动对齐面板**：
     - 实时展示当前运行是否具备晋升为新基线的资格（`eligible`）；
     - 显示详细晋升理由（如吞吐量提升幅度）以及成功晋升的新基线锁定 ID。
3. **主系统压测中心无缝集成 (`PerformanceCenterView.vue`)**：
   - 在压测中心顶部全局操作区增加「基线漂移监控」操作入口（`<DashboardOutlined />`）；
   - 采用 `defineAsyncComponent` 异步模态窗懒加载，不增加首屏体积。

---

## 质量门禁与验证

1. **前端自动化测试**：
   - `src/views/system/components/BaselineDriftMonitor.spec.ts`：**3 passed in 3.43s**；
   - `src/views/system/PerformanceCenterView.spec.ts`：**13 passed in 2.26s**；
   - 全量 Vitest 测试套件：**91 个测试文件全部通过，共 418 项单测 100% PASS**。
2. **静态质量与类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean pass**；
   - `npm run build`：生产环境打包成功无警告（2.20s）。
