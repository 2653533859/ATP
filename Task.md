# ATP 项目任务跟踪

**最后更新**: 2026-03-06
**当前阶段**: Phase 4 - 高级功能

> 状态说明：
> - `[ ]` 待开始
> - `[~]` 进行中
> - `[x]` 已完成
> - `[-]` 已跳过/暂缓

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
- [ ] 执行首次迁移，验证表结构正确

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

- [ ] 在 Worker Docker 镜像中安装 Playwright + Chromium
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

- [ ] 验证 Worker 容器通过 ADB over TCP 连接宿主机真机
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

- [ ] 实现 `TestPlan` CRUD 接口
- [ ] 配置 Celery Beat，支持 Cron 表达式定时触发
- [ ] 实现手动触发 / 定时触发 / Webhook 触发三种模式
- [ ] 前端：测试计划配置页面（Cron 可视化配置）

### 4.4 CI/CD 集成

- [x] 实现 Webhook 触发接口（`POST /api/v1/webhook/trigger`，API Key 认证）
- [x] 测试结果支持 JUnit XML 格式导出（供 Jenkins 解析）
- [x] 提供 GitLab CI `.gitlab-ci.yml` 模板示例
- [x] 编写 CI/CD 集成文档

### 4.5 通知集成

- [ ] 实现邮件通知（SMTP，执行完成后发送报告摘要）
- [ ] 实现企业微信机器人通知
- [ ] 实现钉钉机器人通知
- [ ] 前端：通知配置页面

### 4.6 统计看板

- [ ] 实现统计数据聚合接口（通过率趋势、执行时长、失败 Top 10）
- [ ] 前端：统计看板页面（折线图 / 柱状图 / 饼图，基于 ECharts）

---

## Phase 5 - 完善与优化

### 5.1 接口 Mock Server

- [ ] 实现内置 Mock Server（可配置路径 + 响应）
- [ ] 前端：Mock 规则管理页面

### 5.2 用例版本历史

- [ ] 实现用例修改历史记录（快照存储）
- [ ] 实现用例版本回滚接口
- [ ] 前端：版本历史查看与回滚页面

### 5.3 报告导出

- [ ] 支持执行报告导出为 HTML（内嵌截图）
- [ ] 支持执行报告导出为 PDF

### 5.4 缺陷跟踪集成（可选）

- [ ] Jira 集成：失败用例一键创建 Issue
- [ ] 禅道集成：失败用例一键创建 Bug

### 5.5 安全与性能

- [ ] 敏感配置加密存储（环境变量中的密码、Token）
- [ ] API 接口限流
- [ ] 数据库查询优化（索引审查）
- [ ] 大报告分页加载优化
- [ ] Worker 资源隔离（防止单任务耗尽资源）

### 5.6 运维支持

- [ ] 日志统一收集（结构化日志输出）
- [ ] 健康检查接口（`GET /health`）
- [ ] 截图/报告文件定期清理任务（超过保留期限自动删除）
- [ ] 一键部署脚本与初始化数据（管理员账号、默认环境）

---

## 里程碑汇总

| 里程碑 | 完成条件 | 状态 |
|--------|---------|------|
| **M1** Phase 1 完成 | HTTP 接口测试用例可完整执行并看到报告 | `[x]` |
| **M2** Phase 2 完成 | Playwright 脚本可上传执行，报告含截图 | `[x]` |
| **M3** Phase 3 完成 | 真机连接，uiautomator2 脚本可执行 | `[x]` |
| **M4** Phase 4 完成 | 支持调度、套件、CI/CD 集成、看板 | `[ ]` |
| **M5** Phase 5 完成 | 全功能上线，安全加固 | `[ ]` |
