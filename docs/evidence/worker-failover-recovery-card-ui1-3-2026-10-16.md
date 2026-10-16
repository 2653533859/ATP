# UI1.3 节点失联超时检测与孤儿任务故障转移卡片验收 (2026-10-16)

## 概述与结论

UI1.3（节点失联超时检测与孤儿任务故障转移卡片）已完成全量交付与验证，正式实现 **Phase 1（跨节点 Worker 集群协同调度与故障转移监控台）100% 全量大闭环**：
1. **API 客户端扩展 (`frontend/src/api/clusterWorkers.ts`)**：
   - 增加 `triggerFailoverScan` 与 `listFailoverHistory` 接口封装；
   - 建立 `FailoverSummaryReport` 与 `FailoverRecoveredTask` 强类型定义。
2. **交互卡片组件 (`frontend/src/views/workbench/components/WorkerFailoverRecoveryCard.vue`)**：
   - 支持动态设定心跳超时阈值（默认 30 秒）；
   - 一键触发全集群「心跳超时全网巡检 (Sweep Scan)」操作；
   - 呈现累计巡检批次、最近巡检失联节点数、抢救重调度任务数与安全熔断终止数 4 大 KPI；
   - 实时呈现标记失联下线（`offline`）的 Worker 节点 ID 标签池；
   - 抢救重调度孤儿任务流水明细（任务 ID、名称、失效节点、重试策略、重新分发状态）；
   - 超限安全熔断任务流水明细（任务 ID、名称、失效节点、超限熔断原因）。
3. **监控抽屉内嵌 (`frontend/src/views/workbench/components/ClusterWorkerMonitorDrawer.vue`)**：
   - 将 `WorkerFailoverRecoveryCard` 组件直接内嵌集成于 Worker 监控抽屉中，构成一体化集群监控与容灾控制面板。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/WorkerFailoverRecoveryCard.spec.ts`：**2 passed**；
   - `src/views/workbench/components/ClusterWorkerMonitorDrawer.spec.ts`：**2 passed**；
   - `src/views/workbench/components/AdaptiveTaskQueueDrawer.spec.ts`：**3 passed**；
   - `src/views/workbench/AppWorkbenchView.spec.ts`：**8 passed**；
   - 汇总验证：**15 passed in 601ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.39s, 0 errors**。
