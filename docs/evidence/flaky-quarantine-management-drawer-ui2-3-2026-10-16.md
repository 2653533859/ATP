# UI2.3 CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离抽屉验收 (2026-10-16)

## 概述与结论

UI2.3（CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离抽屉）已完成全量交付与验证，至此 **ATP v3.7.0 Phase 2（动态切片并发看板与代码变更风险全景面板）100% 达成全量大闭环**：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `filterFlakyTests`（对候选测试集执行抖动探测与自适应抑制隔离）、`listFlakyFilterReports`（拉取历史隔离报告列表）、`getFlakyFilterReport`（获取指定报告详情）与 `setGovernanceOverride`（注册用例级人工治理策略覆盖）；
   - 建立 `SuppressionAction`（`normal_passthrough` | `retry_attached` | `isolated_to_quarantine` | `tagged_observation`）、`FlakyFilterMode`、`CaseSuppressionEvaluationItem`、`FlakySuppressionReportItem` 等强类型接口契约。
2. **Flaky 抖动用例自适应抑制隔离控制台抽屉 (`FlakyQuarantineManagementDrawer.vue`)**：
   - **头部模式切换与控制栏**：
     - 单选按钮切换：自适应智能抑制（Auto-Adaptive）、严格隔离（Quarantine All）、仅重试放行（Retry Only）；
     - 支持「重新探测」与「录入治理白名单覆盖」；
   - **核心抑制收益 KPI 看板 (5 大指标卡片)**：
     - 评估用例总数、主干稳固用例数（绿色）、检出 Flaky 抖动数（橙色）、移出主干隔离数（紫色）、附加重试保护数（蓝色）、综合抑制率（40%）；
   - **三选项卡用例处置明细表格**：
     - Tab 1（用例抖动处置总览）：展示用例 ID、历史运行轮次与失败率、彩色抖动指数进度条（Flakiness Score 0~100%）、处置动作标签、重试建议次数与自适应抑制归因；
     - Tab 2（主干放行执行集）：高亮列出真正阻塞主干 CI 的稳固用例 ID 列表；
     - Tab 3（隔离观察测试集）：列出已被安全移出主干队列的隔离用例列表；
   - **录入治理白名单覆盖模态框 (Governance Override Modal)**：
     - 支持输入用例 ID、指定处置动作（强制隔离/附加重试/放行/打标）、治理原因描述与关联工单（如 OPS-8848）。
3. **移动工作台挂载集成 (`AppWorkbenchView.vue`)**：
   - 顶部工具栏挂载「Flaky 抑制隔离」主要操作入口；
   - 随时一键滑出 1040px 抽屉进行测试集偶发抖动排查与自适应隔离。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/FlakyQuarantineManagementDrawer.spec.ts`：**2 passed in 64ms**；
   - `src/views/workbench/AppWorkbenchView.spec.ts`：**8 passed in 1.4s**；
   - 核心工作台测试套件：**36 passed in 2.24s**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 3.07s, 0 errors**。
