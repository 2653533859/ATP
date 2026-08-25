# ATP 当前开发计划与导航对齐跟踪（2026-08-25）

> 本文是参考导航对应的当前执行版计划，负责记录“接下来做什么、完成到什么程度、如何验收”。历史方案和详细实施记录见 [`product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md)；任务勾选同步到 [`Task.md`](../Task.md)，长期记忆同步到 [`MEMORY.md`](../MEMORY.md)。

## 2.4.0 参考导航第三轮开发计划（2026-08-25）

本节是当前最新的计划跟踪入口，学习参考导航的“工作台 → 测试能力 → 测试资产 → 智能中枢 → 系统”结构，继续把高频测试动作从系统管理中移出。2.3.0 及更早内容保留为历史交付记录；后续开发、审查、文档同步和提交均以本节的阶段出口为准。

### 2.4.0 建设目标

- 让用户按“我要做什么”进入功能，而不是先理解后端服务或基础设施菜单。
- 五组入口只负责导航和上下文，具体页面仍可保留兼容 URL；旧 URL 必须能正确映射到所属分组、面包屑和项目上下文。
- 所有可执行能力都按“配置 → 预检 → 执行 → 过程事件 → 报告/证据 → 清理”验收；只有页面打开或接口返回 200 不算闭环。
- Windows 是默认开发与验收环境；Android ADB 由本地 Windows Worker 承担，Web/API 不依赖 Android 真机。Kubernetes、发布级 Prometheus、独立 MinIO、真实模型和外部平台继续作为独立环境门禁。

### 2.4.0 导航分组与开发范围

| 阶段 | 导航分组 | 计划建设内容 | 交付出口 | 当前状态 |
| --- | --- | --- | --- | --- |
| P0 | 工作台 | 首页、我的待办、项目中心、任务中心；统一任务队列、状态、重试、终止、批量操作和失败事件 | 从待办或任务可定位到项目、具体运行、报告和失败证据；权限拒绝可解释 | `[E]` 本地基础已完成，待真实角色数据复核 |
| P1 | 接口测试 | HTTP/HTTPS、REST、GraphQL、WebSocket、SSE、gRPC/Dubbo 适配；认证复用、导入、断言、变量和依赖编排 | 受控目标完成请求、参数/变量传递、断言、报告、导入和清理 | `[E]` 本地能力已完成，协议目标仍需独立验收 |
| P2 | APP 自动化 | Windows Android Worker、设备租约、APK 包身份、低代码/录制、录屏、稳定性/Monkey、性能与事件报告 | 单设备完成步骤、控件属性、日志、截图、录像、事件、报告和清理 | `[E]` Karing 单设备证据已有，跨设备和持续运行仍待复核 |
| P3 | UI 自动化 | Playwright 录制、元素库、页面对象、视觉基线、多浏览器、Trace/HAR/控制台日志和失败定位 | Chromium/Firefox/WebKit 至少完成一次录制、回放、失败证据和资源清理 | `[E]` 本地闭环已完成，真实 Worker/浏览器矩阵待复核 |
| P4 | 性能测试 | 节点注册、并发/速率模型、阶梯/峰值/稳定性、Prometheus 采样、基线/回归、MinIO 保留 | 真实短压、取消、资源指标、报告、告警、留存清理和跨主机恢复有脱敏证据 | `[-]` 缺 Kubernetes、发布级 Prometheus 和独立 MinIO |
| P5 | AI 智能测试 | 模型发现/连接、多模态/思考参数、用例/数据集/Mock 草稿、限额和审计 | 生成结果可编辑、来源可回看、敏感值脱敏、失败和权限边界清晰 | `[E]` 本地实现完成，真实模型仍待受控验收 |
| P6 | 测试资产 | 用例、套件、计划、缺陷、报告、评审之间的上下文和双向追踪 | 失败运行可追到报告/证据/缺陷，角色隔离有效，临时资产可清理 | `[E]` 本地链路和验收工具完成，真实项目矩阵待复核 |
| P7 | 智能中枢 | Hermes 助手、需求与用例生成、知识中枢；查询来源、可编辑草稿和审计 | 使用真实需求/知识条目完成查询与生成，来源可回看且不静默写入业务数据 | `[E]` 本地诊断已完成，真实模型/数据验收待执行 |
| P8 | 系统 | 远程工具箱、配置中心、审计、差异、回滚和能力矩阵 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断可解释，回滚精确且可审计 | `[E]` 本地入口已完成，目标部署复核待执行 |
| P9 | 发布收口 | 能力矩阵、证据索引、运行手册、回滚边界和最终 SHA | 每个未关闭门禁都有原因、依赖、证据路径和复验命令 | `[~]` 等待 P4/P5/P6/P7/P8 外部门禁 |

### 2.4.0 执行顺序与当前下一项

1. 先保持 P4 性能真实环境的阻塞边界，不用单节点 Compose、mock 或跳过项替代 Kubernetes/Prometheus/独立 MinIO 证据。
2. q19 已完成 P6/P7 的管理员基础资产链路和清理复验；下一项先补普通 viewer 角色矩阵，确认项目、用例、运行、报告、缺陷、评审和 Hermes 来源的读写隔离。
3. viewer 矩阵之后再在受控模型配置下复核 P5/P7 的模型发现、连接、多模态/思考参数、可编辑草稿、来源审计和清理；没有真实模型时保持阻塞，不用 HTTP 401 或 mock 结果替代。
4. 最后复核 P8 目标部署的 PostgreSQL/Redis/MinIO/Worker/ADB 诊断、配置差异、单资源回滚、脱敏审计和权限拒绝，再进入 P9 发布收口。
5. 每一项必须执行：实现/调整 → 定向测试 → 受影响全量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 提交并推送。
6. 2.4.11 的 P0 任务中心终止确认已完成本地补强；外部验收顺序不变，下一项仍是提供受控 viewer/管理员凭据执行角色矩阵，再进入真实模型与目标治理门禁。

### 2.4.0 状态口径

- `[x]`：代码、测试、独立审查、问题修复、文档同步和必要的本地证据均完成。
- `[E]`：本地实现和自动化证据完成，但真实设备、服务、角色、模型或目标部署仍未验收。
- `[~]`：正在实施，或等待前置门禁解除。
- `[-]`：外部条件明确缺失或验证失败；必须保留阻塞原因和复验命令。

任何模块从 `[E]` 变为 `[x]` 前，都必须新增脱敏真实环境证据；不能用“页面可访问”“Worker 在线”“HTTP 401”“mock 返回”替代业务闭环。

## 2.4.1 P7 Hermes project retrieval and acceptance harness (local complete, 2026-08-25)

- [x] Added `POST /hermes/query`, scoped by project viewer permission, to retrieve matching requirement, knowledge and case sources with redacted excerpts, stable scores, source references and project navigation paths.
- [x] Hermes free-form prompts now fall back to project retrieval when they do not match an existing local intent; source buttons retain deep links, and the knowledge hub can select the requested `knowledge_id`.
- [x] Added `scripts/n7-intelligence-acceptance.py` and [`n7-intelligence-acceptance.md`](n7-intelligence-acceptance.md): temporary project data, parser, list/detail retrieval, source citations, optional real AI drafts, optional viewer isolation, explicit mutation opt-in and finally cleanup with 404 verification.
- [x] Independent review strengthened the harness to validate every marker-bearing source type, project-scoped path and traceable source reference, and to read requirement/knowledge/case details instead of only list responses.
- **Local evidence**: backend Hermes/acceptance/quality tests `21 passed`; frontend Hermes/knowledge tests `11 passed`; targeted Ruff passed; full backend/frontend/type/build gates still run before commit.
- **Status**: `[E]` local implementation and automated evidence are complete; controlled real model, real requirement/knowledge data, viewer credentials and clean remote deployment evidence remain pending. Do not change N7 to `[x]` until the acceptance command completes against a controlled environment.

## 2.4.2 P7 acceptance defect repair (local fixed, remote redeploy pending, 2026-08-25)

- [x] N7/N6 acceptance scripts now create an explicit temporary module when a blank project has no modules; the branch is covered by script regression tests.
- [x] Real local acceptance reached the requirement creation endpoint and exposed an existing async SQLAlchemy bug: `POST /requirements` committed the ORM object and then serialized expired attributes, causing `MissingGreenlet`/HTTP 500. The endpoint now refreshes the requirement before serialization, with a regression assertion for the refresh.
- [x] The temporary remote project was deleted successfully after the initial failed run; no credentials or response bodies were written. The initial failure was fixed and the latest base acceptance is recorded in section 2.4.3.
- **Status**: `[E]` source and tests are fixed; the q19 base data path was reverified after redeploy, while the viewer and controlled-AI checks remain open.

## 2.4.3 P6/P7 q19 real-data base acceptance and cleanup repair (2026-08-25)

- [x] q19 was fast-forwarded to commit `716d1b3`, rebuilt with migration head `20260825_0066`, and restarted for `backend`, `worker` and `migrate`.
- [x] N6 with `--execute` completed the project → module → case → review → suite → plan → terminal run → internal defect chain; the failed target run was recorded and the temporary project was deleted successfully. The latest report is [`n6-project-asset-acceptance-2026-08-25.json`](evidence/n6-project-asset-acceptance-2026-08-25.json).
- [x] The first N6 cleanup failure was caused by `plan_runs.plan_id` lacking `ON DELETE CASCADE`; migration `20260825_0066` now cascades project-owned module/case/run/suite/plan history and sets deleted dataset references on cases to `NULL`. The stale temporary project from the failed run was removed through the normal API after the migration.
- [x] N7 real-data base checks passed: temporary requirement, knowledge entry and case creation, editable retrieval, all three Hermes source citations and cleanup. The latest report is [`n7-intelligence-acceptance-2026-08-25.json`](evidence/n7-intelligence-acceptance-2026-08-25.json).
- **Status**: `[E]` base q19 data and cleanup paths are verified, but N6/N7 remain environment gates because no ordinary viewer credentials were available; N7 also did not enable a controlled real AI model. Keep both gates partial until those checks are executed.

## 2.4.4 q19 acceptance checkpoint and next gate (2026-08-25)

- [x] N6 administrator path is now recorded as a real q19 base acceptance: project/module/case/review/suite/plan/terminal run/defect link and project cleanup all passed after migration `20260825_0066`.
- [x] N7 base data path is now recorded as a real q19 acceptance: temporary requirement/knowledge/case creation, detail reads, editable retrieval, all three Hermes source types and cleanup passed.
- [ ] N6 ordinary viewer matrix: provide a controlled viewer account, verify cross-project read denial and write denial, then remove the temporary account/project data without touching existing data.
- [ ] N7 controlled AI: provide a temporary model configuration and verify model discovery, connection, multimodal/thinking parameters, editable draft generation, source audit and cleanup; credentials and provider response bodies must not enter evidence.
- [ ] N8 target deployment: run the remote toolbox/configuration-center/audit/rollback permission checks on the target deployment; local tests cannot close this gate.
- **Status**: `[~]` The next development/acceptance entry is the viewer isolation matrix. P4 remains `[-]` until Kubernetes, release-grade Prometheus and independent MinIO are available; P9 remains open until every external gate has evidence or an explicit owner/waiver.

## 2.4.5 P8 system-governance acceptance harness (local complete, 2026-08-25)

- [x] Added `scripts/n8-system-governance-acceptance.py` and [`n8-system-governance-acceptance.md`](n8-system-governance-acceptance.md): read-only remote toolbox diagnostics, configuration-center section/metadata checks, bounded audit CSV export and optional viewer denial checks.
- [x] Configuration revision creation and exact `ROLLBACK` are separate explicit opt-ins; the harness rejects secret-bearing response values, accepts only redacted placeholders, never writes response bodies to evidence, and records revision IDs without pretending audit history is cleanup data.
- [x] Wired the command into Make, CI and pre-commit Ruff coverage; contract/quality tests passed `34` items together with the existing deployment-doc checks.
- **Status**: `[E]` The local harness, security boundaries and runbook are complete; N8 still requires a target deployment, controlled administrator/viewer accounts and real diagnostic/configuration/audit/rollback evidence before it can close.

## 2.4.6 q19 target governance preflight (blocked, 2026-08-25)

- [x] The target q19 backend health endpoint returned `status=ok` through the local tunnel; the acceptance stack was observed running with backend, Worker, PostgreSQL, Redis, MinIO, Prometheus and Web Recorder containers.
- [x] A read-only database inspection identified the active administrator username as `parado`; the controlled login probe still returned HTTP 401. No password field, credential value or response body was read/recorded, no password was guessed further, and no remote mutation was attempted.
- [ ] N8 governance acceptance remains pending: inject a verified administrator and ordinary viewer account through the controlled environment, then run the N8 harness with `--require-role-matrix --allow-mutations --rollback --require-rollback`.
- **Evidence**: [`n8-system-governance-environment-audit-2026-08-25.json`](evidence/n8-system-governance-environment-audit-2026-08-25.json).
- **Status**: `[-]` target authentication is currently blocked; this does not change the local implementation status or close any external release gate.

## 2.4.7 N1 task-center server pagination (local complete, 2026-08-25)

- [x] The task-center API now accepts a bounded `offset` and applies pagination after merging Case, Suite, Plan, Android and Performance runs by creation time; this keeps cross-domain ordering correct instead of paging each source independently.
- [x] The task-center UI uses server pagination, preserves project/status/type/page in the URL, resets to page one when filters change, and keeps the existing role/status checks and refresh race protection.
- [x] Added regression coverage for the merged-domain offset boundary; workbench API `15 passed`, backend non-integration `2380 passed`, frontend task-center `2 passed`, frontend full suite `69 files / 302 tests passed`, type-check/build, Ruff and diff-check passed.
- [x] Independent review fixed initialization order for route-derived task type filters, removed response fields not returned by the backend, and aligned the “more tasks” copy with the new pagination behavior.
- **Status**: `[E]` local implementation, tests, review and documentation are complete; real project-role and execution-data verification remains part of the N1 external acceptance gate.

## 2.4.8 N1 workbench todo server pagination (local complete, 2026-08-25)

- [x] The workbench overview API now accepts a bounded `todo_offset` and applies the offset after merging review items, failed runs, overdue plans and eligible device anomalies by priority/time; each source fetches enough rows for the requested page so one large category cannot hide later categories.
- [x] The “My Todos” UI uses server pagination, preserves project and `todo_page` in the URL, resets to page one when the project changes, and keeps the existing refresh race protection. The previous local table pagination no longer truncates the server result.
- [x] Added regression coverage for priority-ordered cross-source pagination; workbench API `16 passed`, backend non-integration `2381 passed`, frontend full suite `69 files / 302 tests passed`, focused todos `2 passed`, type-check/build, Ruff, format and diff-check passed.
- [x] Independent review fixed the pagination container layout so the new controls remain aligned inside the workbench card.
- **Status**: `[E]` local implementation, tests, review and documentation are complete; real project-role and execution-data verification remains part of the N1 external acceptance gate.

## 2.4.9 N5/N7 controlled AI acceptance preflight (local complete, 2026-08-25)

- [x] Extended `scripts/n7-intelligence-acceptance.py`: `--require-ai` now requires a global admin, selects a saved configuration through `--llm-config-id`/`ATP_LLM_CONFIG_ID`, checks the enabled provider/model, discovers the model list, runs the bounded connection test, binds the saved configuration to the temporary project and then requests editable case drafts.
- [x] Added explicit `--require-vision` and `--require-thinking` gates. The former requires both the saved configuration and discovered model to explicitly advertise vision; the latter requires a saved thinking parameter and discovered reasoning support. Standalone capability flags are rejected instead of being silently ignored.
- [x] The preflight never sends an API Key in its own request payload and reports only configuration ID, provider/model summary, capability booleans and model count; the existing redacted error/client/cleanup boundaries remain in force. Added script/runbook contract coverage.
- [x] N7 script regression `10 passed`, affected AI/LLM tests are included in backend non-integration `2383 passed`, and Ruff/format/diff-check passed.
- **Status**: `[E]` local acceptance preparation, tests, independent review, fixes and documentation are complete; real model credentials/configuration, provider parameter acceptance, project generation and cleanup evidence remain pending.

## 2.4.10 N6 viewer isolation matrix harness (local complete, 2026-08-25)

- [x] Extended `scripts/n6-project-asset-acceptance.py`: when viewer credentials are provided, the command creates a separate temporary isolation project and case, then verifies the viewer can read the primary project's case/review/suite/plan assets (and execution/defect details when `--execute` is enabled).
- [x] Added explicit cross-project read denial checks for project, members, cases, suites, plans and defects, plus write denial for case/module creation; all expected permission failures must be redacted HTTP 403 responses.
- [x] Cleanup now removes the viewer membership and independently deletes/verifies both temporary projects, so a failed secondary cleanup cannot hide the primary cleanup attempt. Added helper contract tests and updated the N6 runbook.
- [x] Viewer authentication accepts a short-lived `ATP_VIEWER_TOKEN` in preference to username/password; the token is never written to request evidence or reports, while the password path remains compatible. Added the password-free runbook example.
- [x] N6 script/API role regression `93 passed`, backend non-integration `2385 passed`, Ruff/format/diff-check passed; independent review found no actionable issue.
- **Status**: `[E]` local role-matrix harness, tests, review, fixes and documentation are complete; controlled viewer/admin credentials and real project data are still required to close the external N6 gate.

## 2.4.11 P0 task-center stop confirmation (local complete, 2026-08-25)

- [x] Added a second confirmation before single-task and batch stop actions in `frontend/src/views/workbench/TaskCenterView.vue`; retry behavior remains direct, while stop uses localized destructive-action copy.
- [x] Revalidated action eligibility inside the actual execution callback so a stale confirmation cannot send a stop request after the task is no longer stoppable.
- [x] Added frontend regression coverage for the confirmation boundary; frontend full suite `69 files / 303 tests passed`, `vue-tsc --noEmit` and production build passed. Independent review found and fixed the stale-confirmation race.
- **Status**: `[E]` local implementation, tests, review, fix and documentation are complete; real role/action permission behavior remains part of the N1/P0 external environment review.

## 2.3.0 参考导航第二轮开发计划（2026-08-25）

本节是当前导航重构的最新执行游标，按参考侧栏的五组职责组织功能，不再把设备、APK、Mock、数据集、Web/API 资产和治理能力全部堆在“系统管理”下面。导航入口、旧 URL 兼容和业务闭环分别记录：入口存在只代表可访问，只有完成配置→执行→过程→报告/证据→清理才算模块闭环。

### 五组导航职责与边界

| 导航分组 | 直接入口 | 负责内容 | 不负责的内容 | 当前状态 |
| --- | --- | --- | --- | --- |
| 工作台 | 首页、我的待办、项目中心、任务中心 | 项目上下文、待办聚合、任务队列、重试/终止/批量操作、状态跳转 | 具体协议和设备配置 | `[E]` 本地闭环已完成，待真实账号/角色复核 |
| 测试能力 | 接口测试、APP 自动化、UI 自动化、性能测试、AI 智能测试 | 测试方式的配置、用例选择、执行、过程观察、报告和证据 | 测试资产的长期归档和系统基础设施治理 | `[E]` 本地闭环已完成，外部依赖分别验收 |
| 测试资产 | 测试用例、测试计划、缺陷管理、测试报告、用例评审 | 复用资产、运行追踪、失败证据、缺陷关联、趋势和评审记录 | Worker/ADB/数据库等基础设施操作 | `[E]` 本地关联已完成，待真实项目权限复核 |
| 智能中枢 | Hermes 助手、需求与用例生成、知识中枢 | 查询、需求解析、可编辑草稿、来源引用和调用审计 | 静默写入用例、需求或知识库 | `[E]` 本地闭环已完成，待真实模型/数据复核 |
| 系统 | 远程工具箱、配置中心 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断、配置版本/差异、审计和单资源回滚 | 日常测试执行和测试资产管理 | `[E]` 本地闭环已完成，待目标部署复核 |

### 2.3.0 模块顺序与验收出口

| 顺序 | 模块 | 本轮交付 | 最小验收出口 | 依赖 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | N0 导航壳与项目上下文 | 五组分组、深链选中、旧 URL 映射、面包屑、窄屏/折叠、权限隐藏 | 刷新和深链不丢项目上下文；入口标题、能力描述和权限一致 | 真实账号角色用于最终复核 | `[E]` |
| 2 | N1 工作台与任务中心 | 待办聚合、任务过滤、轮询、重试、终止、批量执行和失败事件 | 五类任务可查；操作结果、失败原因和事件可追溯；越权被拒绝 | 可清理任务数据 | `[E]` |
| 3 | N2-API 接口测试工作台 | HTTP/GraphQL/WebSocket/gRPC、环境变量/认证复用、导入、断言、报告 | 请求、变量提取、依赖传递、报告下载和权限边界闭环 | 受控协议目标 | `[E]` |
| 4 | N2-APP APP 自动化工作台 | Windows Worker/ADB、设备租约、APK 身份、低代码、录屏、专项任务和报告 | 单设备执行、步骤/事件/日志/截图/录像/报告可回放；冲突可解释 | Windows Android Worker、可清理设备 | `[E]` |
| 5 | N3-UI UI 自动化工作台 | Playwright 录制、元素/页面对象/视觉基线、回放、Trace/HAR/控制台日志 | Chromium/Firefox/WebKit 的录制、回放和失败证据可查看 | 浏览器 Worker | `[E]` |
| 6 | N4 性能测试工作台 | 多节点容量、Prometheus 采样、MinIO 生命周期、趋势/基线/留存 | 真实短压、取消、采样、报告、清理和跨主机恢复均有脱敏证据 | Kubernetes、发布级 Prometheus、独立 MinIO | `[-]` |
| 7 | N5 AI 智能测试 | 模型发现/连接、思考/多模态参数、用例/数据集/Mock 草稿和安全审计 | 结果可编辑、有来源；限额、权限、失败和敏感值边界可解释 | 受控模型、可清理项目 | `[E]` |
| 8 | N6 测试资产与评审 | 用例→套件→计划→运行→报告→缺陷→评审双向追踪 | 失败运行能追到证据/缺陷；普通角色项目隔离有效 | 临时项目、成员和角色矩阵 | `[E]` |
| 9 | N7 智能中枢 | Hermes、需求/用例草稿、知识检索和来源展示 | 结果先进入可编辑草稿；来源可回看；不静默落库 | 真实模型、需求和知识条目 | `[E]` |
| 10 | N8/N9 系统治理与发布收口 | 远程诊断、配置差异/回滚、脱敏审计、能力矩阵和发布证据 | 诊断可解释、回滚精确、普通角色不能越权；最终 SHA 可复核 | 目标部署、迁移数据和前述门禁 | `[~]` |

### 本轮执行规则

1. 先完成 N0～N1 的导航与任务中心回归，再按 N2-API、N2-APP、N3-UI、N4 性能、N5 AI、N6 测试资产、N7 智能中枢和 N8 系统治理复核；N4 性能真实环境仍是独立外部门禁，缺少 Kubernetes/发布级 Prometheus/独立 MinIO 时保持 `[-]`。
2. Windows 是默认开发与验收环境：API/Web 使用本地或远程后端即可；Android 真机只由 Windows Android Worker 执行 ADB，不把 Linux 主机是否连接真机作为 Web/API 的前置条件。
3. 每个模块必须按“实现/调整 → 定向测试 → 受影响全量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 提交推送”推进。
4. 真实设备、模型、协议服务、外部平台和目标部署必须留下脱敏证据；页面可打开、mock、单节点 Compose 或跳过项只能标记 `[E]`/`[-]`，不能写成真实通过。
5. 下一执行入口：先保持 N4 性能环境阻塞边界，准备其复验命令；在等待外部环境期间，优先做 N5 真实模型调用准备、N6 临时项目/角色矩阵和 N9 发布文档一致性检查。

## 2.3.1 N5 AI 模型能力元数据解析（本地完成，2026-08-25）

- [x] 模型发现同时识别第三方返回的 `capabilities`、`modalities`、`input_modalities`、`output_modalities` 和 `supported_modalities` 字段；多模态模型可从 `image`/`vision`/`multimodal` 等阳性元数据得到提示，思考模型可从 `reasoning`/`thinking` 等阳性元数据得到提示。
- [x] 供应商已提供能力字段时，未出现阳性标记的能力继续显示为未知，不再使用模型名猜测覆盖供应商元数据；没有能力字段的旧响应继续使用模型名提示兼容路径。
- [x] 新增多模态与思考元数据、未知能力和原有模型名提示回归；模型发现/API 定向 `20 passed`，受影响 AI 定向 `69 passed`，后端非集成全量 `2340 passed`，Ruff、格式、mypy 和差异检查通过。
- **状态**：`[E]` 本地实现、测试、独立审查、问题修复和文档同步完成；真实供应商返回格式、实际参数接受情况和项目级生成仍待受控模型验收。

## 2.3.2 N5 真实模型环境只读门禁复核（阻塞，2026-08-25）

- [x] 对 q19 acceptance 部署做只读配置核对：AI LLM 配置数量为 `0`，未创建或修改远端配置。
- [x] 对外部模型服务做不带凭据的连通性探针：服务返回 HTTP `401`，只能证明网络入口可达，不能证明模型列表、连接或生成可用；未记录 Token 或响应正文。
- [ ] 真实模型验收仍需在受控配置下完成模型列表、连接、思考/多模态参数、可编辑草稿生成、来源审计和临时项目清理。
- **状态**：`[-]` 外部条件已确认阻塞；脱敏证据见 [`ai-model-environment-audit-2026-08-25.json`](evidence/ai-model-environment-audit-2026-08-25.json)，不得把 HTTP 401 或空配置写成通过。

## 2.3.3 N7 Hermes 跨任务失败诊断（本地完成，2026-08-25）

- [x] 工作台新增统一失败诊断入口：`case` 继续复用既有 LLM/规则诊断链，`suite`、`plan`、`android` 和 `performance` 从各自执行摘要生成规则诊断；所有请求先按任务所属项目做 viewer 权限校验。
- [x] Android 诊断纳入已持久化的崩溃、ANR、卡顿计数、异常事件和错误级执行事件；性能诊断纳入执行器错误、错误率、p95 和基线排查线索；摘要、建议和错误样本均有长度边界，不读取或发送压测配置密钥。
- [x] Hermes 失败任务卡片不再对非 `case` 类型显示“不支持”，改为调用统一工作台诊断接口，并保留原任务详情来源；成功/非异常任务返回明确的“暂无失败原因”，不虚构失败结论。
- [x] 新增跨任务规则诊断与工作台权限/派发回归；后端定向 `13 passed`、后端非集成全量 `2345 passed`，Hermes 定向和前端全量 `69 files / 293 tests passed`，新增服务 mypy、Ruff、格式检查通过，`vue-tsc` 和生产构建通过；独立审查已修复 Android ANR 与通用异常分类优先级问题。
- **状态**：`[E]` 本地实现、测试、审查、问题修复和文档同步完成；真实模型调用、真实需求/知识数据、角色矩阵和可清理项目仍待 N7 外部验收。

## 2.3.4 N6 缺陷状态刷新项目隔离（本地完成，2026-08-25）

- [x] 缺陷状态刷新先解析执行记录所属用例/模块并校验当前用户的项目 viewer 权限；无法解析所属资源时返回明确的 404，不再仅凭登录态访问任意 `run_id`。
- [x] 已保存的缺陷跟踪配置必须与执行记录所属项目一致；跨项目配置在调用外部平台前拒绝，避免越权读取外部 Issue 状态或产生错误审计关联。
- [x] 新增无项目权限和跨项目 tracker 回归；缺陷跟踪 API 定向 `11 passed`，差异检查通过。
- **状态**：`[E]` 本地实现、定向测试、独立审查和文档同步完成；真实项目成员/角色矩阵、外部缺陷平台和可清理失败运行仍待 N6 环境验收。

## 2.3.5 N6 缺陷证据跨类型报告导航（本地完成，2026-08-25）

- [x] 缺陷详情的执行证据按类型跳转到对应报告入口：case 进入运行详情，Android 进入专项报告，性能进入性能工作台，suite/plan 进入各自执行记录抽屉。
- [x] suite/plan 通过 `run_id` 先解析执行记录所属资源，并携带 `project_id` 恢复项目上下文；性能工作台按 `run_id` 选中对应运行，避免跨项目或默认项目导致的“找不到证据”。
- [x] 新增跨类型导航、suite/plan 深链抽屉和性能运行选择回归；前端定向 `23 passed`，全量 `69 files / 297 tests passed`，`vue-tsc` 和生产构建通过；独立审查已修复 suite/plan 深链缺少项目上下文问题。
- **状态**：`[E]` 本地实现、测试、独立审查和文档同步完成；真实项目角色、可清理失败运行和各类报告环境仍待 N6 外部验收。

## 2.3.6 N6 计划报告套件明细导航（本地完成，2026-08-25）

- [x] 计划运行报告中的套件明细新增“查看详情”入口，携带当前 `project_id` 与 `suite_run_id` 跳转到套件执行记录；目标页面按项目过滤套件并展开指定运行，补齐“计划→套件→运行→报告”的追踪链。
- [x] 无效或缺失的 `suite_run_id` 不允许触发跳转；新增计划列表回归，定向 `7 passed`，前端全量 `69 files / 298 tests passed`，`vue-tsc` 和生产构建通过；独立审查未发现问题。
- **状态**：`[E]` 本地实现、测试、独立审查和文档同步完成；真实项目角色、可清理失败运行和目标报告环境仍待 N6 外部验收。

## 2.3.7 N6 数据集影响范围项目上下文（本地完成，2026-08-25）

- [x] 测试数据集影响范围中的案例、套件、计划入口现在保留当前 `project_id`，跳转后可继续使用同一项目上下文，不会回到默认项目或混入其他可见项目；案例详情可继续加载项目环境并返回项目筛选。
- [x] 新增三类影响入口回归；数据集定向 `9 passed`，前端全量 `69 files / 299 tests passed`，`vue-tsc` 和生产构建通过；独立审查已补齐案例入口遗漏的项目上下文。
- **状态**：`[E]` 本地实现、测试、独立审查和文档同步完成；真实项目角色、跨项目可见性和可清理数据仍待 N6 外部验收。

## 2.3.8 N6 用例评审打开详情的项目上下文（本地完成，2026-08-25）

- [x] 用例评审工作台的“打开用例”入口携带评审记录自身的 `project_id`，案例详情可继续加载对应项目环境并保留返回项目筛选。
- [x] 新增评审工作台深链回归；定向 `3 passed`，前端全量 `69 files / 300 tests passed`，`vue-tsc` 和生产构建通过；独立审查确认使用记录项目 ID，未发现跨项目问题。
- **状态**：`[E]` 本地实现、测试、独立审查和文档同步完成；真实项目角色矩阵、跨项目可见性和可清理评审数据仍待 N6 外部验收。

## 2.3.9 N6 工作台任务详情的项目与运行上下文（本地完成，2026-08-25）

- [x] 工作台任务聚合返回的 case、suite、plan、Android 和 performance 详情地址统一保留所属 `project_id`；suite/plan/performance 额外携带对应 `run_id`，从任务中心打开后可直接定位到该次执行记录，不再回到默认项目或仅打开列表。
- [x] 新增五类任务详情路径回归，覆盖项目上下文和运行 ID；定向工作台 API `14 passed`，后端非集成全量 `2352 passed`，Ruff 与差异检查通过。
- [x] 独立审查发现并修复数据集影响范围静态契约仍断言旧的无 `query` 路由写法，改为校验带项目上下文的 `suites`/`plans` 路由；相关回归与工作台测试 `17 passed`。
- **状态**：`[E]` 本地实现、测试、独立审查、问题修复和文档同步完成；真实项目角色矩阵、跨项目可见性、可清理运行和各类报告环境仍待 N6 外部验收。

## 2.3.10 N6 项目资产与角色矩阵验收工具（本地完成，2026-08-25）

- [x] 新增 `scripts/n6-project-asset-acceptance.py`，按临时项目→模块→API 用例→评审→套件→计划→执行/报告→缺陷→清理顺序验证资产链；`--execute` 和 `--allow-mutations` 均需显式开启，普通角色验证通过 `ATP_VIEWER_USERNAME`/`ATP_VIEWER_PASSWORD` 注入。
- [x] 验收报告只保留脱敏 endpoint、资源 ID、状态和有限长度说明；凭据只从环境变量读取，HTTP 错误不回显响应正文，清理在 `finally` 中执行并校验删除后的 404；`Makefile`、CI、pre-commit 和运行手册均已接入。
- [x] 新增安全边界、错误脱敏、清理和质量清单一致性契约；N6 脚本定向 `6 passed`，质量门禁一致性定向 `10 passed`，真实部署执行仍需受控管理员/普通成员和可清理运行数据。
- **状态**：`[E]` 本地工具、测试、独立审查、问题修复和文档同步完成；N6 发布门禁仍待真实项目角色矩阵、执行报告、缺陷链和清理证据。

## 2.2.0 当前开发计划与文档跟踪（2026-08-25）

本节是 2.1.0 之后的当前跟踪节，专门回答“下一步开发什么、依赖什么、何时算完成”。参考导航的五组边界保持不变：工作台、测试能力、测试资产、智能中枢、系统。入口已经存在不等于业务闭环完成；真实设备、外部服务、第三方模型和目标部署必须有独立证据才能关闭对应门禁。

### 后续开发顺序

| 顺序 | 模块 | 主要交付 | 依赖 | 验收出口 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| P0 | N4 性能真实环境 | 多节点调度、容量限制、Prometheus 指标、MinIO 生命周期与跨主机恢复 | Kubernetes、Prometheus、独立 MinIO source/target | 真实短压、取消、采样、报告、清理和恢复回读均有脱敏证据 | `[-]` 环境缺失，暂不开发替代性 mock |
| P1 | N5 AI 真实模型 | 模型列表/连接、思考与多模态参数、用例/数据集/Mock 草稿生成 | 受控模型配置、可清理项目数据 | 结果可编辑、有来源和审计；权限、限额、失败和敏感值边界可解释 | `[E]` 本地完成，待真实模型验收 |
| P2 | N6 测试资产闭环 | 用例→套件→计划→运行→报告→缺陷→评审追踪 | 真实项目成员、角色和可清理运行数据 | 失败运行可追证据和缺陷，项目隔离与越权拒绝有效 | `[E]` 本地完成，待真实数据验收 |
| P3 | N7 智能中枢 | Hermes 查询、需求与用例草稿、知识检索和来源展示 | 真实模型、需求和知识条目 | 生成结果先进入可编辑草稿，来源可回看，不静默写入业务数据 | `[E]` 本地完成，待真实数据验收 |
| P4 | N8 系统治理 | 远程工具诊断、配置差异、脱敏审计、单资源回滚 | 目标部署、管理员/普通角色和迁移数据 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断可解释，回滚精确且可审计 | `[E]` 本地完成，待目标部署复核 |
| P5 | N9 发布收口 | 能力矩阵、证据索引、操作手册、回滚边界和发布结论 | P0-P4 的真实边界和最终提交 SHA | 未关闭门禁均有原因、依赖、负责人、证据路径和复验命令 | `[~]` 等待外部门禁收口 |

### 每个模块的跟踪模板

后续每个模块在移动状态前必须填写并完成以下顺序：

1. 在本节和 `Task.md` 登记范围、依赖、风险、验收出口和复验命令。
2. 完成实现或配置调整，补充对应的 bug 回归测试。
3. 运行定向测试、受影响全量门禁和必要的独立环境验证。
4. 做独立代码审查，修复发现的问题，再重复受影响门禁。
5. 同步 `Task.md`、`MEMORY.md`、路线图、发布状态和必要的操作手册。
6. 使用 Conventional Commit 提交并推送；真实环境未验证的模块只能保留 `[E]` 或 `[-]`。

### 当前推进结论

- 先推进 P0/N4，但只在真实 Kubernetes、Prometheus 和独立 MinIO 条件具备后执行；当前目标主机条件不足，保持阻塞，不用单节点 Compose、mock 或跳过项替代。
- 在 P0 等待期间，可并行准备 P1～P4 的可清理测试数据、角色矩阵和真实环境复验脚本，但不能把本地回归写成真实环境通过。
- P5/N9 只在所有未关闭门禁均有明确边界后收口；当前发布结论仍不是“无条件可发布”。

## 2.2.1 N4 性能 smoke 显式 Kubernetes 门禁（本地完成，2026-08-25）

- [x] `scripts/performance-environment-smoke.py` 新增 `--require-kubernetes`；传入后必须同时提供 `--deployment`，否则在执行前失败，避免漏传 Kubernetes 参数时把跳过项误读为通过。
- [x] Kubernetes 多节点/副本/Worker 资源预检示例、发布清单和 N4 发布证据复验命令均显式使用该门禁；Docker Compose 本地验收仍可不启用该参数。
- [x] 性能脚本定向、发布契约与质量一致性回归 `46 passed`，Ruff、格式、文档标记和差异检查通过。
- **状态**：`[E]` 本地实现、测试、审查和文档同步完成；172.31.27.133 仍只有 Docker Compose，q19 Prometheus 仅作为单节点观察，真实 Kubernetes、发布级 Prometheus 指标覆盖和独立 MinIO 灾备仍未关闭 N4。

## 2.2.2 N4 MinIO 灾备端点独立性门禁（本地完成，2026-08-25）

- [x] `scripts/minio-dr-acceptance.py` 不再只比较端点字符串；同文本主机、`localhost`/回环 IP 别名以及解析到同一 IP 的 source/target 都会在连接 MinIO 前失败。
- [x] 失败证据明确记录 `endpoint-independence`，不会写入访问密钥；跨端点成功路径继续校验复制、回读、恢复、SHA-256 和临时对象清理。
- [x] MinIO 灾备、性能 smoke、发布契约和质量一致性定向回归 `51 passed`，Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地实现、测试、审查和文档同步完成；仍需真实不同主机的 MinIO source/target、生命周期规则和可清理对象完成外部验收。

## 2.1.0 开发计划与跟踪快照（历史基线，2026-08-25）

本节保留 2.1.0 的执行快照；当前唯一有效的执行游标以本文件上方 2.2.0 为准。N2 Karing 单设备闭环已经完成；N4 的真实性能环境门禁在 2.2.0 中继续保持阻塞，环境条件不足时不把本地代码或 q19 Compose 观察结果写成生产通过。每个可交付模块继续执行：**实现/调整 → 定向测试 → 受影响全量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → 提交推送**。

### 当前状态台账

| 顺序 | 模块 | 计划交付 | 最小验收出口 | 状态 | 解除条件/下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 | N4 性能真实环境 | 多节点调度、容量限制、Prometheus 采样、MinIO 生命周期和跨主机恢复 | 真实环境完成短压/取消、采样、报告、保留清理和恢复回读；证据不含凭据 | `[-]` | 提供 Kubernetes、Prometheus、独立 MinIO 源/目标后执行既有 smoke 与真实短压 |
| 2 | N5 AI 智能测试 | 三方模型、多模态/思考参数、用例/数据集/Mock 草稿生成、诊断审计 | 生成结果可编辑、有来源、权限与限额生效，失败和敏感值可解释 | `[E]` | 注入受控模型配置和可清理项目数据，完成真实调用复核 |
| 3 | N6 测试资产 | 用例/套件/计划/缺陷/报告/评审关联、权限和追踪 | 失败运行可追到证据、缺陷、评审，项目隔离有效 | `[E]` | 使用真实项目成员和可清理运行数据完成端到端复核 |
| 4 | N7 智能中枢 | Hermes、需求与用例生成、知识检索和来源展示 | 查询/生成可编辑且带来源，不静默写入业务数据 | `[E]` | 使用真实模型、需求和知识数据完成权限与来源复核 |
| 5 | N8 系统治理 | 远程诊断、配置版本/差异、脱敏审计和单资源回滚 | 诊断可解释、敏感字段不泄露、回滚精确且可审计 | `[E]` | 在目标部署复核密钥边界、角色权限、迁移和回滚 |
| 6 | N9 发布收口 | 能力矩阵、证据索引、操作手册、回滚边界和发布状态 | 每个未关闭门禁都有原因、依赖、负责人和复验命令 | `[~]` | N4 与 N5-N8 真实边界完成后绑定最终 SHA 收口 |

### N4 当前执行拆分

N4 的本地实现已经具备，不重复开发已有采样器。下一轮只按以下顺序做环境验收：

1. **集群与容量**：确认至少两个可调度且 Ready 的 Kubernetes 节点、性能 Worker 副本数、CPU/内存 requests/limits，并运行 `make performance-environment-smoke` 的集群参数检查。
2. **监控采样**：确认 Prometheus readiness、目标服务指标和性能 Worker 指标可查询；执行真实短压与取消，保存脱敏采样、响应时间、错误率和资源关联结果。
3. **对象存储生命周期**：确认独立 MinIO source/target、生命周期策略和最小权限；运行 `make minio-dr-acceptance`，校验复制、目标回读、恢复回源、SHA-256 和临时对象清理。
4. **门禁复核**：对失败重试、任务取消、节点故障和清理结果进行独立审查；任一依赖缺失就保留 `[-]`，并记录复验命令，不用同机 MinIO、单节点 Compose、mock 或跳过项替代。

当前目标主机的只读复核仍显示缺少 Kubernetes CLI/集群、默认 Prometheus readiness 和独立 MinIO 源/目标；q19 的 `29090` Prometheus readiness 和四个 Compose targets 仅作为观察，不替代发布级证据，因此 N4 保持阻塞；证据见 [`performance-environment-audit-2026-08-25.json`](evidence/performance-environment-audit-2026-08-25.json)。

### 后续 N5-N9 入口

- **N5**：模型列表拉取和连接健康检查的本地闭环已完成；下一步在受控真实模型上验证连接、多模态与思考参数开关、草稿生成、来源/审计、限额和敏感值脱敏；只保存摘要，不保存 API Key 或原始提示中的密钥。
- **N6**：建立一组可清理的真实项目数据，验证用例→套件→计划→运行→报告→缺陷→评审链路，以及普通角色的项目隔离。
- **N7**：使用真实需求和知识条目验证 Hermes 查询、需求解析、用例草稿和来源引用；生成结果必须先进入可编辑草稿，不能静默落库。
- **N8**：复核 PostgreSQL/Redis/MinIO/Worker/ADB 诊断、配置差异、单资源回滚、审计和权限拒绝；任何凭据只从受控环境注入。
- **N9**：汇总代码 SHA、测试输出、审查记录、环境证据、操作手册和回滚边界；未通过的门禁必须保留阻塞原因和复验入口，不能发布为“全部完成”。

### 跟踪规则

- `[x]`：代码/配置、测试、独立审查、问题修复、文档同步和提交推送均完成。
- `[E]`：本地实现与回归完成，但真实设备、模型、外部平台或目标部署仍待验收。
- `[~]`：存在进行中的实现、联调或收口工作；`[-]`：被明确外部条件阻塞。
- 每次状态变化必须同步 `Task.md`、`MEMORY.md`、路线图和发布状态；证据文件只存脱敏摘要，禁止写入凭据、Token、预签名 URL、原始日志或二进制。

### 2.1.1 N5 Ollama 无密钥调用边界（2026-08-25）

- [x] AI 用例、测试数据集、Mock 规则、失败诊断和自愈调用统一允许 Ollama 空 API Key；非 Ollama 的空密钥配置仍按解密失败拒绝，避免放宽供应商鉴权边界。
- [x] OpenAI 兼容请求在没有 API Key 时不发送空的 `Authorization: Bearer` 请求头；有密钥的供应商请求头和加密存储行为保持不变。
- [x] 新增 keyless Ollama 用例/数据集/Mock 回归和 LLM 请求头回归；相关 AI 服务定向回归 `88 passed`，后端非集成全量 `2315 passed`，Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地实现、测试、审查和修复完成；真实 Ollama/三方模型列表、健康检查、多模态/思考参数和项目级生成仍需受控环境验收。

### 2.1.2 N5 AI 模型连接健康检查（2026-08-25）

- [x] 新增 `POST /api/v1/ai/llm-configs/test-connection` 和 AI 配置页“测试连接”入口；编辑已有配置时复用数据库中的 Fernet 密钥，新建 Ollama 配置允许空 API Key，跨供应商切换不会误复用旧密钥。
- [x] 健康检查只发送固定短文本，强制 `max_tokens=4`、`timeout=15s`，过滤配置中的平台治理字段并限制温度/token 覆盖；Endpoint 先校验并规范化，错误提示不返回供应商原始响应或密钥，成功结果只返回模型、耗时和审计摘要。
- [x] 增加后端密钥复用、Ollama 无密钥、思考参数保留、Endpoint 规范化和权限回归；后端配置定向 `15 passed`，后端非集成全量 `2317 passed`，前端配置页 `3 passed`、全量 `69 files / 287 tests passed`，类型检查、生产构建、Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地实现、测试、独立审查和修复完成；仍需在受控真实模型上复核模型列表、连接成功/失败、思考与多模态参数和项目级生成，不把本地模拟调用写成外部模型通过。

### 2.1.3 N5 模型能力提示与思考参数快捷配置（2026-08-25）

- [x] AI 配置页新增思考模式快捷选择：关闭（默认）、`thinking=true`、`enable_thinking=true` 和 `reasoning_effort` 三档；选择器会同步高级 JSON，手工 JSON 仍兼容保留。
- [x] 拉取模型后分别提示思考与多模态能力的已识别/未识别/未知状态；能力提示不自动开启思考，模型切换或供应商切换不会静默改变高级参数。
- [x] 新增快捷配置、手工参数兼容和能力提示回归；前端定向 `5 passed`，全量 `69 files / 289 tests passed`，`vue-tsc --noEmit`、生产构建、差异检查和独立审查通过。
- **状态**：`[E]` 本地 UI 交付、测试、审查和修复完成；能力识别仍是供应商列表/模型名提示，真实模型是否接受参数需在受控连接测试和项目生成中复核。

### 2.1.4 N5 AI 生成失败与原始响应安全边界（2026-08-25）

- [x] AI 用例生成不再返回供应商错误响应正文或网络异常字符串；HTTP 错误只保留状态码，超时返回 504，网络错误返回固定的可操作提示，并继续写入不含敏感值的失败审计事件。
- [x] 测试数据集、Mock 规则 AI 生成和模型列表拉取同步收口网络错误；异常信息不回显 URL、请求体、API Key 或供应商响应内容。
- [x] AI 用例生成返回的 `raw_response` 仅保留最多 12,000 个字符，并对 JSON 敏感字段、键值文本、URL 查询密钥和 URL 用户信息脱敏；生成草稿仍走原有可编辑预览和项目权限/限额边界。
- [x] 新增 HTTP 错误正文、网络错误、原始响应脱敏和长度上限回归；AI 用例/治理定向 `21 passed`，数据集/Mock/LLM 相关回归 `78 passed`，后端非集成全量 `2322 passed`，Ruff 和差异检查通过。
- **状态**：`[E]` 本地安全边界、测试、独立审查和修复完成；真实供应商错误格式、模型返回内容和项目级生成仍需在受控模型环境复核，不把本地模拟调用写成真实模型通过。

### 2.1.5 N5/N6 AI 用例来源可追踪摘要（2026-08-25）

- [x] AI 用例生成响应新增安全来源摘要：记录配置 ID、供应商、模型名、接口数量、数据集及版本、去重后的 Mock 规则 ID 和生成时间；不记录 Endpoint、提示词、API Key 或原始响应。
- [x] AI 生成草稿保存时将来源摘要写入用例 `config._ai_source`，用例详情页展示可读来源；已有仅含数据集/Mock 信息的历史用例仍可兼容显示。
- [x] 生成成功和失败审计事件同步记录配置/供应商/模型摘要，便于按实际模型解释生成结果；审计仍不写入密钥、请求正文或供应商原始错误。
- [x] 新增来源 schema、API、保存和详情展示回归；后端变更测试独立 `2 passed`，后端非集成全量 `2323 passed`，前端全量 `69 files / 289 tests passed`，类型检查、生产构建、Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地来源追踪与回归完成；真实模型调用、真实项目数据和 N6 全链路权限仍需受控环境复核。

### 2.1.6 N6 失败运行转内部缺陷入口（2026-08-25）

- [x] 后端已支持从 `case`、`suite`、`plan`、`android` 和 `performance` 失败运行创建内部缺陷，并保留脱敏运行证据；本模块补齐 Android 专项报告详情和性能压测详情的用户入口。
- [x] 仅对失败、异常、取消或停止状态展示“一键创建内部缺陷”；通过或进行中的运行不能创建，重复指纹继续复用已有缺陷并增加出现次数。
- [x] 创建后在当前详情页显示已关联缺陷，并可跳转缺陷管理按执行记录过滤；不在前端保存或拼接未脱敏的运行日志、凭据或预签名地址。
- **最小验收出口**：Android/性能详情入口、失败状态限制、重复缺陷提示、缺陷详情跳转和项目权限边界均有前端回归；后端缺陷 API 回归保持通过。
- [x] 性能定向前端/缺陷页 `17 passed`，后端缺陷/静态契约 `14 passed`，前端全量 `69 files / 292 tests passed`，后端非集成全量 `2326 passed`，类型检查、生产构建、Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地实现、测试、独立审查、问题修复、文档同步和提交推送完成；真实项目角色和真实失败运行仍需 N6 环境复核。

### 2.1.7 N9 发布门禁证据索引与一致性校验（进行中）

- [x] 建立脱敏的发布门禁索引，逐项记录状态、证据路径、阻塞原因、依赖、负责人和复验命令；当前滚动索引不写入候选 SHA，最终发布时由命令行绑定实际 SHA。
- [x] 新增 `scripts/validate-release-evidence.py` 和 Make/CI/预提交入口，拒绝非法状态、重复门禁、缺失阻塞元数据、仓库外证据路径和敏感字段；候选 SHA 必须匹配当前 HEAD，严格发布检查还要求工作区干净。
- **最小验收出口**：当前索引可通过校验；缺少任一未关闭门禁的原因/依赖/负责人/复验命令时校验失败；发布工作流执行同一校验脚本。
- [x] 定向校验与发布契约 `22 passed`，后端非集成全量 `2333 passed`，Ruff/格式/差异检查通过；Windows 无 `make` 时已按 Makefile 等价命令复核。
- **状态**：`[E]` 本地索引、测试、独立审查、问题修复、文档同步和提交推送完成；真实 N4-N8 门禁仍需目标环境复核，N9 整体保持 `[~]`。

### 2.1.8 N9.2 发布文档同步一致性契约（本地完成，待环境验收）

- [x] 将开发计划、`Task.md`、`MEMORY.md`、路线图、发布状态和发布清单的关键标记登记到发布索引，并由同一校验器检查路径存在和内容同步。
- [x] 缺少任一文档、关键模块标记或发布索引链接时，发布校验必须失败，避免只更新代码而遗漏计划/记忆/发布边界。
- **最小验收出口**：当前六份文档均通过标记校验；破坏任一标记的回归测试能稳定失败；CI 继续执行同一校验入口。
- [x] 定向校验与发布契约 `23 passed`，后端非集成全量 `2334 passed`，文档路径/标记、Ruff、格式和差异检查通过。
- **状态**：`[E]` 本地文档同步契约、测试、独立审查、问题修复、文档同步和提交推送完成；真实 N4-N8 门禁仍需目标环境复核。

## 2.0 参考导航对齐开发计划（当前跟踪版）

本版本将参考导航固化为产品级工作台边界：高频能力直接从对应工作台进入，系统管理只保留基础设施、配置和治理入口；设备、APK、Mock、数据集、Web/API 资产等页面继续保留原 URL，通过所属工作台或配置中心进入。后续每个阶段都按“实现/调整 → 定向测试 → 受影响全量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → 提交推送”闭环。

## 2.0.0 本次计划登记与当前执行游标（2026-08-25）

本节是 2.0 计划的最新跟踪快照，优先级覆盖下方早于本节登记的执行顺序描述。参考导航只保留五组产品入口：工作台承接日常协作和任务队列，测试能力承接 API/APP/UI/性能/AI 的配置与执行，测试资产承接用例/套件/计划/缺陷/报告/评审，智能中枢承接 Hermes/需求与用例/知识，系统承接远程诊断、配置、审计和回滚。旧页面继续保留兼容路径，但不再作为“系统管理下全部业务”的主要入口。

| 当前顺序 | 模块 | 本轮目标 | 当前状态与出口 |
| --- | --- | --- | --- |
| 1 | N2 APP 自动化 | 在已通过 Karing 包身份、Worker、低代码和录屏的基础上，完成异常回放、专项任务、Monkey/事件日志、操作时间线、设备日志/媒体和报告详情，再做临时数据清理 | `[x]` Karing 单设备专项与报告/清理闭环已验收；证据见 N2.0.7 |
| 2 | N4 性能测试 | 取得真实 Kubernetes、Prometheus、独立 MinIO 后完成多节点、采样、生命周期、跨主机恢复和清理 | `[-]` 外部环境未提供时保持阻塞，不用 q19 Compose、mock 或跳过项替代 |
| 3 | N5-N8 外部复核 | 复核真实模型、通知/缺陷平台、项目角色、目标部署、权限、脱敏、审计和单资源回滚 | `[E]` 本地实现和回归已完成，真实边界待验收 |
| 4 | N9 发布收口 | 汇总代码、测试、审查、文档、环境证据、回滚边界和剩余阻塞，绑定最终提交 SHA | `[~]` 依赖前置真实环境门禁 |

### 本轮模块交付门禁

1. 先在本计划和 `Task.md` 登记模块范围、依赖、风险和最小验收出口。
2. 完成代码或配置后运行定向测试、受影响全量测试和必要的真实环境验证。
3. 独立检查未提交差异；对每个可操作问题完成修复并重跑受影响门禁。
4. 同步 `Task.md`、`MEMORY.md`、路线图、发布状态及必要的操作手册/证据索引。
5. 用 Conventional Commit 提交并推送，下一模块开始前确认本地与远端 SHA 一致。

未满足真实环境条件的模块只能标记为 `[E]`、`[~]` 或 `[-]`，不能因为入口已显示或本地测试通过而标记为真实闭环完成。

### 2.0.1 目标导航

| 分组 | 入口 | 产品职责 | 需要避免的问题 |
| --- | --- | --- | --- |
| 工作台 | 首页、我的待办、项目中心、任务中心 | 统一项目上下文、聚合待办、查看任务队列和执行反馈 | 用户需要在多个系统页面之间寻找任务状态 |
| 测试能力 | 接口测试、APP 自动化、UI 自动化、性能测试、AI 智能测试 | 从配置、用例选择、执行、过程观察到报告/证据的测试工作台 | 只提供配置页面，没有过程和结果闭环 |
| 测试资产 | 测试用例、测试套件、测试计划、缺陷管理、测试报告、用例评审 | 管理可复用资产，串联运行、失败证据、缺陷和评审 | 运行结果无法追溯到用例、套件、计划和缺陷 |
| 智能中枢 | Hermes 助手、需求与用例生成、知识中枢 | 查询、生成、需求追踪和知识检索，结果可编辑且有来源 | AI 结果静默写入业务数据或无法解释来源 |
| 系统 | 远程工具箱、配置中心 | 依赖诊断、配置版本/差异、审计、回滚和权限治理 | 将业务测试入口全部堆在系统管理下面 |

### 2.0.2 分阶段开发台账

| 阶段 | 开发范围 | 本阶段交付 | 最小验收出口 | 状态 |
| --- | --- | --- | --- | --- |
| N0 | 导航壳与工作台 | 五组侧栏、折叠/刷新/窄屏、深链选中、面包屑、项目上下文和权限入口 | 五组入口可达；刷新和深链不丢上下文；无权限入口不展示 | `[E]` 本地完成，真实账号复核持续维护 |
| N1 | 接口测试 | HTTP、会话复用、环境变量、OpenAPI/Postman、GraphQL、WebSocket、gRPC、报告导出 | 请求、断言、提取、依赖、报告和清理均可追踪 | `[E]` q19 受控目标已通过，生产协议服务独立跟踪 |
| N2 | APP 自动化 | Windows Agent/ADB、设备池、APK 包名、低代码、录屏、专项任务和报告 | Karing 真实 APK 在单设备完成执行、事件、日志、媒体、报告和清理 | `[x]` Karing 单设备真实闭环已验收；真实多设备/兼容性矩阵仍属后续能力 |
| N3 | UI 自动化 | Playwright 录制、元素库、页面对象、视觉基线、Trace/HAR、浏览器矩阵 | Chromium/Firefox/WebKit 均可录制、回放并查看失败证据 | `[E]` 本地/q19 证据已具备，随 Windows 复核 |
| N4 | 性能测试 | 压测模型、节点/副本预检、采样、趋势、基线、报告、保留清理和恢复 | 真实多节点短压、取消、采样、生命周期和跨主机恢复均有证据 | `[~]` 本地入口完成，真实 Kubernetes/Prometheus/独立 MinIO 待验收 |
| N5 | AI 智能测试 | 三方模型、多模态/思考参数、用例/数据集/Mock 草稿生成、诊断和审计 | 结果可编辑、有来源、有权限和限额；失败明确且不泄露密钥 | `[E]` 本地完成，真实模型和项目数据待验收 |
| N6 | 测试资产 | 用例、套件、计划、缺陷、报告、评审之间的关联、追踪和审计 | 失败运行可追到证据/缺陷/评审，套件编排入口可达，项目权限隔离有效 | `[E]` 本地完成，真实项目和外部平台待复核 |
| N7 | 智能中枢 | Hermes、需求与用例生成、知识检索和来源展示 | 查询/生成结果可编辑并带来源，不静默改变业务数据 | `[E]` 本地完成，真实模型、需求和知识数据待验收 |
| N8 | 系统 | 远程工具箱、配置中心、依赖诊断、脱敏、审计和单资源回滚 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断可解释，回滚精确可审计 | `[E]` 本地完成，目标部署和密钥边界待复核 |
| N9 | 发布收口 | 能力矩阵、证据索引、操作手册、回滚边界和发布状态 | 每个未关闭门禁都有原因、依赖、负责人和复验命令 | `[~]` 依赖 N2、N4 和真实外部服务 |

### 2.0.3 当前执行顺序

1. **N2 Karing 单设备闭环**：包名和启动入口、Worker 前置、低代码/录屏、稳定性/Monkey、性能/流畅度专项、事件/日志/报告详情、下载与清理均已通过；下一步转入 N4 真实性能环境门禁。如需要 APK 上传/下载链路，必须另取得同一版本 APK，不能用显示名替代包名。
2. **N4 真实性能环境门禁**：在 N2 可验证项完成后，对真实 Kubernetes、Prometheus 和独立 MinIO 逐项执行多节点/副本、资源采样、生命周期、跨主机恢复和清理验收；缺目标时保持待验收，不以 q19 Compose、mock 或跳过项替代。
3. **N5-N8 外部依赖复核**：依次复核真实模型、通知/缺陷平台、项目角色数据、目标部署、权限、脱敏、审计和回滚；凭据只通过受控环境注入。
4. **N9 发布收口**：绑定最终提交 SHA，汇总测试输出、审查记录、环境证据和剩余阻塞，形成可复核结论。

### 2.0.4 跟踪规则

- `[x]` 仅表示代码/配置、测试、代码审查、问题修复和文档同步均完成。
- `[E]` 表示本地实现和回归完成，但仍缺真实设备、协议服务、模型、外部平台或目标部署证据。
- `[~]` 表示仍有实现、联调或环境验收工作；`[-]` 表示被明确外部条件阻塞，并必须记录解除条件。
- mock、协议桩、页面可打开、Worker 心跳和跳过项不能替代真实业务证据；敏感配置、测试数据和外部凭据不得写入代码、日志或证据文件。
- 每完成一个阶段，必须同步 `Task.md`、`MEMORY.md`、路线图和发布状态，并在下一阶段开始前完成提交和推送。

### 2.0.5 N2 Karing 真机包名与 Worker 前置验收（2026-08-25）

- [x] 在明确目标设备 `172.16.102.91:5555` 上以设备包管理确认 `com.nebula.karing` 已安装，解析到 `com.nebula.karing/.MainActivity`；设备为 Android 14 / SDK 34，未保存 APK 内容或日志正文。
- [x] Windows Android Worker doctor、Backend 登录、PostgreSQL/Redis/MinIO readiness、Worker registry 和 Android 设备扫描通过；扫描返回 3 台在线设备。脱敏证据见 [`android-karing-acceptance-2026-08-25.json`](evidence/android-karing-acceptance-2026-08-25.json) 和 [`windows-android-karing-worker-2026-08-25.json`](evidence/windows-android-karing-worker-2026-08-25.json)。
- [x] 以 `172.16.102.91:5555` 和 `com.nebula.karing` 创建可清理的已审批 Android 低代码用例，完成启动/等待/截图等无破坏动作；`run 27` 的 3/3 步骤、3 张截图和 2 个 Android 产物通过，临时项目已清理。
- [x] 录屏门禁已补强：`windows-local-smoke.ps1` 新增 `-RequireAndroidRecording`，只有 `result_summary.android_artifacts.screen_recording` 存在才算录屏通过；真实 `run 29` 为 `passed`，3/3 步骤、3 张截图、3 个产物且 `recording=True`，临时项目已清理。脱敏证据见 [`android-karing-lowcode-2026-08-25.json`](evidence/android-karing-lowcode-2026-08-25.json) 和 [`android-karing-recording-gate-2026-08-25.json`](evidence/android-karing-recording-gate-2026-08-25.json)。
- [x] 已完成异常回放、性能/稳定性/流畅度专项任务、事件/日志/报告详情、下载和对象清理；真实运行记录只保存脱敏摘要。
- **状态**：`[x]` Karing 包身份、Windows Worker、低代码、截图/录屏、专项任务、事件/日志/报告和临时清理门禁已通过。

## 2.0.6 N2 Karing 单设备稳定性专项与事件时间线验收（2026-08-25）

本轮关闭 N2 的稳定性/Monkey 子模块，并修复真实 Worker 暴露的两类事件写入问题：Monkey 输出消费任务与执行任务并发写入同一个 `AsyncSession` 时，事件提交会重叠；调度层与专项执行器各自创建记录器时，事件序号会重复。现在事件记录器对同一事件循环使用写锁，调度层把同一个记录器传给性能、稳定性、流畅度执行器和产物收尾路径，保证事件序号唯一且按时间线可回放。

- [x] 通过 q19 受控依赖的 Windows Android Worker，以设备 `153 / 172.16.102.91:5555` 和包名 `com.nebula.karing` 执行稳定性专项；运行 `6`、回放运行 `7` 均为 `completed`，回放保留随机种子 `20260825`。
- [x] 运行 `7` 回传 78 条事件，最后序号为 78，重复序号分组为 0；包含 Monkey 启动、37 条 Monkey 日志、25 条 Monkey 动作、进度、Crash、完成和产物事件。
- [x] 运行 `7` 生成 1 条 Crash 记录、raw log 和 screenshot 两类产物；JSON 报告导出和两个产物短期 URL 均返回 200。
- [x] 临时项目 `50` 删除返回 204，删除后查询为 404，匹配项目数为 0；未在仓库、文档或证据中写入凭据、预签名 URL 或原始 logcat。
- [x] 代码审查发现的独立记录器序号重复问题已修复；定向回归 82 项，后端非集成全量 2306 项，Ruff、格式检查和 `git diff --check` 通过。
- **证据**：脱敏记录见 [`android-karing-special-task-2026-08-25.json`](evidence/android-karing-special-task-2026-08-25.json)。
- **状态**：`[x]` 稳定性/Monkey、事件时间线、Crash、设备日志/截图、报告导出和清理已闭环；性能与流畅度结果在 N2.0.7 补齐。
- **下一入口**：转入 N4 真实性能环境；本地 q19 Compose 单节点结果不能替代 Kubernetes/Prometheus/独立 MinIO 门禁。

## 2.0.7 N2 Karing 性能与流畅度专项真实闭环（2026-08-25）

本轮在同一 Windows Android Worker、同一设备 `153 / 172.16.102.91:5555` 和包名 `com.nebula.karing` 上完成性能与流畅度专项，发现并修复两类 Android 14 兼容问题：部分设备的包级 `dumpsys meminfo` 只有标题，性能采样增加 `/proc/<pid>/status` 的 `VmRSS` 兜底；`gfxinfo framestats` 使用 `Total frames` 与 `HISTOGRAM` 的等号格式，解析器改为大小写不敏感并排除 `GPU HISTOGRAM`，避免 FPS 样本为空或混入 GPU 时间。

- [x] 性能运行 `10` 为 `completed`，采集 18 个样本：CPU、`mem_mb`、电量、温度、FPS 和卡顿各 3 条；平均 CPU `34.0%`、平均内存 `346.98 MB`、峰值内存 `350.23 MB`，Crash/ANR 均为 0，事件 12 条且重复序号分组为 0。
- [x] 流畅度运行 `13` 为 `completed`，执行 2 个阶段（滑动、点击），采集 2 个 FPS 样本，平均 FPS `105.26`、峰值 `157.89`、卡顿总数 1，事件 15 条且重复序号分组为 0。
- [x] 两个运行的 JSON 报告导出均返回 HTTP 200；临时项目 `51` 删除返回 204，删除后查询为 404。脱敏证据见 [`android-karing-performance-fluency-2026-08-25.json`](evidence/android-karing-performance-fluency-2026-08-25.json)。
- [x] 代码审查发现并修复 Android 14 内存兜底和 `gfxinfo` 直方图解析问题；相关定向回归 `60 passed`，Ruff 通过；随后重启 Worker 并完成真实复验。
- **状态**：`[x]` N2 Karing 单设备专项、事件/报告下载和临时数据清理闭环完成；N4 真实性能环境仍因缺 Kubernetes/Prometheus/独立 MinIO 保持 `[-]`。

## 2.1 Android 控件属性获取诊断（2026-08-25）

本模块针对 Android 可视化录制中“点击后只能看到坐标、无法判断是否为权限问题”的反馈，补齐 UIAutomator 获取链路的可解释状态。API 进程和 Windows Android Worker 现在都会返回 `found`、`not_found` 或 `unavailable` 状态，并只返回稳定诊断码，不回传 ADB 原始错误；录制界面在设备侧或 Worker 不可用时提示检查设备解锁、UIAutomator、Worker 和权限，同时继续保存坐标步骤，单纯未命中语义控件时保持静默坐标回退。

- **代码范围**：`backend/app/api/v1/device_mirror.py`、`backend/app/worker/tasks_device.py`、`frontend/src/api/index.ts`、`frontend/src/components/common/AndroidStepEditor.vue`、Android 录制诊断工具和中英文文案。
- **回归范围**：后端控件镜像/设备 Worker 定向 `22 passed`；前端录制相关定向 `23 passed`，前端全量 `69 files / 284 tests passed`；后端非集成全量 `2305 passed`；`vue-tsc`、生产构建、Ruff、格式检查和 `git diff --check` 通过。
- **代码审查与修复**：审查发现旧 Worker 未返回 `diagnostic` 时 API 不应新增 `diagnostic: null`，已改为仅在有诊断时返回字段并补兼容回归；未发现权限绕过、原始错误泄露或坐标回退回归。
- **状态**：`[E]` 本地实现、测试、审查和修复完成；真实 Karing 页面、Windows Worker 上的 UIAutomator 权限和实际控件属性回传仍待 N2 真机门禁，不以系统设置探针替代。

## 2.2 测试套件导航归位（2026-08-25）

本模块修复测试套件已经存在路由和页面，却没有进入参考导航“测试资产”侧栏的问题。`/suites` 现在作为独立的“测试套件”入口展示，保留原 URL；深层路径会继续选中测试套件而不是错误选中测试计划，路由补齐统一的菜单标题和能力描述元数据，中英文文案保持一致。

- **代码范围**：`frontend/src/layouts/MainLayout.vue`、`frontend/src/layouts/navigation.ts`、`frontend/src/router/index.ts`、测试资产中英文文案和导航回归。
- **最小验收出口**：侧栏可打开测试套件；`/suites` 与 `/suites/:id` 深链选中 `/suites`；面包屑为“测试资产 → 测试套件”；旧 URL 和套件页面能力不改变。
- **回归范围**：导航定向 `8 passed`，前端全量 `69 files / 285 tests passed`，类型检查、生产构建和 `git diff --check` 通过。
- **代码审查**：独立检查确认没有覆盖测试计划选中逻辑、没有新增重复路由，旧 URL 仍可用；未发现可操作问题。
- **状态**：`[E]` 导航和本地回归完成；真实账号下的权限/项目数据复核随 N0/N6 环境验收维护。

## 2.3 工作台运行记录入口收敛（2026-08-25）

本模块让工作台侧栏与参考导航保持一致：工作台只展示首页、我的待办、项目中心和任务中心，不再额外展示“执行记录”入口。运行列表和运行详情的旧 `/runs`、`/runs/:id` 地址继续保留，任务中心和其他页面的内部跳转不受影响；访问旧地址时侧栏自动选中任务中心，避免出现“页面可打开但没有导航归属”。

- **代码范围**：`frontend/src/layouts/MainLayout.vue`、`frontend/src/layouts/navigation.ts` 和导航回归。
- **最小验收出口**：工作台侧栏只保留参考导航四项；`/runs` 与 `/runs/:id` 旧地址仍可访问并选中 `/tasks`；运行详情面包屑仍显示“工作台 → 执行记录”。
- **回归范围**：导航定向 `9 passed`，前端全量 `69 files / 286 tests passed`，类型检查、生产构建和 `git diff --check` 通过。
- **代码审查与修复**：首次审查发现直接访问 `/runs`（无尾部路径）未被映射，已补齐 `/runs` 与 `/runs/:id` 两种旧地址的回归；修复后未发现其他可操作问题。
- **状态**：`[E]` 本地导航交付完成；运行数据、任务权限和真实账号复核仍按 N0/N6 环境验收维护。

## 1.1 Android 专项应用启动兼容交付（2026-08-25）

本模块作为 N2 Karing 真机门禁前的本地补强，解决 Android 专项执行器把入口固定为 `.MainActivity` 导致真实 APK 无法启动的问题。性能、稳定性和流畅度执行器现在共用 Android 启动辅助：明确填写 Activity 时使用 `am start -n`，留空时使用 Launcher Intent 自动发现入口；流畅度执行器同时尊重前置操作设置的 `auto_start=false`，避免同一任务重复启动应用。专项任务表单留空启动 Activity 时不再写入 `.MainActivity` 默认值，旧任务中已有的显式 Activity 仍保持兼容。

- **代码范围**：`backend/app/services/mobile_special/preflight.py`、Android 性能/稳定性/流畅度执行器，以及专项任务中英文启动 Activity 提示和默认值。
- **回归范围**：显式 Activity、Launcher 自动发现、启动失败、前置启动后不重复启动均有回归；受影响后端全量 `2295 passed`，四个改动测试文件独立运行 `3/25/19/15 passed`，前端全量 `67 files / 275 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。
- **状态**：`[E]` 本地实现、代码审查和回归完成；真实 Karing APK、Windows Android Worker/ADB、真实启动组件、专项任务媒体和报告仍待环境验收，不使用其他应用替代。
- **下一入口**：先取得 Karing APK 或真实 `package_name`，在在线 Android Worker 上按 APK → 低代码 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 清理执行；N4 Kubernetes/Prometheus/独立 MinIO 仍作为独立外部环境门禁等待目标。

## 1.2 Windows Android 包名与启动入口验收探针（2026-08-25）

为推进 N2 真机门禁，`scripts/windows-android-acceptance.ps1` 现在支持可选 `-LaunchActivity`：指定 `-AppPackage` 后，脚本先确认包已安装，再通过 `cmd package resolve-activity --brief` 校验显式 Activity，未指定时校验 `MAIN/LAUNCHER` 入口。该检查只解析 Package Manager，不启动或修改应用；脱敏报告新增 `app.package`、请求组件和解析组件，仍不保存包内容或日志正文。

- **回归范围**：脚本契约 `2 passed`，脚本目录 `93 passed`，质量/发布文档回归 `15 passed`，PowerShell 语法检查通过。
- **设备验证**：当前在线设备使用 `com.android.settings` 做自动 Launcher 和显式 `.Settings` 两条只读探针，均通过；这不代表 Karing 已安装或关闭 Karing 真机门禁。
- **状态**：`[E]` 本地脚本、文档、回归和设备探针完成；真实 Karing APK/包名、Worker 调度、低代码、录屏/异常回放、专项任务和报告仍待验收。
- **下一入口**：用户提供或上传 Karing APK 后，以 Manifest 包名、设备 `pm path` 和 Activity 解析三重证据确认目标，再执行单设备 Android 闭环。

## 1.3 Android 低代码控件属性录制与坐标回退（2026-08-25）

本模块补齐 Android 可视化录制的“可读定位 + 可执行兜底”链路。点击截图时保留 UIAutomator 返回的文本、resource-id、content-desc、className 和 bounds，同时保存原始屏幕坐标；回放优先按 resource-id、文本、无障碍描述定位，控件属性找不到或 UIAutomator 不可用时回退录制坐标。这样既不会把录制结果退化成只有坐标，也避免页面轻微变化后步骤完全无法执行。

- **代码范围**：`frontend/src/utils/androidRecording.ts`、`frontend/src/components/common/AndroidStepEditor.vue`、`backend/app/worker/executors/android_lowcode_executor.py`。
- **回归范围**：后端 Android 低代码执行器定向 `42 passed`，非集成全量 `2297 passed`；前端录制参数与标准步骤定向 `4 passed`，前端全量 `68 files / 277 tests passed`；`vue-tsc`、生产构建、后端 Ruff、格式检查和 `git diff --check` 均通过。
- **代码审查**：独立检查确认选择器优先级为 resource-id → 文本 → content-desc，坐标仅作为最后回退；未发现可操作问题。
- **状态**：`[E]` 本地实现、回归和审查完成；真实 Karing 仍需在 Windows Android Worker 上验证 UIAutomator 权限、录制控件属性、低代码执行和媒体/报告链路，不能用 `com.android.settings` 探针替代。
- **下一入口**：取得 Karing APK/真实包名后，执行单设备 APK → 控件属性录制 → 低代码回放 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 清理闭环。

## 1.4 Android 低代码长按与输入控件定位（2026-08-25）

本模块修复两个会让低代码步骤“看似保存、执行却不符合操作语义”的问题：长按步骤此前只对坐标执行，文本/resource-id 只会走普通点击；输入步骤此前只按 resource-id 聚焦，且 Python 脚本可能把要输入的内容误当成控件文本。现在长按统一按 resource-id、文本、content-desc 定位后发送同点 swipe 长按，输入将输入内容与目标控件定位分离，支持 `targetText`、resource-id 和 content-desc，目标不存在时明确失败，不会误写当前焦点。

- **代码范围**：`backend/app/worker/executors/android_lowcode_executor.py`、`frontend/src/components/common/AndroidStepEditor.vue`、Android 标准步骤/独立 Python 脚本生成器及中英文文案。
- **回归范围**：后端 Android 低代码定向 `45 passed`，非集成全量 `2300 passed`；前端标准步骤/脚本生成定向 `11 passed`，前端全量 `68 files / 279 tests passed`；`vue-tsc`、生产构建、Ruff、格式检查和 `git diff --check` 均通过。
- **代码审查**：独立检查确认旧坐标步骤仍兼容，长按和输入均复用控件属性优先、明确失败的定位链路；未发现可操作问题。
- **状态**：`[E]` 本地实现、回归和审查完成；真实 Karing APK、Worker UIAutomator 权限及真机长按/输入行为仍待环境验收。
- **下一入口**：保持 N4 真实 Kubernetes/Prometheus/独立 MinIO 门禁等待目标；取得 Karing 后继续单设备完整闭环。

## 1.5 Android 可视化滑动的分辨率适配（2026-08-25）

本模块补齐 Android 可视化录制滑动在不同设备上的坐标稳定性。截图拖动生成的滑动步骤现在保存录制屏幕的宽高；Worker 回放时读取当前设备生效的 `wm size`，按宽高比例缩放并限制坐标范围，方向滑动也优先使用当前屏幕尺寸。无法读取尺寸或历史步骤没有尺寸元数据时保留原有默认坐标和原始坐标行为。独立 Python 脚本同样使用 `device.window_size()` 适配方向滑动和带尺寸元数据的坐标滑动，标准步骤摘要显示录制屏幕尺寸。

- **代码范围**：`frontend/src/utils/androidRecording.ts`、`frontend/src/components/common/AndroidStepEditor.vue`、Android 标准步骤/脚本生成器、中英文文案，以及 `backend/app/worker/executors/android_lowcode_executor.py`。
- **回归范围**：后端 Android 低代码定向 `47 passed`，非集成全量 `2302 passed`；前端录制/标准步骤/脚本生成定向 `16 passed`，前端全量 `68 files / 282 tests passed`；`vue-tsc`、生产构建、Ruff、格式检查和 `git diff --check` 通过。
- **代码审查**：独立检查确认旧步骤无尺寸元数据仍兼容，设备尺寸读取失败时保留旧默认值，动态坐标在当前屏幕范围内裁剪；未发现可操作问题。
- **状态**：`[E]` 本地实现、回归和审查完成；真实 Karing APK、Windows Android Worker、横竖屏切换和不同分辨率真机回放仍待环境验收，不把本地测试替代为真实设备证据。
- **下一入口**：N4 真实 Kubernetes/Prometheus/独立 MinIO 环境门禁仍是主游标；取得 Karing 后，在单设备闭环中验证截图尺寸、方向滑动、跨分辨率滑动、录屏/异常回放和报告证据。

## 1.0 当前计划登记（2026-08-25）

> 本节为 1.0 历史登记；当前执行口径以本文前部的 2.0.5 N2 最新环境跟踪和 2.0.3 执行顺序为准。这里保留当时的阻塞快照，避免改写历史验收记录。

本节记录 1.0 版本当时的执行口径，后续历史交付记录仍按当时顺序保留；当前口径以本文前部 2.0 台账为准。N4 的本地代码链路已经覆盖 Worker/目标服务采样、Kubernetes 容量预检、保留清理、跨端点 MinIO 恢复和生命周期门禁，真实目标仍需单独验收。

### 下一阶段顺序

1. **N4 性能生产环境验收**：先用真实 Kubernetes 目标执行多节点、Worker 副本和资源门禁；再用独立 MinIO 目标执行复制、回源、生命周期和清理；最后用真实 Prometheus 验证 Worker 与目标服务指标来源、查询失败记录和报告时间线。没有对应目标时保持“待环境验收”，不得用 q19 Compose 或 mock 替代。
2. **N2 Karing Android 单设备闭环**：用户提供/上传 Karing APK 后，以 `pm list packages` 和 Manifest 双重确认 `package_name`，再执行 APK 下载、低代码点击/滑动、录屏/异常回放、专项任务、事件/日志/报告和清理；在真实包确认前不使用其他应用替代。
3. **N5-N8 外部依赖复核**：按真实三方模型、通知供应商、外部缺陷平台、项目/角色数据和目标部署顺序验收；凭据只通过环境变量或临时部署注入，测试数据完成后清理。
4. **N9 发布收口**：绑定最终提交 SHA，整理能力矩阵、测试输出、代码审查记录、环境证据、操作手册、回滚边界和未关闭门禁，形成可复核的发布结论。

### 下一项模块登记：N4 真实性能环境门禁

| 项目 | 内容 |
| --- | --- |
| 范围 | Kubernetes 多节点/副本/Worker 资源预检、Worker/目标服务指标采样、MinIO 生命周期与跨端点恢复、运行指标/报告和临时对象清理 |
| 已有入口 | `scripts/performance-environment-smoke.py`、`scripts/minio-dr-acceptance.py`、`make minio-dr-acceptance`、`--require-metric-source` |
| 依赖 | 可控 Kubernetes 集群、独立 MinIO 源/目标端点、Prometheus 地址及最小权限凭据 |
| 最小验收出口 | 多节点短压成功；容量不足/资源缺失明确失败；至少得到 `performance-worker` 和 `target-service-prometheus` 非空样本；MinIO 复制/回源 SHA-256 一致；生命周期规则命中；临时对象清理为零；证据不含凭据 |
| 当前状态 | `[E]` 本地实现与回归完成，真实环境缺失，暂不关闭 N4 发布门禁 |
| 复验命令 | `make performance-environment-smoke`；`make minio-dr-acceptance`；按目标配置追加 `--min-ready-nodes`、`--min-worker-replicas`、`--require-worker-resources` 和 `--require-metric-source` |

### 统一交付门禁

下一项模块仍必须按“实现/调整 → 定向回归 → 受影响全量质量门禁 → 独立代码审查 → 修复 → 同步 `Task.md`、路线图、发布状态和 `MEMORY.md` → Conventional Commit 提交并推送”执行。外部目标缺失时，只记录可复用入口和阻塞证据，不把跳过项标为通过。

## 0.9 当前开发计划登记（2026-08-25）

本节是当前执行口径，优先级高于本文后面的历史交付记录。产品导航按参考方案保持五组：工作台、测试能力、测试资产、智能中枢、系统；设备、APK、专项任务、Mock、数据集、Web/API 资产和平台治理页面保留兼容 URL，但从所属工作台或配置中心进入，不再全部堆在系统管理下。

### 当前阶段台账

| 阶段 | 导航模块 | 当前目标 | 状态 | 进入下一阶段的条件 |
| --- | --- | --- | --- | --- |
| N0 | 工作台 | 稳定首页、待办、项目中心、任务中心的项目上下文、深链、权限和任务事件 | `[E]` | 真实账号复核刷新、窄屏、角色和任务状态 |
| N1 | 接口测试 | 受控 GraphQL、WebSocket、流式 gRPC 和 HTML/JUnit/PDF 完整报告闭环已完成 | `[E]` | 协议创建/执行/断言/提取/报告/清理均有脱敏证据 |
| N2 | APP 自动化 | 等待 Karing 真实 APK/包名，完成单设备执行、录屏、专项任务和结果回传 | `[-]` | 设备包管理确认包名，且低代码、专项、媒体、报告和清理通过 |
| N3 | UI 自动化 | 维护 Playwright 录制、回放、元素/页面对象、Trace/HAR 和浏览器矩阵 | `[E]` | Chromium、Firefox、WebKit 的失败证据可追踪 |
| N4 | 性能测试 | Worker/目标服务采样、Kubernetes 多节点/副本/Worker 资源预检、保留清理和跨端点 MinIO 复制/恢复 smoke 已完成 | `[E]` | 多节点容量、取消、采样、报告、生命周期和恢复演练有真实环境证据 |
| N5-N8 | AI、测试资产、智能中枢、系统 | 以真实项目、模型、角色和目标部署复核本地能力 | `[E]` | 来源、权限、脱敏、审计和回滚均可复核 |
| N9 | 发布收口 | 汇总代码 SHA、测试、证据、操作手册和剩余阻塞 | `[~]` | 所有未关闭门禁都有负责人、原因和复验命令 |

### 当前执行顺序

1. **N4 性能真实环境**：本地代码入口已齐；下一步只做真实 Kubernetes、Prometheus、MinIO 目标验收，验证多节点调度、资源采样、生命周期、保留清理和跨主机恢复。
2. **N2 Android Karing 单设备门禁（阻塞但不阻塞 N4）**：用户提供或上传 Karing APK 后，以 `pm list packages` 和 Manifest 解析结果确认真实 `package_name`，再按 APK → 低代码 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 下载/清理执行。
3. **N5-N8 外部依赖复核**：在 N4 不具备生产目标时，继续验证真实模型、通知、外部缺陷平台、项目数据、权限、审计和配置回滚。
4. **N5-N8 外部依赖复核**：依次验证真实 AI 模型、通知供应商、外部缺陷平台、项目数据、权限、审计和配置回滚。
5. **N9 发布收口**：生成最终能力矩阵和证据索引；未通过项保持“待环境验收”，不得用 mock、跳过项或页面可打开替代。

### 统一模块交付门禁

每完成一个模块，必须依次完成：实现/调整 → 定向回归 → 受影响全量质量门禁 → 独立代码审查 → 修复审查问题 → 同步 `Task.md`、路线图、发布状态和 `MEMORY.md` → Conventional Commit 提交并推送。只有完成这一闭环，才允许把模块状态从 `[~]` 改为 `[x]` 或 `[E]`。

### 0.9.2 N1 受控协议目标交付

- **实现范围**：`acceptance-target` 增加 GraphQL POST、WebSocket 握手/文本回显；目标测试覆盖 gRPC Unary、Server Streaming、Client Streaming 和 Bidi Streaming。
- **真实证据**：q19 GraphQL run `19`、WebSocket run `20`、gRPC Server Streaming run `23`、Client Streaming run `24`、Bidi Streaming run `25` 全部通过，临时项目清理后同名项目匹配数为 `0`。脱敏证据见 [`evidence/api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)。
- **质量门禁**：目标/部署契约和协议执行器回归 `90 passed`，后端非集成全量 `2288 passed`，Ruff、格式检查、`git diff --check` 和独立代码审查通过；代码提交 `5b07a3e` 已推送。
- **边界**：本项不关闭完整报告导出/详情治理、生产协议服务或外部环境门禁，下一入口为 N1 完整报告闭环。

### 0.9.3 N1 完整报告闭环交付

- **实现范围**：运行详情页新增 JUnit XML 导出，HTML/PDF/JUnit 三种报告格式均可从详情页下载；既有步骤、截图、录像、设备矩阵和错误证据继续由详情/HTML 报告承载。
- **真实证据**：q19 临时项目 `42`、用例 `27`、运行 `26` 通过；详情 `200`，HTML `200/2561 bytes`、JUnit XML `200/220 bytes` 且可解析、PDF `200/167056 bytes`；删除临时项目后匹配数 `0`。脱敏证据见 [`evidence/report-closure-2026-08-25.json`](evidence/report-closure-2026-08-25.json)。
- **质量门禁**：前端定向 `11 passed`、后端报告/导出 `24 passed`、前端全量 `67 files / 275 tests passed`，类型检查、生产构建、`git diff --check` 和独立代码审查通过；代码提交 `86f3bf7` 已完成。
- **边界**：本项关闭 q19 受控报告详情/导出证据；生产协议服务、生产对象存储和外部发布环境仍保持待验收，下一入口为 N4 性能真实环境。

### 0.9.4 N4 Kubernetes 性能容量预检

- **实现范围**：扩展 `scripts/performance-environment-smoke.py` 的 Kubernetes 检查，可选验证可调度 Ready 节点数、性能 Worker Deployment 的 desired/available 副本数，以及指定 Worker 容器的 CPU/内存 `resources.requests/limits`。
- **使用方式**：在真实集群验收时追加 `--min-ready-nodes`、`--min-worker-replicas` 和 `--require-worker-resources`；默认不启用，既有 Deployment/Pod smoke 行为保持兼容。
- **质量门禁**：脚本回归 `29 passed`，Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- **边界**：当前 Linux 目标只有 Docker Compose、没有 Kubernetes 集群，本项只关闭预检实现和本地回归，不关闭真实多节点、生产 Prometheus/MinIO 生命周期或跨主机恢复。

### 0.9.5 N4 跨端点 MinIO 恢复验收入口

- **实现范围**：新增 `scripts/minio-dr-acceptance.py`，从 `ATP_MINIO_DR_SOURCE_*` 与 `ATP_MINIO_DR_TARGET_*` 读取两端连接信息，验证源端探针回读、目标端复制/回读、恢复回源和 SHA-256 一致性，并在结束时清理唯一前缀下的临时对象。
- **生命周期门禁**：默认审计两端规则数量；通过重复参数 `--require-lifecycle-rule PREFIX=DAYS` 时，要求两端均存在 `Enabled`、前缀和过期天数完全匹配的规则。报告只包含端点、桶、规则要求和摘要，不包含账号、密钥或对象内容。
- **质量门禁**：脚本回归 `3 passed`；质量门禁一致性和灾备文档回归 `17 passed`，Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- **边界**：当前 `172.31.27.133` 没有独立 MinIO 灾备端点，因此本项只关闭验收入口和本地回归；真实跨主机恢复、生产生命周期和长期保留仍待目标环境。

## 1. 目标导航

产品导航按五组组织，侧栏只承担高频入口；设备、APK、专项任务、Mock、数据集、Web/API 资产和治理页面保留兼容 URL，但从所属工作台或配置中心进入。

| 导航分组 | 入口 | 主要职责 |
| --- | --- | --- |
| 工作台 | 首页、我的待办、项目中心、任务中心 | 统一项目上下文、待办聚合、任务队列和操作反馈 |
| 测试能力 | 接口测试、APP 自动化、UI 自动化、性能测试、AI 智能测试 | 完成配置、执行、过程观察、报告和证据闭环 |
| 测试资产 | 测试用例、测试计划、缺陷管理、测试报告、用例评审 | 管理可复用资产，串联运行、失败证据、缺陷和评审 |
| 智能中枢 | Hermes 助手、需求与用例生成、知识中枢 | 提供可追溯查询、草稿生成、需求追踪和知识检索 |
| 系统 | 远程工具箱、配置中心 | 依赖诊断、配置版本/差异、审计和精确回滚 |

## 2. 状态口径

- `[x]` 已完成：代码、测试、审查、修复和文档均已完成，并且本地质量门禁通过。
- `[E]` 已实现待环境验收：本地实现和回归已完成，但还缺真实设备、协议服务、模型、外部平台或目标部署证据。
- `[~]` 进行中：仍有代码、联调或验收工作，不能作为发布通过。
- `[ ]` 未开始：尚未进入实施。
- `[-]` 阻塞/暂缓：需要外部条件或用户提供信息；必须写明解除条件。

`[E]` 不等同于生产通过；mock、协议桩、跳过项、Worker 心跳和页面可打开都不能替代真实业务证据。

## 3. 当前模块台账

| 顺序 | 模块 | 已完成 | 当前剩余工作 | 最小验收出口 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 0 | 导航壳与信息架构 | 五组侧栏、深层路由选中、旧 URL 映射、面包屑和权限入口 | 用当前账号补刷新、窄屏、角色和项目上下文复核 | 五组入口可达；刷新/深链不丢上下文；权限隐藏一致 | `[E]` |
| 1 | 工作台与任务中心 | 项目筛选、待办聚合、轮询、重试、终止、批量操作和失败事件 | 用真实项目数据复核五类任务及越权操作 | 任务状态、失败原因、操作事件可追踪 | `[E]` |
| 2 | API 测试工作台 | 环境变量、认证复用、OpenAPI/Postman、HTTP/GraphQL/WebSocket/gRPC、断言/提取/依赖 | q19 已通过 HTTP、会话复用、gRPC TLS Unary、GraphQL、WebSocket、三种流式 gRPC、HTML/JUnit/PDF 报告以及 OpenAPI/Postman 导入预览/落库/回读/清理；协议用例已在保存和派发两层拒绝无效/空步骤 | 请求、断言、变量传递、报告和权限边界完整 | `[E]` |
| 3 | APP 自动化工作台 | Windows Android Worker 配对、扫描、租约、截图/控件、APK 上传与包名解析、通用 APK 低代码录屏和设备产物 | Karing APK/真实包名、专项任务、APK 下载、完整报告和异常回放验收 | 单设备真实 APK 执行；事件、日志、媒体、报告和清理可追踪 | `[~]` |
| 4 | UI 自动化工作台 | Playwright 录制、元素库、页面对象、视觉基线、Trace/HAR、网络/Console 日志、多浏览器 | 用最新 Windows 运行档案复核录制和回放失败证据 | Chromium/Firefox/WebKit 可录制、执行和定位失败 | `[E]` |
| 5 | 性能测试工作台 | 本地压测模型、采样、趋势、基线、报告、保留清理和 q19 短压 | 真实多节点、容量限制、Prometheus/MinIO 生命周期、跨主机恢复 | 真实节点完成短压、取消、采样、报告和恢复演练 | `[~]` |
| 6 | AI 智能测试与 Hermes | 三方模型配置、模型拉取、多模态/思考参数、用例/数据/Mock 草稿生成、调用审计 | 配置可用真实模型，验证来源、限额、失败诊断和敏感值脱敏 | 生成结果可编辑、有来源；无权限/无模型时明确失败 | `[E]` |
| 7 | 测试资产与智能中枢 | 用例—计划—运行—报告—缺陷—评审关联，需求追踪和知识检索本地闭环 | 用真实项目数据复核权限和外部缺陷映射 | 失败运行可追到证据/缺陷/评审，知识结果可追溯 | `[E]` |
| 8 | 远程工具箱与配置中心 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断、配置版本/差异、审计、单资源回滚 | 在目标部署复核密钥、角色和回滚 | 输出脱敏；越权拒绝；回滚精确且可审计 | `[E]` |
| 9 | 发布质量收口 | 发布状态、能力矩阵、证据索引、操作手册和回滚边界 | 绑定最终提交 SHA，关闭或明确所有环境门禁 | 文档、证据、代码 SHA 和未完成项一致 | `[~]` |

## 4. 本轮开发顺序

### 4.1 P0：先关闭当前可验证链路

1. **API 真实协议目标** `[~]`：q19 受控目标已完成临时 API 用例创建、评审审批、HTTP 请求、状态码断言、JSONPath 提取、显式会话复用、gRPC TLS Unary、GraphQL、WebSocket、三种流式 gRPC、OpenAPI/Postman 解析、导入预览/落库/回读/清理、终态查询和清理。证据见 [`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json) 和 [`api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)。完整报告仍保持环境验收项。
2. **Android 单设备闭环**：取得 Karing APK 或真实 `package_name`，按“APK 下载 → 低代码 → 录屏 → 性能/稳定性/流畅度专项 → 事件/日志/报告 → 下载与清理”顺序执行；没有真实包时保持阻塞，不使用其他应用冒充 Karing。
3. **Windows API/Web 复核**：在 Android 阶段不阻塞的同时，用当前有效账号复跑认证、依赖、文件传输、Web 低代码、报告导出和浏览器矩阵，保留脱敏 JSON 证据。

### 4.2 P1：再补真实外部能力

4. **通知供应商**：使用临时 SMTP/企业微信/钉钉目标验证投递、重试、限流、回执和错误脱敏，结束后清理凭据和测试数据。
5. **外部缺陷平台**：使用临时 Jira/禅道/GitHub/GitLab 项目验证创建、去重、状态同步、权限和清理；没有凭据时只维护本地适配器。
6. **性能生产环境**：验证多节点调度、容量拒绝、资源采样、Prometheus/MinIO 生命周期、长期趋势和跨主机恢复；没有 Kubernetes/Prometheus 目标时不关闭门禁。
7. **发布收口**：把同一提交 SHA、测试结果、代码审查记录、环境证据、操作手册和回滚边界汇总到发布状态文档。

## 5. 每个模块的强制交付流程

每个模块都必须按以下顺序执行，不能只修改页面就标记完成：

1. 在本文和 `Task.md` 登记范围、依赖、风险和最小验收出口。
2. 实现或调整代码，补充对应的回归测试；敏感配置只通过环境变量或临时部署注入。
3. 运行定向测试，再运行受影响的全量质量门禁。
4. 独立检查未提交 diff，进行代码审查；发现问题先修复，再重跑门禁。
5. 更新 `Task.md`、`MEMORY.md`、路线图、发布状态和必要的操作手册/证据索引。
6. 使用 Conventional Commit 提交并推送；推送后记录提交 SHA 和验证结果。

## 6. 当前风险与解除条件

| 风险 | 影响 | 解除条件 |
| --- | --- | --- |
| Karing APK/包名未在当前设备确认 | APP 专项任务、应用级动作和完整报告不能验收 | 提供或上传 Karing APK，并以 `pm list packages`/解析结果确认包名 |
| 生产协议服务和发布环境未形成真实证据 | API 工作台只能维持“受控目标已验收、生产环境待验收” | 提供生产协议服务、对象存储和发布窗口，复跑协议/报告/清理证据 |
| 通知、外部缺陷平台无目标凭据 | 不能声称真实投递或外部同步通过 | 提供临时目标和最小权限凭据，且不写入仓库 |
| 生产性能环境未提供 | 多节点、跨主机恢复和生产监控保持待验收 | 提供可控 Kubernetes/Prometheus/MinIO 目标及回滚窗口 |

## 7. 更新记录

- 2026-08-25：登记 1.0 当前执行计划：N4 本地性能采样、Kubernetes 容量预检、MinIO 跨端点恢复和生命周期门禁代码已齐，下一步转为真实目标验收；N2 Karing、N5-N8 外部依赖和 N9 发布收口按依赖顺序跟踪。
- 2026-08-25：API 工作台在 q19 受控 HTTP 目标完成真实创建/审批/执行/状态码断言/JSONPath 提取/清理，定向执行器回归 `77 passed`；证据见 [`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)。
- 2026-08-25：API 工作台显式 `session_lifecycle=reuse` 的两步登录/当前用户场景通过，登录请求体密码在执行证据中脱敏，临时项目清理成功；证据见 [`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)。
- 2026-08-25：补齐 API gRPC TLS 自签名/私有 CA 支持：用例可配置公有 PEM 根证书和 SNI 服务名，执行器拒绝私钥且不把证书写入步骤请求快照；q19 Unary 真实目标通过，临时项目清理成功。证据见 [`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)，代码提交为 `96c7db0`。
- 2026-08-25：加固 OpenAPI/Postman 导入解析：保留 `0/false/空字符串` 示例，解析 Postman 字符串 URL 查询参数，跳过禁用请求头/查询项并支持 urlencoded/formdata 示例；q19 按 `75ed756` 的 `/ai/cases/parse-schema` 真实接口返回 OpenAPI 1 个接口/1 个参数、Postman 1 个接口/3 个参数。证据见 [`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)；导入预览/落库、后续协议和完整报告仍待验收。
- 2026-08-25：完成 API 导入预览/落库闭环并修复异步 SQLAlchemy 懒加载导致的 500：导入读取模块时预加载所属项目，q19 真实完成 OpenAPI 解析（响应码 `201`）→预览 `1/0`→落库 `201`→回读状态断言/步骤结果→项目删除 `204`。定向回归 `42 passed`、后端非集成全量 `2270 passed`，证据见 [`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)，代码提交为 `a8f6e26`；后续只剩其他协议和完整报告验收。
- 2026-08-25：修复 GraphQL/WebSocket/gRPC 空步骤误报通过：派发层在协议执行前拒绝缺失、空数组和 `null` 的 `config.steps`，运行终态为 `error` 并写入可解释原因；API 的旧配置默认主请求兼容不变。派发/HTTP 家族定向 `94 passed`，后端非集成全量 `2279 passed`，前端类型检查、生产构建、Ruff 和差异检查通过；代码审查未发现问题。真实 GraphQL/WebSocket/流式 gRPC 和完整报告目标仍待环境验收。
- 2026-08-25：补齐协议用例保存时校验：创建/更新 GraphQL、WebSocket、gRPC 配置时检查步骤、endpoint/url、消息、target/proto/service/method，失败返回 `422` 且不创建快照/脏用例；与派发层规则保持一致。用例管理定向 `35 passed`，后端非集成全量 `2282 passed`，Ruff、差异检查和代码审查通过。真实协议目标和完整报告仍待环境验收。
- 2026-08-25：补齐报告中心按用例类型统计：后端按当前用户可见项目聚合 API、GraphQL、WebSocket、gRPC、Web、Android 等已完成运行，返回总运行/通过/失败/异常/通过率；前端报告中心增加类型分布、通过率进度条和空态，补齐中英文文案。报告定向回归 `5 passed`、前端报告页 `3 passed`、后端非集成全量 `2282 passed`，`vue-tsc`、生产构建、Ruff 和差异检查通过，代码审查未发现问题。真实多协议目标和完整报告环境证据仍待验收。
- 2026-08-25：修复 Windows smoke 凭据边界：默认只读取当前账号 `ATP_USERNAME/ATP_PASSWORD`，不再自动回退或混用 `FIRST_ADMIN_*`；仅通过显式 `-UseBootstrapCredentials` 才验证全新数据库的初始化账号。补充脚本契约回归和操作手册，避免管理员改密后误报/反复 401；Windows 真实 API/Web smoke 仍需使用当前有效账号复验。
- 2026-08-25：修复报告中心跨用例对比误导：默认从最近记录中选择同一用例的基线/当前运行，切换任一选择器时自动对齐另一侧的同用例记录，并在请求前复核同用例约束；代码审查发现并修复了初版禁用选项造成的选择死锁。报告页回归 `4 passed`，前端全量 `66 files / 270 tests passed`，type-check、生产构建和差异检查通过。
- 2026-08-25：补齐协议用例前端保存校验：抽取 GraphQL、WebSocket、gRPC 的必填项校验纯函数，空字符串/空格和空消息数组在创建/更新请求前直接提示，后端 `422` 继续作为最终防线。工具函数回归 `8 passed`，前端全量 `66 files / 272 tests passed`，`vue-tsc`、生产构建和差异检查通过，代码审查未发现可操作问题；真实协议目标和完整报告仍待环境验收。
- 2026-08-25：补齐 APK 包名身份一致性保护：Manifest 可解析包名时以其为准，手工包名不一致在 MinIO 上传/数据库写入前返回 `400`，匹配值和无 Manifest 场景保持兼容并归一化空白。APK/API 与发布契约定向 `22 passed`，后端非集成全量 `2284 passed`，Ruff、差异检查和代码审查通过；真实 Karing APK、下载端点、专项任务和完整报告仍待环境验收。
- 2026-08-25：补齐 Android 专项任务设备目标校验：创建、更新和手工触发在进入 Worker 前确认 `device_id` 存在，不存在/已下线返回 `400`，避免任务或运行记录进入等待后才失败。专项任务路由 `32 passed`，后端非集成全量 `2287 passed`，Ruff、差异检查和代码审查通过；真实设备在线状态、租约、ADB 操作和 Karing 仍待环境验收。
- 2026-08-25：补齐 Android 专项 APK 选择体验：选择器仅展示已解析包名的资产，选中后自动绑定并锁定包名，清空 APK 同步清除包名，未选择 APK 仍可手工填写；工具函数回归 `2 passed`，前端全量 `67 files / 274 tests passed`，`vue-tsc`、生产构建和差异检查通过，代码审查未发现可操作问题。真实 Karing APK、设备执行、专项任务和完整报告仍待环境验收。
- 2026-08-25：重新完成 Windows API/Web 完整 smoke：当前账号登录、PostgreSQL/Redis/MinIO readiness、Web Worker、Playwright `12 passed`、浏览器矩阵、文件上传/清理、Web 低代码下载、HTML/JUnit 报告和临时项目清理全部通过；脱敏证据为 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)，来源提交 `35ad777`。Android 检查按可选参数跳过，N2 Karing 真实门禁仍未关闭；下一步转向 N1 其他协议/完整报告真实证据。

## 8. 参考导航学习版执行台账（2026-08-25）

这份台账把参考导航中的菜单分组转换成可持续追踪的开发阶段。导航入口可达只代表信息架构完成；只有满足“代码/配置、回归测试、代码审查修复、文档同步和对应环境证据”的模块，才可以关闭本地交付。真实设备、外部服务、第三方模型和生产基础设施缺失时，保留 `[E]` 或 `[-]`，不使用页面截图、mock、跳过项或 Worker 心跳替代验收。

| 编号 | 导航分组 | 阶段目标 | 最小验收出口 | 当前状态 |
| --- | --- | --- | --- | --- |
| N0 | 导航壳与工作台 | 首页、待办、项目中心、任务中心统一项目上下文，深链和权限入口稳定 | 折叠/刷新/窄屏/深链可用；待办、任务状态和失败事件可追踪 | `[E]` 本地完成，真实账号复核随 Windows smoke 维护 |
| N1 | 接口测试 | HTTP、环境变量、会话复用、OpenAPI/Postman 导入、gRPC TLS Unary、GraphQL、WebSocket、流式 gRPC 和完整报告形成闭环 | 请求、断言、提取、依赖、导入预览/落库/回读、报告和清理有证据 | `[E]` q19 受控协议与报告闭环已通过；生产环境独立跟踪 |
| N2 | APP 自动化 | Windows Agent/ADB、APK 包名、低代码、录屏、专项任务、事件/日志/报告回传 | Karing 真实 APK 在单设备上完成执行、失败定位、媒体查看和清理 | `[~]` 包身份、Worker、低代码和录屏回传已通过；专项与报告仍待验收 |
| N3 | UI 自动化 | Playwright 录制、元素/页面对象、视觉基线、Trace/HAR、日志和多浏览器 | Chromium/Firefox/WebKit 均可录制、回放并查看失败证据 | `[E]` 本地/q19 证据已有，继续随 Windows 复核 |
| N4 | 性能测试 | 压测模型、节点分片、采样、趋势、基线、报告和保留清理 | 多节点容量校验、采样、基线门禁、报告和恢复演练可复核 | `[~]` 本地和 q19 短压完成；生产多节点/监控/恢复待验收 |
| N5 | AI 智能测试 | 模型拉取、多模态/思考参数、草稿生成、诊断和调用审计 | 结果带来源、可编辑、可限额；失败和敏感值处理可解释 | `[E]` 本地完成，真实模型和项目数据待验收 |
| N6 | 测试资产 | 用例、计划、缺陷、报告、评审串联运行和证据 | 运行可追到步骤证据、缺陷、评审和项目权限 | `[E]` 本地完成，真实项目和外部缺陷平台待验收 |
| N7 | 智能中枢 | Hermes、需求与用例生成、知识检索形成可追溯入口 | 查询/生成结果可编辑并带来源，不静默写入业务数据 | `[E]` 本地完成，真实模型、需求和知识数据待验收 |
| N8 | 系统 | 远程工具箱、配置中心、审计和单资源回滚集中管理 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断脱敏，回滚精确且可审计 | `[E]` 本地完成，目标部署和密钥边界待复核 |
| N9 | 发布收口 | 汇总能力矩阵、代码 SHA、测试、环境证据、操作手册和回滚边界 | 所有未关闭门禁有负责人、阻塞原因和复验命令 | `[~]` 依赖 N2、N4 及真实外部服务收口 |

### 当前执行游标

1. **N4 性能真实环境**：N1 q19 受控协议与报告闭环已通过；N4 本地采样、容量预检、保留清理和跨端点恢复入口已齐，下一步验证真实多节点、Prometheus/MinIO 生命周期和跨主机恢复。
2. **N2 APP 自动化**：Karing 的真实 `package_name`、Worker 前置、低代码和录屏回传已确认；下一步完成异常回放、性能/稳定性/流畅度专项任务、事件/日志/报告详情、下载和最终清理。
3. **N0/N3 Windows 复核**：已完成当前账号认证、依赖、文件传输、Web 低代码、浏览器矩阵和报告导出的完整 smoke；脱敏证据见 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)。
4. **N4～N9 外部收口**：依次验证性能真实环境、通知、外部缺陷平台与发布索引，保持凭据只存在于受控环境。

每个游标项完成后，必须按“实现/调整 → 定向测试 → 全量质量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送”推进，完成后才移动到下一项。
