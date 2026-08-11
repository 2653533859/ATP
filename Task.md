# ATP 项目任务跟踪

> Q18 最新开发计划、前后实现对比和剩余任务：[`docs/q18-latest-status-2026-08-07.md`](docs/q18-latest-status-2026-08-07.md)。

## 2026-08-07 AI generation context fixes

- [x] Limit Mock rules selected for one AI generation request to 20 and show a localized warning when the limit is exceeded.
- [x] Expand the Mock rule action column and enable horizontal scrolling so all row actions remain usable.
- [x] Persist the selected dataset version on AI-generated cases and load that immutable snapshot during parameterized execution.
- [x] Persist AI generation provenance in `_ai_source` (`dataset_id`, `dataset_version`, `mock_rule_ids`) and include the same context in generation audit events.

**最后更新**: 2026-08-10
**当前工作快照（2026-08-11）**: 本次已完成浏览器 HttpOnly Cookie 会话、WebSocket URL 脱敏、混合套件设备子任务队列隔离、启动配置 100 项对齐和 Windows/Cookie 冒烟脚本适配。后端非集成测试为 `1740 passed`，独立测试文件扫描为 `243 passed, 0 failed`，但覆盖率为 `80.45%`，低于 `82%` 门禁；当前质量状态与剩余任务见 [`docs/status-2026-08-11.md`](docs/status-2026-08-11.md)。
**平台分层（2026-08-10）**: Windows 是日常开发、Web/API/Android 联调和本地回归主线；Linux/Kubernetes 性能 Worker、真实设备池、macOS/iOS、专用浏览器 Worker、Prometheus 与外部通知属于目标环境开发/发布验收，不阻塞 Windows 日常开发。
**当前阶段**: Q1–Q12 路线图已全部完成；Q13 七个工作项中六个本地项全部完成；Q14 本地项已全部完成（Q14-01 Android/ADB 执行器族收口，Q14-02 API-router sweep，Q14-03 五个工作台页 mount tests，Q14-04 per-project retention real cleanup，Q14-05 gitleaks pre-commit，Q14-06 Q13 acceptance summary），并已发布 `docs/q14-acceptance-summary.md`。Q15 已完成 Q15-02（后端测试单文件可运行）、Q15-03（Windows CI job）、Q15-04（前端系统管理页面挂载测试）、Q15-05（worker/维护模块覆盖 + 门禁校准）、Q15-06（chartTheme 负载敏感）、Q15-07（Q14 acceptance summary），Q15-01 完成本地可做部分（服务端分支保护在当前 GitHub 套餐下不可得，已降级为本地钩子 + 文档约定并如实说明边界）。部署/灾备的仓库级配置也已收口：`make validate-deployment-readiness`、Helm 外部 Secret、ServiceMonitor、TLS 重定向和备份/恢复脚本契约已落地；校验器在 Windows 无 `sh`/`bash` 时会明确跳过 shell 语法检查，发布机可用 `--require-shell` 强制校验。真实集群部署、备份恢复和 smoke evidence 仍需外部环境。当前后端 TOTAL 为 **86.04%**（Python 3.12 / CI 口径；本地 Python 3.14 为 85.55%），门禁 **82**，`1467 passed`；前端 statements 为 **32.96%**（门禁 31.5，`128 passed`），`views/system` statements 为 **37.36%**。当前外部阻塞项为 Q15-00 / 原 Q14-00 / 原 Q13-00（Q12-05 生产 SLO 历史 + Android 真机演练采集）以及生产部署/灾备演练证据；对应模板已在 `docs/templates/` 固化，并提供 `make collect-q12-evidence` 自动查询 Prometheus、ATP API 和 ADB 后生成三份证据及附件，`make scaffold-q12-evidence` 仅作为草稿初始化，`make validate-q12-evidence` 做结构校验。覆盖工作累计发现并修复四个潜伏生产 500：grpc protobuf5、mobile-special create_task、ai_healing ProjectRole.engineer、global-variables create_variable（value_encrypted 重复关键字，变量库此前无法创建任何变量）。

**历史验证（2026-08-06）**: 当前工作区当时与 `origin/main` 同步至 `135906d`。以下 Q15 质量基线来自 2026-08-05 对验证提交 `87f0fc7` 的全量重跑；本次同步还包含 Q14 验收、部署/灾备仓库契约及相关回归测试，修改业务代码后需重新执行完整门禁。后端 `make test-backend-coverage` 在两个解释器下均通过门禁 82：Python 3.12（CI 口径）`1467 passed`、TOTAL `86.04%`；Python 3.14（本地 `backend/.venv`）`1467 passed`、TOTAL `85.55%`。**两者语句总数不同（13962 vs 13367，差 595 条、约 0.5 个百分点）**，抬门禁须以 3.12 为准并复验 3.14，口径说明见 `docs/coverage-baseline-2026-q13.md` 的 Interpreter note。`make test-backend-standalone` 为 `191 passed, 0 failed`（每个非 integration 测试文件单独可跑，防止测试间隐式耦合）。`make lint` / `make format-check`（381 文件）/ `make mypy`（76 源文件）全部通过；完整 pre-commit 链 8/8 通过（含 gitleaks）。`npm --prefix frontend run test:coverage` 为 `31 files / 128 tests passed`、statements `32.96%`、branches `27.81%`、functions `26.36%`、lines `34.04%`，`views/system` statements `37.36%`，门槛 31.5 / 26.5 / 24.5 / 32.5 通过。`npm run type-check` 与 `npm run build` 均通过。**门禁强制力如实说明**：`main` 无 required status checks（private 仓库 + 免费套餐，`branches/main/protection` 与 `rulesets` 均 403），CI 红绿只是通知，本地钩子可被 `--no-verify` 绕过，详见 `docs/ci-workflows.md`「门禁强制力现状」。Q12 自动采集器仍按既有留证通过定向回归（延迟取峰值、空窗口判为数据缺口、证据已存在时在采集前中止、`increase(...[1d])` 按实际统计日归档、整数计数不得被去零、凭据只认 `ATP_USERNAME`/`ATP_PASSWORD` 六条不变量）。历史验证：Docker Python 3.12 目标运行时、真实依赖 integration、前端 E2E、SLO 薄切、安全扫描与 GitHub runner 矩阵均按 Q10/Q11/Q13 文档留证。

**Q17 历史验证（2026-08-07）**：统一性能执行器、Locust worker 链路、gRPC Proto 动态编译及 Unary/Streaming 本地真实服务联调已完成；新增 `scripts/performance-environment-smoke.py`、外部环境验收 Runbook、Worker 镜像 grpc 依赖构建校验和专用 Worker metrics 健康探针。后端非集成回归 `1578 passed`，独立测试扫描 `210 passed, 0 failed`；前端 `36 files / 143 tests passed`，`npm run type-check` 和 `npm run build` 通过；后端覆盖率 `83.78%`（门禁 82）通过，Ruff、mypy（90 个源文件）、`git diff --check` 和部署 readiness 通过。Alembic head 为 `20260529_0044`。真实 Docker worker 镜像构建、Linux/Kubernetes Locust 压测和外部 gRPC 目标服务仍属于环境验收。

**下一步计划（2026-08-07）**:

- [x] Q17-02：gRPC Proto 动态编译、Unary/Streaming 并发、TLS/metadata 安全、取消、统一摘要和本地真实服务回归。
- [x] Q17-03：新增 `scripts/performance-environment-smoke.py`、外部验收 Runbook、Kubernetes/Docker Worker 镜像与容器 grpc 依赖检查、节点队列/allowlist 检查和专用 Worker metrics 健康探针；补充 ARM64 Docker Compose 隔离验收栈、`.env.performance-acceptance.example`、TLS gRPC/HTTP 目标和 Worker 挂载 CA 配置。
- [ ] Q17-04 环境验收：在 Linux/Kubernetes 专用 performance worker 构建并启动包含 grpcio/grpcio-tools 的镜像，使用真实 TLS 和外部 gRPC/Locust 目标服务完成 smoke、取消、节点 allowlist 与资源采样验证。
- [ ] 发布收口：依据环境验收证据更新 `docs/performance-executor-evaluation.md`、部署 runbook 和 release/PR 说明；若目标服务或证书未准备好，保留为明确的外部环境阻塞项。

## Q18 能力扩展入口（2026-08-07）

- [x] 开发计划：`docs/implementation-plan-2026-Q18-capability-expansion.md`。
- [x] 能力基线与前后对比：`docs/capability-baseline-2026-08-07.md`。
- [~] Q18-API：Cookie、multipart、XML/XPath、JSON Schema 资产、SSE、OpenAPI/Swagger/Postman 导入、受限前后置动作、统一结果契约、场景编排、受控数据集组合、事务导入、Provider/Consumer 契约资产 CRUD/版本化及 `/system/api-contract-assets` 管理/比较 UI 已完成；外部/远程 `$ref` 已支持 warn/reject 发布策略，真实联调和高级认证仍待补。
- [~] Q18-Windows：Windows 本地启动、远端 PostgreSQL/Redis/MinIO、PowerShell 进程托管、Playwright/ADB、本地回归入口、`local-dev.cmd doctor`、PowerShell Android 网络诊断和全量本地冒烟已具备；冒烟实测通过真实健康/登录/认证读接口、Playwright 9 项、Chromium/Firefox/WebKit 页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务，Android 扫描与 Web 低代码真实下载仍需真实设备/页面数据，k6/Locust/JMeter 是否安装按本机实际使用场景处理。
- [~] Q18-Web：多浏览器配置、Trace、网络/Console 摘要、元素库/POM CRUD 与执行、绑定项目录制自动写入资产、文件操作、视觉回归、浏览器矩阵和定位器修复建议已完成；本地 Chromium/Firefox/WebKit 页面烟测已补齐，真实 Firefox/WebKit Worker 和关键 UI/E2E 仍待补。
- [~] Q18-Mobile：Android 设备租约、标准安装/卸载/清理/启动、录屏、设备日志、系统动作和兼容性矩阵已完成；iOS/Appium 的设备/IPA 资产、租约、专用队列、W3C Worker 和统一结果已完成本地实现；真实设备池并行、macOS/XCUITest、iOS 外部系统事件仍待补。
- [~] Q18-Performance：自动阶梯、目标服务指标、JMeter 非 GUI/JTL/HTML、多节点分片聚合、容量分析和性能通知摘要已完成代码实现；真实 Prometheus、节点镜像、外部通知渠道和性能验收仍待补。
- [~] Q18-验收：本地后端非集成 1724 项、前端全量 37 文件/146 测试、Playwright E2E 9 项、迁移、mypy 120 源文件、Ruff、Bandit、pip-audit、npm audit、类型检查/构建和文档已通过；真实设备、真实性能节点、外部服务和真实 API 联调仍待环境验收。

**Q18 下一阶段计划（2026-08-10）**：

- [~] Q18-Windows：启动前检查、性能执行器检测、Android PowerShell 网络诊断和全量本地冒烟已完成；`scripts/windows-local-smoke.ps1` 已归档脱敏 JSON 证据，剩余 Android 扫描与 Web 低代码真实下载场景。
- [ ] Q17-04：在 Linux/Kubernetes 隔离栈完成性能 Worker 镜像、Locust/gRPC/TLS 目标、取消、节点 allowlist、资源采样和 JMeter 外部验收。
- [ ] Q18-API：使用真实 Provider/Consumer 规格完成契约比较联调，并补齐 OAuth2/Digest 等高级认证的需求评审与实现。
- [ ] Q18-Web：在专用 Worker 上验收 Firefox/WebKit、Trace、网络/Console、文件操作和视觉回归，并补充关键 UI/E2E。
- [ ] Q18-Mobile：准备 Android 设备池和 macOS iOS/Appium 环境，完成租约并发、矩阵、录屏、系统动作及 iOS 最小闭环验收。
- [ ] Q18-Performance：接入真实 Prometheus、外部通知渠道和多节点压测结果，归档带日期的性能基线与回归证据。
- [ ] 发布收口：将真实环境证据同步到 Q18 状态、性能 Runbook、部署文档和发布说明；在证据缺失前保持“部分实现/待验收”标记。

- [x] P0：整理提交 / PR 范围，按主题拆分当前大 diff：环境与依赖兼容、权限与缺陷联动、AI 诊断/治理、前端体验与文档进度。
- [x] P0：在 CI 或 Docker/目标 Python 3.12 环境复跑后端回归，确认 Python 3.14 条件 pin 不影响目标运行时。
- [x] P0：补跑前端质量命令：`npm run type-check`、`npm run build`，必要时补关键页面截图或构建日志。
- [x] P1：做最终 code review pass，重点检查新增权限边界、审计日志提交次数、AI 调用降级、依赖版本条件与 Makefile setup 兼容性。
- [x] P1：归档发布证据：测试命令、通过结果、已知 warnings、环境准备说明，并同步到 PR 描述 / release notes。
- [x] P2：进入 Q10 Phase 5 收口，ruff 最小 lint/format 门禁、pytest-cov 覆盖率基线、前端 Vitest 两批测试、Bandit SAST、依赖漏洞扫描清零、Gitleaks/Trivy/Dependabot security workflow 与目标 Docker Python 3.12 回归已落地；下一步按以下顺序推进：
  1. [x] 集成测试：`suite-run` / `plan-trigger` / `notification` / `bug-report` 已补齐并在真实 Postgres / Redis / MinIO 环境跑通。
  2. [x] E2E：suite / plan 前端关键路径已覆盖加载、触发执行、查看记录，完整 Playwright E2E 为 `9 passed`。
  3. [x] SLO：已补 API 可用性、P95、run 成功率 3 条薄切指标与错误预算面板。
  4. [x] 收口：flaky 治理、`docs/q10-acceptance-summary.md`、README / Task.md / release evidence 最终同步已完成。
- [x] P2：Q11 全部完成；Android Worker ADB 控制路径、host-network 约束和安全诊断方式已形成实测/文档/静态契约证据，物理真机 shell 验收明确保留为外部环境项。
- [x] Q16-06：性能压测执行控制已补齐，包含 `cancelling` 状态、Redis 取消信号、k6 子进程安全终止、前端状态轮询与进度展示；后端 52 项定向回归通过，当前完整非集成回归 `1507 passed`，前端 `36 files / 142 tests passed`，type-check 与生产构建通过。
- [x] Q16-07：新增性能压测 JSON/CSV 报告导出、脱敏快照、阈值门禁摘要与前端门禁状态展示；相关后端 54 项、前端报告工具 2 项回归通过。
- [x] Q16-08 已完成：基线对比、定时执行和 CI 阈值门禁。

> 状态说明：
> - `[ ]` 待开始
> - `[~]` 进行中
> - `[x]` 已完成
> - `[-]` 已跳过/暂缓
>
> 文档同步说明：本文件已按当前仓库实现状态更新；`[~]` 表示基础能力已落地，但仍有明确缺口或尚缺联调/工程化收口。

---

## Phase 1 - 基础框架（MVP）

> 目标：跑通完整主流程，接口测试用例能够配置 → 执行 → 看报告

### 1.1 工程初始化

- [x] 创建 `docker-compose.yml`，包含 PostgreSQL / Redis / MinIO 服务
- [x] 创建 `.env.example`，定义所有必要环境变量
- [x] 初始化 FastAPI 后端项目结构（`backend/`）
- [x] 初始化 Vue 3 + TypeScript 前端项目结构（`frontend/`）
- [x] 配置前端开发代理，解决跨域问题
- [x] 配置 Nginx，托管前端静态资源并反代后端 API

### 1.2 数据库与 ORM

- [x] 配置 SQLAlchemy 2.x async 连接 PostgreSQL
- [x] 配置 Alembic 数据库迁移工具
- [x] 创建核心数据表：`User`、`Role`
- [x] 创建项目结构数据表：`Project`、`Module`、`TestCase`
- [x] 创建执行相关数据表：`TestRun`、`CaseResult`、`StepResult`
- [x] 创建环境相关数据表：`Environment`、`EnvVariable`
- [x] Alembic 迁移文件、迁移回归测试、Docker Compose migrate 服务与 Helm 迁移 Job 已补齐；首建流程统一为 Alembic 驱动，`create_all` 仅保留在显式本地排障开关中

### 1.3 用户认证

- [x] 实现用户注册/登录接口（`POST /api/v1/auth/login`）
- [x] 实现 JWT Token 签发与验证中间件
- [x] 实现 Token 刷新接口（`POST /api/v1/auth/refresh`）
- [x] 实现基于角色的权限控制（RBAC）依赖注入
- [x] 前端：实现登录页面（用户名/密码）
- [x] 前端：实现 HttpOnly Cookie 会话、自动携带凭据与 CSRF 请求头（Bearer 仍兼容外部 API 客户端）
- [x] 前端：实现未登录自动跳转登录页（路由守卫）

### 1.4 项目/模块/用例 CRUD

- [x] 实现项目管理接口（增删改查）
- [x] 实现模块管理接口（树形结构，支持嵌套）
- [x] 实现用例基础 CRUD 接口
- [x] 实现接口用例详情表（`ApiTestCase`）的存储与查询
- [x] 前端：项目列表页面
- [x] 前端：模块树形目录组件
- [x] 前端：用例列表页面（支持按模块过滤）
- [x] 前端：接口用例创建/编辑表单（URL、Method、Headers、Body、断言）
### 1.5 接口测试执行器（HTTP REST）

- [x] 搭建 Celery + Redis 任务队列基础框架
- [x] 实现 HTTP 接口测试执行器（基于 `httpx`）
  - [x] 发送请求（GET / POST / PUT / DELETE / PATCH）
  - [x] 支持 Headers、Query Params、JSON Body、Form Body
  - [x] 支持 Basic Auth / Bearer Token 认证
  - [x] 实现断言逻辑（状态码 / JSONPath / 响应头 / 响应时间）
  - [x] 实现变量提取（从响应 JSONPath 提取，存入上下文）
- [x] 实现执行任务触发接口（`POST /api/v1/cases/{id}/run`）
- [x] 实现执行结果写入数据库
- [x] 实现 WebSocket 推送执行状态到前端

### 1.6 执行报告（基础版）

- [x] 前端：执行记录列表页面
- [x] 前端：单次执行报告页面（总览 + 用例列表 + 步骤详情）
- [x] 前端：WebSocket 接收实时执行状态并更新 UI
- [x] 实现执行记录查询接口（`GET /api/v1/runs/{id}`）

### 1.7 环境管理

- [x] 实现环境 CRUD 接口（开发/测试/预发/生产）
- [x] 实现环境变量的存储与查询
- [x] 接口测试执行时注入环境变量（URL 前缀替换、变量占位符解析）
- [x] 前端：环境管理页面

---

## Phase 2 - Web UI 测试

> 目标：支持 Playwright + pytest 脚本的上传、执行与报告展示

### 2.1 脚本存储

- [x] 配置 MinIO 客户端（Python `minio` SDK）
- [x] 实现脚本文件上传到 MinIO（`POST /api/v1/cases/{id}/script`）
- [x] 实现脚本文件下载/预览接口
- [x] 前端：集成 Monaco Editor 在线代码编辑器
- [x] 前端：脚本上传与在线编辑页面

### 2.2 Playwright 执行器

- [x] 在 Worker Docker 镜像中安装 Playwright + Chromium
- [x] 实现 pytest 脚本执行器
  - [x] 从 MinIO 下载脚本到临时目录
  - [x] 调用 `pytest --json-report` 命令执行
  - [x] 解析 `pytest-json-report` 结果，映射到平台数据结构
  - [x] 收集失败截图，上传到 MinIO
  - [x] 清理临时目录
- [x] 实现执行配置：浏览器类型 / 无头模式 / 分辨率 / 超时
- [x] 修复脚本模式回归问题（pytest 超时参数、Monaco 双向绑定、浏览器选项约束、MinIO bucket 自动初始化）

### 2.3 Web 用例低代码模式

- [x] 设计步骤数据结构（操作类型 + 参数）
- [x] 实现低代码用例存储接口
- [x] 支持操作：跳转 URL / 点击 / 输入 / 断言文本 / 断言元素可见 / 等待 / 截图
- [x] 前端：步骤配置表单（可拖拽排序）
- [x] 实现低代码用例 → Playwright API 调用的执行器

### 2.4 报告增强（截图/录像）

- [x] 执行报告中展示每个步骤的截图
- [x] 支持失败步骤高亮
- [x] 支持 Playwright 录像（`.webm`）上传与播放

---

## Phase 3 - Android UI 测试

> 目标：支持 uiautomator2 + pytest 脚本执行，真机设备管理

### 3.1 设备管理

- [x] 实现 ADB 设备扫描服务（`adb devices` 定期轮询）
- [x] 实现设备 CRUD 接口（`GET /api/v1/devices`）
- [x] 实现设备状态监控（在线/离线，Celery Beat 定时扫描）
- [x] 前端：设备列表页面（显示设备名、系统版本、状态）

### 3.2 APK 管理

- [x] 实现 APK 文件上传到 MinIO
- [x] 实现 APK 版本管理接口（关联项目，支持多版本）
- [x] 前端：APK 管理页面（上传、列表、删除）

### 3.3 uiautomator2 执行器

- [x] Worker 容器侧已安装 `adb`，执行前新增设备可达性校验，并补齐 ADB over TCP 真机联调说明；通过 `app.services.adb_resilience` 抽象层（自动 disconnect/connect 重连 + 心跳监控 + 命令重试）消化宿主网络与设备抖动，4 个执行器（android / perf / stability / fluency）统一接入
- [x] 实现 Android pytest 脚本执行器
  - [x] 从 MinIO 下载脚本到临时目录
  - [x] 自动安装 APK 到目标设备
  - [x] 调用 `pytest --json-report` 执行
  - [x] 解析结果，收集截图上传 MinIO
  - [x] 清理临时目录
- [x] 实现执行配置：设备选择 / APK 版本 / 超时

### 3.4 设备屏幕镜像

- [x] 实现 MJPEG 截图流（后端定期调用 `uiautomator2.screenshot()` 推流）
- [x] 前端：嵌入屏幕镜像视频流组件

### 3.5 Android 低代码模式

- [x] 支持操作：点击坐标 / 点击元素（text/resourceId/xpath）/ 长按 / 滑动 / 输入 / 截图断言
- [x] 前端：步骤配置表单
- [x] 实现低代码步骤 → uiautomator2 API 调用的执行器

---

## Phase 4 - 高级功能

### 4.1 接口测试协议扩展

- [x] **GraphQL**：支持 Query / Mutation，变量配置，断言
- [x] **WebSocket**：建立连接 / 发送消息 / 接收断言 / 超时配置
- [x] **gRPC**：上传 `.proto` 文件，方法调用，响应断言

### 4.2 测试套件

- [x] 实现 `TestSuite` CRUD 接口
- [x] 支持跨类型用例组合（Web + 接口 + Android）
- [x] 支持套件内用例顺序配置
- [x] 支持套件级数据驱动（CSV / JSON 参数化）
- [x] 实现套件执行触发接口（`POST /api/v1/suites/{id}/run`）
- [x] 前端：套件管理页面

### 4.3 测试计划与调度

- [x] 实现 `TestPlan` CRUD 接口
- [x] 配置 Celery Beat，支持 Cron 表达式定时触发
- [x] 实现手动触发 / 定时触发 / Webhook 触发三种模式
- [x] 前端：测试计划配置页面已实现（创建/编辑/执行/记录查看），并已支持半可视化 Cron 配置、表达式校验与可读化提示

### 4.4 CI/CD 集成

- [x] 实现 Webhook 触发接口（`POST /api/v1/webhook/trigger`，API Key 认证）
- [x] 测试结果支持 JUnit XML 格式导出（供 Jenkins 解析）
- [x] 提供 GitLab CI `.gitlab-ci.yml` 模板示例
- [x] 编写 CI/CD 集成文档

### 4.5 通知集成

- [x] 实现邮件通知（SMTP，执行完成后发送报告摘要）
- [x] 实现企业微信机器人通知
- [x] 实现钉钉机器人通知
- [x] 前端：通知配置页面
- [x] 限制通知读接口为工程师权限，避免泄露 Webhook/Secret
- [x] 在企业微信/钉钉返回非 200 或非零 `errcode` 时抛错，避免误报发送成功
- [x] 删除项目时级联删除通知配置，避免外键阻塞项目删除

### 4.6 统计看板

- [x] 实现统计数据聚合接口（总览、通过率趋势、执行时长趋势、失败 Top 10、执行人 Top、触发方式分布、计划/套件趋势）
- [x] 前端：统计看板页面（折线图 / 柱状图，基于 ECharts + vue-echarts）
- [x] 支持按项目、时间范围、用例类型筛选

---

## Phase 5 - 完善与优化

### 5.1 接口 Mock Server

- [x] 实现 MockRule 数据模型与 Alembic 迁移（`mock_rules` 表）
- [x] 实现 Mock 规则 CRUD 接口（`/api/v1/mock-rules`）
- [x] 实现 Mock 服务入口（`ANY /mock/{project_id}/{path}`，数据库实时匹配）
- [x] 前端：Mock 规则管理页面（规则表格 + 创建/编辑 Modal）
- [x] 前端：显示 Mock 服务基地址，方便复制使用

### 5.2 用例版本历史

- [x] 实现用例修改历史记录（快照存储）
- [x] 实现用例版本回滚接口
- [x] 前端：版本历史查看与回滚页面

### 5.3 报告导出

- [x] 支持执行报告导出为 HTML（内嵌截图）
- [x] 支持执行报告导出为 PDF
- [x] 支持单用例 / 套件 / 计划执行结果导出为 JUnit XML

### 5.4 缺陷跟踪集成（可选）

- [x] Jira 集成：失败用例一键创建 Issue
- [x] 禅道集成：失败用例一键创建 Bug
- [x] 敏感配置脱敏返回与落库加密基础能力

### 5.5 安全与性能

- [x] 敏感配置加密存储（环境变量中的密码、Token）
- [x] API 接口限流
- [x] 数据库查询优化（索引审查）
- [x] 大报告分页加载优化
- [x] Worker 资源隔离（防止单任务耗尽资源）

### 5.6 运维支持

- [x] 日志统一收集（结构化日志输出）
- [x] 健康检查接口（`GET /health`）
- [x] 截图/报告文件定期清理任务（超过保留期限自动删除）
- [x] 一键部署脚本与初始化数据（管理员账号、默认环境）

### 5.7 统一用例管理体验

- [x] 设计统一用例管理模块，支持在单页内切换项目、查看模块树、管理用例与直接执行
- [x] 后端用例列表接口支持按 `project_id` 过滤，满足统一页面按项目聚合查询
- [x] 前端新增独立的“用例管理”导航入口，并兼容项目页/看板跳转
- [x] 统一用例管理页支持项目选择、模块筛选、用例 CRUD、历史回滚入口与执行环境选择
- [x] 修复统一入口下模块树与 Android 用例编辑的项目上下文依赖，完成本地与部署验证

### 5.8 已完成的收口工作

- [x] 测试计划体验收口：Cron 可视化配置、表达式校验、可读化提示
- [x] Android 真机容器联调说明与前置校验补齐
- [x] 套件 / 计划级 HTML / PDF 报告导出
- [x] 缺陷跟踪附件上传、重复缺陷检测、连接测试、字段映射、状态同步、GitHub Issues 集成与执行详情页联动展示
- [x] 统计看板缓存与筛选维度补齐（执行人、触发方式、计划/套件趋势、case_type 联动）
- [x] Mock 条件响应、批量导入导出、缓存加速、响应模板、请求样本录制与规则版本号管理
- [x] 计划级自动缺陷结果展示、套件级 case run 明细展示与 Run / Suite / Plan 三层体验收口
- [x] 为新增的 Mock、缺陷跟踪、统计缓存、Android 前置校验补关键回归测试

### 5.9 后续可选优化项

- [x] Android 真机在不同宿主机 / Docker 网络环境下的稳定性验证沉淀（`docs/android-device-debugging.md` 新增"宿主网络与 Docker 环境差异"专章 + `scripts/android-network-doctor.sh` 一键诊断脚本）
- [x] Android 真机执行链路抖动自愈（`backend/app/services/adb_resilience.py` 抽象层：自动 disconnect/connect 重连 + 异步心跳监控 + 命令级重试；android / perf / stability / fluency 4 个执行器统一接入；可经 `ADB_RECONNECT_*` / `ADB_HEARTBEAT_*` 配置开关一键关闭）
- [x] 部署、运维与性能优化的持续打磨（Q7 Phase 3 已完成 Celery 队列 routing + 文档、慢查询 Grafana 面板、K8s resources 模板、worker 多阶段镜像优化；实际镜像体积与执行器冒烟需在 Docker 环境复验）
- [x] 少量页面残余 `any` / 宽类型结构的工程化收口（P1.6 批 1-4 已完成；`frontend/src` 除 locale 文案 key `any_method` 外无显式 any）

### 5.10 Q3 前端国际化 i18n

> 目标：在不影响现有布局与交互的前提下，支持中英文切换，并逐步移除前端页面硬编码中文文案。

- [x] `vue-i18n` 基础设施、语言切换与本地存储记忆已接入
- [x] 登录页、导航栏、通用按钮、Dashboard、计划列表已迁移
- [x] 套件列表已迁移：`SuiteList.vue` 的列表、批量操作、执行记录列、执行策略标签与错误提示已接入 `t(...)`
- [x] 用例主列表已迁移：`CaseList.vue` 的筛选、统计卡、批量导入/导出/移动、执行环境弹窗、工作流操作与消息提示已接入 `t(...)`
- [x] 执行记录与执行详情已迁移：`RunList.vue` / `RunDetail.vue` 的导出、步骤统计、截图/请求/响应区、缺陷创建弹窗、缺陷状态刷新与分页文案已接入 `t(...)`
- [x] Android 专项任务页已迁移：`SpecialTaskListView.vue` 的任务筛选、表格列、任务表单、调度配置与执行/删除消息已接入 `t(...)`
- [x] 系统管理部分页面已迁移：环境管理、通知配置、全局变量库、AI 模型配置已接入中英文文案
- [x] 本轮迁移已通过 `npm run type-check`（`vue-tsc --noEmit`）
- [x] 设备管理、APK 管理、Mock 服务已迁移：`DeviceList.vue`、`ApkList.vue`、`MockRuleList.vue` 的筛选、表格、弹窗、状态标签与消息提示已接入中英文文案
- [x] 项目列表与计划表单已迁移：`ProjectList.vue`、`PlanList.vue` 的项目卡片、AI 模型绑定、计划表单、Cron 配置、执行策略与消息提示已接入中英文文案
- [x] 后端通知模板 i18n 化：`services/notifier.py` 支持语言参数，通知配置增加语言字段
- [x] 英文文案复核：对业务术语、错误提示和 AI 生成相关提示进行二次校对（轻量 review pass 已完成；2026-05-21）

#### 后续执行计划

建议按页面耦合度和风险分批推进，单批完成后均执行 `npm run type-check`：

1. [x] 用例详情与历史批次：`CaseDetail.vue`、`CaseHistoryDrawer.vue` 已迁移，详情页、复制/评审/执行弹窗、版本对比与回滚提示已接入中英文文案，并通过 `npm run type-check`。
2. [x] 用例编辑抽屉批次：`AIGenerateDrawer.vue`、`WebCaseDrawer.vue`、`AndroidCaseDrawer.vue` 已迁移，AI 生成流程、Web 脚本/低代码配置、Android 配置表单主要可见文案已接入 locale，并通过 `npm run type-check`。
3. [x] Android 专项报告批次：`ReportCenterView.vue`、`ReportDetailView.vue` 已迁移，报告筛选、统计卡、趋势图图例、异常事件、报告文件、导出/下载提示已接入中英文文案，并通过 `npm run type-check`。
4. [x] 系统设置剩余批次：`StorageManagementView.vue`、`BugTrackerList.vue` 已迁移，存储策略、清理预览、缺陷跟踪表单、连接测试和删除确认已接入中英文文案，并通过 `npm run type-check`。
5. [x] 公共组件批次：`LowcodeStepEditor.vue`、`AndroidStepEditor.vue`、`ModuleTree.vue`、`KvEditor.vue`、`CaseStepEditor.vue`、`BatchOperationBar.vue` 已迁移，复用按钮、占位符、步骤类型、模块弹窗文案已接入 locale，并通过 `npm run type-check`。
6. [x] 后端通知模板批次：通知配置已增加语言选项，`services/notifier.py` 可根据配置生成中英文通知标题与正文；邮件、企业微信、钉钉通知均可按配置语言发送，并通过通知相关后端测试。
7. [x] 设备 / APK / Mock 批次：`DeviceList.vue`、`ApkList.vue`、`MockRuleList.vue` 已迁移，筛选、表格列、创建/编辑弹窗、状态标签、导入导出、屏幕镜像与消息提示已接入 locale；目标文件扫描无中文命中，并通过 `npm run type-check`。
8. [x] 项目 / 计划补齐批次：`ProjectList.vue`、`PlanList.vue` 已迁移，项目卡片、AI 模型绑定、计划表单、Cron 编辑器、Webhook Secret、执行策略和消息提示已接入 locale；目标文件扫描无中文命中，并通过 `npm run type-check`。
9. [x] 文案复核批次：已完成 `SuiteList.vue` 与 `CaseFormDrawer.vue` 迁移，套件表单/弹窗/抽屉、用例表单 4 类 case_type 配置均已接入 locale；已执行 `rg "[一-龥]" frontend/src/views frontend/src/components` 收口扫描，剩余中文仅限开发注释与 `RunDetail.vue` 后端错误字符串匹配（`认证` / `超时` / `不存在`），无剩余可见中文 UI 文案。

---

## 里程碑汇总

| 里程碑 | 完成条件 | 状态 |
|--------|---------|------|
| **M1** Phase 1 完成 | HTTP 接口测试用例可完整执行并看到报告 | `[x]` |
| **M2** Phase 2 完成 | Playwright 脚本可上传执行，报告含截图 | `[x]` |
| **M3** Phase 3 完成 | 真机连接，uiautomator2 脚本可执行 | `[x]` |
| **M4** Phase 4 完成 | 支持调度、套件、CI/CD 集成、看板 | `[x]` |
| **M5** Phase 5 完成 | 全功能上线，安全加固 | `[x]` |

---

## Phase 4.6 统计看板 — 后续优化计划

> 以下为统计看板的迭代优化项，按优先级排列，可在 Phase 5 或后续迭代中逐步实施。

### P0 - 体验完善（建议优先）

- [x] 看板空状态引导：无数据时显示引导提示（"还没有执行记录，去创建用例吧"）
- [x] 图表 Loading 状态：数据加载中显示骨架屏或 Spin
- [x] 通过率趋势补零：无执行的日期也在 X 轴显示（值为 0），避免折线断裂
- [x] 失败 Top 10 点击跳转：点击柱状图某条目可跳转到对应用例详情页
- [x] 响应式布局：小屏/平板下卡片和图表自适应宽度

### P1 - 维度扩展

- [x] 按用例类型（API / Web / Android）分组统计饼图 — Q5 长尾 1 收口；`GET /statistics/case-type-distribution`（按 case_type 分组返回 total/passed/failed/error/pass_rate + 5min cache）+ `DashboardView` 新增 LazyChartCard 饼图（pie 含详细 tooltip）

### P2 - 性能优化

- [x] 高频查询加 Redis 缓存：statistics 已有 5 分钟缓存；dataset list 与 mobile statistics 已补 60 秒 TTL 自然失效缓存
- [x] `test_runs` 表添加复合索引：`(status, created_at)` 和 `(case_id, status, created_at)` — Q5 长尾 2 收口；alembic 0029 新增 `ix_test_runs_case_id_status_created_at`，与 0015 的 `(status, created_at)` 互补
- [x] 看板数据按需加载：首屏只加载总览和通过率趋势，其余图表通过 `LazyChartCard` + `IntersectionObserver` 滚动到可视区再请求
- [x] 大时间跨度（> 90 天）自动切换为按周聚合：前端 days > 90 时传 `aggregate=weekly`，后端 4 个 trend 端点用 PostgreSQL `date_trunc('week', ...)` 聚合

### P3 - 高级功能

- [x] 看板数据导出：支持图表导出 PNG 图片与统计数据 CSV
- [x] 自定义看板：用户可选择显示/隐藏图表卡片，自定义排序并持久化到 localStorage
- [x] 项目级看板 vs 全局看板切换：Dashboard 支持全局/单项目 segmented 切换，单项目模式显示项目下拉并记忆选择，全局模式不传 project_id
- [x] 通过率/时长异常告警：支持项目级告警规则/事件、定时检查、通知触发、抑制窗口、规则配置页和 Dashboard 项目级告警提示

---

## Phase 5.1 Mock Server — 后续优化计划

> 以下为 Mock Server 的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 规则快速复制：一键复制已有规则，修改路径/响应即可
- [x] 响应体语法高亮：monospace 等宽字体 + JSON 格式化按钮
- [x] Mock 请求日志：记录最近 N 次命中 Mock 服务的请求（method/path/timestamp），方便调试
- [x] 路径模板支持：支持 `/api/users/{id}` 形式的路径参数匹配

### P1 - 功能增强

- [x] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则（D.2 - `POST /mock-rules/{id}/promote-sample`）
- [x] Mock 规则版本管理：规则修改历史，支持回滚（D.2 - `MockRuleSnapshot` 表 + 列表/回滚 API）

### P2 - 高级功能

- [x] 独立端口模式：可选将 Mock 服务运行在独立端口，URL 不带 `/mock/` 前缀 — P1.3 Q5 收口；`backend/app/mock_main.py` 独立 FastAPI 子应用 + `docker-compose.yml` 中 `mock-standalone` service（profile=`mock-standalone`），裸路径 `/{project_id}/{path}`
- [x] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则
- [x] Mock 规则版本管理：规则修改历史，支持回滚

---

## Phase 5.2 用例版本历史 — 后续优化计划

> 以下为用例版本历史的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 快照详情展开/折叠 config JSON 内容，便于查看完整配置差异
- [x] 版本对比：选择两个版本进行 diff 可视化（name/description/tags/config 逐字段对比）
- [x] 快照列表分页加载：快照数量过多时分页查询，避免一次加载全部
- [x] 快照操作人显示为用户名而非 user_id（JOIN users 表或前端缓存映射）

### P1 - 功能增强

- [x] 手动创建快照：支持用户主动保存当前版本（不依赖编辑触发），并添加版本备注
- [x] 快照保留策略：可配置最大快照数量（如保留最近 50 个），超出自动清理最旧快照
- [x] 批量回滚确认：回滚前弹出详细对比弹窗，显示当前值 vs 快照值（后端 diff API 已就绪 `GET /cases/{id}/snapshots/diff?from=&to=`，前端弹窗待跟进）
- [x] 快照搜索：支持按版本号、名称关键字搜索快照（list_snapshots 新增 `q` 参数）

### P2 - 高级功能

- [x] 快照导出/导入：支持将某个版本导出为 JSON 文件，或从 JSON 导入恢复
- [x] 用例克隆自快照：从历史版本直接创建新用例（而非回滚覆盖原用例）
- [x] 审计日志：记录每次回滚操作的触发人、时间、源版本号，供合规审查 — Q5 长尾 3 收口；`rollback_case` 写入 `audit_logs (action=case.rollback, resource_type=test_case, project_id, detail=回滚用例 X → 快照 vN (snapshot_id=...))`，可在系统-审计日志页按 `case.rollback` 筛选查看

---

## Phase 5.3 报告导出 — 后续优化计划

> 以下为报告导出的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 导出按钮 Loading 提示优化：PDF 生成较慢（~3s），增加进度提示文案
- [x] HTML 报告样式增强：添加打印友好的 @media print 样式
- [x] 报告中显示用例类型标签（API / Web / Android）
- [x] 报告时间显示时区：当前使用服务器本地时间，改为 UTC+8 或可配置时区

### P1 - 功能增强

- [x] 报告模板可选：支持简洁版（无请求/响应）和完整版两种模板（`?template=summary|full`）
- [x] 视频嵌入：HTML 报告中嵌入执行录像（仅 HTML 版本，PDF 不支持视频）— P1.1 Q5 收口，从 `run.result_summary.video_url` 自动渲染 `<video controls>`

### P2 - 高级功能

- [x] 批量导出：支持选中多个执行记录一次性导出为 ZIP 包（`POST /runs/export/zip`，最多 50 条）
- [x] 定时报告邮件：结合通知模块，定时生成并发送 HTML 报告邮件 — P1.2 Q5 收口；NotificationConfig.config 新增 `attach_html_report` 开关，开启时 plan/suite 完成自动生成 HTML 报告并以 multipart/alternative 嵌入邮件正文
- [x] 自定义报告封面：支持配置公司 Logo、项目名称、报告标题（`?cover_title&cover_logo_url`）
- [x] 报告 CDN 缓存：生成后存入 MinIO，重复下载直接返回缓存文件（key 含 `updated_at` 自动失效）

---

## Phase 5.4 缺陷跟踪集成 — 后续优化计划

> 以下为缺陷跟踪集成的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 创建成功后在执行详情页显示已关联的缺陷链接（存储 bug_id + bug_url 到 TestRun.result_summary）
- [x] 缺陷创建前预览：弹窗中展示即将提交的标题和描述内容，确认后再提交
- [x] 错误信息截断提示：当 error_message 或 response_data 过长时显示截断提示
- [x] 创建失败时给出更友好的错误提示（区分认证失败 / 网络超时 / 项目不存在等）

### P1 - 功能增强

- [x] 禅道多产品支持：配置中支持多产品切换（`product_map` 映射 + `override_product_id` 参数）

### P2 - 高级功能

- [x] GitLab Issues 集成：扩展第三方平台支持（`TrackerType.gitlab` + 完整 CRUD/查询/duplicate）

---

## Phase 5.5 安全与性能 — 后续优化计划

> 以下为安全与性能的迭代优化项，按优先级排列。

### P0 - 安全加固

- [x] 敏感配置落库加密：当前仅脱敏返回，后续可在写入时 Fernet 加密、读取时解密
- [x] 限流规则可配置化：将限流阈值移入 config.py / 环境变量，无需改代码即可调整
- [x] CSRF Token 保护：对非 API 客户端（浏览器直接访问）添加 CSRF 防护

### P1 - 性能增强

- [x] 分页游标优化：`cases/runs.py` 已上线 Keyset (cursor) 分页，OFFSET 模式向后兼容；下轮推广到 suites/plans
- [x] 执行记录列表延迟加载 steps：列表查询不 eager-load steps，仅详情页加载（`PaginatedRunsOut.items` 已收敛为 `TestRunListItem`）
- [x] Redis 查询缓存：9 个 statistics 端点统一走 `@cached_json` 装饰器（TTL 5min），删除原函数体内冗余双层 cache 逻辑

### P2 - 运维支持

- [x] 慢查询监控：SQLAlchemy event listener，> `SLOW_QUERY_THRESHOLD_MS`（默认 1s）的 SQL 输出 WARNING（带 trace_id + SQL 截断），并写入当前 OTel span 的 `atp.slow_query` attribute
- [x] Celery 任务超时告警：`task_failure` 信号识别 `SoftTimeLimitExceeded` + `task_revoked` 识别硬超时 → WARNING 日志 + OTel span attribute `atp.task_timeout=soft|hard`
- [x] 定期清理过期 test_runs 数据：超过保留天数的执行记录自动归档/删除（Celery `cleanup_old_completed_runs` 每日定时 + 新增 admin 预览/手动触发 API `/api/v1/admin/runs/retention/{preview,run}`）

---

## Phase 5.6 运维支持 — 后续优化计划

> 以下为运维支持的迭代优化项，按优先级排列。

### P0 - 日志完善

- [x] 日志级别可通过环境变量 `LOG_LEVEL` 动态配置
- [x] 请求级别 trace_id 注入：每个 HTTP 请求生成唯一 ID 贯穿日志链路
- [x] 关键业务操作审计日志：用例创建/删除、用户登录/权限变更等写入独立审计表

### P1 - 清理策略增强

- [x] 按项目维度配置不同保留天数 — P1.4 Q5 MVP 收口；`Project.run_retention_days_override` 字段 + 迁移 + Schema + `resolve_project_retention` / `preview_old_runs_by_project` service + `GET /admin/runs/retention/per-project-preview` 端点（清理任务暂仍按全局调度，per-project 真实清理待下迭代）
- [x] 清理前生成清理报告（即将删除的文件数量/大小），支持管理员确认 — Q5 长尾 4 收口；后端 `preview_old_runs` 已返回 plan/suite/test/mobile 数量 + `estimated_objects`，前端新增 `system/RunRetentionView.vue` 展示全局+按项目预览，"执行清理"按钮带 Popconfirm 二次确认显示待删数量
- [x] 支持手动触发清理（管理后台按钮）— Q5 长尾 4 收口；调用既有 `POST /admin/runs/retention/run`，结果展示在"本次清理结果"卡片

### P2 - 部署与监控

- [x] Kubernetes Helm Chart 部署方案（`deploy/helm/atp/` 含 backend/worker/beat/flower 4 Deployment + Service/Ingress/HPA/ConfigMap/Secret + `docs/deploy-helm.md`；Q6 P1.7 补齐 `values.yaml` 字段注释与 `values.schema.json`）
- [x] Prometheus + Grafana 监控集成（compose profile=observability 启停；backend `/metrics` + celery-exporter；预置 `ATP Overview` 仪表盘；自定义业务指标 stats_cache / slow_queries / celery_timeouts / run_retention_deleted；Q6 P1.7 新增 `deploy/grafana/alerts/atp-alerts.yaml` 5 条告警模板）
- [x] 数据库自动备份脚本（pg_dump 定时备份到 MinIO；`scripts/backup-postgres.sh` + `tasks_db_backup.py` 日/周双调度 + 保留策略 `DB_BACKUP_RETAIN_DAILY=7` / `DB_BACKUP_RETAIN_WEEKLY=4`；Q6 P1.7 新增 `scripts/restore-postgres.sh` 与 `docs/disaster-recovery.md` 恢复演练文档）

---

## Android 专项测试中心

> 实现时间：2026-03-30 ~ 2026-03-31

### 数据模型层

- [x] `MobileSpecialTask` — 专项任务（名称、类型、设备范围、APK配置、调度配置）
- [x] `MobileSpecialRun` — 执行记录（状态、耗时、摘要JSON快照）
- [x] `MobileMetricSample` — 指标采样（CPU/内存/FPS/电池，时间序列）
- [x] `MobileIncident` — 异常事件（crash/ANR/Fatal日志/Watchdog）
- [x] `MobileRunArtifact` — 报告产物（CSV/JSON/截图/日志/Trace文件）
- [x] `GlobalVariable` — 全局变量库（项目级/全局，加密存储）
- [x] Alembic 迁移文件

### 执行器层

- [x] `android_perf_executor.py` — 性能测试：周期性采样 CPU/内存/电池，写入指标样本，生成CSV
- [x] `android_stability_executor.py` — 稳定性测试：Monkey随机探索 + logcat监控崩溃/ANR
- [x] `android_fluency_executor.py` — 流畅度测试：场景化FPS采样 + jank计算
- [x] `adb_client.py` — ADB命令构建器（meminfo/gfxinfo/cpuinfo/batterystats/logcat）
- [x] `parsers.py` — 指标数据解析（meminfo/cpuinfo/gfxinfo/batterystats/logcat）
- [x] `collectors.py` — 采样会话管理 + 设备就绪校验
- [x] `aggregator.py` — 指标聚合 + 任务类型特定摘要计算

### Celery 调度

- [x] `tasks_mobile_special.py` — `run_mobile_special_task` 任务路由
- [x] `check-mobile-special-schedules` — Cron表达式轮询定时触发
- [x] `cleanup-stale-mobile-special-runs` — 超时运行记录清理

### REST API

- [x] Tasks CRUD + `POST /tasks/{id}/run` 触发执行
- [x] Runs 查询 + `POST /runs/{id}/stop` 停止
- [x] `GET /runs/{id}/samples` 指标样本
- [x] `GET /runs/{id}/incidents` 异常事件
- [x] `GET /runs/{id}/artifacts` 产物列表
- [x] `GET /runs/{id}/export/csv` CSV导出
- [x] `GET /runs/{id}/export/json` JSON完整报告导出
- [x] `GET /statistics/overview` 总览统计
- [x] `GET /statistics/trend` 每日趋势
- [x] `GET /statistics/task-stats` 各任务统计
- [x] GlobalVariable CRUD + Fernet加密

### 前端页面

- [x] 专项任务列表页（SpecialTaskListView.vue）— 项目/类型筛选、创建/编辑抽屉、执行/编辑/删除
- [x] 报告中心（ReportCenterView.vue）— KPI卡片、14天趋势图、运行记录表、导出、停止
- [x] 报告详情（ReportDetailView.vue）— 任务信息、KPI卡片、指标趋势图（ECharts）、异常事件表、报告文件表
- [x] 全局变量库（GlobalVariableLibrary.vue）— 项目级/全局切换、加密值遮罩/显隐、新建/编辑/删除

### 测试

- [x] `test_mobile_special_migration.py` — 迁移文件测试（5个测试）
- [x] `test_mobile_special_schema.py` — Schema验证测试（19个测试）
- [x] `test_mobile_special_parsers.py` — 解析器单元测试（15个测试）
- [x] `test_mobile_special_collectors.py` — 采样器测试（5个测试）
- [x] `test_android_perf_executor.py` — 性能执行器测试（8个测试）
- [x] `test_android_stability_executor.py` — 稳定性执行器测试（6个测试）
- [x] `test_android_fluency_executor.py` — 流畅度执行器测试（6个测试）
- [x] `test_mobile_special_tasks_api.py` — 任务API测试
- [x] `test_global_variables_api.py` — 全局变量API测试
- [x] `test_mobile_special_stats_api.py` — 统计Schema测试（3个测试）

### 2026-04-01 回归修复收口

- [x] 修复启动模型加载链路遗漏 `mobile_special_*` / `global_variables` 表注册的问题
- [x] 修复专项任务启用调度时 `next_run_at` 未初始化，导致定时任务永不触发的问题
- [x] 修复 worker 执行前未将 `device_id` 解析为设备 serial 的问题，并保留手动运行覆盖参数
- [x] 修复统计接口在 SQLAlchemy 2.0 下 `case()` 调用方式不兼容导致报表中心加载失败的问题
- [x] 修复全局变量读取接口返回密文的问题，支持默认脱敏与按需显式查看明文
- [x] 修复稳定性执行器使用一次性 `logcat -d` 导致运行期间 crash/ANR 漏采集的问题
- [x] 修复报告中心按任务类型筛选无效的问题，并完成后端测试与前端构建验证

---

## Q10 — 质量与稳定性深化（质量门禁优先）

> 实施计划：`docs/implementation-plan-2026-Q10.md`（2026-05-30 编制）
> 当前状态：已启动；发布收口与 PR 范围整理完成，Q10 已落地 ruff/mypy/coverage/Vitest/Bandit/依赖扫描，且 pip/npm 依赖漏洞已清零。
> 定位：从「功能完整」推进到「质量可度量、回归可防护、工程可信赖」；不新增业务方向。
> 缺口画像：基础质量门禁、ruff format 基线、依赖漏洞清零、密钥/镜像扫描、Dependabot/security workflow、真实依赖集成、suite / plan 关键运行路径 E2E、SLO 薄切、flaky 治理与最终验收文档已完成。

### 启动顺序（2026-07-08 更新）

- [x] 0.1 发布收口：确认当前优化批次的提交范围、测试证据、文档同步和 PR 描述。
- [x] 0.2 环境矩阵验证：Python 3.14 本地全量回归通过；Docker `python:3.12-slim-bookworm` 目标运行时全量后端回归通过。
- [x] 0.3 前端构建验证：`npm run type-check` 与 `npm run build` 已通过，当前仅保留已知 circular chunk 警告。
- [x] 0.4 Q10 Phase 1 开工：新增 ruff 配置与 lint job，先以最小豁免建立可持续门禁。
- [x] 0.5 Q10 Phase 4 开工：新增 Bandit、pip-audit 与 npm audit 本地扫描命令，记录 SAST 与依赖漏洞基线。
- [x] 0.6 Q10 Phase 4 依赖升级收口：升级 FastAPI/Starlette、python-multipart、pytest/pytest-asyncio、Jinja2、cryptography、prometheus-fastapi-instrumentator、Vite/Vitest、Axios、ECharts、vue-i18n，并用 npm overrides 覆盖残留传递依赖漏洞；Q11-02 复扫时已将 `python-jose` 迁移到 `PyJWT[crypto]==2.13.0` 以移除 `ecdsa` 漏洞链。
- [x] 0.7 Q10 Phase 1 format 基线收口：执行 `ruff format backend/app backend/tests`，新增 `make format` / `make format-check`，并将 `ruff format --check` 接入 CI 与 pre-commit。
- [x] 0.8 Q10 Phase 5 收口：已新增并跑通 suite-run / plan-trigger / notification / bug-report 集成用例；补齐 `test_suites.config` 与 `bug_trackers.tracker_type` Alembic 迁移缺口后，真实 Postgres / Redis / MinIO 环境 integration suite 为 `10 passed`，二次重复运行仍为 `10 passed`；suite / plan 前端关键运行路径 E2E 已通过；SLO 薄切已新增 run outcome 指标、3 条 SLO 口径与 Grafana 错误预算面板；flaky 治理已新增 marker、一次有界重试和处理约定；Q10 验收总结与 README / 进度文档已同步。

### Phase 1 — 后端代码质量门禁 [P0]

- [x] ruff lint + format 配置（`pyproject.toml`）+ 存量基线豁免（per-file-ignores）：已启用 F821/F822/F823 最小 lint 门禁，并完成 format 全量基线
- [x] ruff format 一次性统一（独立 commit + `.git-blame-ignore-revs`）：格式化已落地，`.git-blame-ignore-revs` 已新增；待提交后只需补入格式化 commit SHA
- [x] mypy 渐进式覆盖 `core/` / `schemas/` / `services/`
- [x] `.pre-commit-config.yaml` 新建
- [x] CI 新增 lint job（ruff check + format --check）：`backend-lint` job 已同时运行 `ruff check` 与 `ruff format --check`

### Phase 2 — 测试覆盖率门禁 [P0]

- [x] pytest-cov 接入（`[tool.coverage]`）+ 跑出后端覆盖率基线并记录
- [x] CI 加 `--cov-fail-under=<基线-1%>` 门禁 + 覆盖率报告 artifact

### Phase 3 — 前端单元测试从 0 到 1 [P0]

- [x] vitest + @vue/test-utils + jsdom + @vitest/coverage-v8 接入
- [x] 首批：`stores/auth` / `api/http`(拦截器/401) / `utils/websocket` / 1-2 纯组件
- [x] 第二批：`stores/theme` / `utils/chartTheme`，覆盖主题持久化、DOM 属性、系统深色偏好、ECharts 主题注册幂等和主题切换
- [x] CI 前端 test 步骤（与 type-check/build 并列）

### Phase 4 — 自动化安全扫描 [P1]

- [x] bandit SAST + 基线豁免
- [x] pip-audit（后端）+ npm audit / osv-scanner（前端）依赖扫描：本地命令已落地；后端 6 个包 25 条记录、前端 16 条记录已完成升级收口，当前 `pip-audit` 与 `npm audit --audit-level=moderate` 均为 0 漏洞
- [x] trivy 镜像扫描（联动 release-readiness）：新增 security workflow，对 backend / worker / frontend 镜像按 HIGH/CRITICAL 阻断
- [x] gitleaks 密钥扫描（CI + pre-commit）：CI Gitleaks 扫描 + 本地 pre-commit 官方钩子（v8.24.3，复用 .gitleaks.toml；Q14-05 收口）
- [x] `.github/dependabot.yml` 四生态 + `.github/workflows/security.yml`（仅 high/critical 阻断）

### Phase 5 — 集成扩展 + SLO + 收口 [P2]

- [x] 5.1 集成测试补 suite-run / plan-trigger / notification / bug-report
  - [x] 5.1.1 新增 suite-run / plan-trigger 链路用例：创建项目/模块/API 用例、审批用例、创建套件、触发 suite run、创建计划、触发 plan run。
  - [x] 5.1.2 在真实 Postgres / Redis / MinIO 环境执行 integration suite，并记录命令与结果：临时端口 Postgres `55432` / Redis `6380` / MinIO `19000`，空库 `alembic upgrade head` 通过，`backend/tests/integration -m integration` 为 `10 passed`，二次重复运行仍为 `10 passed`。
  - [x] 5.1.3 补 notification 真实配置/发送降级路径集成验证：覆盖创建、敏感字段遮蔽、测试发送走解密配置、Webhook 失败转 HTTP 500。
  - [x] 5.1.4 补 bug-report 失败执行到缺陷创建/关联/去重的集成验证：覆盖 tracker 创建、连接测试解密配置、重复缺陷短路、创建缺陷写回 run summary、刷新状态、手动关联既有缺陷。
- [x] 5.2 E2E 补 suite / plan 关键路径
  - [x] 5.2.1 suite：加载套件、触发执行、查看执行记录抽屉。
  - [x] 5.2.2 plan：加载计划、手动触发、查看计划运行记录。
  - [x] 5.2.3 完整 Playwright E2E 回归：`9 passed`。
- [x] 5.3 flaky 治理（pytest-rerunfailures + 标记 + 文档）
  - [x] 5.3.1 明确 integration / e2e flaky 标记策略与重试边界：`docs/flaky-governance.md` 已新增。
  - [x] 5.3.2 将重试策略接入 CI 或记录为 release-readiness 手工步骤：integration workflow 已接入 `--reruns 1 --reruns-delay 2`，Playwright CI 保持 `CI=true` 时一次重试。
- [x] 5.4 SLO 薄切（API 可用性 / P95 / run 成功率 3 条 + 错误预算面板，复用既有 Grafana）
  - [x] 5.4.1 定义 3 条 SLO 与数据来源：`docs/slo-guide.md` 已覆盖 API 可用性、P95、run 成功率与错误预算口径。
  - [x] 5.4.2 更新 Grafana dashboard / alert 说明：`ATP Overview` 已新增 4 个 SLO 面板，`docs/observability-guide.md` 已同步。
- [x] 5.5 `docs/q10-acceptance-summary.md` + README / Task.md 收口
  - [x] 5.5.1 汇总质量门禁、安全扫描、覆盖率、集成/E2E、SLO 验收证据。
  - [x] 5.5.2 同步 README、Task.md、CONTEXT.md、MEMORY.md 与 release evidence。

---

## Q11 / Q12 — 生产就绪与持续质量优化

- [x] Q11 全部 15 项完成，验收证据见 `docs/q11-acceptance-summary.md`。
- [x] Q12-00 消除 41 条 `PytestCollectionWarning`：`backend/tests/conftest.py` 的 `pytest_pycollect_makeitem` 钩子统一跳过从 `app.*` 导入的 `Test*` 类（测试保留原始类名导入），pytest 将该警告升级为错误；完整后端回归 `840 passed`。
- [x] Q12-01 刷新覆盖率基线：后端 `53.46%` / 门禁 `52%`；前端 statements `3.66%`、branches `4.06%`、functions `2.26%`、lines `3.92%`，已建立 3%/3%/2%/3% 初始门禁及 CI artifact。
- [x] Q12-02 增补认证、用例执行、调度和报告关键前端流程测试：四个切片均完成，前端 `47 passed`，全源 coverage `4.44/4.88/3.01/4.66%`，门禁同步抬升。
- [x] Q12-03 收敛依赖弃用提示：vue-i18n 升级到 `11.4.6`（Composition 模式无 breaking），传递依赖 glob 经 npm override 固定到 `13.0.6`；clean install 零 `npm warn deprecated`。46 tests、type-check、build、E2E 9 passed。
- [x] Q12-04 前端 chunk 边界治理：改用 unplugin-vue-components 按需注册 Ant Design（替代全局 app.use），并将 chartTheme 移出入口依赖；/login 首屏 gzip 传输 773.9→510.1 kB（-34%），ant-design chunk 1502.45→1246.41 kB，构建零告警；46 tests、type-check、E2E 9 passed。后续已完成：components.d.ts 已开启并提交，112 处存量 a-* props 类型不匹配全部修复（见下条）。
- [x] Q12 类型加固：开启 unplugin-vue-components dts，修复全部 112 处存量 a-* props 类型错误（bodyCell record 断言 helper、v-model null 断言、badge/handler 签名收窄），vue-tsc 对模板组件 props 实现真实检查；46 tests、type-check 0 错、build、E2E 9 passed、后端 841 passed。
- [x] Q12-05（本地部分）冻结外部就绪证据口径：`docs/q12-external-readiness-evidence.md` 定义 SLO 7/14 天历史与 Android 真机演练的记录字段、通过标准与证据落点，契约测试 3 passed；采集执行待环境（长期抓取部署 + 真机）。
- [x] Q13 规划发布：`docs/optimization-roadmap-2026-q13.md`——7 个工作项：Q13-00 承接 Q12-05 采集与 Q12 验收、Q13-01 执行链路覆盖（tasks.py+9 executors，后端 53%→60%、gate 52→56）、Q13-02 服务/API 覆盖（bug_reporter/ai_healing/failure_diagnosis/exports/mobile_special）、Q13-03 前端工作台四视图行为切片（statements ≥8%）、Q13-04 Ant Design 路由级 chunk 证据与决策、Q13-05 AI 自愈 apply 闭环切片（feature-flag+审计）、Q13-06 依赖卫生。首个动作：Q13-01 执行器单元缝。
- [x] Q13-01 切片 1（执行链主体）：新增 `test_tasks_execution_chain.py` 34 项测试覆盖 run_test_case/run_test_suite/run_test_plan/_execute_plan_suite/check_cron_plans/check_dashboard_alerts 全部主干与异常分支；tasks.py 35%→86%，后端 TOTAL 53%→55.65%（878 passed）；单元缝约定沉淀到 `docs/coverage-baseline-2026-q13.md`。
- [x] Q13-01 切片 2（HTTP 家族执行器）+ 收官：`test_http_family_executors.py` 46 项测试只 fake 传输边界（httpx/websockets/grpc channel），api/graphql/websocket/grpc 执行器 3-8%→88-94%；**发现并修复生产级故障**：protobuf 5+ 移除 `message_factory.GetPrototype`，grpc 执行器此前每次执行必报错，改用 `GetMessageClass`。后端 TOTAL 60.03%（924 passed），CI 门禁 52%→56%。
- [x] Q13-02 切片 1（服务层）：`test_bug_reporter_unit.py` 38 项（Jira/禅道/GitHub/GitLab 四平台共用一个脚本化 httpx fake，payload 组装/鉴权/去重/JQL 转义/错误路径全走真实现）+ `test_failure_diagnosis.py` 15 项（规则分类矩阵、修复建议映射、LLM 成功/失败/限额/兜底三态）；bug_reporter 20%→95%、failure_diagnosis 12%→97%，TOTAL 63.35%（962 passed）。
- [x] Q13-02 切片 2（ai_healing run 级）：`test_ai_healing_run_level.py` 23 项——run_diagnosis_for_run 全状态（幂等/case 缺失/无配置/step 不足/缓存命中/日限额/解密失败/LLM 成败）、缓存键顺序无关性、文本与 vision 日限额、截图装载、run hook 阈值与入队兜底；ai_healing 46%→89%，TOTAL 64.50%（985 passed）。
- [x] Q13-02 切片 3（exports）：`test_exports_junit_reports.py` 18 项——run/suite/plan 三级 JUnit（含无 step 的 run 级 failure/error/skipped 合成、套件缺失 error 用例、真实 TestRun 耗时回查）、suite/plan 聚合 HTML 构建器、HTML 缓存命中/未命中、PDF 路由（Playwright 渲染边界 fake）、缓存读写存储异常吞；exports 36%→92%，TOTAL 65.97%（1003 passed）。
- [x] Q13-02 切片 4（mobile_special API）+ 收官：`test_mobile_special_routes.py` 16 项——任务 CRUD（访问检查/调度刷新/None 字段不覆盖）、触发（config 快照/设备回退/Celery 入队）、停止守卫、runs 联表查询、samples/incidents/artifacts、CSV/JSON 导出；**发现并修复生产级故障**：create_task 因 schema 的 created_by 与显式 kwarg 键冲突而每次调用必 500。mobile_special 45%→91%，TOTAL 66.98%（1019 passed），CI 门禁 56%→62%。
- [x] Q13-03 切片 1（CaseList）：抽 `utils/caseList`（level 筛选/待评审与 flaky 计数/工作流守卫状态机/flaky 提示参数/模块树扁平化），`caseList.spec.ts` 5 组断言；CaseList.vue 改用受测 helper（activeFilterTags 仅保留 i18n 标签映射、工作流守卫单点分发），type-check 0 错、E2E 仍绿；前端 statements 4.38%→4.65%（51 passed），门禁抬至 4.4/5.1/2.9/4.6。
- [x] Q13-03 切片 2（RunDetail）：抽 `utils/runDetail`（步骤状态统计/展开策略/参数化迭代摘要/run 级自愈与失败诊断载荷归一化/主错误摘要截断/状态色），`runDetail.spec.ts` 7 组断言；RunDetail.vue 改调 helper，type-check 0 错、run-detail E2E 仍绿；前端 statements 4.65%→5.10%（58 passed），门禁抬至 4.85/6.35/3.35/4.95。
- [x] Q13-03 切片 3（SuiteList）：扩充 `utils/suiteList`（模块后代映射 buildModuleDescendantMap、tree-select 空枝剪裁 buildModuleTreeOptions、用例不可执行原因分类 caseExecutionReasonKey、结构化用例筛选谓词 passesSuiteCaseStructuralFilter），`suiteList.spec.ts` +4 组断言；SuiteList.vue 删本地副本改调 util，type-check 0 错、suite-plan E2E 仍绿；前端 statements 5.10%→5.54%（62 passed），门禁抬至 5.3/7.15/3.45/5.35。
- [x] Q13-03 切片 4（DashboardView）：抽 utils/dashboardView（日期区间生成 generateDateRange、泛型趋势补零 fillTrendGaps 含 today 注入、布局归一化 normalizeDashboardLayout），dashboardView.spec.ts 6 组断言（含钉住『已存在但结构错误的已知 key 既不保留也不补回』的微妙契约）；DashboardView.vue 删本地副本改调 util，type-check 0 错、dashboard E2E 与生产构建仍绿；前端 statements 5.54%→5.95%（68 passed），门禁抬至 5.7/7.5/3.7/5.7。四工作台切片全部完成；≥8% 验收目标顺延到 form-drawer 追加切片。
- [x] Q13-03 追加切片（CaseFormDrawer）：抽 utils/caseFormConfig（配置步骤解析 getFirstStep、form body 回填 parseFormBody、GraphQL 变量 parseGraphqlVariables、WebSocket 消息归一 normalizeWsMessage、保存态请求体 resolveRequestBody），caseFormConfig.spec.ts 6 组断言；CaseFormDrawer.vue 删本地解析副本改调 util，type-check 0 错、E2E 与构建仍绿；前端 statements 5.95%→6.33%（branches 越过 8%，74 passed），门禁抬至 6.05/8.05/3.9/6.1。
- [x] Q13-03 切片（PlanList cron）：扩充 utils/planList（buildCronExpression 按 daily/weekly/custom 拼 cron、formatCronTime 补零 HH:MM），planList.spec.ts +3 组断言；PlanList.vue cron 预览/描述改调 util，type-check 0 错、suite-plan E2E 与构建仍绿；前端 statements 6.33%→6.40%（branches 8.4%，77 passed）。helper 抽取对 statements 边际收益已递减——到 8% 需组件挂载测试（@vue/test-utils），非继续抽 helper；已在 roadmap 记录评估与建议。
- [x] Q13-06 依赖卫生：审阅并固化 frontend allowScripts 白名单（core-js 赞助提示/fsevents 原生绑定/vue-demi Vue3 入口切换，三者均核实无害），npm ci 零 allow-scripts 与零弃用告警、audit 0 漏洞；新增 docs/dependency-hygiene.md 与契约测试 test_dependency_hygiene.py（3 passed）。顺带修复 Q13-03 slice4 重构后遗留的 test_dashboard_routes 静态契约（DEFAULT_DASHBOARD_LAYOUT 已移至 utils/dashboardView）。
- [x] Q13-04 Ant Design 路由级 chunk 证据与决策：实测 /login 首屏在单体 antd chunk 下拉取 374.7/510.1 kB gzip（73%）；移除 manualChunks 的 ant-design 归并、让按需组件随路由分裂后，/login 首屏 510→336 kB（-34%，-174 kB，远超 15% 门槛），代价 dist JS 总量 +~35 kB（共享运行时在少数路由 chunk 重复）。结论 GO 并采纳，chunkSizeWarningLimit 1500→600（echarts 563 成新上限）；全量 E2E 9 passed 于真实浏览器验证。证据与决策见 docs/frontend-bundle-decision.md，契约测试同步更新。
- [x] Q13-05 AI 自愈 apply 闭环（iter5 phase 2）：加 `AI_HEALING_APPLY_ENABLED`（默认关，apply 未启用返回 403；preview 只读门常开）+ 7 项行为测试（iter5 API 0%→72%）；修复端点 `ProjectRole.engineer` 潜在 500（第三个覆盖工作暴露的生产故障）+ 两处 sys.modules 测试隔离脆性。全库 1029 passed、TOTAL 67.76%。
- [x] Q13-03 收官（挂载测试切片）：`ApkList.spec.ts`（4 项）+ `DeviceList.spec.ts`（5 项）@vue/test-utils 挂载测试，ApkList 0→56%、DeviceList 0→62%；**前端 statements 6.40%→8.51%，达成 ≥8% 验收线**（挂载测试 +1pt/个 vs helper +0.07pt/个）。门禁 8.2/9.6/6.2/8.15，type-check/build/全量 E2E 绿。所有本地 Q13 项完成，仅剩 Q13-00 待环境。
- [x] Q13-01 补切片（web 家族执行器）：`test_web_executor.py`（8 项，fake subprocess.run 写 json-report + MinIO 边界，覆盖脚本缺失/超时/无测试/多步映射/截图上传/浏览器回退/healing hook）+ `test_web_lowcode_executor.py`（8 项，fake Page 记录动作分发 goto/click/fill/assert/press/wait/screenshot/unknown + 变量替换递归）。web_executor 13%→84%、web_lowcode 15%→51%，后端 TOTAL 67.76%→69.29%（1045 passed）；两文件加 minio 符号导入保护，免疫跨文件 stub 污染。
- [x] Q13-01 补切片（android 家族执行器）：扩充 `test_android_lowcode_executor.py`（+11 项，fake `_adb_cmd` 覆盖 click/long_click/swipe(方向+坐标)/input(转义+clear)/press_key(命名+原样)/start_app/stop_app/assert_text/assert_element/wait/screenshot/未知动作 + 变量递归替换）与 `test_android_executor.py`（+3 项，run_android_case 的脚本缺失/设备缺失/设备不可达三个前置守卫）。android_lowcode 15%→53%、android_executor 12%→23%，**后端 TOTAL 69.29%→70.23%，九个执行器全部有行为覆盖**（1059 passed）。
- [x] 后端覆盖延伸（environments API）：数据驱动挑最大 0% 模块——`test_environments_routes.py`（11 项，list/create/update/delete 环境 + 变量读取掩码 + 批量保存的删/插/密钥加密，含 404 与项目访问角色断言、重复 key 校验）。`api/v1/environments.py` 0%→100%，后端 TOTAL 70.23%→70.92%（1070 passed），CI 门禁 62%→66%。
- [x] 后端覆盖延伸（WebSocket 端点）：`test_ws_routes.py`（15 项，fake session/redis/WebSocket）——token 校验（缺失/非法/非 access 类型/用户缺失或禁用/有效）、run 订阅授权阶梯全五档（admin/触发者/用例创建者/项目成员/项目 owner + 各拒绝分支）、握手（未授权 1008/禁止 1008/accept）→pubsub 转发→收到 completed 主动关闭 + finally 清理。`api/v1/ws.py` 0%→89%，后端 TOTAL 70.92%→71.62%（1085 passed）。两个最大的 0% 模块（environments/ws）均已覆盖。
- [x] 后端覆盖延伸（mobile_special collectors）：`test_mobile_special_collectors_sampling.py`（10 项，fake run_adb_shell + parse_*）——SamplingSession 的 PID 解析（有/无输出）、四个采样器的 parser 路由与空输出→None、PeriodicSampler 的按 metric_types 产出/跳过 None/停止、device/package 校验器。`services/mobile_special/collectors.py` 0%→92%，后端 TOTAL 71.62%→72.26%（1095 passed）。
- [x] 后端覆盖延伸（mobile_special 调度分发）：`test_tasks_mobile_special_dispatch.py`（15 项，沿用 tasks.py 单元缝范式）——run_mobile_special_task 的 run/task 缺失、按 task_type 路由到 perf/stability/fluency executor、config 合并+设备解析、executor 异常→failed+completed 推送、设备 serial 解析；check_mobile_special_schedules 触发+cron 重排+坏 cron 禁用；cleanup 批量 update；3 个纯 helper 优先级。`worker/tasks_mobile_special.py` 26%→97%，后端 TOTAL 72.26%→72.87%（1110 passed）。至此 mobile-special 全链路（API/tasks/collectors/parsers）均有行为覆盖。
- [x] backend coverage extension (plans API, core business entity): test_plans_routes.py (16 tests) — suite-id validation (dup/missing/wrong-project) + env validation (404/wrong-project), create cron next_run_at + webhook secret gen, update next-run clear when not cron, manual run trigger env-var merge + empty/404 guards, and the webhook trigger secret-auth ladder (404 / non-webhook 400 / bad-secret 403 / empty-suites 400). api/v1/plans.py 55 -> 80%, backend TOTAL 73.76 -> 74.16% (1154 passed).
- [x] backend coverage extension (bug_trackers API, closes the bug-report subsystem with the earlier bug_reporter service): test_bug_trackers_routes.py (13 tests) — config encrypt-on-create + mask-on-read, the _merge_sensitive_config keep-existing-secret-when-masked/omitted invariant on update, CRUD 404s, and test-connection (inline config, saved-secret merge, type-mismatch graceful reject, backend-error swallow). api/v1/bug_trackers.py 55 -> 75%, backend TOTAL 73.41 -> 73.76% (1138 passed).
- [x] backend coverage extension (projects API, permission-system root): test_projects_routes.py (15 tests) — project CRUD (creator auto-owner + auto code), module-tree build/nest/sort + module CRUD access checks, member list mapping, member add (404 missing user / 409 duplicate), role update, and the remove-member last-owner-block security invariant. api/v1/projects.py 41 -> 79%, backend TOTAL 72.87 -> 73.41% (1125 passed).
- [ ] Q12-05 补充生产型 SLO 历史和物理 Android 设备执行证据。

当前路线图：`docs/optimization-roadmap-2026-q15.md`（2026-07-31 起草，**待评审**）。上一轮 Q14 七项中本地可执行项已全部完成，`docs/q14-completion-audit.md` 逐项记录完成证据；Q14-00 承接 Q12-05 采集（待环境），需要生产 SLO 7/14 天历史和 Android 真机演练后再发布 `docs/q12-acceptance-summary.md`。

---

## Q14 — 覆盖固化与工程遗留收口

> 实施计划：`docs/optimization-roadmap-2026-q14.md`（2026-07-11 编制）

- [ ] Q14-00 承接 Q12-05：生产 SLO 7/14 天历史 + Android 真机演练采集，随后发布 `docs/q12-acceptance-summary.md`（待外部环境；`make collect-q12-evidence` 已可自动采集 Prometheus/API/ADB 并生成证据，`make scaffold-q12-evidence` 仅作草稿初始化，`make validate-q12-evidence` 做结构校验）
- [x] Q14-01 Android/ADB 执行器覆盖：android 四执行器 82-93%、web/android_lowcode 97/98%、adb_service 97%；TOTAL 81%、CI 门禁 66→70（Makefile 同步 70）
- [x] Q14-02 API 路由覆盖扫尾：suites 100%、notifications 99%，并补齐 ai_healing_stats / devices / healing_prompt_examples 路由缝；TOTAL 82.20%、1310 passed
- [x] Q14-03 前端工作台挂载测试：CaseList / RunDetail / SuiteList / DashboardView / PlanList 均有组件级挂载测试；前端 statements 21.48%、102 passed，门禁提升到 20.5
- [x] Q14-04 按项目保留天数真实清理：override 项目按各自截止时间清理四种 run 类型，全局兜底排除 override 项目；预览补齐 test/mobile 按项目统计；run_retention 78→90%
- [x] Q14-05 Gitleaks pre-commit 本地钩子：官方钩子 v8.24.3 接入 `.pre-commit-config.yaml` 复用 `.gitleaks.toml`；Makefile 门禁漂移已在 Q14-01 一并修复（52→70）
- [x] Q14-06 Q13 验收总结：`docs/q13-acceptance-summary.md` 已发布（六个工作项 + 覆盖延伸 53→74-75% + 四个生产 bug + 前端 4.38→8.51%）

---

## Q15 — 门禁生效与测试可靠性（草案，待评审）

> 实施计划：`docs/optimization-roadmap-2026-q15.md`（2026-07-31 起草，尚未立项；以下条目在评审通过前不作为承诺范围）
>
> 实测输入（2026-07-31）：后端 TOTAL 82.73%（13962 语句 / 2045 未覆盖，1327 passed，门禁 70）；前端 statements 21.48% / branches 18.48% / functions 17.44% / lines 22%；183 个非 integration 测试文件逐个单独运行有 10 个失败（5.5%）。

- [ ] Q15-00 承接 Q14-00 / Q12-05：生产 SLO 7/14 天历史 + Android 真机演练采集，随后发布 `docs/q12-acceptance-summary.md`（待外部环境，已连续顺延三个季度；若环境短期不可得，应显式重新定界而非继续顺延）
- [~] Q15-01 让已声明的门禁真正拦得住（本地部分完成；服务端强制力不可得）：确认并记录 `main` 的分支保护状态、把 `ci.yml` 各 job 设为 required status checks（若当前套餐不支持，则退化为文档约定 + 本地钩子并如实说明）；`pre-commit install` 纳入 `make setup` 与 CLAUDE/AGENTS 验证章节；修掉 `.pre-commit-config.yaml` 中 mypy 钩子对环境 `PATH` python 的依赖；补 Makefile 与 `ci.yml` 覆盖率门禁的漂移回归
- [x] Q15-02 后端测试单文件可运行：183 个非 integration 文件逐个通过；8 个 `No module named 'app'` 走统一 `sys.path` 引导（扩展 `backend/tests/_paths.py` 或加 `tests/__init__.py`）、根 conftest 的 `app.api.deps` stub 补 `assert_project_access` / `require_project_access`、`test_conftest_stubs.py` 不再依赖环境中可导入的 `tests` 包；CI 增加逐文件扫描防回归
- [x] Q15-03 Windows CI job：`ci.yml` 增加 `windows-latest` 后端 pytest job（Python 3.12，单测已 stub 基础设施故无需 service container），纳入 Q15-01 的 required 集合；`docs/ci-workflows.md` 说明范围与刻意排除项（integration / E2E 仍仅 Linux）
- [x] Q15-04 前端系统管理页面挂载测试：新增 `DatasetLibrary` / `StorageManagementView` / `NotificationList` / `BugTrackerList` / `MockRuleList` / `mobile-special/ReportCenterView` 六组组件测试；前端 `31 files / 128 tests`，statements `32.96%`，`views/system` statements `37.36%`，达到 ≥35% / ≥28% 目标；Vitest 门禁提升为 statements/branches/functions/lines `31.5 / 26.5 / 24.5 / 32.5`；实际文件路径与原草案中的 `MockRulesView`、`views/system/ReportCenterView.vue` 差异已按仓库路由校准
- [x] Q15-05 后端 worker / 维护任务覆盖与门禁校准：`worker/tasks_performance.py`（当前 0%）、`worker/tasks_db_backup.py`、`services/ai_healing_stats.py`、`services/dashboard_alerts.py`、`services/mobile_special/aggregator.py` 补行为缝；后端 TOTAL ≥86%，CI 门禁 70→82 使其重新贴近实际
- [x] Q15-06 处理 `chartTheme.spec.ts` 的负载敏感：或给其动态 import 配相称的超时（或去掉动态 import），或按 `docs/flaky-governance.md` 立案登记原因/证据/退出条件；不接受「全局抬高 testTimeout」了事，需说明选择了哪条路径及理由

**Q15 进展（2026-08-06）**：Q15-02 / Q15-03 / Q15-04 / Q15-05 / Q15-06 / Q15-07 已完成，Q15-01 完成本地可做部分；仅剩待外部环境的 Q15-00。Q15-04 新增六组组件级挂载测试，覆盖初始化、错误提示、配置 CRUD、导入导出、清理执行、报告筛选/停止/下载、图表主题切换与卸载清理等行为；完整前端 `31 files / 128 tests passed`，statements `32.96%`，`views/system` statements `37.36%`，类型检查和生产构建通过。实际代码中 `MockRuleList.vue` 位于 `views/mock`，`ReportCenterView.vue` 位于 `views/mobile-special`，已按真实路由记录。分支保护经实测不可得 —— 仓库是个人账户下的 private 仓库，`branches/main/protection` 与 `rulesets` 两个 API 均返回 403（需 GitHub Pro 或转为 public），因此 required status checks 无法配置，Q15-01 与 Q15-03 中「纳入 required 集合」一条在当前套餐下无法满足，已按路线图预案降级为「文档约定 + 本地钩子」并在 `docs/ci-workflows.md`「门禁强制力现状」如实说明其边界（可被 `--no-verify` 绕过）。过程中另修两个既有缺陷：mypy 钩子与 `ci.yml` 的 lint job 都只装开发依赖，看不到 SQLAlchemy 真实签名（`d116359^` 的 run_retention.py 只报 8 个错而完整环境报 12 个，少掉的 4 条 `not_in()` arg-type 正是催生本季度的那批）；ruff 的受检脚本清单此前只在 Makefile 生效，CI 与钩子都没覆盖 `scripts/`。Q15-05 把五个指定模块（`tasks_performance` 0%、`aggregator` 9%、`ai_healing_stats` 26%、`tasks_db_backup` 44%、`dashboard_alerts` 56%）抬到 93–100%，并补了四个路由 —— 其中 `api/v1/auth.py` 与 `api/v1/scripts.py` 此前均为 0%（CLAUDE.md 举例引用的 `backend/tests/api/test_auth.py` 实际并不存在）。Q15-07 已发布 `docs/q14-acceptance-summary.md`，Q15-00 仍等待生产型 SLO 历史与物理 Android 设备证据。后端 `1467 passed`、TOTAL **86.04%（Python 3.12，CI 口径）/ 85.55%（Python 3.14，本地）**，门禁 70 → **82**；同一命令在两个解释器下语句总数不同（13962 vs 13367，差 0.5 个百分点），这正是路线图规划输入 82.73% 本地复现不出来的原因，抬门禁以 3.12 为准并复验 3.14，详见 `docs/coverage-baseline-2026-q13.md` 的 Interpreter note。单文件扫描 `191 passed, 0 failed`，完整 pre-commit 链 8/8 通过。

- [x] Q15-07 Q14 验收总结：按 Q13 格式发布 `docs/q14-acceptance-summary.md`（六个本地工作项、覆盖弧线后端 74%→82.73% 与前端 8.51%→21.48%、Q14-00 顺延、以及门禁未生效放过的两个缺陷：`run_retention` mypy 报错与仅在 Windows 触发的测试断裂）；2026-08-06 已发布

---

## Q16 — 性能压测中心可视化升级与环境联动

> 立项日期：2026-08-06。目标是把当前“k6 脚本执行与结果查看”薄切，升级为测试人员可以直接配置的 HTTP 压测工作台；仍以 k6 为第一阶段执行器，不扩展为 APM 平台。
> 方案基线：`docs/performance-testing-thin-slice.md`「Q16 升级计划」。

### Phase 1 — 可视化压测场景与环境注入（本次开发范围）

- [x] Q16-01 可视化创建 HTTP 场景：URL、Method、Headers、Params、Body、认证方式、状态码/响应内容检查。
- [x] Q16-02 内置 smoke/load/stress/spike/soak 五类压力模板，自动生成 k6 脚本并继续支持手写脚本上传。
- [x] Q16-03 运行时选择环境后，自动注入环境变量；环境变量在触发时加密固化到本次运行快照，由 worker 使用该快照解密加载，运行中修改环境不会影响已触发任务。
- [x] Q16-04 支持环境变量占位符 `{{VARIABLE_NAME}}`，在 URL、请求头、参数和请求体中统一解析。
- [x] Q16-05 增加可视化配置的前端单元测试、环境注入 API 回归测试和脚本生成器测试。

### Phase 2 — 运行控制与结果可用性

- [x] Q16-06 增加执行进度轮询、实时状态刷新和安全停止任务。
- [x] Q16-07 增加结果 JSON/CSV 导出、压测报告摘要和阈值门禁结果的可读化展示。
- [x] Q16-08 增加基线回归比较、定时执行和 CI 阈值门禁。

### Phase 3 — 专业压测能力

- [x] Q16-09 接入 CPU、内存、PostgreSQL、Redis、MinIO 等系统指标并与压测时间线关联。
- [x] Q16-10 支持分布式压测节点、节点资源限制和压测网络出口隔离。
- [x] Q16-11 数据集参数化和复杂用户行为编排：数据集版本固定、worker-only 注入、字段占位符和顺序多步骤 HTTP 行为已完成。
- [x] Q17-01 统一性能执行器契约并接入 Locust：能力矩阵、公共进程生命周期、Locust CSV 摘要适配和前端执行器选择已落地；真实 worker 镜像联调保留为环境验收项。
- [x] Q17-02 gRPC 性能执行器：完成 `.proto` 上传、动态 descriptor 编译、Unary/Server Streaming/Client Streaming/Bidi Streaming 并发调用、TLS/metadata 安全校验、取消、节点 allowlist、统一摘要及本地真实服务联调；待 Linux/Kubernetes 目标服务环境验收。

**Q16 验收口径**：新建可视化场景无需手写 k6 脚本或 options JSON；选择环境后目标地址与变量可直接用于执行；敏感环境变量不出现在普通用户可见的 options 快照；原有脚本上传、异步执行、指标趋势和结果对比功能保持兼容。

**Q16 Phase 2 进展（2026-08-07）**：Q16-01 至 Q16-08 已完成。新增 `cancelling` 状态、Redis 取消标记、k6 子进程安全终止、前端活动 run 轮询与进度估算；新增安全 JSON/CSV 报告导出、脱敏快照、阈值门禁汇总/展示、持久化基线、按时区 Cron 调度、重叠保护和 CI API Key 门禁脚本。完整非集成后端回归 `1507 passed`，前端 `36 files / 142 tests passed`，Ruff、mypy、type-check 与生产构建通过；下一步进入 Q16-09。

**Q16 Phase 3 进展（2026-08-07）**：Q16-09 已完成。performance worker 在 k6 运行期间按配置采集 CPU、内存、PostgreSQL、Redis、MinIO 指标，样本通过 `performance_metric_samples` 与 `PerformanceRun` 关联；新增 Prometheus `atp_performance_resource` gauge、资源指标查询 API 和压测详情时间线，可按指标切换查看。采集异常按组件隔离，不阻断压测；完整非集成后端回归 `1514 passed`，前端 `36 files / 142 tests passed`，type-check、生产构建、Ruff 和 mypy 通过；下一步进入 Q16-10 分布式压测节点与资源隔离。

**Q16 Phase 3 进展（2026-08-07）**：Q16-10 已完成。新增 `PerformanceNode` 模型与 `20260529_0043_add_performance_nodes.py` 迁移，支持节点注册、心跳、在线状态、队列绑定以及节点级 VU/并发/目标出口约束；手动和定时 run 均可绑定节点队列，worker 启动前再次校验节点身份与容量；性能中心新增节点状态卡片、容量和心跳展示及运行/定时节点选择；Helm 增加 dedicated performance worker 节点参数和可选 Egress NetworkPolicy。Q16-10 定向回归 `72 passed`，前端 type-check 和 Helm schema 校验通过；下一步进入 Q16-11 Locust/gRPC、数据集参数化和复杂用户行为编排。

**Q16-11 进展（2026-08-07）**：已完成 k6 数据集参数化和多步骤用户行为编排。压测定义绑定数据集后，触发 run 固定当前版本，worker 通过 `ATP_DATASET_JSON` 注入数据行；可视化脚本支持字段占位符、按 VU 轮转数据和顺序 HTTP 步骤/think time。

**Q17-01/Q17-03 进展（2026-08-07）**：新增统一性能执行器能力矩阵和公共 subprocess 生命周期，k6 保持兼容；Locust 已接入 `.py` 上传、headless 执行、aggregate CSV 结果归一、threshold 解析、取消/超时、数据集/环境注入、节点能力校验和前端执行器选择。gRPC 已接入 `.proto` 上传、动态 descriptor、四种调用模式、并发/迭代、TLS/metadata 校验、取消和统一结果报告；新增外部环境 smoke 命令、JSON 证据报告、Kubernetes rollout/Pod/镜像依赖检查、真实运行/取消入口和 Worker 健康探针；补充 ARM64 Docker Compose 隔离验收栈、可复现 TLS gRPC/HTTP 目标和 Worker 公有 CA 挂载配置。本地真实 gRPC 服务回归已覆盖，后端非集成回归 `1578 passed`；Linux 主机已确认仅有 Docker/Compose，Q17-04 仍需在该隔离栈上完成真实 smoke、取消、allowlist 和资源采样证据。

**2026-08-06 修复补充**：同步完成启动配置安全校验与草稿脱敏、Ollama 无 Key 配置、AI 模型多模态能力切换、Web 录制事件去重/会话清理/Linux display 提示，以及压测环境快照确定性和敏感参数过滤。后端非集成测试 `1486 passed`，前端 `35 files / 139 tests passed`，type-check、生产构建和 Ruff 均通过。

**2026-08-07 审查修复与文档同步**：修复性能调度共享队列与专用节点队列消费关系，增加 Worker 启动后的持续心跳和异常后重排队；修复 Webhook 执行器透传、Locust/gRPC 进度估算，以及定时任务跳过活动 run 时 `next_run_at` 未提交问题。已同步 `docs/celery-queues.md`、`docs/deploy-helm.md`、`docs/performance-testing-thin-slice.md` 和外部验收 Runbook；本轮定向回归 `93 passed`，性能服务/任务回归 `46 passed`，Ruff、格式检查和 `git diff --check` 通过。完整 Worker 套件的 8 个失败为既有 MinIO/数据库测试桩隔离问题，仍需单独治理；Q17-04 Linux/Kubernetes 真实环境验收仍未完成。

**2026-08-07 AI 生成上下文增强**：AI 用例生成已支持按当前项目选择一个测试数据集和多个 Mock 规则；后端校验项目归属，向模型提供数据集字段/少量样例、Mock 方法/路径/状态码/响应体/录制样本，并在发送前脱敏密码、Token、Cookie、Authorization 等敏感字段。生成草稿使用数据集字段占位符，保存时自动绑定所选数据集；Mock 规则只作为生成上下文，不会被 AI 自动修改。已补充后端脱敏/权限/Prompt 回归测试、前端选择控件和治理文档。
