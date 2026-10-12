# N4.1 ~ N4.5 Hermes 可恢复测试操作与命令闭环证据（2026-10-12）

## 概述与结论

N4 阶段全部核心机制（持久草稿体系扩展、确认权限与版本防冲突、共用命令服务与资源身份、处理记录交互与模型评测治理）已全部完成代码演进与自动化回归验证：
1. **N4.1 新八类操作面板接入持久草稿**：
   - 扩展 Schema `HermesDraftType` 支持全部 8 类操作面板草稿（`test_plan`, `record`, `api`, `regression`, `repair`, `android`, `defect`, `knowledge`, `summary`）；
   - 会话草稿持久化存储于 `HermesSession.drafts`，页面刷新、重新登录及跨会话恢复均可继续回读草稿并编辑。
2. **N4.2 确认时版本检查、权限校验与重复确认幂等性**：
   - 重复确认幂等复用：对已确认草稿再次提交确认时，幂等返回已有确认结果与关联资源编号（`status="confirmed"`），不再抛出 409 异常；
   - 并发版本防冲突：针对用例配置草稿，严格校验 `expected_updated_at`；若目标用例已被并发修改，精确返回 409 拦截，避免覆盖新版本；
   - 确认时根据草稿类型安全生成或更新实体资源（如创建 `Defect`、`KnowledgeEntry`，更新 `TestCase`，创建 `TestPlan`）。
3. **N4.3 共用命令服务扩展与资源身份保护**：
   - `hermes_commands.py` 扩充 `CommandAction` 动作集合，支持 `update_case`, `create_defect`, `create_knowledge`, `run_case` 等动作；
   - `command_resource` 正确解析并校验目标资源的合法性与生命周期状态（`available`, `missing`, `replaced`, `unverified`）；
   - 跨项目非法重放拦截并标记为 `replaced`，保证多租户/项目边界安全隔离。
4. **N4.4 处理记录交互、运行状态跟踪与项目隔离**：
   - `GET /hermes/action-records` 扩展兼容 `SuiteRun` 与 `TestRun`，使单用例执行与套件运行状态实时反映在操作历史中；
   - 根据动作类型动态生成目标结果跳转路径（`/bugs?...`、`/runs/...`、`/cases/...` 等）；
   - 前端操作面板切换项目时自动清空旧项目历史并拉取新项目记录，做到项目严格隔离。
5. **N4.5 模型效果评测、治理指标与安全降级**：
   - 固定 10 题评测集（`hermes-core-v2`）准确判定有效证据引用、拒答正确性与完整性；
   - `build_governance_summary` 聚合会话延迟 P95、拒答率、无结果率、引用覆盖率与 Token 成本追踪；
   - 遇到模型超时或异常时安全受控降级为规则检索，不中断用户会话。

## 测试与代码清单

- `backend/app/schemas/hermes.py`：定义 `HermesDraftType` 覆盖全部面板类型，保留 `payload` 校验。
- `backend/app/services/hermes_commands.py`：扩展 `CommandAction`、资源解析与命令记录。
- `backend/app/api/v1/hermes.py`：`confirm_hermes_draft` 支持全类型分流确认、幂等复用与版本防覆盖。
- `backend/app/api/v1/suites.py`：`list_hermes_action_records` 兼容多模型资源状态与结果路径。
- `frontend/src/views/intelligence/components/HermesActionsPanel.vue`：动态渲染处理记录类型、直达链接与项目切换监听。
- `backend/tests/api/test_n4_hermes_recoverable_operations.py`：4 项测试通过（草稿持久化、版本拦截与幂等复用、扩展命令与资源身份、处理记录路径解析）。
- `backend/tests/services/test_n4_5_hermes_actions_evaluation.py`：3 项测试通过（八类操作载荷规范、治理摘要指标聚合、评测集算法与拒答判定）。
- 全量 Hermes 测试：共 87 项全部通过（`test_hermes_routes.py`, `test_hermes_tools.py`, `test_hermes.py` 等）。

## 质量门禁

1. **定向测试**：87 项全部通过。
2. **静态质量**：`ruff check`、`ruff format`、`mypy` 188 个源文件全部通过。
3. **前端质量**：`vue-tsc` 与 `vite build` 0 错误。
