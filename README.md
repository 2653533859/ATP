# ATP

ATP（Automated Testing Platform）是一个面向团队协作的自动化测试平台，覆盖接口测试、Web UI 测试、Android UI 测试，以及套件编排、计划调度、执行报告和通知集成。

## 当前状态

截至 2026-10-26，ATP 已实现统一自动化测试平台主线，v2.7.0 的 12 项研发任务在 [`Task.md`](Task.md) 中均已闭环。当前源码还包含 AutoDroid 对照计划的 A1/A2 接口改进与 M1/M2 Android 改进，代码和定向验证已完成，真实环境验收仍待补。功能、部署与未完成计划以 [`docs/project-status-2026-10-26.md`](docs/project-status-2026-10-26.md) 为当前入口，版本交付明细见 [`docs/v2.7.0-release-notes.md`](docs/v2.7.0-release-notes.md)。

最近的 Linux 生产现场记录是 2026-10-16 的 v2.7.0 割接：PostgreSQL 迁移至 `20261015_0081`、Helm revision 65，健康检查和两次真实 API 用例 Canary 通过。该记录不代表实时线上状态，也不证明后续提交已部署；详见 [`docs/evidence/linux-site-production-cutover-v2-7-0-2026-10-16.md`](docs/evidence/linux-site-production-cutover-v2-7-0-2026-10-16.md)。

## 已实现能力

- **平台主线**：用户认证与角色权限、项目/模块/用例管理、套件与计划调度、执行记录、报告、统计、通知、缺陷跟踪和 Mock 服务。
- **测试执行**：HTTP/REST、GraphQL、WebSocket、gRPC、Web UI、Android；脚本与低代码执行、截图/录像和报告展示。
- **智能与设备**：Hermes MCP 工具、视觉断言与定位自愈、Android 真机池与矩阵执行、iOS 设备资产与 WDA 会话自愈。
- **编排与可观测性**：多协议 DAG 工作流、数据流校验与单步调试，TraceContext 注入、Jaeger 瀑布图及异常归因。
- **治理与部署**：敏感数据脱敏、API Key 治理、灾备演练；Windows SQLite 单机模式与 Linux PostgreSQL/Redis/Celery/MinIO 服务器模式。

## 验收与后续工作

v2.7.0 发布时的 Ruff、格式检查、mypy、Bandit、专项测试和迁移头验证结果见发布说明。iOS 的 macOS/Xcode/WebDriverAgent/真机端到端环境仍须按 [`docs/ios-device-automation-plan.md`](docs/ios-device-automation-plan.md) 单独验收；其他外部服务和实时生产状态也需在目标环境复核。当前 `main` 没有 required status checks，CI 结果不会阻断推送，具体门禁和触发条件见 [`docs/ci-workflows.md`](docs/ci-workflows.md)。

## 项目结构

- `backend/`：FastAPI API、SQLAlchemy 模型、Celery 任务、执行器、服务层
- `frontend/`：Vue 3 + TypeScript 前端页面与交互
- `docker/`：容器相关补充资源
- `docs/`：设计与集成文档
- `backend/tests/`：后端 API / service / worker / migration 回归测试
- `Task.md`：按模块跟踪当前完成度
- `PRD.md`：产品范围与目标定义

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Ant Design Vue、Pinia、Vue Router、Monaco Editor
- 后端：FastAPI、SQLAlchemy Async、Alembic、Pydantic Settings
- 调度与基础设施：Celery、Redis、PostgreSQL、MinIO、Flower、Docker Compose
- 执行器：httpx、websockets、grpcio、pytest、pytest-json-report、Playwright、uiautomator2

## 快速开始

### 1. 准备配置

复制根目录配置文件：

```bash
cp .env.example .env
```

Windows PowerShell 可使用：

```powershell
Copy-Item .env.example .env
```

首次启动前请至少修改：

- `APP_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `FIRST_ADMIN_PASSWORD`

也可以登录前端后打开“系统管理 → 启动配置”快速编辑并下载 `.env`，详见 [`docs/startup-config.md`](docs/startup-config.md)。

数据库初始化默认走 Alembic，而不是应用启动时自动建表：

```bash
cd backend
alembic upgrade head
```

迁移、升级、回滚和 drift 排查流程见 `docs/migrations.md`。

只有在本地临时排障或首次手工引导且明确知道风险时，才建议短暂开启：

```env
APP_AUTO_CREATE_TABLES=true
```

#### 清理与存储治理（可选调整）

以下环境变量控制定期清理与告警，缺省值已是常规推荐：

- `FILE_RETENTION_DAYS` — 旧版统一保留天数；可被启用的 `StoragePolicy` 覆盖
- `RUN_CLEANUP_ENABLED` / `RUN_RETENTION_DAYS` / `RUN_CLEANUP_BATCH_SIZE` — 终态运行记录清理任务
- `STORAGE_ALERT_SIZE_GB` — MinIO bucket 总大小阈值（GB），超过时给管理员发站内通知；`0` 关闭告警
- `STORAGE_ALERT_INTERVAL_SECONDS` — 同一阈值告警最短间隔，默认 1 小时

如需邮件通知，还需配置：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_SSL`
- `SMTP_TLS`

### 2. 使用 Docker Compose 启动

```bash
docker compose up --build
```

启动后常用入口：

- 平台入口：`http://localhost`
- Flower：`http://localhost:5555`
- MinIO Console：`http://localhost:9001`

首次启动会根据 `.env` 中的 `FIRST_ADMIN_*` 自动创建管理员账号。

### 3. 复用外部 PostgreSQL / Redis / MinIO 启动

如果基础设施已经在外部环境运行，不要直接使用默认的 `docker-compose.yml`。仓库已提供只启动应用服务的 compose 文件：

```bash
docker compose -f docker-compose.app.yml up --build -d
```

说明见：`docs/external-infra-run.md`

## 本地开发

### 推荐路径：Docker Compose 一键启动

```bash
cp .env.example .env
make dev
```

等价命令：

```bash
docker compose up --build
```

如果本机使用旧版 Compose，也可以运行 `docker-compose up --build`。`Makefile` 会自动探测 `docker compose` / `docker-compose`；必要时可用 `make COMPOSE="docker compose" dev` 覆盖。

启动后常用入口：

- 平台入口：`http://localhost`
- Flower：`http://localhost:5555`
- MinIO Console：`http://localhost:9001`
- Jaeger UI：`http://localhost:16686`

### 本地直跑：基础设施走 Docker，应用进程本机启动

```bash
cp .env.example .env
make infra-up
make migrate
```

然后分别启动后端、Worker、Beat 和前端：

```bash
make backend
make worker
make beat
make frontend
```

本地直跑入口：

- 后端 API：`http://localhost:8000`
- 前端开发服务：`http://localhost:5173`
- MinIO Console：`http://localhost:9001`

停止基础设施：

```bash
make infra-down
```

### 环境变量校准

`.env.example` 覆盖后端、前端、Worker、PostgreSQL、Redis、MinIO、ADB、AI 自愈、性能压测、清理任务、备份和 OTel/Jaeger 的常用变量。首次启动前至少修改：

- `APP_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `FIRST_ADMIN_PASSWORD`
- `WEBHOOK_API_KEY`

生产或共享环境不要使用示例密码。

## 常用开发命令

### 前端

```bash
cd frontend
npm install
npm run dev
npm run type-check
npm run build
```

### 后端

```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### 测试

```bash
make test-backend
make test-frontend-build
```

更多测试命令：

| 场景 | 命令 | 说明 |
| --- | --- | --- |
| 后端单元 / 契约回归 | `make test-backend` | 跳过真实基础设施 integration 测试 |
| 前端类型检查 + 构建 | `make test-frontend-build` | 等价于 `npm run type-check && npm run build` |
| 前端 E2E | `make test-frontend-e2e` | 使用 Playwright，按 `frontend/playwright.config.ts` 启动 mock dev server |
| 集成测试 | `make test-integration` | 需要真实 PostgreSQL / Redis / MinIO，并设置 `ATP_INTEGRATION_TESTS=1` |
| 数据库迁移 | `make migrate` | 从当前库执行 `alembic upgrade head` |
| Release readiness | GitHub Actions 手动触发 `Release readiness` | 构建 backend / worker / frontend 镜像，并检查 worker 内置 k6 |

如本机 Python 命令不是 `python3`，可以用 `make PYTHON=/path/to/python ...` 覆盖；如 Compose 命令不同，可以用 `make COMPOSE="docker compose" ...` 覆盖。

## 文档

- 当前项目状态与验收边界：`docs/project-status-2026-10-26.md`
- 当前进度与模块完成度：`Task.md`
- 产品需求与整体范围：`PRD.md`
- 平台详细操作手册：`docs/user-operation-manual.md`
- CI/CD 集成说明：`docs/cicd-integration.md`
- GitHub Actions 工作流说明：`docs/ci-workflows.md`
- Windows 本地运行说明：`docs/windows-local-run.md`
- Android 真机联调说明：`docs/android-device-debugging.md`
- iOS 设备自动化与环境验收：`docs/ios-device-automation-plan.md`
- 外部基础设施运行说明：`docs/external-infra-run.md`
- 前端到后端再到 Worker 的调用链：`docs/backend-request-flow.md`

## 持续集成

仓库已配置 GitHub Actions（`.github/workflows/ci.yml`），主 CI 每周日北京时间 10:00 定时运行，也可手动触发；当前不会在 `push` 或 `pull_request` 时自动运行。主 CI 包括：

- **空库迁移校验**：从干净 PostgreSQL 16 执行 `alembic upgrade head`，防止迁移链断裂
- **后端 pytest**：以 Postgres 16 + Redis 7 为 service container 运行非 integration 回归、82% 覆盖率门禁及单文件独立扫描
- **前端测试、type-check 与 build**：运行 Vitest 覆盖率、`vue-tsc --noEmit` 与 `vite build`

真实基础设施 integration、Playwright E2E 与 release readiness 目前仅手动运行。`main` 未配置 required status checks；触发方式、依赖服务和排查建议见 `docs/ci-workflows.md`。

## 说明

- 当前通知会在“测试套件”和“测试计划”执行完成后触发；单用例通知暂不在当前范围内。
- 前端已通过 `manualChunks` 把 `ant-design-vue`、`echarts`、`@ant-design/icons-vue`、`vuedraggable`、`monaco-editor` 拆为独立 chunk，按路由懒加载；首屏只载入用到的部分。后续若进一步追求体积，可改为 `ant-design-vue` 按需引入（需移除 `main.ts` 中的全局 `app.use(Antd)`）。
