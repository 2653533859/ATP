# ATP 项目开发上下文文档

> 本文档用于在新会话中快速恢复开发上下文，包含架构决策、已完成功能、关键代码位置、待续任务等。

**生成时间**: 2026-03-03
**最近同步**: 2026-07-09
**项目路径**: `/Users/parado/MyProject/ATP`
**参考文档**: `PRD.md`（需求文档）、`Task.md`（任务跟踪）

---

## 0. 当前进度快照（2026-07-08）

`docs/optimization-roadmap-2026.md` 中 ATP 后续优化路线已全部完成：**29 / 29 项均为 `[x] 已完成`**。

已完成阶段：

- 阶段 1：工程稳定性与本地体验（S1-01 ~ S1-06）
- 阶段 2：前端体验收口（S2-01 ~ S2-06）
- 阶段 3：测试平台业务闭环（S3-01 ~ S3-06）
- 阶段 4：后端架构与运维能力（S4-01 ~ S4-06）
- 阶段 5：AI 辅助能力（S5-01 ~ S5-05）

最近完成的 AI 能力：

- 失败原因总结：执行详情可基于日志、断言、截图线索生成简明诊断。
- AI 用例草稿生成增强：支持 OpenAPI、Postman、cURL、接口样例和自然语言需求。
- 用例修复建议：接口返回变更或断言失败时，展示步骤/断言/请求数据更新建议。
- AI 诊断反馈闭环：支持采纳/拒绝反馈，并统计采纳率、错误特征和回归有效性。
- Prompt 与模型配置治理：项目级模型、prompt 模板、调用限额、错误降级和 LLM 参数过滤已文档化并接入关键 AI 调用。

2026-07-06 收口修复：

- 缺陷手动关联接口已补齐项目权限校验：`POST /runs/{run_id}/link-bug` 在写入执行结果前要求当前用户具备该项目 `editor` 权限。
- AI governance 与 failure diagnosis 两个服务模块已纳入当前 diff，避免干净检出时 `app.services.ai_governance` / `app.services.failure_diagnosis` 导入失败。
- 缺陷状态刷新审计日志已修复 undefined `body.bug_id`，改为使用已有 `bug_info["bug_id"]`。
- 已补充静态回归，覆盖手动关联缺陷的权限校验要求。
- Q10 Phase 5 已补 suite-run / plan-trigger / notification / bug-report 集成链路，并在真实 Postgres / Redis / MinIO 临时环境跑通；过程中发现并修复 `test_suites.config` 缺失 Alembic 迁移、`bug_trackers.tracker_type` 纯迁移首建仍为 varchar 的问题。
- 前端 suite / plan 关键路径 E2E 已补齐：suite 加载、触发执行、打开执行记录，以及 plan 加载、手动触发、查看执行历史均通过 Playwright mock 模式验证。
- Q10 SLO 薄切已补齐：新增 `atp_run_outcomes_total{entity_type,status}`，Grafana `ATP Overview` 新增 API 可用性、API P95、run 成功率和 API 错误预算剩余 4 个面板，并新增 `docs/slo-guide.md`。
- Q10 flaky 治理已补齐：新增 `pytest-rerunfailures==16.4`、`flaky` marker、integration CI 一次有界重试、Playwright CI 重试边界说明与 `docs/flaky-governance.md`。
- Q10 验收收口已补齐：新增 `docs/q10-acceptance-summary.md`，README 已加入 Q10 质量与稳定性索引，Task / MEMORY / CONTEXT / release evidence 已同步。
- Q11 下一轮优化路线已建立：`docs/optimization-roadmap-2026-q11.md`，优先级为 PR / commit 拆分、发布说明、SLO 生产校准、前端覆盖率增长和运维 runbook。Q11-00 已完成，拆分计划见 `docs/q11-pr-split-plan.md`；Q11-01 已完成，发布说明 / 风险 / 回滚记录见 `docs/q10-release-notes.md`；Q11-02 已完成，CI matrix 本地与 GitHub runner 证据、PyJWT 迁移、Gitleaks/Trivy/镜像修复记录见 `docs/q11-ci-matrix-evidence.md`；Q11 Phase 1 已完成，SLO 预生产基线、生产采样窗口、目标依据、triage runbook 和告警暂缓决策见 `docs/slo-guide.md`；Q11-20 已完成，project/module/case navigation helpers 与 Vitest 覆盖见 `frontend/src/utils/caseNavigation.ts`；Q11-21 已完成，suite / plan list pure helpers 与 Vitest 覆盖见 `frontend/src/utils/suiteList.ts` 和 `frontend/src/utils/planList.ts`；Q11-22 已完成，`EnvironmentList.vue` 三态 smoke 测试见 `frontend/src/views/system/EnvironmentList.spec.ts`，并修正 CaseList E2E mock 响应契约；Q11-30 已完成，当前 release-readiness runbook 与静态/workflow 契约见 `docs/q9-release-checklist.md` 和 `backend/tests/worker/test_q9_release_readiness.py`；Q11-31 已完成，失败定时计划演练见 `docs/scheduled-plan-incident-drill.md`；Q11-32 已完成，依赖、安全和镜像回滚见 `docs/dependency-security-rollback.md`，前端镜像已改用 `npm ci`。

最近验证记录：

- `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration`：825 passed（Python 3.14 本地 venv）
- 临时真实依赖环境（Postgres `55432` / Redis `6380` / MinIO `19000`）空库 `alembic upgrade head`：通过；`backend/tests/integration -m integration`：10 passed，且同库二次重复运行仍为 10 passed
- Docker `python:3.12-slim-bookworm` + `gcc libpq-dev`，执行 `python -m pytest backend/tests -q --ignore=backend/tests/integration`：823 passed（依赖升级后的目标运行时基线）
- `python3 -m pytest backend/tests/frontend backend/tests/migrations/test_migration_policy.py backend/tests/worker/test_worker_lifecycle_policy.py -q`：90 passed
- `python3 -m pytest backend/tests/frontend/test_bug_link_frontend.py backend/tests/frontend/test_failure_diagnosis_static.py`：10 passed
- `backend/.venv/bin/python -m pytest backend/tests/services/test_device_sync.py backend/tests/api/test_ai_llm_configs_api.py backend/tests/worker/test_async_runner.py backend/tests/worker/test_suite_execution_config.py -q`：18 passed
- `make lint PYTHON=backend/.venv/bin/python`：通过（ruff F821/F822/F823 最小门禁）
- `make format-check PYTHON=backend/.venv/bin/python`：通过（332 files already formatted）
- `make mypy PYTHON=backend/.venv/bin/python`：通过（`core` / `schemas` / `services` 共 76 个文件）
- `make security-bandit PYTHON=backend/.venv/bin/python`：通过（medium/high 0；low 63 可见不阻断）
- `make security-pip-audit PYTHON=backend/.venv/bin/python`：通过；后端依赖已清零（No known vulnerabilities found）
- `make security-npm-audit`：通过；前端依赖已清零（found 0 vulnerabilities）
- Q11-02 dependency replay：`python-jose` 已替换为 `PyJWT[crypto]==2.13.0`，本地 venv 已清理 `python-jose` / `ecdsa` / `rsa` / `pyasn1`，`pip check` 通过。
- Q11-02 CI replay：GitHub `CI (integration)` 失败定位为 OTel FastAPI instrumentation 在 endpoint 为空时仍挂载，且早于 route registration；已改为 endpoint 配置时才在 include_router 之后挂载。后续 runner 暴露并已修复 `types-redis` / Redis `aclose` typing、Trivy action tag、Gitleaks 历史 allowlist、worker k6 Go CVE、frontend Alpine 包 CVE 与 observability 文案契约问题。最终 `main` commit `c1ef60c` 的 CI `28998360621`、Security `28998360606`、Integration `28998366738`、Release readiness `28998368776`、E2E `28998370798` 全部成功。
- `.github/workflows/security.yml` / `.github/dependabot.yml`：已新增并通过 YAML 解析；覆盖 Gitleaks、pip-audit、npm high/critical audit、Trivy 镜像扫描与四生态 Dependabot
- `make pre-commit PYTHON=backend/.venv/bin/python`：通过（YAML/EOF/whitespace、backend ruff、frontend Vitest）
- `make test-backend-coverage PYTHON=backend/.venv/bin/python`：823 passed，总覆盖率 53.47%，52% 门槛达成
- `npm --prefix frontend run test`：18 passed
- `npm --prefix frontend run e2e -- suite-plan.spec.ts`：2 passed
- `npm --prefix frontend run e2e`：9 passed
- SLO 薄切验证：Grafana dashboard JSON 校验通过；SLO 定向 worker 测试 23 passed；相关 ruff 检查通过
- Q11-10 SLO 校准：`docs/slo-guide.md` 已记录当前证据窗口、缺少连续生产 Prometheus 历史的限制、7 天初始生产校准和 14 天稳定生产校准要求，以及 availability / P95 / run success rate 目标依据。
- Q11-11 SLO runbook：`docs/slo-guide.md` 已补充首五分钟检查、availability / latency / run success / error budget 排查路径、升级条件和 incident 记录模板。
- Q11-12 告警阈值决策：`docs/slo-guide.md` 已明确暂缓 paging-grade SLO 告警到连续生产 Prometheus 历史可用后，并记录 availability / P95 / error budget / run success rate 阈值草案和启用条件。
- Q11-20 前端导航测试：新增 `frontend/src/utils/caseNavigation.spec.ts` 覆盖路由 id、review status、case-list query、项目跳用例、用例详情和 query-vs-param 优先级；`npm --prefix frontend run test` 为 8 files / 22 tests，`type-check` 与 `build` 通过。
- Q11-21 suite / plan helper 测试：新增 `frontend/src/utils/suiteList.spec.ts` 与 `frontend/src/utils/planList.spec.ts`，覆盖配置规范化、状态 / schedule 颜色、duration / percent、cron 校验 / preset、运行汇总、失败项和 suite progress；`npm --prefix frontend run test` 为 10 files / 30 tests，`type-check` 与 `build` 通过。
- Q11-22 system page smoke 测试：新增 `frontend/src/views/system/EnvironmentList.spec.ts`，覆盖项目选择前、环境加载中、空环境和 API 错误状态；同时修正 `frontend/e2e/fixtures/mock-api.ts` 的 `/cases` 返回结构；Vitest 为 11 files / 33 tests，目标 E2E 为 4 passed。
- Q11-30 release-readiness runbook：`docs/q9-release-checklist.md` 已覆盖同 SHA 证据、lint / format / mypy / coverage、安全、真实依赖 integration、E2E、SLO JSON、镜像、迁移、Helm、烟测和回滚；相关 docs/static tests 为 10 passed，workflow YAML 与 Grafana JSON 校验通过。
- Q11-31 scheduled-plan incident drill：新增 `docs/scheduled-plan-incident-drill.md` 与实现契约，覆盖 Beat/Celery、Redis DB 0/1/2、数据库父子运行状态、通知和自动缺陷副作用，以及避免重复执行的恢复准则；相关契约 12 passed。
- Q11-32 dependency/security rollback：新增 `docs/dependency-security-rollback.md` 与实现契约，前端镜像改为 `npm ci`；clean install 后 33 tests、type-check/build、Docker build、pip/npm audit 均通过。
- Q11-40 ResizeObserver warning：定位为 CaseList 空表仍强制横向滚动触发 Ant Design Vue 首帧测量循环；改为有数据时才设置 `scroll.x`；pageerror 防护已上移至共享 fixture（`e2e/fixtures/mock-api.ts` 对任何非白名单未捕获页面异常判失败，ResizeObserver 噪声在白名单内），全部 spec 自动继承；全量 E2E 9 passed 且警告消失。
- Q11-41 bundle decision：保留 Ant Design / icons 独立 chunk，拒绝会触发 1.5 MB 告警的合并方案；移动专项报告改用 modular ECharts，chunk 从 1126.62/374.44 gzip kB 降至 563.41/191.53 kB，构建零告警。
- Q11-42 Android worker connectivity：实测容器 ADB 与 Docker Desktop `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037` 控制路径；修正文档中的自动复用/5555 误解，增加 host-gateway、共享 server 安全诊断模式和跨平台约束。当前无真机，shell/data-plane 作为环境侧验收项保留。
- Flaky 治理验证：`pytest --markers` 可见项目 `flaky` marker 与 rerunfailures marker；`--reruns 1` 定向测试 2 passed；CI workflow YAML 解析通过
- Q10 验收文档：`docs/q10-acceptance-summary.md` 已汇总质量门禁、安全扫描、覆盖率、集成/E2E、SLO 与 flaky 治理证据
- `npm --prefix frontend run test:coverage`：通过，当前前端全仓覆盖率基线 1.8%
- `python3 -m pytest backend/tests/frontend -q`：78 passed
- `python3 -m pytest backend/tests/services/test_ai_case_parsers.py -q`：13 passed
- `python3 -m py_compile ...`：通过
- `npm run type-check`：通过
- `npm run build`：通过；仅保留已知 `ant-design-icons -> ant-design -> ant-design-icons` circular chunk 警告
- `python3 -m json.tool docker/grafana/dashboards/atp-overview.json`：通过
- `git diff --check`：通过

Python 3.14 本地环境说明：已通过 Homebrew `libpq` 提供 `pg_config`，并在安装时显式使用 `libpq` / `openssl@3` 的 keg-only 编译路径；`backend/requirements.txt` 已为 Python 3.14 增加 SQLAlchemy、grpcio/grpcio-tools、Playwright 与 OpenTelemetry 的版本条件 pin。

关键新增/更新文档：

- `docs/optimization-roadmap-2026.md`：当前项目进度来源，29/29 完成。
- `docs/ai-governance.md`：AI 模型、prompt、限额和降级治理。
- `docs/observability-guide.md`：Prometheus/Grafana 可观测性与 MinIO 指标。
- `docs/disaster-recovery.md`、`docs/backup-restore-drill-record.md`：数据库和对象存储备份恢复演练。
- `docs/domain-boundaries.md`、`docs/worker-lifecycle.md`、`docs/audit-log-policy.md`：架构、Worker、审计治理。

下一步建议：Q11 路线图全部完成并进入验收归档；下一轮重点处理测试告警信噪比、前端覆盖率门槛、依赖生命周期和外部环境实证。

---

## 1. 项目概述

ATP（Automated Testing Platform）是一个统一自动化测试平台，目标功能：

- **接口测试**：REST / GraphQL / WebSocket / gRPC
- **Web UI 测试**：Playwright + pytest 脚本
- **Android UI 测试**：uiautomator2 + pytest 脚本
- **用例管理**：树形目录、标签、套件、调度
- **双模式**：工程师写脚本上传 / 业务人员低代码配置

---

## 2. 技术选型（最终确定）

| 层 | 技术 | 说明 |
|----|------|------|
| 前端框架 | Vue 3 + TypeScript | Vite 构建 |
| 前端组件库 | **Ant Design Vue 4.x** | 已选定 |
| 状态管理 | Pinia | |
| 路由 | Vue Router 4 | |
| HTTP 客户端 | axios | |
| 后端框架 | **FastAPI 0.115** | |
| ORM | SQLAlchemy 2.x async | |
| 数据库迁移 | Alembic | |
| 数据库 | **PostgreSQL 16** | Docker 内 |
| 缓存/队列 | **Redis 7** | DB0=Celery, DB1=Result, DB2=PubSub |
| 任务队列 | Celery 5.x | |
| 对象存储 | MinIO | 本地私有化 |
| 接口执行 | httpx + jsonpath-ng | |
| Web 测试 | Playwright + pytest | |
| Android 测试 | **uiautomator2**（非 Appium）| |
| 脚本执行器 | pytest + pytest-json-report | |
| 实时推送 | Redis Pub/Sub → WebSocket | |
| 部署 | Docker Compose | 本地私有化 |
| Python 版本 | **3.12** | |

---

## 3. 目录结构与文件说明

```
ATP/
├── PRD.md                          需求文档
├── Task.md                         任务跟踪（带完成状态）
├── CONTEXT.md                      本文档（开发上下文）
├── .env.example                    环境变量模板（复制为 .env 使用）
├── docker-compose.yml              生产环境完整编排（7个服务）
├── docker-compose.dev.yml          开发环境（只启 postgres/redis/minio）
├── docker/
│   └── nginx.conf                  Nginx 反代配置（/api/ → backend:8000, /ws/ → websocket）
│
├── backend/
│   ├── Dockerfile                  FastAPI 镜像（启动时执行 alembic upgrade head）
│   ├── Dockerfile.worker           Celery Worker 镜像（含 Playwright Chromium + ADB）
│   ├── requirements.txt            Python 依赖
│   ├── alembic.ini                 Alembic 配置（URL 由 env.py 覆盖）
│   ├── alembic/
│   │   └── env.py                  迁移环境（使用同步 psycopg2 URL）
│   └── app/
│       ├── main.py                 FastAPI 入口：lifespan 建表+初始化管理员，注册路由
│       ├── core/
│       │   ├── config.py           Settings（pydantic-settings，读 .env）
│       │   ├── database.py         async engine + AsyncSessionLocal + get_db()
│       │   ├── security.py         JWT 签发/验证 + 密码哈希
│       │   └── redis_client.py     Redis 客户端：publish_run_event() / get_async_redis()
│       ├── models/
│       │   ├── base.py             DeclarativeBase + TimestampMixin
│       │   ├── user.py             User（UserRole 枚举：admin/engineer/tester/viewer）
│       │   ├── project.py          Project + Module（树形，parent_id 自引用）
│       │   ├── case.py             TestCase + TestRun + StepResult（CaseType/RunStatus 枚举）
│       │   └── environment.py      Environment + EnvVariable
│       ├── schemas/
│       │   ├── auth.py             LoginRequest / TokenResponse / UserOut
│       │   ├── project.py          ProjectOut / ModuleOut / ModuleTree
│       │   └── case.py             TestCaseOut / TestRunOut / StepResultOut
│       ├── api/
│       │   ├── deps.py             get_current_user() / require_roles() / require_admin
│       │   └── v1/
│       │       ├── router.py       汇总路由（prefix=/api/v1）
│       │       ├── auth.py         /auth/login, /auth/refresh, /auth/me
│       │       ├── projects.py     /projects CRUD + /modules CRUD + 树形查询
│       │       ├── cases.py        /cases CRUD + /cases/{id}/run + /runs 查询
│       │       └── ws.py           WebSocket /ws/runs/{run_id}（Token 鉴权 + Redis 订阅）
│       └── worker/
│           ├── celery_app.py       Celery 实例配置
│           ├── tasks.py            run_test_case task（路由到对应执行器）
│           └── executors/
│               └── api_executor.py HTTP 接口执行器（httpx + 断言 + 变量提取 + Redis publish）
│
└── frontend/
    ├── Dockerfile                  多阶段构建（node build → nginx 托管）
    ├── nginx.conf                  前端容器内 Nginx 配置（同 docker/nginx.conf）
    ├── vite.config.ts              开发代理：/api → localhost:8000, /ws → ws://localhost:8000
    ├── tsconfig.json
    └── src/
        ├── main.ts                 Vue 入口（注册 Pinia + Router + Ant Design Vue）
        ├── App.vue                 根组件（<RouterView />）
        ├── env.d.ts                Vite 环境类型声明（import.meta.env）
        ├── api/
        │   ├── http.ts             axios 封装（Token 拦截 + 401 跳登录）
        │   └── index.ts            所有 API 方法（authApi / projectApi / moduleApi / caseApi / runApi）
        ├── router/index.ts         路由定义 + 路由守卫（未登录跳 /login）
        ├── stores/auth.ts          Pinia：token / user / login() / logout()
        ├── utils/websocket.ts      WebSocket 封装（自动重连 3 次，Token 通过 ?token= 传递）
        ├── layouts/MainLayout.vue  主布局（侧边栏 + 顶栏 + <RouterView />）
        ├── components/common/
        │   ├── ModuleTree.vue      树形模块目录（新建/删除，emit select 事件）
        │   ├── KvEditor.vue        Key-Value 行编辑器（Headers/Params/Form Body 共用）
        │   └── CaseFormDrawer.vue  用例创建/编辑抽屉（接口测试完整配置）
        └── views/
            ├── auth/LoginView.vue      登录页
            ├── project/ProjectList.vue 项目卡片列表（点击进入用例页）
            ├── case/CaseList.vue       左侧模块树 + 右侧用例表格 + 执行触发
            ├── run/RunList.vue         执行记录列表
            ├── run/RunDetail.vue       执行报告详情（WebSocket 实时更新步骤）
            └── system/EnvironmentList.vue  环境管理（占位，待实现）
```

---

## 4. 数据模型关系

```
User ──────────────────────────────────────┐
  │ owner_id                               │ creator_id / triggered_by
Project                                 TestCase ── TestRun ── StepResult
  └── Module (树形，parent_id 自引用)       │   └── config: JSON（用例配置）
        └── TestCase (case_type: api/web/android)

Environment
  └── EnvVariable (key/value/is_secret)
```

**TestCase.config 结构（接口测试）：**
```json
{
  "steps": [{
    "name": "主请求",
    "url": "https://...",
    "method": "GET",
    "headers": {},
    "params": {},
    "body_type": "none|json|form|raw",
    "body": null,
    "auth": { "type": "none|bearer|basic|apikey", "token": "", ... },
    "timeout": 30,
    "assertions": [
      { "target": "status_code|body|header|duration", "operator": "eq|contains|gt|lt|exists", "expected": "200", "expression": "" }
    ],
    "extractions": [
      { "variable": "token", "expression": "$.data.token" }
    ]
  }]
}
```

---

## 5. API 端点清单

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/auth/login` | 登录，返回 access_token + refresh_token |
| POST | `/api/v1/auth/refresh` | 刷新 Token |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| GET | `/api/v1/projects` | 项目列表 |
| POST | `/api/v1/projects` | 创建项目 |
| PATCH | `/api/v1/projects/{id}` | 更新项目 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |
| GET | `/api/v1/projects/{id}/modules` | 获取模块树（递归） |
| POST | `/api/v1/modules` | 创建模块 |
| PATCH | `/api/v1/modules/{id}` | 更新模块 |
| DELETE | `/api/v1/modules/{id}` | 删除模块 |
| GET | `/api/v1/cases` | 用例列表（支持 module_id / case_type / tag 过滤） |
| POST | `/api/v1/cases` | 创建用例 |
| GET | `/api/v1/cases/{id}` | 用例详情 |
| PATCH | `/api/v1/cases/{id}` | 更新用例 |
| DELETE | `/api/v1/cases/{id}` | 删除用例 |
| POST | `/api/v1/cases/{id}/run` | 触发执行（返回 TestRun，异步） |
| GET | `/api/v1/runs` | 执行记录列表（支持 case_id 过滤） |
| GET | `/api/v1/runs/{id}` | 执行详情（含 steps） |
| WS | `/ws/runs/{run_id}?token=xxx` | 实时执行事件推送 |
| GET | `/health` | 健康检查 |

---

## 6. WebSocket 事件格式

连接地址：`ws://host/ws/runs/{run_id}?token={access_token}`

```jsonc
// 执行开始
{ "type": "run_status", "run_id": 1, "status": "running" }

// 步骤完成（每步结束后推送）
{
  "type": "step_result", "run_id": 1,
  "step": {
    "step_index": 0, "name": "主请求", "status": "passed",
    "duration_ms": 123,
    "request_data": { "method": "GET", "url": "...", "headers": {}, "params": {}, "body": null },
    "response_data": { "status_code": 200, "headers": {}, "body": {}, "duration_ms": 123 },
    "error_message": null
  }
}

// 执行结束（前端收到后关闭 WebSocket）
{ "type": "completed", "run_id": 1, "status": "passed", "duration_ms": 456 }
```

**Redis Channel**: `atp:run:{run_id}`（DB 2）

---

## 7. 执行链路（接口测试）

```
前端触发 POST /api/v1/cases/{id}/run
  → 创建 TestRun（status=pending）→ 返回 run 对象
  → 前端跳转 /runs/{id}，连接 WebSocket
  → Celery Worker 收到任务
      → TestRun.status = running → Redis publish run_status
      → api_executor.run_api_case()
          → 遍历 steps：发请求 → 断言 → 变量提取 → 写 StepResult → Redis publish step_result
      → 最终 TestRun.status = passed/failed → Redis publish completed
  → WebSocket 自动关闭
  → 前端兜底：WS 关闭后再拉一次 GET /runs/{id} 确保状态最新
```

---

## 8. 环境变量说明（.env）

```bash
# 复制 .env.example 为 .env 并修改以下值：
POSTGRES_PASSWORD=         # 数据库密码
MINIO_ROOT_PASSWORD=       # MinIO 密码
APP_SECRET_KEY=            # JWT 密钥（随机 32+ 字符）
FIRST_ADMIN_PASSWORD=      # 首次启动自动创建的管理员密码
```

---

## 9. 启动方式

### 开发模式（推荐）

```bash
# 1. 启动基础设施
cp .env.example .env   # 修改密码等配置
docker compose -f docker-compose.dev.yml up -d

# 2. 启动后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 启动 Celery Worker（新终端）
cd backend
celery -A app.worker.celery_app worker --loglevel=info

# 4. 启动前端（新终端）
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 生产模式（Docker Compose 全量）

```bash
cp .env.example .env   # 修改生产密码
docker compose up -d --build
# 访问 http://localhost
```

**默认管理员账号**：`admin` / `Admin@123456`（可在 .env 中修改）

---

## 10. 关键设计决策（已定）

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 移动端框架 | uiautomator2（非 Appium） | 纯 Python、更轻量、无需 Node.js + Appium Server |
| 实时推送 | Redis Pub/Sub → WebSocket | Worker 为独立进程，无法直接推送，通过 Redis 解耦 |
| WebSocket 鉴权 | URL Query `?token=xxx` | 浏览器 WebSocket API 不支持自定义 Header |
| 数据库迁移 | Alembic（同步 psycopg2） | alembic 不支持 asyncpg，env.py 自动转换 URL |
| 用例配置存储 | JSON 字段（config 列） | 不同类型用例结构差异大，JSON 更灵活 |
| 首次建表 | `create_all` + Alembic 并存 | lifespan 兜底建表，Alembic 负责增量迁移 |
| publish 失败处理 | `_safe_publish_run_event` 吞异常 | 实时推送是 best-effort，不能影响执行结果落库 |

---

## 11. 优化路线当前进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 1：工程稳定性与本地体验 | ✅ 完成 | README、`.env.example`、Makefile、迁移校验、测试矩阵、CI 文档已补齐 |
| 阶段 2：前端体验收口 | ✅ 完成 | Dashboard、用例管理、执行详情、系统页、权限可见性、窄屏适配完成 |
| 阶段 3：测试平台业务闭环 | ✅ 完成 | 导入导出、套件/计划报告、缺陷联动、数据集影响面、通知策略、flaky 标记完成 |
| 阶段 4：后端架构与运维能力 | ✅ 完成 | 领域边界、迁移规范、Worker 生命周期、审计、可观测性、备份恢复完成 |
| 阶段 5：AI 辅助能力 | ✅ 完成 | 失败总结、草稿生成、修复建议、反馈闭环、Prompt/模型治理完成 |

详细任务状态以 `docs/optimization-roadmap-2026.md` 为准，当前为 **29 / 29 完成**。

---

## 12. 下一步建议

Q1-Q11 路线图内功能项已完成。当前进入 Q12 持续质量优化：

- Q11-02：已完成本地主矩阵复跑、GitHub runner 证据归档，以及 Security / Trivy / Gitleaks / typing 后续修复。
- Q11-10：已校准 API availability / P95 预生产窗口与目标，并把观测窗口、目标依据、暂缓项同步到 `docs/slo-guide.md`。
- Q11-11：已补充 SLO triage runbook，将 availability、latency、run success rate、error-budget 异常映射到首轮排查动作。
- Q11-12：已决定 SLO 告警阈值策略；在没有连续生产 Prometheus 历史前暂缓 paging-grade alerting，并记录明确 deferred decision 与阈值草案。
- Q11-20：已补充 project / module / case navigation utilities 的前端测试。
- Q11-21：已补充 suite / plan list pure helpers 的前端测试。
- Q11-22：已补充 `EnvironmentList.vue` system page smoke component test，并覆盖 loading / empty / error 状态。
- Q11-30：已升级 release-readiness runbook，纳入 Q10 全套质量、安全、integration、E2E 与 SLO 校验。
- Q11-31：已新增失败定时计划 incident drill checklist，覆盖执行链路、外部副作用与安全恢复。
- Q11-32：已新增依赖/安全更新回滚 runbook，并将前端镜像安装收敛为 lockfile 严格的 `npm ci`。
- Q11-40：已修复 CaseList 空表横向滚动导致的 ResizeObserver E2E warning，并加入回归断言。
- Q11-41：已完成 bundle 分包决策并将 ECharts chunk 体积降低约一半。
- Q11-42：已完成 Android Worker ADB 控制路径演练并记录物理设备/宿主网络约束。
- Q12-00：已消除 41 条 pytest 收集警告，完整后端回归 `840 passed`，并把 `PytestCollectionWarning` 固化为错误门禁。
- Q12-01：已刷新后端 `53.46%` 与前端 statements `3.66%` 覆盖率基线；前端已建立初始多指标门禁和 CI 报告 artifact。
- Q12-02：认证、用例执行、计划调度和报告四个切片均已完成；前端 47 tests，coverage `4.44/4.88/3.01/4.66%` 并同步抬升门禁。
- Q12 review cleanup：pytest 收集拦截集中到 conftest 钩子（还原 17 个文件的 Test* 别名）、echarts 注册收敛到 chartTheme、run helpers 改命名路由并被 SuiteList 复用、e2e 共享 fixture 拦截未捕获页面异常、release-readiness 改跑 pytest 契约；前端 46 tests，门禁按余量策略微调为 `4.1/4.55/2.7/4.35%`。
- Q12-03：vue-i18n 升级 `11.4.6`、传递 glob override 到 `13.0.6`，clean install 零弃用告警；新增独立 i18n chunk。副作用：ant-design chunk 1502.45 kB 越过 1500 告警线，Q12-04 触发条件成立（阈值不抬，见 `docs/frontend-bundle-decision.md`）。
- Q12-04：Ant Design 改为 unplugin-vue-components 按需注册，chartTheme 移出 main.ts 入口依赖（echarts 不再进登录首屏）。实测 /login gzip 传输 773.9→510.1 kB（-34%），ant-design chunk 降至 1246.41 kB，构建告警消除。dts 类型生成暂关（会暴露约 112 处存量 a-* props 类型错误，单列加固项）。
- Q12 类型加固：dts 已开启（components.d.ts 提交入库），112 处存量类型错误全部修复；表格 record 用 asXxx 断言 helper、可空 v-model 用行内 as 断言、badge/回调签名收窄；4 个前端静态契约断言同步更新。
- Q12-05（本地部分）：新增 `docs/q12-external-readiness-evidence.md` 冻结两项外部证据的口径（SLO 历史：绝对日期窗口/逐 SLO 达成值/突破 triage/告警决定；真机演练：拓扑+doctor 输出+run 数据量+产物+通过标准），并加契约测试防漂移。剩余为纯环境依赖执行。
- 下一项：Q12-03 依赖弃用提示收敛。

---

## 13. 已知问题 / 注意事项

1. **Alembic 首次迁移**：目前用 `create_all` 兜底建表，正式环境建议执行：
   ```bash
   cd backend && alembic revision --autogenerate -m "init" && alembic upgrade head
   ```

2. **Android 设备连接**：Worker 可直接连接网络设备 `<device-ip>:5555`；如需复用宿主机 ADB server，设置 `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037`。Linux/Desktop/Kubernetes 差异及物理设备限制见 `docs/android-worker-connectivity-rehearsal.md`。

3. **WebSocket 鉴权**：WS 连接通过 URL `?token=access_token` 传递 JWT，ws.py 中已实现 `_get_ws_user()` + `_can_subscribe_run()` 权限校验

4. **MinIO 控制台**：开发时访问 `http://localhost:9001`（默认账号见 .env）

5. **Celery Flower 监控**：生产时访问 `http://localhost:5555`

6. **前端 nginx.conf**：`frontend/nginx.conf` 是容器内使用的，与 `docker/nginx.conf` 内容相同（由用户修改）
