# UI2.2 代码变更规模/圈复杂度与核心敏感度三维风险雷达大盘验收 (2026-10-16)

## 概述与结论

UI2.2（代码变更规模/圈复杂度与核心敏感度三维风险雷达大盘）已完成全量交付与验证：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `evaluateRisk`（基于 Git Diff 评估代码变更三维风险指数与等级）、`listRiskReports`（拉取历史风险列表）与 `getRiskReport`（获取指定风险报告详情）；
   - 建立 `RiskLevel`（`CRITICAL` | `HIGH` | `MEDIUM` | `LOW`）、`RiskDimensionBreakdownItem`、`ChangeRiskReportItem`、`EvaluateChangeRiskRequest` 等强类型接口契约。
2. **代码变更风险三维雷达大盘页面 (`ChangeRiskRadarDashboard.vue`)**：
   - **综合风险与准入指示大横幅 (Verdict Banner)**：
     - 大字圆环呈现综合风险分（0-100分，例如 78.5 分红底）；
     - 四级风险徽章（`CRITICAL` / `HIGH` / `MEDIUM` / `LOW`）与明确的准入动作指示（如：`阻断直接合流：必须执行全量回归用例并要求至少 2 位核心研发专家双人评审`）；
   - **三维风险拆解指标卡片网格 (3 Dimension Cards)**：
     1. **变更代码规模 (Volume, 权重 30%)**：展示增/删行数、文件数与体量描述；
     2. **圈复杂度增量 (Complexity, 权重 35%)**：展示 AST 控制流分支/异常处理节点增量；
     3. **核心资产涉敏度 (Criticality, 权重 35%)**：展示触及的涉密敏感模块数与判定；
   - **三维风险雷达图 (ECharts Radar)**：
     - 实测三维风险得分 vs 安全基准线（≤25分）全景雷达对比；
   - **双列归因面板**：
     - 风险驱动因子摘要清单（Risk Factors）；
     - 涉及的高危敏感文件清单（High Risk Files）与行内告警。
3. **路由配置 (`frontend/src/router/index.ts`)**：
   - 注册路由 `/quality/change-risk`（`change-risk-radar-dashboard`），受工程师与管理员权限管控。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/quality/ChangeRiskRadarDashboard.spec.ts`：**2 passed in 55ms**；
   - `src/views/quality/CodeToTestDependencyGraphView.spec.ts`：**2 passed in 59ms**；
   - `src/router/navigationRoutes.spec.ts`：**2 passed in 3ms**；
   - 核心质量大盘与分析单测：**18 passed in 833ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.66s, 0 errors**。
