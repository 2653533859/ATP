# ATP v3.7.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**代码变更影响面分析、精准测试推荐选择与变异质量门禁前端控制台全量落地 (Code Impact, Smart Test Selection & Mutation Quality Studio)**
> 承接基准：以 v3.6.0 交付的 12 项 AST 差异分析、测试选择、切片均衡、变异测试与 PR 门禁引擎为底座，打造高保真、直观交互的前端控制台与全景分析看板。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 代码变更差异语法树与精准测试推荐工作台控制台 (Code Diff AST & Smart Test Selection Studio)**
  - 聚焦 Diff 语法高亮与符号映射抽屉、源码-测试用例血缘图谱视图、以及精准测试集推荐与裁剪卡片。
- **Phase 2: 动态切片并发看板与代码变更风险全景面板 (Dynamic Sharding & Risk Scoring Console)**
  - 聚焦 LPT 贪心装箱并发分片甘特图卡片、变更风险三维雷达大盘、以及 Flaky 抖动用例自适应隔离抽屉。
- **Phase 3: 代码变异测试执行与断言盲区热力工作台 (Mutation Testing & Assertion Studio)**
  - 聚焦一阶语法变异算子注入生成弹窗、变异体执行状态监控抽屉、以及变异得分与断言盲区热力视图。
- **Phase 4: CI/CD PR 全要素质量门禁与 Reviewer 机器人控制中心 (PR Quality Gate & CI Bot Hub)**
  - 聚焦 PR 合并准入仲裁卡片、GitHub/GitLab 评论卡片实时预览与广播抽屉、以及流水线 Checkpoint 检查点全景监控视图。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：代码变更差异语法树与精准测试推荐工作台控制台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **Git Diff 代码变更语法高亮与符号路由映射抽屉** | git_diff_ast_analyzer | 落地 `GitDiffAstViewerDrawer.vue` 组件与 API 客户端；展示代码差异、AST 变更类/函数/装饰器列表与受影响 API 路由；见 docs/evidence/git-diff-ast-viewer-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[x]` | **代码符号与自动化测试用例双向血缘图谱视图** | code_to_test_mapping_indexer | 落地 `CodeToTestDependencyGraphView.vue` 视图与路由；基于 ECharts 关系力导向图呈现模块-函数-端点-用例的多维调用血缘；见 docs/evidence/code-to-test-dependency-graph-view-ui1-2-2026-10-16.md |
| UI1.3 `[ ]` | **精准测试集推荐裁剪率与一键回归执行卡片** | smart_test_selection_engine | 落地 `SmartTestSelectionWorkbenchCard.vue` 组件；展示 TIA 策略选择、80%+ 冗余裁剪率、推荐用例置信度排序与一键执行。 |

---

### Phase 2：动态切片并发看板与代码变更风险全景面板

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[ ]` | **LPT 贪心装箱并发切片甘特图与负载均衡卡片** | dynamic_test_shard_partitioner | 落地 `DynamicTestShardingGanttCard.vue` 组件；呈现 N 个 Worker 分片用例装箱甘特图、总耗时方差极小化与理论加速比。 |
| UI2.2 `[ ]` | **代码变更规模/圈复杂度与核心敏感度三维风险雷达大盘** | change_risk_scorer | 落地 `ChangeRiskRadarDashboard.vue` 组件；呈现代码体量、圈复杂度增量与涉敏资产三维得分、CRITICAL-LOW 四级风险与准入建议。 |
| UI2.3 `[ ]` | **CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离抽屉** | flaky_test_suppression_filter | 落地 `FlakyQuarantineManagementDrawer.vue` 组件；展示抖动指数、自适应重试/隔离标签、以及治理白名单工单覆盖录入。 |

---

### Phase 3：代码变异测试执行与断言盲区热力工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **一阶语法变异算子注入生成与变异代码对比弹窗** | code_mutation_operator_engine | 落地 `CodeMutationOperatorGeneratorModal.vue` 组件；支持 ROR/LCR/AOR/RVO/BVO 算子选择、单变异体独立隔离与代码双栏比对。 |
| UI3.2 `[ ]` | **变异体沙箱执行实时进度与 Killed/Survived 监控抽屉** | mutation_execution_runner | 落地 `MutationExecutionLiveMonitorDrawer.vue` 组件；展示变异体执行状态流（Killed 绿标 / Survived 红标），定位击毙用例。 |
| UI3.3 `[ ]` | **变异得分 (Mutation Score) 与断言盲区热力报告页面** | mutation_score_calculator | 落地 `MutationScoreHeatmapReportView.vue` 视图与路由；量化变异得分百分比、算子细分雷达图、以及断言缺失代码行与修复指引。 |

---

### Phase 4：CI/CD PR 全要素质量门禁与 Reviewer 机器人控制中心

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **PR 代码变更全要素质量门禁合并准入仲裁卡片** | pr_quality_gatekeeper | 落地 `PrQualityGatekeeperDashboardCard.vue` 组件；展示通过/阻断/条件通过三态状态徽章、规则裁决表格与整改行动项。 |
| UI4.2 `[ ]` | **GitHub / GitLab 交互式 Reviewer 评论卡片预览与广播抽屉** | pr_comment_bot_dispatcher | 落地 `PrCommentBotPreviewDrawer.vue` 组件；支持 Markdown 实时所见即所得渲染与向 GitHub/GitLab 模拟/真实分发。 |
| UI4.3 `[ ]` | **CI/CD 流水线 Checkpoint 检查点全景监控看板页面** | ci_pipeline_checkpoint_api | 落地 `CiPipelineCheckpointMonitorView.vue` 页面与路由；展示端到端四阶段流水线执行状态、Exit Code (0/1/2) 与高对比度控制台日志。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
