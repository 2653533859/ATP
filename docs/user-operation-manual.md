# ATP 项目操作手册

本文档面向 ATP（Automated Testing Platform）平台的使用者、测试工程师、管理员与本地开发联调人员，说明如何启动系统、登录平台、配置基础数据、创建与执行测试、查看报告以及处理常见问题。

## 1. 系统定位

ATP 是统一自动化测试平台，当前已支持：

- 接口测试：HTTP / REST、GraphQL、WebSocket、gRPC。
- Web UI 测试：Playwright 脚本模式、低代码步骤模式、截图与录像报告。
- Android UI 测试：ADB 设备扫描、APK 管理、uiautomator2 脚本模式、低代码步骤模式、屏幕镜像。
- 编排能力：测试套件、测试计划、Cron 定时、Webhook 触发、CI/CD 集成。
- 报告能力：执行记录、报告详情、HTML / PDF / JUnit XML 导出。
- 平台增强：Mock 服务、环境变量、全局变量、通知、缺陷跟踪、存储治理、统计看板、数据集、性能压测、AI 用例生成、AI 自愈建议。

当前 iOS 自动化仅有规划文档，尚未实现执行链路。详见 `docs/ios-device-automation-plan.md`。

## 2. 访问入口与账号

### 2.1 本地开发入口

Windows 本地开发默认入口：

```text
前端登录页：http://127.0.0.1:5173/login
后端健康检查：http://127.0.0.1:8000/health
MinIO 控制台：http://localhost:9001 或本地环境实际 MinIO 地址
```

Docker Compose 部署默认入口：

```text
平台入口：http://localhost
Flower：http://localhost:5555
MinIO Console：http://localhost:9001
```

### 2.2 初始管理员

首次启动会根据 `.env` 中的配置创建管理员：

```env
FIRST_ADMIN_USERNAME=
FIRST_ADMIN_PASSWORD=
FIRST_ADMIN_EMAIL=
```

如果无法登录，请先确认：

- 数据库迁移已执行到 head。
- 后端日志中存在管理员初始化成功或用户已存在的记录。
- 当前访问的是前端入口，不是后端 API 地址。

### 2.3 角色说明

平台包含基于角色的权限控制。常见角色：

- `admin`：系统管理员，可访问审计日志、执行记录清理、看板告警、AI 自愈示例/报表等管理页面。
- `engineer`：工程师，可管理项目、用例、套件、计划、执行与常规配置。
- `tester`：测试人员，偏向创建、执行和查看测试资产。
- `viewer`：查看者，偏向只读访问。

具体权限以当前后端 RBAC 实现为准。

## 3. 本地启动与停止

### 3.1 Windows 一键启动

在项目根目录执行：

```powershell
cd F:\A__Project\ATP
.\local-dev.cmd up
```

查看状态：

```powershell
.\local-dev.cmd status
```

查看日志：

```powershell
.\local-dev.cmd logs
```

重启：

```powershell
.\local-dev.cmd restart
```

停止：

```powershell
.\local-dev.cmd down
```

脚本会启动：

- Backend API
- Celery Worker
- Celery Beat
- Frontend Vite

日志和 PID 文件位于：

```text
.local-run/
```

### 3.2 手动开发启动

后端：

```powershell
cd F:\A__Project\ATP\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload
```

前端：

```powershell
cd F:\A__Project\ATP\frontend
npm install
npm run dev
```

Worker：

```powershell
cd F:\A__Project\ATP\backend
.\.venv\Scripts\Activate.ps1
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

Beat：

```powershell
cd F:\A__Project\ATP\backend
.\.venv\Scripts\Activate.ps1
celery -A app.worker.celery_app beat --loglevel=info
```

### 3.3 Docker Compose 启动

完整栈：

```bash
docker compose up --build
```

后台运行：

```bash
docker compose up --build -d
```

停止：

```bash
docker compose down
```

复用外部 PostgreSQL / Redis / MinIO 时：

```bash
docker compose -f docker-compose.app.yml up --build -d
```

## 4. 首次初始化流程

推荐按以下顺序初始化：

1. 准备 `.env` 与 `backend/.env`。
2. 启动 PostgreSQL、Redis、MinIO。
3. 执行数据库迁移：

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

4. 启动后端、Worker、Beat、前端。
5. 访问登录页，用管理员账号登录。
6. 创建项目。
7. 创建模块。
8. 配置环境变量、全局变量、通知和缺陷跟踪。
9. 创建测试用例。
10. 执行用例，查看执行记录和报告。

## 5. 页面导航

主菜单包含：

| 菜单 | 用途 |
| --- | --- |
| 统计看板 | 查看执行趋势、通过率、失败 Top、执行人 Top、触发方式分布等 |
| 项目管理 | 创建项目、维护项目成员 |
| 用例管理 | 管理接口、Web、Android 等测试用例 |
| 执行记录 | 查看单用例、套件、计划执行历史与报告 |
| 测试套件 | 组合多个用例并批量执行 |
| 测试计划 | 配置手动、Cron、Webhook 等触发方式 |
| 设备管理 | 扫描与维护 Android 设备 |
| APK 管理 | 上传和管理 Android APK |
| Mock 服务 | 管理 Mock 规则、查看请求日志 |
| Android 专项 / 专项任务 | 创建性能、稳定性、流畅度等 Android 专项任务 |
| Android 专项 / 报告中心 | 查看 Android 专项执行报告 |
| 系统管理 / 环境管理 | 配置运行环境与环境变量 |
| 系统管理 / 通知配置 | 配置邮件、企业微信、钉钉通知 |
| 系统管理 / 缺陷跟踪 | 配置 Jira、禅道、GitHub Issues 等缺陷系统 |
| 系统管理 / 存储管理 | 管理 MinIO 文件保留、清理和存储告警 |
| 系统管理 / 全局变量 | 配置跨项目或项目级变量 |
| 系统管理 / AI 模型配置 | 配置 AI 用例生成与自愈所需模型 |
| 系统管理 / 测试数据集 | 管理数据集、schema、版本和校验策略 |
| 系统管理 / 性能压测中心 | 上传 k6 脚本、触发压测、查看趋势与对比 |
| 系统管理 / 审计日志 | 管理员查看操作审计 |
| 系统管理 / 执行记录清理 | 管理员预览与清理历史执行记录 |
| 系统管理 / 看板告警 | 管理员配置看板指标告警 |

## 6. 项目与模块管理

### 6.1 创建项目

操作路径：

```text
项目管理 -> 新建
```

建议填写：

- 项目名称：业务系统或 App 名称。
- 项目编码：稳定、短小、可读，例如 `mall-app`。
- 描述：说明项目范围。

创建项目后，可进入成员管理，为不同用户分配项目角色。

### 6.2 创建模块

操作路径：

```text
用例管理 -> 选择项目 -> 模块目录 -> 新建模块
```

模块建议按业务域划分，例如：

- 登录注册
- 商品搜索
- 订单支付
- 个人中心

模块支持树形结构，可创建子模块。

## 7. 环境与变量

### 7.1 环境管理

操作路径：

```text
系统管理 -> 环境管理
```

常见环境：

- 开发环境
- 测试环境
- 预发环境
- 生产环境

每个环境下可以配置变量，例如：

```text
base_url=https://test-api.example.com
token=xxx
```

执行接口用例时，可通过变量占位符引用环境变量。

### 7.2 全局变量

操作路径：

```text
系统管理 -> 全局变量
```

全局变量适合存储跨环境或跨用例复用的值：

- 通用账号
- 公共 Header
- 公共业务参数

敏感变量建议标记为 secret，避免明文展示。

## 8. 用例管理

操作路径：

```text
用例管理
```

用例通常归属于：

```text
项目 -> 模块 -> 用例
```

### 8.1 接口用例

支持类型：

- HTTP / REST
- GraphQL
- WebSocket
- gRPC

接口用例建议配置：

- 请求方法
- URL 或路径
- Headers
- Query Params
- Body
- 认证方式
- 断言
- 变量提取

常见断言：

- 状态码等于 `200`
- JSONPath 字段等于预期值
- 响应头包含指定值
- 响应时间小于阈值

常见变量提取：

```text
从 $.data.token 提取 token，供后续步骤使用
```

### 8.2 Web UI 用例

Web 用例支持两种模式：

- 脚本模式：上传或编辑 pytest + Playwright 脚本。
- 低代码模式：配置跳转、点击、输入、等待、断言、截图等步骤。

低代码步骤建议顺序：

1. 跳转 URL。
2. 等待页面关键元素出现。
3. 输入账号、密码。
4. 点击登录按钮。
5. 断言页面文本或元素可见。
6. 必要时截图。

### 8.3 Android 用例

Android 用例支持：

- pytest + uiautomator2 脚本模式。
- 低代码步骤模式。

低代码步骤支持：

- 点击坐标
- 点击元素
- 长按
- 滑动
- 输入
- 截图断言

Android 低代码定位方式可按页面实际情况选择 text、resourceId、xpath 等。

### 8.4 AI 用例生成

操作入口通常位于用例管理页面的 AI 生成功能。

可输入：

- 需求描述
- OpenAPI 内容
- cURL 请求

生成后会得到可编辑草稿，确认无误后再保存为正式用例。

使用前需要先在：

```text
系统管理 -> AI 模型配置
```

配置模型服务。

## 9. 执行用例

### 9.1 单用例执行

操作路径：

```text
用例管理 -> 选择用例 -> 执行
```

执行前选择：

- 执行环境
- 运行配置
- Android 用例所需设备 / APK
- Web 用例所需浏览器配置

执行后可在：

```text
执行记录
```

查看结果。

### 9.2 批量执行

可通过：

- 用例列表批量选择后执行。
- 测试套件执行。
- 测试计划触发。

批量执行前建议确认：

- 用例状态为可执行。
- 环境变量完整。
- Android 设备在线。
- Worker 正常运行。

## 10. 测试套件

操作路径：

```text
测试套件
```

测试套件用于组合多个用例，适合：

- 冒烟测试
- 回归测试
- 业务链路测试
- 跨接口 / Web / Android 混合流程

操作步骤：

1. 新建测试套件。
2. 选择所属项目。
3. 添加用例。
4. 调整用例执行顺序。
5. 配置套件级参数或数据集。
6. 保存并执行。

执行完成后，可在套件运行记录中查看每个 case run 明细。

## 11. 测试计划

操作路径：

```text
测试计划
```

测试计划用于定时或外部触发执行。

支持触发方式：

- 手动触发
- Cron 定时触发
- Webhook 触发

配置建议：

1. 选择项目。
2. 选择测试套件或用例集合。
3. 选择执行环境。
4. 设置触发方式。
5. 配置通知策略。
6. 按需开启自动创建缺陷。

Webhook 触发适合 CI/CD 系统调用。具体集成方式见 `docs/cicd-integration.md`。

## 12. 执行记录与报告

操作路径：

```text
执行记录
```

可查看：

- 执行状态
- 开始 / 结束时间
- 耗时
- 触发方式
- 执行人
- 用例结果
- 步骤详情
- 请求 / 响应
- 截图 / 录像
- AI 自愈建议
- 缺陷创建结果

报告支持导出：

- HTML
- PDF
- JUnit XML

JUnit XML 适合 Jenkins、GitLab CI 等系统解析。

## 13. Android 设备与 APK

### 13.1 设备扫描

操作路径：

```text
设备管理 -> 扫描设备
```

本机先确认 ADB：

```powershell
adb devices
```

无线 ADB：

```powershell
adb tcpip 5555
adb connect <device-ip>:5555
adb devices
```

看到 `<device-ip>:5555 device` 后，再回到平台扫描设备。

### 13.2 APK 管理

操作路径：

```text
APK 管理 -> 上传 APK
```

建议记录：

- 所属项目
- 包名
- 版本号
- 构建号
- APK 文件

Android 用例或专项任务执行时，可选择对应 APK。

### 13.3 屏幕镜像

设备管理页面可查看设备屏幕镜像。若镜像不可用，优先检查：

- 设备是否在线。
- uiautomator2 是否可连接。
- 手机是否授权 USB / 无线调试。
- Worker 是否能访问该设备。

## 14. Android 专项任务

操作路径：

```text
Android 专项 -> 专项任务
```

适合：

- 性能测试
- 稳定性测试
- 流畅度测试

创建任务时配置：

- 项目
- 任务类型
- 设备范围
- APK
- 包名
- 运行参数
- Cron 配置

报告查看：

```text
Android 专项 -> 报告中心
```

报告中可查看：

- 执行趋势
- 指标样本
- Crash / ANR / fatal log / watchdog 事件
- 附件、截图、原始日志、trace 文件

## 15. Mock 服务

操作路径：

```text
Mock 服务
```

可创建 Mock 规则：

- 请求方法
- 路径模板
- 匹配条件
- 响应状态码
- 响应头
- 响应体

使用方式：

1. 创建 Mock 规则。
2. 复制页面展示的 Mock 服务基地址。
3. 在被测系统或接口用例中调用该地址。
4. 查看最近请求日志与匹配结果。

适合在后端接口未完成或需要稳定构造异常场景时使用。

## 16. 通知配置

操作路径：

```text
系统管理 -> 通知配置
```

支持：

- SMTP 邮件
- 企业微信机器人 Webhook
- 钉钉机器人 Webhook

配置后建议先执行测试发送，确认通道可用。

通知通常在测试套件和测试计划执行完成后触发。

## 17. 缺陷跟踪

操作路径：

```text
系统管理 -> 缺陷跟踪
```

支持集成：

- Jira
- 禅道
- GitHub Issues
- GitLab 类型扩展

建议配置：

- 服务地址
- Token / 用户凭据
- 项目映射
- 字段映射
- 状态同步规则

在执行报告页面，可针对失败结果创建缺陷。平台支持重复缺陷检测和截图附件上传。

## 18. 数据集

操作路径：

```text
系统管理 -> 测试数据集
```

数据集适合做数据驱动测试。

支持能力：

- 数据上传与预览
- schema 字段校验
- soft / hard-block 校验策略
- 版本历史
- 回滚
- 引用影响面查询

建议使用方式：

1. 新建数据集。
2. 定义字段 schema。
3. 上传或录入 rows。
4. 设置校验策略。
5. 在用例、套件或计划中引用。

## 19. 性能压测中心

操作路径：

```text
系统管理 -> 性能压测中心
```

当前性能压测中心基于 k6 脚本。

操作步骤：

1. 新建性能测试。
2. 上传 k6 脚本。
3. 设置执行器、VUs、duration、threshold。
4. 触发执行。
5. 查看 RPS、p95、p99、错误率、threshold 结果。
6. 使用趋势和 run 对比分析变化。

为避免误压生产环境，可配置：

```env
PERFORMANCE_TARGET_ALLOWLIST=
PERFORMANCE_MAX_VUS=
PERFORMANCE_MAX_DURATION_SECONDS=
```

## 20. AI 能力

### 20.1 AI 模型配置

操作路径：

```text
系统管理 -> AI 模型配置
```

用于配置：

- 模型供应商
- API Base URL
- API Key
- 模型名称
- 是否支持视觉能力

### 20.2 AI 用例生成

在用例管理中通过需求、OpenAPI 或 cURL 生成用例草稿。生成后必须人工检查再保存。

### 20.3 AI 自愈建议

用例执行失败后，平台可生成结构化修复建议，例如：

- 定位器替换
- 等待策略调整
- 断言修正
- 参数安全修复

建议由测试人员人工确认后应用，不建议无审核自动改用例。

管理员可在：

```text
系统管理 -> AI 自愈示例
系统管理 -> AI 自愈报表
```

维护高质量示例和查看采纳率。

## 21. 存储管理与清理

操作路径：

```text
系统管理 -> 存储管理
```

可管理：

- MinIO bucket 使用情况
- 按前缀统计对象
- 存储保留策略
- 过期对象预览
- 阻塞对象与孤儿引用
- 清理执行

执行记录清理：

```text
系统管理 -> 执行记录清理
```

建议先预览，再执行清理。

重要环境变量：

```env
FILE_RETENTION_DAYS=
RUN_CLEANUP_ENABLED=
RUN_RETENTION_DAYS=
RUN_CLEANUP_BATCH_SIZE=
STORAGE_ALERT_SIZE_GB=
```

## 22. 统计看板与告警

操作路径：

```text
统计看板
```

可查看：

- 总用例数
- 总执行次数
- 通过率
- 执行趋势
- 失败 Top
- 执行人 Top
- 触发方式分布
- 计划 / 套件趋势

管理员可配置：

```text
系统管理 -> 看板告警
```

告警指标包括通过率、平均耗时、失败数量、错误数量、总运行数等。

## 23. 审计日志

操作路径：

```text
系统管理 -> 审计日志
```

仅管理员可访问。

审计日志用于追踪关键操作，例如：

- 创建 / 修改 / 删除项目
- 修改配置
- 执行清理
- 权限相关操作

## 24. 常见排障

### 24.1 前端打不开

检查：

```powershell
.\local-dev.cmd status
```

确认 Frontend Vite 正在运行，并访问：

```text
http://127.0.0.1:5173/login
```

如端口被占用：

```powershell
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
```

### 24.2 后端健康检查失败

访问：

```text
http://127.0.0.1:8000/health
```

查看日志：

```powershell
.\local-dev.cmd logs
```

常见原因：

- PostgreSQL 不可达。
- Redis 不可达。
- MinIO 不可达。
- Alembic revision 未升级到 head。
- `.env` 与 `backend/.env` 配置不一致。

### 24.3 数据库迁移失败

执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade head
```

若出现 schema drift，先查看 `docs/migrations.md`，不要直接手工删表或改 `alembic_version`。

### 24.4 Worker 不消费任务

检查 Worker 状态：

```powershell
.\local-dev.cmd status
```

查看 Worker 日志：

```powershell
.\local-dev.cmd logs
```

常见原因：

- Redis 地址或密码错误。
- Worker 未监听对应队列。
- 任务卡在 pending。
- Celery Beat 未运行，定时任务未投递。

### 24.5 MinIO 上传失败

检查：

- `MINIO_HOST`
- `MINIO_PORT`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `MINIO_BUCKET`

确认 MinIO 健康：

```powershell
Invoke-WebRequest -UseBasicParsing http://<minio-host>:9000/minio/health/live
```

### 24.6 Android 设备扫描不到

先在本机确认：

```powershell
adb devices
```

如果没有设备：

```powershell
adb kill-server
adb start-server
adb devices
```

无线 ADB：

```powershell
adb tcpip 5555
adb connect <device-ip>:5555
adb devices
```

确认状态为 `device` 后，再到平台扫描。

### 24.7 用例执行失败

优先查看执行详情中的：

- 错误堆栈
- 请求 / 响应内容
- 断言详情
- 截图 / 录像
- 环境变量解析结果
- AI 自愈建议

常见原因：

- 环境选错。
- 变量未配置或提取失败。
- 接口返回结构变化。
- UI 元素定位器失效。
- Android 设备离线或 App 未安装。

## 25. 日常使用建议

- 用例先在单用例执行中验证通过，再加入套件和计划。
- 定时计划建议先设置较低频率，确认稳定后再提高频率。
- Mock 规则命名要包含业务场景，便于排查。
- Android 无线设备建议保持充电和同一局域网。
- AI 生成和 AI 自愈建议必须人工审核。
- 清理存储和执行记录前先预览。
- 重要配置变更后查看审计日志确认记录完整。

## 26. 相关文档

- `README.md`：项目总览与快速开始。
- `Task.md`：当前进度与模块完成度。
- `PRD.md`：产品需求与范围。
- `docs/windows-local-run.md`：Windows 本地启动说明。
- `docs/android-device-debugging.md`：Android 真机联调说明。
- `docs/cicd-integration.md`：CI/CD 集成说明。
- `docs/migrations.md`：数据库迁移说明。
- `docs/external-infra-run.md`：外部基础设施运行说明。
- `docs/ios-device-automation-plan.md`：iOS 设备自动化扩展规划。
