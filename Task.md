# ATP 项目任务跟踪

**最后更新**: 2026-05-19
**当前阶段**: Q3 - 效率工具化与可观测性增强

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
- [~] 已提交 Alembic 迁移文件与迁移回归测试，但首建流程仍依赖启动时 `create_all` 兜底，尚未统一为纯迁移驱动

### 1.3 用户认证

- [x] 实现用户注册/登录接口（`POST /api/v1/auth/login`）
- [x] 实现 JWT Token 签发与验证中间件
- [x] 实现 Token 刷新接口（`POST /api/v1/auth/refresh`）
- [x] 实现基于角色的权限控制（RBAC）依赖注入
- [x] 前端：实现登录页面（用户名/密码）
- [x] 前端：实现 Token 存储与自动携带（axios 拦截器）
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

- [~] Worker 容器侧已安装 `adb`，执行前新增设备可达性校验，并补齐 ADB over TCP 真机联调说明；最终稳定性仍受宿主机网络与设备环境影响
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

- [ ] Android 真机在不同宿主机 / Docker 网络环境下的稳定性验证沉淀
- [ ] 部署、运维与性能优化的持续打磨
- [ ] 少量页面残余 `any` / 宽类型结构的工程化收口

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
- [ ] 英文文案复核：对业务术语、错误提示和 AI 生成相关提示进行二次校对

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
9. [~] 文案复核批次：已执行 `rg "[一-龥]" frontend/src/views frontend/src/components` 收口扫描；当前剩余可见中文主要集中在 `SuiteList.vue`、`CaseFormDrawer.vue`，需作为下一轮前端 i18n 迁移继续跟踪；`RunDetail.vue` / `DashboardView.vue` 剩余多为注释或后端错误字符串判断。

---

## 里程碑汇总

| 里程碑 | 完成条件 | 状态 |
|--------|---------|------|
| **M1** Phase 1 完成 | HTTP 接口测试用例可完整执行并看到报告 | `[x]` |
| **M2** Phase 2 完成 | Playwright 脚本可上传执行，报告含截图 | `[x]` |
| **M3** Phase 3 完成 | 真机连接，uiautomator2 脚本可执行 | `[~]` |
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

- [ ] 按用例类型（API / Web / Android）分组统计饼图

### P2 - 性能优化

- [ ] 高频查询加 Redis 缓存（TTL 5 分钟），避免大量并发时直接打数据库
- [ ] `test_runs` 表添加复合索引：`(status, created_at)` 和 `(case_id, status, created_at)`
- [ ] 看板数据按需加载：首屏只加载总览和通过率趋势，其余图表滚动到可视区再请求
- [ ] 大时间跨度（> 90 天）自动切换为按周聚合，避免 X 轴过密

### P3 - 高级功能

- [ ] 看板数据导出：支持导出为 PNG 图片或 CSV 数据
- [ ] 自定义看板：用户可选择显示/隐藏哪些图表卡片，自定义布局
- [ ] 项目级看板 vs 全局看板切换
- [ ] 通过率/时长异常告警：通过率低于阈值或时长突增时自动标红提醒

---

## Phase 5.1 Mock Server — 后续优化计划

> 以下为 Mock Server 的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 规则快速复制：一键复制已有规则，修改路径/响应即可
- [x] 响应体语法高亮：monospace 等宽字体 + JSON 格式化按钮
- [x] Mock 请求日志：记录最近 N 次命中 Mock 服务的请求（method/path/timestamp），方便调试
- [x] 路径模板支持：支持 `/api/users/{id}` 形式的路径参数匹配

### P1 - 功能增强

- [ ] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则
- [ ] Mock 规则版本管理：规则修改历史，支持回滚

### P2 - 高级功能

- [ ] 独立端口模式：可选将 Mock 服务运行在独立端口，URL 不带 `/mock/` 前缀
- [ ] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则
- [ ] Mock 规则版本管理：规则修改历史，支持回滚

---

## Phase 5.2 用例版本历史 — 后续优化计划

> 以下为用例版本历史的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 快照详情展开/折叠 config JSON 内容，便于查看完整配置差异
- [x] 版本对比：选择两个版本进行 diff 可视化（name/description/tags/config 逐字段对比）
- [x] 快照列表分页加载：快照数量过多时分页查询，避免一次加载全部
- [x] 快照操作人显示为用户名而非 user_id（JOIN users 表或前端缓存映射）

### P1 - 功能增强

- [ ] 手动创建快照：支持用户主动保存当前版本（不依赖编辑触发），并添加版本备注
- [ ] 快照保留策略：可配置最大快照数量（如保留最近 50 个），超出自动清理最旧快照
- [ ] 批量回滚确认：回滚前弹出详细对比弹窗，显示当前值 vs 快照值
- [ ] 快照搜索：支持按版本号、名称关键字搜索快照

### P2 - 高级功能

- [ ] 快照导出/导入：支持将某个版本导出为 JSON 文件，或从 JSON 导入恢复
- [ ] 用例克隆自快照：从历史版本直接创建新用例（而非回滚覆盖原用例）
- [ ] 审计日志：记录每次回滚操作的触发人、时间、源版本号，供合规审查

---

## Phase 5.3 报告导出 — 后续优化计划

> 以下为报告导出的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 导出按钮 Loading 提示优化：PDF 生成较慢（~3s），增加进度提示文案
- [x] HTML 报告样式增强：添加打印友好的 @media print 样式
- [x] 报告中显示用例类型标签（API / Web / Android）
- [x] 报告时间显示时区：当前使用服务器本地时间，改为 UTC+8 或可配置时区

### P1 - 功能增强

- [ ] 报告模板可选：支持简洁版（无请求/响应）和完整版两种模板
- [ ] 视频嵌入：HTML 报告中嵌入执行录像（仅 HTML 版本，PDF 不支持视频）

### P2 - 高级功能

- [ ] 批量导出：支持选中多个执行记录一次性导出为 ZIP 包
- [ ] 定时报告邮件：结合通知模块，定时生成并发送 HTML 报告邮件
- [ ] 自定义报告封面：支持配置公司 Logo、项目名称、报告标题
- [ ] 报告 CDN 缓存：生成后存入 MinIO，重复下载直接返回缓存文件

---

## Phase 5.4 缺陷跟踪集成 — 后续优化计划

> 以下为缺陷跟踪集成的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 创建成功后在执行详情页显示已关联的缺陷链接（存储 bug_id + bug_url 到 TestRun.result_summary）
- [x] 缺陷创建前预览：弹窗中展示即将提交的标题和描述内容，确认后再提交
- [x] 错误信息截断提示：当 error_message 或 response_data 过长时显示截断提示
- [x] 创建失败时给出更友好的错误提示（区分认证失败 / 网络超时 / 项目不存在等）

### P1 - 功能增强

- [ ] 禅道多产品支持：配置中支持多产品切换

### P2 - 高级功能

- [ ] GitLab Issues 集成：扩展第三方平台支持

---

## Phase 5.5 安全与性能 — 后续优化计划

> 以下为安全与性能的迭代优化项，按优先级排列。

### P0 - 安全加固

- [x] 敏感配置落库加密：当前仅脱敏返回，后续可在写入时 Fernet 加密、读取时解密
- [x] 限流规则可配置化：将限流阈值移入 config.py / 环境变量，无需改代码即可调整
- [x] CSRF Token 保护：对非 API 客户端（浏览器直接访问）添加 CSRF 防护

### P1 - 性能增强

- [ ] 分页游标优化：高数据量场景下从 OFFSET 分页切换为 Keyset (cursor) 分页
- [ ] 执行记录列表延迟加载 steps：列表查询不 eager-load steps，仅详情页加载
- [ ] Redis 查询缓存：高频读取的统计数据加 Redis 缓存（TTL 5 分钟）

### P2 - 运维支持

- [ ] 慢查询监控：记录 > 1s 的 SQL 查询并输出警告日志
- [ ] Celery 任务超时告警：软超时时发送通知给管理员
- [ ] 定期清理过期 test_runs 数据：超过保留天数的执行记录归档或删除

---

## Phase 5.6 运维支持 — 后续优化计划

> 以下为运维支持的迭代优化项，按优先级排列。

### P0 - 日志完善

- [x] 日志级别可通过环境变量 `LOG_LEVEL` 动态配置
- [x] 请求级别 trace_id 注入：每个 HTTP 请求生成唯一 ID 贯穿日志链路
- [x] 关键业务操作审计日志：用例创建/删除、用户登录/权限变更等写入独立审计表

### P1 - 清理策略增强

- [ ] 按项目维度配置不同保留天数
- [ ] 清理前生成清理报告（即将删除的文件数量/大小），支持管理员确认
- [ ] 支持手动触发清理（管理后台按钮）

### P2 - 部署与监控

- [ ] Kubernetes Helm Chart 部署方案
- [ ] Prometheus + Grafana 监控集成（应用指标 + 基础设施指标）
- [ ] 数据库自动备份脚本（pg_dump 定时备份到 MinIO）

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


