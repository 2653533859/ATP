# GitHub Actions 工作流说明

本文记录仓库当前 CI / E2E / integration / release readiness 工作流的触发条件、依赖服务和常见失败排查方式。

## `ci.yml` — 主 CI

- **触发**：push 到 `main`；针对 `main` 的 pull request。
- **Jobs**：
  - `Empty database migration`：启动干净 PostgreSQL 16，执行 `cd backend && alembic upgrade head`。
  - `Backend pytest`：启动 PostgreSQL 16 + Redis 7，运行 `python -m pytest backend/tests -q --ignore=backend/tests/integration`。
  - `Frontend type-check + build`：运行 `npm ci`、`npm run type-check`、`npm run build`。
- **依赖服务**：PostgreSQL、Redis；MinIO 相关能力在主 CI 里通过测试 stub 覆盖，真实 MinIO 放在 integration workflow。
- **常见排查**：
  - 迁移失败：先本地执行 `make infra-up && make migrate`，检查新增迁移的 `down_revision`、枚举、索引和约束是否能从空库创建。
  - 后端测试失败：确认失败用例是否属于真实基础设施测试；integration 用例应放在 `backend/tests/integration` 并带 `integration` marker。
  - 前端构建失败：先运行 `cd frontend && npm run type-check` 定位 TypeScript 错误，再运行 `npm run build` 验证产物。

## `test-integration.yml` — 真实基础设施集成测试

- **触发**：手动 `workflow_dispatch`；每日 UTC 03:17 定时。
- **范围**：`backend/tests/integration`，覆盖 auth、case-run、mock 等真实链路。
- **依赖服务**：PostgreSQL 16、Redis 7、MinIO 容器。
- **关键环境**：
  - `ATP_INTEGRATION_TESTS=1`
  - `CELERY_TASK_ALWAYS_EAGER=true`
  - `CELERY_TASK_EAGER_PROPAGATES=true`
- **常见排查**：
  - 服务未就绪：查看 `Wait for services` 步骤中 Postgres、Redis、MinIO 的健康检查输出。
  - 数据库结构异常：确认 `Run Alembic migrations` 已成功；失败时优先回到主 CI 的空库迁移 job 排查。
  - 任务未同步返回：确认测试期 Celery eager 变量没有被覆盖。

## `test-e2e.yml` — 前端 Playwright E2E

- **触发**：手动 `workflow_dispatch`；每日 UTC 03:43 定时。
- **范围**：`frontend/e2e`，使用 mock API 模式，不依赖真实后端。
- **依赖服务**：无外部服务；Playwright 会按 `frontend/playwright.config.ts` 启动前端 dev server。
- **Artifacts**：失败时上传 `frontend/playwright-report/`。
- **常见排查**：
  - 元素定位失败：优先下载 Playwright report，看截图、trace 和实际路由。
  - 本地复现：运行 `cd frontend && npm ci && npm run e2e`。
  - 首次环境缺浏览器：运行 `npm run e2e:install` 安装 Chromium 依赖。

## `release-readiness.yml` — 发布就绪检查

- **触发**：手动 `workflow_dispatch`；每日 UTC 19:37 定时。
- **Jobs**：
  - `Docker image build checks`：构建 backend、worker、frontend 镜像，并用 worker 镜像执行 `k6 version`。
  - `Release checklist contract`：检查 `docs/q9-release-checklist.md` 中仍包含迁移、Helm 和 performance 相关发布检查项。
- **依赖服务**：无外部服务；依赖 Docker build 上下文和 Dockerfile。
- **常见排查**：
  - 镜像构建失败：先本地执行 `docker build -t atp-backend:local backend/` 或对应 frontend / worker build。
  - worker k6 检查失败：确认 `backend/Dockerfile.worker` 中仍安装并暴露 k6。
  - checklist contract 失败：确认发布清单没有误删迁移、Helm 或性能压测相关步骤。

## 本地命令对照

| 目标 | 本地命令 |
| --- | --- |
| 空库迁移 | `make infra-up && make migrate` |
| 后端主回归 | `make test-backend` |
| 前端类型检查 + build | `make test-frontend-build` |
| 前端 E2E | `make test-frontend-e2e` |
| 集成测试 | `make test-integration` |
| Docker 发布构建抽查 | `docker build -t atp-backend:local backend/` |

本地 `make` 默认使用 `python3`；如虚拟环境命令不同，可使用 `make PYTHON=/path/to/python test-backend`。
