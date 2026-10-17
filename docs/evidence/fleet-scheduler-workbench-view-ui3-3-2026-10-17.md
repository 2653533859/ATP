# UI3.3 真机集群并发调度中枢工作台页面验收 (2026-10-17)

## 概述与交付物

UI3.3（真机集群并发调度中枢工作台页面）已全量研发交付并挂载路由 `/workbench/fleet-scheduler`，**标志着 ATP v5.4.0 Phase 3（集群热力透视与调度工作台中枢）全量大闭环**：
1. **中枢总控页面 (`frontend/src/views/workbench/FleetSchedulerWorkbenchView.vue`)**：
   - **头部 Hero 概览**：展示系统定位、版本标签（`v5.4.0 Scheduler`, `Fleet Topology`）与核心能力简介，支持一键刷新工作台、唤起设备集群热力透视抽屉与发起模拟调度演练；
   - **4 大 Bento KPI 核心指标卡**：
     - 真机集群健康在线率（`96.8%`，实时心跳正常与温区可达）；
     - 纳管在线物理真机（`32 台`，覆盖 iOS 与 Android 设备池）；
     - 自适应路由秒级派发率（`99.4%`，累计 3500+ 次最优匹配）；
     - 故障热漂移自愈成功率（`100%`，<500ms 续跑，拦截 14 起故障）。
   - **三大盘 Tabs 分组管理**：
     - **Tab 1: 物理真机实时健康水位大盘**：支持平台过滤（iOS / Android）、UDID 搜索、真机列表展示（平台、电池温度与色条、电量、并发水位、隧道 RTT 时延、健康得分与状态），支持“透视健康”操作；
     - **Tab 2: 任务并发调度决策流水**：展示历史调度决策列表（决策 ID、任务 ID、目标平台、调度状态、选中真机、适应度分与决策依据）；
     - **Tab 3: AIMD 动态反压流控中枢**：展示当前自适应窗口大小（Window Size）、排队等待深度、集群饱和度与反压等级（NORMAL / LIGHT_THROTTLING / HEAVY_BACKPRESSURE / OVERFLOW_REJECTION），支持一键手动触发反压重平衡演算；
   - **多组件深度联动**：
     - 深度集成 UI3.1（`DeviceFleetHealthDrawer.vue`）与 UI3.2（`SchedulerTopologyModal.vue`）。
2. **路由挂载 (`frontend/src/router/index.ts`)**：
   - 挂载路由 `/workbench/fleet-scheduler`（name: `fleet-scheduler-workbench`，限定 `ENGINEER_ONLY` 权限）。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/FleetSchedulerWorkbenchView.spec.ts`：5 passed；
   - `frontend/src/views/workbench/components/DeviceFleetHealthDrawer.spec.ts`：4 passed；
   - `frontend/src/views/workbench/components/SchedulerTopologyModal.spec.ts`：3 passed；
   - **累计 12 passed across all Phase 3 spec files (100% PASS)**。
2. **TypeScript 强类型检查**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (20.5s)**
3. **生产环境构建打包**：
   - `npm run build` (`vite build`)：**4570 modules transformed, built in 3.74s, 0 errors.**
