# ATP

ATP（Automated Testing Platform）是一个面向团队协作的自动化测试平台，覆盖接口测试、Web UI 测试、Android UI 测试，以及套件编排、计划调度、执行报告和通知集成。

## 当前状态

- 当前仓库已具备统一自动化测试平台的主线能力，不再是规划稿或仅验证单点功能的原型。
- 前后端、任务调度、对象存储、通知集成、测试套件、测试计划、报告导出、缺陷跟踪、统计看板、Mock 能力与 Android 联调说明均已落地。
- 当前剩余工作已从“主线功能缺失”转为“持续优化项”，例如 Android 环境稳定性验证、部署运维打磨与少量工程化尾项。

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

- 数据库迁移能力已存在，当前默认要求先执行 Alembic；仅在显式打开 `APP_AUTO_CREATE_TABLES=true` 时保留兜底建表
- Android 真机能力已具备 ADB 扫描、执行器、截图/镜像与 ADB over TCP 联调说明；若使用 Docker Worker，仍需结合宿主机网络环境完成最终连通验证
- 统计看板、Mock Server、用例版本历史、报告导出、缺陷跟踪等模块已落地基础能力，仍有若干体验、联调与工程化收口项待继续完善

### 已实现的增强能力

- 统计看板：后端聚合接口 + 前端 ECharts 页面，支持按项目、时间范围、用例类型筛选，并为高频查询增加短 TTL 缓存；新增执行人 Top、触发方式分布、计划/套件趋势
- 内置 Mock Server 与规则管理页面，支持路径模板匹配、条件响应、批量导入导出、最近请求日志、匹配缓存、响应模板、请求样本录制与规则版本号管理
- 用例版本历史 / 回滚
- 报告导出为 HTML / PDF，且支持单用例 / 套件 / 计划维度 JUnit XML 与 HTML/PDF 导出
- Jira / 禅道 / GitHub Issues 缺陷跟踪增强：连接测试、重复缺陷检测、截图附件上传、字段映射、状态同步、自动创建缺陷与页面联动展示
- 套件 / 计划运行结果展示增强：支持套件级 case run 明细查看、计划级自动缺陷结果展示
- 敏感配置加密、接口限流、索引审查、大报告分页优化、Worker 资源隔离
- 结构化日志统一收集、截图/报告文件清理任务、一键部署脚本
- Android 真机联调沉淀：执行前设备可达性校验、ADB over TCP 联调说明、Docker worker 连接建议
- 前端国际化基础能力：已接入 `vue-i18n`、语言切换与本地存储记忆；登录、导航、Dashboard、计划 / 套件 / 用例主列表、执行记录 / 执行详情、Android 专项任务，以及环境、通知、全局变量、AI 模型配置等系统页面已完成中英文文案迁移
- AI 自愈建议（iter5）：结构化定位 / 等待 / 断言 / 安全参数修复建议，人审应用、回归 run 关联与运行详情页预览采纳
- AI 用例生成：需求 / OpenAPI / cURL 输入生成可编辑草稿，生成→保存漏斗统计与质量权重 prompt 示例
- 性能压测中心：k6 脚本上传、独立 `performance` 队列与 worker、指标 / threshold / raw summary 展示、趋势与 run 对比、目标 allowlist 与 VUs / duration 限制
- 数据集 Dataset v2 治理：schema 字段校验、上传预览、soft / hard-block 策略、版本历史与回滚、引用影响面查询
- 用户偏好服务端持久化：Dashboard 布局等偏好同步到服务端并保留 localStorage 兜底
- AI 自愈采纳率报表：按用例类型 / 错误特征查看采纳率、生产反馈回归通过率与用例生成漏斗

> Q8/Q9 能力的设计与验收详见：`docs/implementation-plan-2026-Q8.md`、`docs/implementation-plan-2026-Q9.md`、`docs/q8-acceptance-summary.md`、`docs/q9-acceptance-summary.md`、`docs/dataset-v2.md`、`docs/performance-testing-thin-slice.md`、`docs/q9-release-checklist.md`。

### 当前仍建议继续完善的方向

- Android 真机在不同宿主机 / Docker 网络环境下的稳定性验证与排障经验沉淀
- 部署、运维与性能优化的持续打磨
- 前端 i18n 剩余页面迁移：用例详情与抽屉、Android 专项报告中心 / 详情、存储管理、缺陷跟踪配置，以及部分公共步骤编辑器
- 少量页面的工程化类型收口与体验细节优化

后续 i18n 执行拆分与验收标准见：`Task.md` 的 `5.10 Q3 前端国际化 i18n` 与 `docs/implementation-plan-2026-Q3.md` 的 `方向 F`。

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
python -m pytest backend/tests -q
```

## 文档

- 当前进度与模块完成度：`Task.md`
- 产品需求与整体范围：`PRD.md`
- CI/CD 集成说明：`docs/cicd-integration.md`
- Windows 本地运行说明：`docs/windows-local-run.md`
- Android 真机联调说明：`docs/android-device-debugging.md`
- 外部基础设施运行说明：`docs/external-infra-run.md`
- 前端到后端再到 Worker 的调用链：`docs/backend-request-flow.md`

## 持续集成

仓库已配置 GitHub Actions（`.github/workflows/ci.yml`），在 `push` 到 `main` 与 `pull_request` 时并行执行：

- **后端 pytest**：以 Postgres 16 + Redis 7 为 service container 运行 `backend/tests` 全量回归
- **前端 type-check + build**：`vue-tsc --noEmit` 与 `vite build` 双重保障类型与产物

同一分支的旧 CI 会自动取消，避免连续推送时的资源浪费。

## 说明

- 当前通知会在“测试套件”和“测试计划”执行完成后触发；单用例通知暂不在当前范围内。
- 前端已通过 `manualChunks` 把 `ant-design-vue`、`echarts`、`@ant-design/icons-vue`、`vuedraggable`、`monaco-editor` 拆为独立 chunk，按路由懒加载；首屏只载入用到的部分。后续若进一步追求体积，可改为 `ant-design-vue` 按需引入（需移除 `main.ts` 中的全局 `app.use(Antd)`）。
