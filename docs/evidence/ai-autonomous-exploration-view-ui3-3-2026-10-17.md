# UI3.3 AI 自主探索与意图生成工作台中枢页面验收 (2026-10-17)

## 概述与交付物

UI3.3（AI 自主探索与意图生成工作台中枢页面）已全量研发交付并挂载路由 `/workbench/ai-exploration`，**标志着 ATP v5.2.0 Phase 3（意图对话生成抽屉与自主探索大盘中枢）全量大闭环**：
1. **中枢核心页面 (`frontend/src/views/workbench/AiAutonomousExplorationView.vue`)**：
   - **头部 Hero 概览**：展示系统定位、版本标签（`v5.2.0 AI Core`, `Autonomous VLM Explorer`）与核心能力简介，支持一键刷新、唤起意图合成弹窗与创建自主探索会话；
   - **4 大 Bento KPI 核心指标卡**：
     - 意图工作流推导成功率（`99.2%`，累计 35+ 意图成功转化为 DAG）；
     - 多模态探索覆盖状态总数（`186 个`，跨 Web / iOS / Android 界面）；
     - 探索轨迹逆向工作流转化率（`94.8%`，已固化 80+ 自动化业务测试流）；
     - 探索中捕获异常缺陷数（`12 起`，含白屏卡死、死锁与 5xx 弹窗）。
   - **双大盘 Tabs 分组管理**：
     - **Tab 1: 多模态 VLM 自主探索会话大盘**：支持平台过滤（Web / iOS / Android）、关键字搜索、会话列表展示（会话 ID、平台、设备标识、探索目标、执行步数与发现状态数），支持“查看图谱与推演”和“一键固化为工作流”操作；
     - **Tab 2: 自然语言意图驱动生成历史**：展示历史自然语言业务意图、提取的业务领域、协议矩阵徽标集合、拓扑步骤规模，支持点击查看拓扑与对话微调；
   - **闭环联动与弹窗系统**：
     - 启动探索会话弹窗：支持选择目标终端平台（Web / iOS 真机 / Android 真机）、输入设备标识、业务目标及最大探索步数；
     - 深度集成 UI3.1（`IntentWorkflowGenerateModal.vue`）与 UI3.2（`AutonomousExplorationDashboardDrawer.vue`）。
2. **路由挂载 (`frontend/src/router/index.ts`)**：
   - 挂载路由 `/workbench/ai-exploration`（name: `ai-autonomous-exploration-workbench`，限定 `ENGINEER_ONLY` 权限）。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/AiAutonomousExplorationView.spec.ts`：5 passed；
   - `frontend/src/views/workbench/components/AutonomousExplorationDashboardDrawer.spec.ts`：5 passed；
   - `frontend/src/views/workbench/components/IntentWorkflowGenerateModal.spec.ts`：5 passed；
   - `frontend/src/views/workbench/HybridWorkflowWorkbenchView.spec.ts`：4 passed；
   - **累计 19 passed across all 4 workbench test files (100% PASS)**。
2. **TypeScript 强类型检查**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass!**
3. **生产环境构建打包**：
   - `npm run build` (`vite build`)：**4550 modules transformed, built in 3.85s, 0 errors.**
