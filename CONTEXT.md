# ATP 项目开发上下文文档

> 本文档用于在新会话中快速恢复开发上下文，包含架构决策、已完成功能、关键代码位置、待续任务等。

**生成时间**: 2026-03-03
**最近同步**: 2026-07-05
**项目路径**: `/Users/parado/MyProject/ATP`
**参考文档**: `PRD.md`（需求文档）、`Task.md`（任务跟踪）

---

## 0. 当前进度快照（2026-07-05）

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

最近验证记录：

- `python3 -m pytest backend/tests/frontend -q`：78 passed
- `python3 -m pytest backend/tests/services/test_ai_case_parsers.py -q`：13 passed
- `python3 -m py_compile ...`：通过
- `npm run type-check`：通过
- `npm run build`：通过；仅保留已知 `ant-design-icons -> ant-design -> ant-design-icons` circular chunk 警告
- `python3 -m json.tool docker/grafana/dashboards/atp-overview.json`：通过
- `git diff --check`：通过

关键新增/更新文档：

- `docs/optimization-roadmap-2026.md`：当前项目进度来源，29/29 完成。
- `docs/ai-governance.md`：AI 模型、prompt、限额和降级治理。
- `docs/observability-guide.md`：Prometheus/Grafana 可观测性与 MinIO 指标。
- `docs/disaster-recovery.md`、`docs/backup-restore-drill-record.md`：数据库和对象存储备份恢复演练。
- `docs/domain-boundaries.md`、`docs/worker-lifecycle.md`、`docs/audit-log-policy.md`：架构、Worker、审计治理。

下一步建议：进入发布收口或 PR/提交整理阶段，优先做变更分组、最终集成测试、截图/运行证据归档和发布说明。

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

当前没有路线图内待实现任务。建议转入交付收口：

- 整理工作树变更，按阶段或能力拆分提交。
- 运行目标环境下的 integration / E2E / release readiness。
- 为关键前端能力补截图或录屏证据。
- 汇总发布说明、配置变更、迁移/回滚注意事项。
- 如果准备发 PR，优先附上本轮验证命令和已知 build warning。

---

## 13. 已知问题 / 注意事项

1. **Alembic 首次迁移**：目前用 `create_all` 兜底建表，正式环境建议执行：
   ```bash
   cd backend && alembic revision --autogenerate -m "init" && alembic upgrade head
   ```

2. **Android 设备连接**：Worker 容器需要访问宿主机 ADB，生产环境需在 docker-compose.yml 中开启 `network_mode: host`（已注释，需要时取消注释）

3. **WebSocket 鉴权**：WS 连接通过 URL `?token=access_token` 传递 JWT，ws.py 中已实现 `_get_ws_user()` + `_can_subscribe_run()` 权限校验

4. **MinIO 控制台**：开发时访问 `http://localhost:9001`（默认账号见 .env）

5. **Celery Flower 监控**：生产时访问 `http://localhost:5555`

6. **前端 nginx.conf**：`frontend/nginx.conf` 是容器内使用的，与 `docker/nginx.conf` 内容相同（由用户修改）
