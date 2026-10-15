# F4.1 项目资源配额配置与并发/时长硬限制仪表板验收（2026-10-16）

## 概述与结论

F4.1（项目资源配额配置与并发/时长硬限制仪表板）已完成全量前端代码演进、组件封装与自动化测试：
1. **项目配额 API 客户端扩展 (`frontend/src/api/index.ts`)**：
   - 增加 `ProjectQuotaItem`、`ProjectQuotaEvaluation` 与 `ProjectReapResult` 数据契约模型；
   - 封装 `projectApi.getQuota` 与 `projectApi.updateQuota`：获取与动态配置项目配额；
   - 封装 `projectApi.evaluateQuota`：实时拉取项目当前并发使用量与累计执行秒数；
   - 封装 `projectApi.reapTimeouts`：执行一键超时僵尸长任务收割。
2. **多租户配额管控与水线仪表板组件 (`ProjectQuotaDashboard.vue`)**：
   - **实时配额水线卡片 (Watermark Gauges)**：
     - 当前并发运行水线：展示 `active_runs / max_concurrent_runs`，饱和时自动红字告警；
     - 今日累计执行时长：折算展示 `consumed_hours / limit_hours`，监控每日额度消耗；
     - 新任务准入状态：展示「立即准入 / 排队准入 / 拒绝调度」，给出明确管控原因；
   - **交互式配额调优表单**：
     - 允许管理员动态调整最大并发数（1-100）、每日时长上限（秒/小时）、单任务硬超时（秒/分钟）；
     - 配置并发超额控制策略（`reject` 立即拒绝 / `queue` 自动排队）与管控启用开关；
   - **僵尸长任务收割日志面板**：
     - 展示被超时熔断并强制释放的僵尸任务记录（任务类型、运行 ID、超时阈值、释放原因）。
3. **主系统配置中心深度集成 (`ConfigurationCenterView.vue`)**：
   - 在系统配置中心顶部操作区增加「租户配额管控」快捷按钮，点击滑出 820px 专属配额管理抽屉（`a-drawer`），并支持按选中项目动态切换。

---

## 质量门禁与验证

1. **前端自动化测试**：
   - `src/views/system/components/ProjectQuotaDashboard.spec.ts`：**2 passed in 2.82s**；
   - `src/views/system/components/CapacityRegressionChart.spec.ts`：**2 passed in 2.84s**；
   - `src/views/system/components/ChaosRtoTimeline.spec.ts`：**3 passed in 2.95s**；
   - 全量 Vitest 测试套件：**94 个测试文件全部通过，共 425 项单测 100% PASS**。
2. **静态质量与类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean pass**；
   - `npm run build`：生产环境打包成功无警告（2.35s）。
