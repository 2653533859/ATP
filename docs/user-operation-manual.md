# ATP 项目操作手册

本文档面向 ATP（Automated Testing Platform）平台的使用者、测试工程师、管理员与本地开发联调人员，说明如何启动系统、登录平台、配置基础数据、创建与执行测试、查看报告以及处理常见问题。当前导航按“工作台、测试能力、测试资产、智能中枢、系统”五组组织；代码已完成但依赖真实设备、Worker、外部服务或生产数据的能力，会明确标注“待环境验收”。

## 1. 系统定位

ATP 是统一自动化测试平台，当前已支持：

- 接口测试：HTTP / REST、GraphQL、WebSocket、gRPC。
- Web UI 测试：Playwright 脚本模式、低代码步骤模式、截图与录像报告。
- Android UI 测试：ADB 设备扫描、APK 管理、uiautomator2 脚本模式、低代码步骤模式、屏幕镜像。
- 编排能力：测试套件、测试计划、Cron 定时、Webhook 触发、CI/CD 集成。
- 报告能力：执行记录、报告详情、HTML / PDF / JUnit XML 导出。
- 平台增强：Mock 服务、环境变量、全局变量、通知、缺陷跟踪、存储治理、统计看板、数据集、性能压测、AI 用例生成、AI 自愈建议、远程工具箱和配置中心。

iOS/Appium 已具备本地 W3C 执行边界、资产和租约；真实 macOS/Xcode/XCUITest/签名 IPA/设备验收仍属于目标环境开发。

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

在项目根目录执行。先把 `$RepoRoot` 改为你的实际项目目录：

```powershell
$RepoRoot = 'E:\csh\MyProject\ATP'
Set-Location $RepoRoot
.\local-dev.cmd up
```

启动前预检：

```powershell
.\local-dev.cmd doctor
```

Windows 全量本地冒烟：

```powershell
.\scripts\windows-local-smoke.ps1
```

该命令会检查真实后端健康、管理员登录、认证读接口、前端登录页、Playwright mock E2E、Chromium/Firefox/WebKit 页面矩阵、临时文件上传/清理和 HTML/JUnit 报告生成，并在 `.local-run` 生成脱敏 JSON 报告。相对 `-ReportPath` 按项目根目录解析；没有历史执行记录时报告检查会失败，需要跳过时显式使用 `-SkipReports`。如果服务通过 `startup.cmd -Profile remote-infra` 或其他档案运行，应使用相同的 `-EnvFile`，避免 doctor 检查另一套基础设施；首次没有 Web 用例时，可用 `-SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload -SkipReports` 自动创建临时下载用例并在终态后清理；需要自动启动服务时加 `-StartServices`；验证结束后停止服务加 `-StopServicesAfter`；Android 设备诊断使用 `-AndroidTarget '<device-ip>:5555'`，完整边界与未覆盖项见 [`docs/windows-local-run.md`](windows-local-run.md)。

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
Set-Location (Join-Path $RepoRoot 'backend')
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload
```

前端：

```powershell
Set-Location (Join-Path $RepoRoot 'frontend')
npm install
npm run dev
```

Worker：

```powershell
Set-Location (Join-Path $RepoRoot 'backend')
.\.venv\Scripts\Activate.ps1
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

Beat：

```powershell
Set-Location (Join-Path $RepoRoot 'backend')
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
| 工作台 | 首页、我的待办、项目中心、任务中心；集中查看待评审、失败任务、逾期计划和设备异常 |
| 测试能力 | 接口测试、APP 自动化、UI 自动化、性能测试和 AI 智能测试；每个入口尽量覆盖配置、执行、过程和结果 |
| 测试资产 | 测试用例、测试计划、缺陷管理、测试报告和用例评审；管理可复用、可追踪的测试产物 |
| 智能中枢 | Hermes 助手、需求与用例追踪、知识中枢；跨模块提供查询、生成和检索能力 |
| 系统 | 远程工具箱、配置中心；存储、通知、用户、审计、保留策略和告警从配置中心的配置域/平台治理快捷区进入 |

侧栏按上述五组折叠展示，不再把测试业务入口和系统治理页面全部堆在下面。API 合约资产、Web 资产、Mock、数据集、设备、APK、专项任务与报告由对应测试工作台承接；进入旧页面 URL 时仍会高亮所属工作台。系统侧栏只保留远程工具箱和配置中心，配置中心提供配置域、原页面入口和管理员专属的平台治理快捷区；原有 URL、角色权限和书签均保持不变。

### 5.1 工作台与任务中心

从“工作台 -> 我的待办”查看待评审用例、失败任务、逾期计划和设备异常；从“工作台 -> 任务中心”统一筛选 Case、Suite、Plan、Android 和 Performance 任务。重试、终止和批量操作仍按当前用户角色、任务状态和任务类型限制，操作完成后可跳转到原领域详情页。

### 5.2 远程工具箱与配置中心

“系统 -> 远程工具箱”用于快速判断 PostgreSQL、Redis、MinIO、Android/Web Worker、ADB 和性能节点是否可用。检查结果只展示状态、耗时、队列/能力等脱敏信息；导出的 JSON 也不包含密码、Token、连接地址或原始异常。真实目标主机、Worker 和浏览器环境仍需单独验收。

“系统 -> 配置中心”用于统一查看有权限的启动配置、项目环境、全局变量、AI、存储、通知和性能节点。启动配置保持只读；其他配置只展示脱敏摘要，可进入原页面编辑。管理员或工程师可以查看历史版本、字段差异和影响提示；需要回退时必须在确认框输入精确的 `ROLLBACK`，回退只作用于选中的单个资源并生成新的版本和审计记录。配置中心不会直接重启服务，也不会批量删除或重建资源。

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
系统 -> 环境管理
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
系统 -> 全局变量
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

gRPC 用例会根据 Proto 中方法的声明自动选择调用模式：Unary、Server Streaming、Client Streaming 或 Bidi Streaming。可以直接粘贴 Proto 内容，也可以分别选择主 `.proto` 和 import 文件；文件会在浏览器端读取并保存到用例配置，不会作为请求文件上传。Worker 执行前会在临时目录重建文件包，并拒绝绝对路径和 `..` 路径。Unary/Server Streaming 的请求填写 JSON 对象；Client/Bidi Streaming 的请求填写非空 JSON 数组。服务端流式响应会以 JSON 数组保存，可继续使用 JSONPath 提取和响应断言。

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
系统 -> AI 模型配置（或系统 -> 配置中心中的 AI 配置域）
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

如果当前后端使用 Windows Android Agent，并将 `ADB_SCAN_MODE` 配置为 `worker`，点击扫描后页面会先显示任务排队状态，再等待 Worker 将本机 ADB 结果写回；不要把返回的旧列表当作最终扫描结果。若任务长时间未完成，请检查 `windows-android-worker.ps1 status/logs`。

Worker 模式下，截图、屏幕流、点击、滑动和“按坐标获取控件”也会通过 `ANDROID_WORKER_QUEUE` 派发到 Windows Android Worker 执行。公网 API 主机只负责鉴权和转发，不需要安装 ADB；若这些操作超时，请确认 Worker 与 API 使用同一个 Redis、Worker 正在监听该队列，并检查 `windows-android-worker.ps1 status/logs`。

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

上传 APK 后，平台会自动读取 `AndroidManifest.xml`，保存包名、版本名和版本号。Android 用例和 Android 专项任务中的 APK 选择器会展示包名；在专项任务中选择 APK 后会自动填充应用包名，手工修改仍然有效。APK 只能选择当前项目下的资源，不能跨项目引用。

### 13.3 屏幕镜像

设备管理页面可查看设备屏幕镜像。若镜像不可用，优先检查：

- 设备是否在线。
- uiautomator2 是否可连接。
- 手机是否授权 USB / 无线调试。
- Worker 是否能访问该设备。

## 14. Android 专项任务

操作路径：

```text
测试能力 -> APP 自动化 -> 专项任务
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
- 性能监控：CPU、内存、电量、温度
- 卡顿 / FPS 监控：FPS、慢帧次数
- Crash / ANR 监控：采集 logcat 异常
- 异常回放：发现 Crash / ANR 后保留屏幕回放与异常日志
- Cron 配置

报告查看：

```text
测试资产 -> 测试报告 -> Android 报告
```

报告中可查看：

- 执行趋势
- 指标样本
- 设备最新指标及指标趋势图
- Crash / ANR / fatal log / watchdog 事件
- CSV 指标、异常日志和异常回放文件

异常回放文件不会在每次运行后无条件长期保留：Worker 只在启用异常回放且发现 Crash / ANR 时，将录屏上传到 MinIO；录屏按 `replay_seconds`（默认 30 秒，允许 5-1800 秒）滚动分段，设备端最多保留前一段和当前段，避免长任务持续占用空间。报告详情页的“报告文件”区域可以直接打开或下载回放和日志。

执行过程会在报告详情页实时展示：

- 当前阶段、当前步骤和整体进度。
- 设备序列号与在线状态。
- 已采集的指标采样数量，以及实时指标点。
- Worker 日志和实时发现的 Crash / ANR 事件。

页面优先通过 `/ws/runs/{run_id}` 接收 Redis 事件；Android 专项订阅会附带 `run_type=mobile`，与普通用例的同 ID 运行隔离。WebSocket 暂时不可用时，详情页会每 3 秒轮询运行状态、指标和异常列表。执行结束后，页面会自动刷新为最终报告，实时采样不会替代数据库中的正式样本。

事件时间线会在报告详情页持久化展示每个执行阶段和操作，包含发生时间、阶段、动作、参数、结果和耗时；展开“参数/结果”即可查看本次操作的完整 JSON。

稳定性（Monkey）任务还会记录随机种子、Monkey 命令、动作日志和汇总结果。报告详情页可以点击“按原随机种子回放”创建新的回放任务；回放会复用原运行配置和种子，但会生成独立的运行记录，不会覆盖原报告。

事件记录单次运行最多保存 5000 条，报告时间线按同一上限加载。Monkey 日志超过上限时保留前面的事件，最终报告和回放种子仍然可用。

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

条件支持字符串精确匹配，也支持以下受控 JSON 操作符：

```json
{
  "scene": {"$in": ["success", "pending"]},
  "request_id": {"$contains": "test-"},
  "token": {"$exists": true}
}
```

`$exists` 判断字段是否存在，`$contains` 判断字符串是否包含片段，`$in` 判断值是否属于给定枚举。未知操作符、嵌套对象和数组条件会被拒绝；多个条件字段同时存在时按 AND 关系匹配。多条规则同时匹配时，系统依次优先选择 HTTP 方法精确的规则、路径静态段更多且占位符更少的规则、条件字段更多的规则，最后按规则 ID 倒序选择；规则变更会自动清理旧缓存。

使用方式：

1. 创建 Mock 规则。
2. 复制页面展示的 Mock 服务基地址。
3. 在被测系统或接口用例中调用该地址。
4. 查看最近请求日志与匹配结果。

适合在后端接口未完成或需要稳定构造异常场景时使用。

页面也提供“AI 生成 Mock”入口：

1. 先选择项目；可选中已有规则作为生成参考，也可以不选择规则直接填写要求。
2. 填写生成规则数量和业务要求，点击“开始生成”。项目必须已绑定启用的 AI 模型。
3. 在预览窗口检查并按需修改 JSON；AI 结果不会自动写入数据库。
4. 点击“保存 Mock 规则”后才会创建规则。页面上的“AI 生成用例”仍用于根据 Mock 规则生成测试用例草稿，两者用途不同。

生成结果只允许保存为 Mock 规则字段，不应放入真实密码、Cookie、Token 或其他敏感信息；生成数量单次最多 20 条，序列化结果超过限制时需要减少数量或缩短响应体。

## 16. 通知配置

操作路径：

```text
系统 -> 通知配置
```

支持：

- SMTP 邮件
- 企业微信机器人 Webhook
- 钉钉机器人 Webhook

配置后建议先执行测试发送，确认通道可用。

通知通常在测试套件和测试计划执行完成后触发。

通知配置中的“发送可靠性”可以设置失败重试次数（0-3）和首次重试等待时间（0-30 秒）。默认重试次数为 0，不改变旧配置行为。启用后，仅网络超时、连接失败、HTTP 5xx 或 429 会按指数退避重试；错误 Webhook、供应商明确拒绝和其他配置错误不会重复发送。测试发送和真实执行通知使用同一策略。重试耗尽后仍会记录失败日志，但不会回滚已完成的执行结果；真实 SMTP、企业微信和钉钉还应在目标环境验证限流与重复投递语义。

通知配置页下方的“最近投递记录”会展示当前项目最近 20 次实际投递，包括渠道、成功/失败、尝试次数、时间和脱敏失败原因。记录不保存邮件正文、Webhook 密钥或 Token；删除通知配置后历史仍可查询，但配置名称会显示为“已删除通知”。`NOTIFICATION_DELIVERY_CLEANUP_ENABLED=true` 时，Beat 每日执行清理任务，按 `NOTIFICATION_DELIVERY_RETENTION_DAYS`（默认 30 天）删除旧记录；如需长期留存，应在生产环境关闭自动清理并制定数据库归档策略。

审计日志清理默认关闭。只有确认合规保留和归档策略后，才设置 `AUDIT_LOG_CLEANUP_ENABLED=true`；Beat 每日按 `AUDIT_LOG_RETENTION_DAYS`（默认 365 天，范围 1-3650）删除旧审计记录，并在同一事务写入 `audit_log_cleanup` 审计事件。清理失败会回滚删除和审计事件，避免出现“删除成功但没有审计记录”的状态。

## 17. 缺陷跟踪

操作路径：

```text
测试资产 -> 缺陷管理
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
测试资产 -> 测试数据集
```

数据集适合做数据驱动测试。

支持能力：

- 数据上传与预览
- schema 字段校验
- soft / hard-block 校验策略
- 版本历史
- 回滚
- 引用影响面查询
- 项目内 AI 生成合成测试数据（生成结果先进入编辑器，不自动保存）

建议使用方式：

1. 新建数据集。
2. 定义字段 schema。
3. 上传或录入 rows。
4. 设置校验策略。
5. 在用例、套件或计划中引用。

也可以点击页面顶部的“AI 生成数据”快速生成：先选择项目，填写数据集名称、行数和生成要求，点击“开始生成”后检查编辑器中的 JSON 行，再点击“保存”。已有数据集可以从对应操作入口生成覆盖草稿；AI 不会直接覆盖数据库，生成结果仍需经过 Schema 校验和版本保存。项目必须先绑定启用的 AI 模型，单次最多生成 200 行。

数据集编辑器中的“存储方式”可选择：小数据集使用“数据库”（最多 500 行、序列化后 256KB），较大数据集使用“MinIO 对象存储”（最多 50MB JSON）。MinIO 模式只在 PostgreSQL 保存对象引用和行数，执行、AI 取样、导出和版本回滚会自动读取对象；切换或覆盖模式会先写入新对象，数据库提交成功后再清理旧的当前对象，提交失败时保留旧引用并清理本次新对象。只修改名称、描述等元数据时，接口也会回读当前 MinIO 对象并返回完整 rows，避免编辑器误显示为空。

管理员可通过 API 核对项目范围内的 MinIO 数据集对象：

```http
POST /api/v1/projects/{project_id}/datasets/storage/reconcile
{}
```

默认是只读 dry-run，会返回扫描对象数、数据库引用数、孤儿对象数和对象名称预览；确认无误并完成备份后，才使用 `{ "purge": true }` 清理未被当前数据集或版本引用的对象。清理只作用于当前项目的 `datasets/{project_id}/` 前缀，单个对象删除失败会记录在 `errors` 中；每次核对或清理都会写入审计日志。

如果 API 用例关联了数据集，可在数据集配置区域填写“数据准备动作（JSON）”。它会在本次参数化执行创建子运行前执行一次，用于调用测试服务准备数据，并通过 `post_actions` 提取共享变量；提取变量会注入每一行，行字段同名时覆盖共享变量。动作只支持受限 DSL（`request`、`set_variable`、`delete_variable`、`assert`），最多 20 个动作，单个请求最多 60 秒、响应最多 1MB，不执行 Python/JavaScript，也不会修改数据集本身。request URL 会先做公网/DNS 校验，拒绝本机、内网、链路本地和保留地址；动作配置不是 JSON 数组时会明确报错。准备失败时不会创建子运行，父运行会记录失败摘要。

## 19. 性能压测中心

操作路径：

```text
测试能力 -> 性能测试
```

性能压测中心支持 k6、Locust、gRPC 和 JMeter。Windows 本地默认适合功能联调；JMeter 需要额外安装 Java/JMeter，并在 `PERFORMANCE_EXECUTORS` 中显式加入 `jmeter`。Linux/Kubernetes 专用 Worker 才用于生产级并发和多节点结论。

操作步骤：

1. 新建性能测试。
2. 上传对应执行器脚本或协议文件（k6/Locust/JMeter/gRPC Proto）。
3. 设置执行器、VUs、duration、threshold。
4. 触发执行。
5. 查看 RPS、p95、p99、错误率、threshold 结果。
6. 使用趋势和 run 对比分析变化。

如果通过网络重试或 CI/CD 重复提交同一次压测，应复用同一个 `idempotency_key`。同一压测定义下，同键同请求会复用已有 Run；同键但环境、节点或 options 不同会返回 `409`。不传幂等键时，每次提交都会创建独立 Run。

性能 Run 的通知沿用“系统 -> 通知配置”中的项目级通道。启用通知后，正常完成、阈值失败、基线回归、节点/资源异常，以及执行器未启用、节点不可用、容量不足和启动前取消等提前终止结果，都会进入同一通知链路；正文会展示 RPS、P95/P99、错误率、阈值状态和触发原因。只有 `scope=all` 的项目通道会匹配性能事件，套件/计划专用通道不会匹配。可用 `status_filters` 只接收失败告警。通知发送失败只记录 Worker 日志，不改变已经落库的 Run 结果。

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
系统 -> AI 模型配置（或系统 -> 配置中心中的 AI 配置域）
```

用于配置：

- 模型供应商
- API Base URL
- API Key
- 模型名称
- 是否支持视觉能力

三方模型建议选择“OpenAI 兼容（三方）”协议：

- 适用于 Open WebUI、One-API、LiteLLM 等提供 OpenAI-compatible `/v1` 接口的服务。
- Endpoint 填写服务 Base URL，通常以 `/v1` 结尾；平台会从 `{Endpoint}/models` 拉取模型，并通过 `{Endpoint}/chat/completions` 调用。
- 这类服务必须填写它自己的 API Token；原生 Ollama 才可以不填 API Key，地址通常是 `http://主机:11434`。
- 是否支持多模态、思考参数需要以实际模型和供应商文档为准，页面上的模型名称提示不能替代服务端能力确认。

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
测试能力 -> AI 智能测试 -> AI 自愈示例
测试能力 -> AI 智能测试 -> AI 自愈报表
```

维护高质量示例和查看采纳率。

## 21. 存储管理与清理

操作路径：

```text
系统 -> 存储管理
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
系统 -> 执行记录清理
```

建议先预览，再执行清理。

如果项目配置了“运行记录保留天数覆盖”，项目级预览会按覆盖天数统计
Plan、Suite、TestRun 和 MobileSpecialRun；全局预览会排除这些项目，执行时也按
相同范围处理，避免预览数量与实际清理数量不一致。项目级表格会分别展示这四类运行记录和关联对象估算。
执行完成后，结果区域还会展示每个项目实际删除的四类运行记录和 MinIO 对象数量。
清理完成后，全局预览和项目级预览会同时自动刷新，便于立即核对剩余数量。
系统会先提交运行记录删除，再清理关联 MinIO 对象；若对象删除失败，可通过存储管理的孤儿对象核对继续治理，不会先删除仍被运行记录引用的附件。
当候选 TestRun 或 MobileRun 超过单批清理大小时，预览会标注 MinIO 对象数为“首批抽样”；确认框会提示实际数量可能更多。该数字用于风险提示，不代表全部附件的精确数量，实际清理结果以“已删除 MinIO 对象数”为准。

重要环境变量：

```env
FILE_RETENTION_DAYS=
RUN_CLEANUP_ENABLED=
RUN_RETENTION_DAYS=
RUN_CLEANUP_BATCH_SIZE=
NOTIFICATION_DELIVERY_CLEANUP_ENABLED=
NOTIFICATION_DELIVERY_RETENTION_DAYS=
AUDIT_LOG_CLEANUP_ENABLED=
AUDIT_LOG_RETENTION_DAYS=
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
系统 -> 看板告警
```

告警指标包括通过率、平均耗时、失败数量、错误数量、总运行数等。

## 23. 审计日志

操作路径：

```text
系统 -> 审计日志
```

仅管理员可访问。

审计日志用于追踪关键操作，例如：

- 创建 / 修改 / 删除项目
- 修改配置
- 执行清理
- 权限相关操作

列表支持按项目 ID、用户 ID、动作类型和起止时间筛选，动作下拉框也包含审计清理和导出事件。时间范围会按浏览器生成的 ISO-8601 时间传给后端；结束时间早于开始时间时会提示参数错误，不会返回误导性的空结果。管理员可以点击“导出 CSV”下载当前筛选结果，页面最多导出 5000 条，服务端最多接受 10000 条；导出使用 UTF-8 BOM，且会对可能被表格软件解释为公式的文本进行保护，不提供无上限的全量导出。成功导出会写入 `audit_log_export` 审计事件，记录操作者、筛选摘要、上限和导出条数，不记录日志正文或敏感信息。

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
- `docs/product-navigation-roadmap-2026-08-24.md`：五组产品导航和 N0～N6 开发计划。
- `docs/capability-baseline-2026-08-07.md`：能力矩阵、当前实现、目标状态和环境验收证据。
- `docs/q18-latest-status-2026-08-07.md`：最新前后实现对比与发布边界。
