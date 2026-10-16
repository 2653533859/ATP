# ATP v3.6.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**代码变更差异影响面分析、精准测试推荐选择与 PR 质量门禁引擎 (Code Change AST Impact Analysis, Smart Test Selection & PR Quality Gate)**
> 承接基准：以 v3.4.0 容器调度/自愈/诊断引擎与 v3.5.0 前端控制台为基础，突破代码级别的变更影响面分析与智能测试集动态裁剪，将传统耗时数小时的全量回归时间压缩至数分钟，实现精细化 CI 效能飞跃与代码级变异质量把关。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1: 代码变更差异 (Git Diff AST) 语义分析与测试用例智能映射引擎 (Code Change AST & Impact Mapping Engine)**
  - 聚焦 Git Commit / PR Unified Diff 的 AST 语法树解析、符号级变更识别与 Code-to-Test 双向依赖图谱推导。
- **Phase 2: 动态测试切片并发调度与变更风险指数模型 (Dynamic Test Sharding & Change Risk Scoring)**
  - 聚焦多 Worker 容器并行切片调度均衡算法、代码变更圈复杂度风险打分与 Flaky 抖动用例自适应隔离。
- **Phase 3: 代码变异测试与断言有效性评分引擎 (Mutation Testing & Assertion Adequacy Engine)**
  - 聚焦一阶代码变异算子注入（条件取反、边界篡改、空返回）、测试用例变异捕获检测与变异得分（Mutation Score）量化。
- **Phase 4: CI/CD PR 自动化准入卡点与多平台 Webhook 机器人 (PR Quality Gate & CI Bot)**
  - 聚焦 GitHub / GitLab 质量门禁准入卡点、富文本 PR Reviewer 评论机器人与流水线 Checkpoint REST API 闭环。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：代码变更差异 (Git Diff AST) 语义分析与测试用例智能映射引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| S1.1 `[x]` | **Git Diff AST 语法树代码变更语义提取与符号差异解析服务** | 无 | 落地 `git_diff_ast_analyzer` 服务与 `/ci-impact/diff-ast/*` API；解析 Unified Diff，基于 Python AST 提取变更类、函数、路由装饰器与代码行范围；见 docs/evidence/git-diff-ast-analyzer-s1-1-2026-10-16.md |
| S1.2 `[x]` | **代码函数/端点与自动化测试用例双向依赖映射索引引擎** | S1.1 | 落地 `code_to_test_mapping_indexer` 服务与 `/ci-impact/mapping/*` API；建立源码符号（模块/类/函数/API路由）与测试用例的多对多血缘拓扑关系图；见 docs/evidence/code-to-test-mapping-indexer-s1-2-2026-10-16.md |
| S1.3 `[x]` | **基于变更影响面的最小化必要测试集智能推导与选择引擎** | S1.2 | 落地 `smart_test_selection_engine` 服务与 `/ci-impact/test-selection/*` API；运行 TIA 算法，智能裁剪冗余用例，输出高置信度精准回归测试子集；见 docs/evidence/smart-test-selection-engine-s1-3-2026-10-16.md |

---

### Phase 2：动态测试切片并发调度与变更风险指数模型

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| S2.1 `[x]` | **多容器弹性 Worker 负载均衡动态测试切片分发器** | S1.3 | 落地 `dynamic_test_shard_partitioner` 服务与 `/ci-impact/sharding/*` API；依据历史执行耗时将推荐用例集贪心切片为 N 个均衡并发分片；见 docs/evidence/dynamic-test-shard-partitioner-s2-1-2026-10-16.md |
| S2.2 `[x]` | **代码变更行数/圈复杂度与核心度多维风险指数模型** | S1.1 | 落地 `change_risk_scorer` 服务与 `/ci-impact/risk-score/*` API；量化变更风险分 (0-100)，自动判定代码变更危险等级；见 docs/evidence/change-risk-scorer-s2-2-2026-10-16.md |
| S2.3 `[ ]` | **CI 选定测试集高频抖动 Flaky 用例自适应抑制隔离过滤器** | S1.3 | 落地 `flaky_test_suppression_filter` 服务与 `/ci-impact/flaky-filter/*` API；联动抖动治理库，自动标记并隔离偶发失败非致命用例。 |

---

### Phase 3：代码变异测试与断言有效性评分引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| S3.1 `[ ]` | **代码变更行一阶语法变异算子注入生成引擎** | S1.1 | 落地 `code_mutation_operator_engine` 服务与 `/ci-impact/mutations/*` API；支持条件反转、边界偏移、返回值篡改等变异算子安全注入。 |
| S3.2 `[ ]` | **变异体执行检验与捕获/存活状态判定执行器** | S3.1 | 落地 `mutation_execution_runner` 服务与 `/ci-impact/mutations/execute/*` API；驱动选定测试用例执行变异体，统计 Killed / Survived 状态。 |
| S3.3 `[ ]` | **用例断言有效性量化与变异得分 (Mutation Score) 计算器** | S3.2 | 落地 `mutation_score_calculator` 服务与 `/ci-impact/mutations/score/*` API；计算变异得分百分比，精准定位"跑过但无实质断言"的脆弱用例。 |

---

### Phase 4：CI/CD PR 自动化准入卡点与多平台 Webhook 机器人

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| S4.1 `[ ]` | **PR 代码变更全要素质量门禁与合并准入判定仲裁器** | S2.2, S3.3 | 落地 `pr_quality_gatekeeper` 服务与 `/ci-impact/pr-gate/*` API；综合测试通过率、变异得分、风险指数判定 PR 是否准入通过。 |
| S4.2 `[ ]` | **GitHub / GitLab 交互式 PR Reviewer 评论与卡片广播机器人** | S4.1 | 落地 `pr_comment_bot_dispatcher` 服务与 `/ci-impact/pr-bot/*` API；自动向 Git PR 评论区渲染高颜值影响面图谱与执行摘要。 |
| S4.3 `[ ]` | **CI/CD 流水线 Checkpoint 检查点通用集成 CLI 与 OpenAPI** | S4.1 | 落地 `ci_pipeline_checkpoint_api` 服务与 `/ci-impact/checkpoint/*` API；提供 CLI 工具与流水线状态返回，支持 Jenkins/GitHub Actions 阻断。 |

---

## 3. 质量门禁规则

1. **单测覆盖与独立运行**：所有新服务与新端点在 `backend/tests/services/` 具备对应的独立单测，`pytest-standalone-sweep.py` 100% 通过。
2. **静态质量与类型安全**：`ruff check`、`ruff format --check` 与 `mypy` 保持 0 issues，无类型漂移。
3. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带完整时间戳与断言日志的验证记录。
4. **统一 Git 提交规范**：严格遵循 Conventional Commits 格式。
