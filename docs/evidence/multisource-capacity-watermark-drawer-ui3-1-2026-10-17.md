# UI3.1 多源基础设施 (DB池/Redis/MQ) 容量水位监控抽屉验收 (2026-10-17)

## 概述与结论

UI3.1（多源基础设施容量水位监控抽屉 `MultisourceCapacityWatermarkDrawer.vue`）已全量交付并完成验证，正式开启 **ATP v4.7.0 Phase 3（压测容量水位实时监控与防雪崩自适应熔断控制台）**：
1. **核心抽屉实现 (`frontend/src/views/workbench/components/MultisourceCapacityWatermarkDrawer.vue`)**：
   - **4 大容量水位核心 KPI 指标卡片**：
     - 综合健康负载指数（`health_load_index_pct`，如 `78.5%`）；
     - 峰值资源利用率（`max_utilization_pct`，如 `88.0%`）；
     - 木桶短板瓶颈资源（`weakest_bottleneck_resource`，如 `db_connection_pool_master`）；
     - 防雪崩熔断建议裁决（`BREAKER_TRIPPED` 红色 / `HEALTHY_PASS` 绿色）；
   - **基础设施多源资源水位监控大表 (Infrastructure Resources Watermark)**：
     - 资源标识与详细监控指标名；
     - 资源分类 Tag（`DATABASE_POOL`, `REDIS_CACHE`, `MESSAGE_QUEUE`, `HOST_SYSTEM`）；
     - 实时指标度量值（当前值 / 上限 与单位，如 `440 / 500 conn`）；
     - 容量水位 Progress 进度条与四阶水位彩色 Tag：
       - `SAFE`（<70%，绿色）
       - `WARNING`（70%~85%，橙色）
       - `SATURATED`（85%~95%，紫色）
       - `EXHAUSTED`（≥95%，红色）；
   - **木桶短板调优与应急处置建议大卡 (Remediation Actions)**：
     - 自动化分析输出针对瓶颈资源的扩容建议与熔断降级操作指引；
   - **即时采样演算**：
     - 提供“即时多源容量水位采样”与“刷新水位数据”动作，联动后端实时评估。
2. **工作台挂载 (`frontend/src/views/workbench/PerformanceWorkbenchView.vue`)**：
   - 在性能测试工作台工具栏新增 `<a-button size="small" class="toolbar-btn" @click="showWatermarkDrawer = true"><DashboardOutlined /> 容量水位监控</a-button>` 唤起抽屉。
3. **API 客户端对接 (`frontend/src/api/fullLinkStressTesting.ts`)**：
   - 联动后端 `/api/v1/stress/bottleneck-guardian/watermark/meter` 与 `/reports` REST API。

## 质量与测试门禁验证

1. **组件单元测试 (`MultisourceCapacityWatermarkDrawer.spec.ts` & `PerformanceWorkbenchView.spec.ts`)**：
   - `MultisourceCapacityWatermarkDrawer.spec.ts`：2 passed；
   - `PerformanceWorkbenchView.spec.ts`：5 passed；
   - 总体 Vitest 套件：**7 passed 100%**。
2. **TypeScript 严格类型检查 (`vue-tsc --noEmit`)**：
   - 0 errors, clean pass!
3. **生产环境构建 (`vite build`)**：
   - 成功编译 4494 个模块，产物完整生成，耗时 3.62s，零构建错误。
