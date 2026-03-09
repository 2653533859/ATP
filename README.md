# ATP

ATP（Automated Testing Platform）是一个面向团队协作的自动化测试平台，覆盖接口测试、Web UI 测试、Android UI 测试，以及套件编排、计划调度、执行报告和通知集成。

## 当前状态

- 当前仓库已经进入“可运行的 Phase 4”阶段，不再只是 PRD/规划稿。
- 前后端、任务调度、对象存储、通知集成、测试套件、测试计划等核心模块均已有实现。
- 本 README 与 `Task.md` 已按当前仓库实际实现状态同步；其中 `[~]` 表示基础能力已落地，但仍存在已知缺口。

## 已实现能力

### 基础平台

- 用户登录、JWT 鉴权、基于角色的权限控制
- 项目 / 模块 / 用例管理
- 环境管理与环境变量注入
- 执行记录查询、报告详情、WebSocket 实时状态推送
- `GET /health` 健康检查接口

### 测试类型与执行能力

- 接口测试：HTTP/REST、GraphQL、WebSocket、gRPC
- Web UI 测试：
  - pytest + Playwright 脚本模式
  - 低代码步骤模式
  - 截图、录像、报告展示
- Android UI 测试：
  - pytest + uiautomator2 脚本模式
  - 低代码步骤模式
  - 设备扫描、APK 管理、屏幕镜像

### 编排与集成

- 测试套件管理与执行
- 测试计划管理
- 手动触发、Cron 定时触发、Webhook 触发
- 计划执行记录查看
- 通知配置与测试发送：
  - SMTP 邮件
  - 企业微信机器人 Webhook
  - 钉钉机器人 Webhook
- CI/CD 集成：Webhook 触发、JUnit XML 导出、GitLab CI 示例文档

## 当前未完成 / 仍待完善

### 已实现但未完全收口

- 数据库迁移能力已存在，但首建流程仍保留启动时 `create_all` 兜底，尚未完全收敛为纯 Alembic 驱动
- 测试计划前端页面已实现，但 Cron 仍为文本输入，尚未做到可视化配置
- Android Worker 已内置 `adb` 与 Playwright/Chromium，但“通过容器稳定连接宿主机真机”的联调验证仍缺明确落地记录

### 尚未实现的功能

- 统计看板（聚合接口 + ECharts 页面）
- 内置 Mock Server 与规则管理页面
- 用例版本历史 / 回滚
- 报告导出为 HTML / PDF
- Jira / 禅道缺陷跟踪集成
- 敏感配置加密、接口限流、索引审查、大报告分页优化、Worker 资源隔离
- 结构化日志统一收集、截图/报告文件清理任务、一键部署脚本

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
uvicorn app.main:app --reload
```

### 测试

```bash
python -m pytest backend/tests -q
```

## 文档

- 当前进度与模块完成度：`Task.md`
- 产品需求与整体范围：`PRD.md`
- CI/CD 集成说明：`docs/cicd-integration.md`
- Windows 本地运行说明：`docs/windows-local-run.md`
- 前端到后端再到 Worker 的调用链：`docs/backend-request-flow.md`

## 说明

- 当前通知会在“测试套件”和“测试计划”执行完成后触发；单用例通知暂不在当前范围内。
- 前端已可构建运行，但生产包体积仍偏大，后续建议继续做代码拆分与按需加载优化。
