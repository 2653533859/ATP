# ATP 后续优化跟踪计划

> 创建日期：2026-06-03
> 最近同步：2026-07-08
> 用途：记录 ATP 平台从“功能可用”走向“稳定、好用、可运维”的后续优化路线，方便按阶段跟踪进度。

## 当前进度

截至 2026-07-06，本路线图 **29 / 29 项全部完成**，阶段 1 ~ 阶段 5 均已收口。

最近完成的收尾项：

- S5-02：AI 用例草稿生成增强，支持 OpenAPI、Postman、cURL、接口样例和自然语言需求。
- S5-03：用例修复建议，执行详情可展示接口返回变更/断言失败时的步骤、断言、请求数据更新建议。
- S5-04：AI 诊断反馈闭环，支持采纳/拒绝反馈，并统计采纳率、错误特征和回归有效性。
- S5-05：Prompt 与模型配置治理，支持项目级模型、prompt 模板、调用限额、错误降级和 LLM 参数过滤。
- 2026-07-06 复查修复：缺陷手动关联接口补齐项目 `editor` 权限校验；AI governance / failure diagnosis 服务文件已纳入当前 diff；缺陷状态刷新审计日志修复 undefined `body.bug_id`。

最近验证记录：

- `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration`：823 passed（Python 3.14 本地 venv）
- Docker `python:3.12-slim-bookworm` + `gcc libpq-dev`，执行 `python -m pytest backend/tests -q --ignore=backend/tests/integration`：823 passed（依赖升级后的目标运行时基线）
- `python3 -m pytest backend/tests/frontend backend/tests/migrations/test_migration_policy.py backend/tests/worker/test_worker_lifecycle_policy.py -q`：90 passed
- `python3 -m pytest backend/tests/frontend/test_bug_link_frontend.py backend/tests/frontend/test_failure_diagnosis_static.py`：10 passed
- `backend/.venv/bin/python -m pytest backend/tests/services/test_device_sync.py backend/tests/api/test_ai_llm_configs_api.py backend/tests/worker/test_async_runner.py backend/tests/worker/test_suite_execution_config.py -q`：18 passed
- `make lint PYTHON=backend/.venv/bin/python`：通过（ruff F821/F822/F823 最小门禁）
- `make mypy PYTHON=backend/.venv/bin/python`：通过（`core` / `schemas` / `services` 共 76 个文件）
- `make security-bandit PYTHON=backend/.venv/bin/python`：通过（medium/high 0；low 63 可见不阻断）
- `make security-pip-audit PYTHON=backend/.venv/bin/python`：通过（No known vulnerabilities found）
- `make security-npm-audit`：通过（found 0 vulnerabilities）
- `.github/workflows/security.yml`：已新增 Gitleaks、pip-audit、npm high/critical audit、Trivy 镜像扫描
- `.github/dependabot.yml`：已新增 pip、npm、Docker、GitHub Actions 周期更新配置
- `make pre-commit PYTHON=backend/.venv/bin/python`：通过（YAML/EOF/whitespace、backend ruff、frontend Vitest）
- `make test-backend-coverage PYTHON=backend/.venv/bin/python`：823 passed，总覆盖率 53.47%，52% 门槛达成
- `npm --prefix frontend run test`：18 passed；`npm --prefix frontend run test:coverage`：通过，当前前端全仓覆盖率基线 1.8%
- `python3 -m pytest backend/tests/frontend -q`：78 passed
- `python3 -m pytest backend/tests/services/test_ai_case_parsers.py -q`：13 passed
- `python3 -m py_compile ...`：通过
- `npm run type-check`：通过
- `npm run build`：通过；仅保留已知 `ant-design-icons -> ant-design -> ant-design-icons` circular chunk 警告
- `python3 -m json.tool docker/grafana/dashboards/atp-overview.json`：通过
- `git diff --check`：通过

Python 3.14 本地后端环境已修复：通过 Homebrew `libpq` 提供 `pg_config`，安装时显式使用 `libpq` / `openssl@3` 编译路径，并为 Python 3.14 增加兼容依赖 pin（SQLAlchemy、grpcio/grpcio-tools、Playwright、OpenTelemetry）。Docker Python 3.12 目标运行时已完成全量后端回归，确认条件 pin 不影响当前部署基线。

## 当前基线

| 方向 | 当前状态 | 说明 |
| --- | --- | --- |
| 主 CI | 已通过 | 后端单元测试、前端 type-check、前端 build 已在 GitHub Actions 通过 |
| E2E | 已通过 | 登录、Dashboard、用例列表、执行详情等 7 条 Playwright 用例通过 |
| Integration | 已通过 | 真实 Postgres / Redis / MinIO 下的 auth、case-run、mock 核心链路通过 |
| Release readiness | 已通过 | 后端、worker、前端镜像构建与 worker 工具检查通过 |
| 前端 | 优化路线已完成 | Dashboard、用例管理、执行详情、系统页、权限可见性、窄屏适配均已收口 |
| 后端 | 优化路线已完成 | 迁移链、测试稳定性、领域边界、运维能力、AI 治理均已收口 |

## 优先级原则

1. P0 优先修“会阻断开发、测试、部署”的问题。
2. P1 优先补齐“日常使用闭环”，让平台能稳定承载真实测试工作。
3. P2 做体验增强、效率工具和可观测性深化。
4. AI 能力先做实用闭环，不做展示型功能。

## 阶段 1：工程稳定性与本地体验

目标：让新环境能低成本启动、验证、排错。

| 编号 | 任务 | 优先级 | 状态 | 验收标准 |
| --- | --- | --- | --- | --- |
| S1-01 | 完善 `README.md` 本地启动说明 | P0 | [x] 已完成 | 前端、FastAPI、Celery、Postgres、Redis、MinIO 启动命令清晰可复制 |
| S1-02 | 校准 `.env.example` | P0 | [x] 已完成 | 覆盖后端、前端、worker、MinIO、Redis、数据库必要变量 |
| S1-03 | 增加一键开发命令 | P1 | [x] 已完成 | 提供 `make dev` 或等价脚本，能启动核心服务 |
| S1-04 | 增加空库迁移校验 | P0 | [x] 已完成 | CI 能验证从空 Postgres 执行 `alembic upgrade head` 成功 |
| S1-05 | 整理测试命令矩阵 | P1 | [x] 已完成 | README 中明确单元测试、E2E、integration、release readiness 的运行方式 |
| S1-06 | CI 工作流文档化 | P1 | [x] 已完成 | `docs/` 中有每条 workflow 的触发条件、依赖服务、失败排查方式 |

## 阶段 2：前端体验收口

目标：让平台第一眼和日常操作都更像成熟测试平台。

| 编号 | 任务 | 优先级 | 状态 | 验收标准 |
| --- | --- | --- | --- | --- |
| S2-01 | Dashboard 工作台优化 | P1 | [x] 已完成 | 显示今日执行、失败趋势、待审批、告警、最近运行入口 |
| S2-02 | 用例管理页体验打磨 | P1 | [x] 已完成 | 筛选、批量操作、步骤编辑、状态/审批流清晰 |
| S2-03 | 执行详情页排查链路优化 | P1 | [x] 已完成 | 步骤、日志、截图、Trace、AI 诊断集中展示 |
| S2-04 | 系统管理页视觉统一 | P2 | [x] 已完成 | 存储、告警、变量、通知、AI 配置页面布局风格一致 |
| S2-05 | 权限可见性优化 | P1 | [x] 已完成 | 不同角色只看到可操作入口，禁用态/提示明确 |
| S2-06 | 移动端/窄屏基础适配 | P2 | [x] 已完成 | 核心列表、详情、表单在常见窄屏不重叠、不截断 |

## 阶段 3：测试平台业务闭环

目标：补齐从用例到报告、缺陷和复盘的完整流程。

| 编号 | 任务 | 优先级 | 状态 | 验收标准 |
| --- | --- | --- | --- | --- |
| S3-01 | 用例导入导出体验增强 | P1 | [x] 已完成 | 支持模板下载、导入校验、错误行提示、导入预览 |
| S3-02 | 套件/计划执行报告增强 | P1 | [x] 已完成 | 报告能展示通过率、失败 Top、耗时、关联用例和失败原因 |
| S3-03 | 缺陷联动闭环 | P1 | [x] 已完成 | 失败用例可创建/关联 GitHub/GitLab/Jira/禅道缺陷，并回写状态 |
| S3-04 | 数据集引用影响面 | P2 | [x] 已完成 | 数据集详情展示被哪些用例、套件、计划引用，并提供引用原因和跳转入口 |
| S3-05 | 通知策略细化 | P2 | [x] 已完成 | 可按项目、套件、计划、执行状态配置通知规则，发送前按策略过滤 |
| S3-06 | flaky 用例标记 | P2 | [x] 已完成 | 根据最近执行历史识别不稳定用例，并在用例列表和套件报告中提示 |

## 阶段 4：后端架构与运维能力

目标：降低长期维护成本，提高部署、排错和恢复能力。

| 编号 | 任务 | 优先级 | 状态 | 验收标准 |
| --- | --- | --- | --- | --- |
| S4-01 | 领域模块边界梳理 | P1 | [x] 已完成 | case、execution、reporting、notification、mock、ai 边界清晰，并记录跨域契约 |
| S4-02 | Alembic 迁移规范加固 | P0 | [x] 已完成 | enum、索引、约束迁移有统一模板、编写指南和回归测试 |
| S4-03 | Worker 状态与重试规范 | P1 | [x] 已完成 | 任务状态、超时、失败、重试、取消与恢复路径有统一规范和回归检查 |
| S4-04 | 审计日志增强 | P2 | [x] 已完成 | 关键配置、执行、权限、删除操作有可追踪审计记录和审计策略 |
| S4-05 | 可观测性看板增强 | P2 | [x] 已完成 | 慢查询、队列积压、接口错误率、MinIO 使用量可观测 |
| S4-06 | 备份恢复演练 | P1 | [x] 已完成 | 有数据库/对象存储备份与恢复演练文档和验证记录 |

## 阶段 5：AI 辅助能力

目标：让 AI 直接服务测试生产效率。

| 编号 | 任务 | 优先级 | 状态 | 验收标准 |
| --- | --- | --- | --- | --- |
| S5-01 | 失败原因总结 | P1 | [x] 已完成 | 执行详情可根据日志/断言/截图生成简明诊断 |
| S5-02 | AI 用例草稿生成增强 | P1 | [x] 已完成 | 从 OpenAPI、接口样例、自然语言需求生成可编辑草稿 |
| S5-03 | 用例修复建议 | P2 | [x] 已完成 | 接口返回变更或断言失败时给出步骤/断言更新建议 |
| S5-04 | AI 诊断反馈闭环 | P2 | [x] 已完成 | 用户可采纳/拒绝建议，系统统计采纳率和有效性 |
| S5-05 | Prompt 与模型配置治理 | P2 | [x] 已完成 | 项目级模型、提示词模板、调用限额和错误降级可配置 |

## 近期建议排期

> 历史排期已完成；后续建议进入发布收口、PR 拆分、最终集成验证和发布说明整理。

| 周期 | 聚焦目标 | 推荐任务 |
| --- | --- | --- |
| 第 1 周 | 稳定开发与 CI 基线 | S1-01、S1-02、S1-04、S1-05 |
| 第 2 周 | 前端核心工作台 | S2-01、S2-02、S2-03 |
| 第 3 周 | 业务闭环 | S3-02、S3-03、S3-06 |
| 第 4 周 | 运维与架构收口 | S4-02、S4-03、S4-05 |
| 第 5 周以后 | AI 效率增强 | S5-01、S5-02、S5-04 |

## 跟踪方式

- 状态约定：
  - `[ ] 未开始`
  - `[~] 进行中`
  - `[x] 已完成`
  - `[!] 阻塞`
- 每完成一个任务，在本文件更新状态，并补充对应 PR、commit、测试证据或截图。
- 每周复盘一次：
  - 哪些任务完成
  - 哪些任务延期
  - 哪些任务需要降级或拆分
  - CI / E2E / integration 是否仍保持绿色

## 完成定义

一项任务只有同时满足以下条件，才标记为已完成：

1. 代码或文档已合入主分支。
2. 相关测试已通过，或明确说明无需测试。
3. 用户可验证的入口、命令或截图已记录。
4. 不引入新的 CI 红点。
