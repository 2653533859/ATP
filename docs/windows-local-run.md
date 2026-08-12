# ATP Windows 本地单命令启动

本文档说明如何在 Windows 本地用一条命令启动 ATP 的前后端开发栈，同时连接运行在 WSL / Linux Docker 主机上的 PostgreSQL、Redis、MinIO。

性能执行器说明：Windows 启动脚本会自动发现 `%LOCALAPPDATA%\ATP\tools\k6\k6.exe`，也支持通过用户级 `ATP_K6_HOME` 指定 k6 目录。发现路径只注入本次启动的 Worker 子进程，不会修改仓库中的 `.env` 或机器级 PATH；执行 `doctor` 可确认 k6、Locust、gRPC 和 JMeter 的可用性。k6 的 Windows 安装方式参见 [Grafana k6 安装文档](https://grafana.com/docs/k6/latest/set-up/install-k6/)。

Android 工具说明：Windows 启动脚本和 `android-network-doctor.ps1` 会自动发现 `ATP_ADB_HOME`、`ANDROID_HOME`/`ANDROID_SDK_ROOT` 下的 `platform-tools`，以及 `%LOCALAPPDATA%\Android\Sdk\platform-tools` 和 `%LOCALAPPDATA%\ATP\tools\platform-tools`。这些路径只注入当前 PowerShell 进程及其子 Worker，不会修改系统 PATH；因此通常不需要为了 ATP 手工修改机器环境变量。若 Android SDK 安装在自定义目录，可在选中的启动档案中填写 `ANDROID_HOME`，或在用户环境变量中设置 `ATP_ADB_HOME`。

## 适用场景

- 前端、后端、Celery Worker、Celery Beat 运行在 Windows 本机
- PostgreSQL、Redis、MinIO 运行在 WSL / Linux Docker 主机
- 远端主机地址由 `.env` 或启动档案提供；文档不固化环境地址。当前根目录 `.env` 目标为 `172.31.27.133`，若该主机不可用，可临时使用已验收的 `remote-infra.env`，但必须明确记录实际运行数据源。
- Android 真机通过 Windows 本机 `adb` 直连

Web 录制默认使用 `WEB_RECORDER_MODE=local`，浏览器在 API 进程内启动。如果配置为 `WEB_RECORDER_MODE=worker`，`local-dev.cmd up` 会额外托管 `python -m app.web_recording_worker`；可通过 `local-dev.cmd status` 和 `local-dev.cmd logs` 检查录制 Worker。Windows 桌面模式不需要 `WEB_RECORDER_DISPLAY`。

`local-dev.cmd doctor` 会在启动前校验 `WEB_RECORDER_MODE`、Python Playwright 包和 Chromium 浏览器是否存在；Worker 模式还会校验 Worker 入口、Redis 队列前缀和正整数并发上限。缺少 Chromium 时按提示执行 `backend\.venv\Scripts\python.exe -m playwright install chromium`。Android Agent 的 `scripts\windows-android-worker.ps1 doctor` 会额外检查 Celery/Redis Python 依赖和 ADB，避免进程启动后才暴露依赖问题。

这种模式适合本地开发与联调：Windows 侧进程直接访问真机与浏览器，基础设施继续复用 Linux Docker 环境。

## Windows 与目标环境边界

Windows 是日常开发主线，负责 API、Web、Android、AI、数据集、Mock、报告和本地回归。Linux/Kubernetes 性能 Worker、真实设备池、macOS/iOS、容器内 Firefox/WebKit、Prometheus 和外部通知属于目标环境开发/验收，不要求在 Windows 上模拟生产并发。

先在当前 PowerShell 会话设置项目目录，下面命令不依赖固定盘符：

```powershell
$RepoRoot = 'E:\csh\MyProject\ATP' # 修改为你的实际项目目录
Set-Location $RepoRoot
```

## 一次性准备

### 1. 后端依赖

```powershell
Set-Location (Join-Path $RepoRoot 'backend')
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
playwright install chromium firefox webkit
```

### 2. 前端依赖

```powershell
Set-Location (Join-Path $RepoRoot 'frontend')
npm ci
```

如果锁文件和当前环境不一致，再执行：

```powershell
npm install
```

### 3. 本地环境变量

先复制本地环境文件：

```powershell
Set-Location $RepoRoot
Copy-Item .env.example .env
```

然后按你的本地私有凭据修改 `.env`。不要把密码提交进仓库。

连接 WSL / Linux Docker 主机时，至少确认这些配置指向远端地址：

```env
POSTGRES_HOST=<server-host>
POSTGRES_USER=<database-user>
REDIS_HOST=<server-host>
MINIO_HOST=<server-host>
MINIO_ROOT_USER=<minio-user>
APP_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
APP_AUTO_CREATE_TABLES=false
```

如果你的 Redis、PostgreSQL、MinIO 端口不是默认值，再同步补齐：

```env
POSTGRES_PORT=5432
POSTGRES_CONNECT_TIMEOUT_SECONDS=5
REDIS_PORT=6379
MINIO_PORT=9000
```

`POSTGRES_CONNECT_TIMEOUT_SECONDS`、`REDIS_CONNECT_TIMEOUT_SECONDS` 和 `MINIO_CONNECT_TIMEOUT_SECONDS` 默认均为 `5`，允许范围为 `1-120` 秒，分别限制三类基础设施的连接/操作等待时间。远程 PostgreSQL 不可达时，启动会在 PostgreSQL 超时后记录明确警告并退出本次迁移检查，不会无限停在 application startup。

远端档案中的主机地址和用户名只是占位符，需改成实际 PostgreSQL、Redis 和 MinIO 连接信息；启动配置页面会把这些占位符列为未完成项。密码、应用密钥和 Webhook Key 也必须使用目标环境的真实值，且不要提交到 Git。

说明：

- 默认要求先执行 `alembic upgrade head` 完成建表或迁移
- 应用启动时会做一次 Alembic head 校验，DB revision 与 head 不一致会在日志输出 WARNING
- `APP_AUTO_CREATE_TABLES=true` 只建议用于本地临时排障，不建议作为日常启动路径

## 单命令启动与配置档案

如果需要在多种运行方式之间切换，不要反复覆盖根目录 `.env`，使用配置档案入口：

```powershell
Copy-Item .\config\startup-profiles\local-all.env.example .\config\startup-profiles\local-all.env
Copy-Item .\config\startup-profiles\remote-infra.env.example .\config\startup-profiles\remote-infra.env
Copy-Item .\config\startup-profiles\android-agent.env.example .\config\startup-profiles\android-agent.env
```

交互式选择启动方式：

```powershell
.\startup.cmd
```

也可以直接指定：

```powershell
.\startup.cmd -Profile local-all -Action up
.\startup.cmd -Profile remote-infra -Action restart
.\startup.cmd -Profile android-agent -Action up
.\startup.cmd -Profile android-agent -Action status
```

也可以打开前端的“系统管理 → 启动配置”页面，在“启动方式”下拉框中选择四种档案之一。选择档案会回填对应的基础设施地址、队列、Worker 身份和执行器配置；保存草稿只保存在当前浏览器，不会直接重启服务。复制或下载 `.env` 后，仍需在 Windows 终端执行上面的 `startup.cmd` 命令启动对应进程。

四种档案分别表示：

- `local-all`：Windows 本机启动 Backend、Worker、Beat、Frontend，并连接本机基础设施。
- `remote-infra`：Windows 本机启动 Backend、Worker、Beat、Frontend，但 PostgreSQL、Redis、MinIO 使用远程地址。
- `android-agent`：Windows 只启动 Android Worker，本机执行 ADB；任务和结果通过远程 PostgreSQL、Redis、MinIO 交互。
- `performance-agent`：Windows 只启动性能 Worker，消费独立性能队列并通过节点 ID 注册心跳；任务和结果通过远程 PostgreSQL、Redis、MinIO 交互。

使用 `android-agent` 时，如果后端的 `ADB_SCAN_MODE=worker`，设备页扫描会显示 Worker 任务状态并等待本机 ADB 结果；不会立即把旧设备列表当成扫描结果。若只在 Windows 本地运行完整栈，可保持 `ADB_SCAN_MODE=local`。
`android-agent` 启动的 Worker 会自动注册 `ANDROID_WORKER_ID` 并通过 Redis TTL 发送心跳；设备管理页能显示当前在线 Agent。若 Redis 不可用，设备列表仍可加载，但在线 Agent 状态会显示为空，需先检查 Redis 连通性和 Worker 日志。
`local-all` 与 `android-agent` 不应在同一台 Windows 主机上同时运行：前者默认的普通 Worker 也会监听 `android,mobile_special`，后者是专用 Android Worker。`windows-local.ps1 up/restart` 和 `windows-android-worker.ps1 up/restart` 会双向识别队列重叠，发现冲突时在停止现有服务前阻止启动并提示切换档案。完整本地栈请选择 `local-all`，远程后端加本机 ADB 请选择 `android-agent`。

`startup.cmd -Profile <profile> -Action status` 会显示实际运行档案、PostgreSQL/Redis/MinIO 地址和队列。该状态来自脱敏运行元数据，不会输出密码；如果服务异常退出或执行 `down`，元数据会被清理，避免把未运行的配置文件误认为当前数据源。

### Windows 性能 Agent

如果性能节点页面已经登记了节点，但压测任务需要在另一台 Windows 主机执行，可使用专用性能 Worker：

```powershell
Copy-Item .\config\startup-profiles\performance-agent.env.example .\config\startup-profiles\performance-agent.env
# 修改远程 PostgreSQL/Redis/MinIO、PERFORMANCE_NODE_ID、PERFORMANCE_NODE_QUEUE 和出口白名单
.\startup.cmd -Profile performance-agent -Action doctor
.\startup.cmd -Profile performance-agent -Action up
.\startup.cmd -Profile performance-agent -Action status
.\startup.cmd -Profile performance-agent -Action logs -Tail 200
```

该模式只消费配置的专用节点队列（例如 `performance.worker-a`），并通过 Redis/数据库心跳把节点置为在线；共享 `performance` 队列仍由普通性能 Worker 消费。`doctor` 会阻止缺少 Python/Celery/Redis 依赖、服务端口不可达、节点 ID/队列非法或误使用共享队列的启动；k6、Locust、gRPC、JMeter 等执行器缺失只会作为可选能力警告。页面登记的节点 ID 和 `PERFORMANCE_NODE_QUEUE` 必须与配置文件一致，否则节点会显示离线并给出队列不一致原因。

真实档案位于 `config/startup-profiles/*.env`，模板是同名 `.env.example`，真实档案已被 Git 忽略。`startup.ps1` 以及两个底层 PowerShell 启动脚本的 `-EnvFile` 都只向新启动的子进程注入选中档案，不会覆盖根目录 `.env` 或当前 PowerShell 会话。

### Windows 本地 Prometheus 目标指标

Windows 可以直接运行一份只监听回环地址的 Prometheus，用于把目标服务指标采集到性能 run 的时间线中。脚本不会修改系统 PATH；Prometheus 二进制放在用户目录 `%LOCALAPPDATA%\ATP\tools\prometheus`，配置只抓取本机 ATP Backend `/metrics`。

官方 Windows amd64 安装包和版本信息见 [Prometheus 下载页](https://prometheus.io/download/)。将 `prometheus.exe` 和同目录依赖解压到上述目录后执行：

```powershell
.\scripts\windows-prometheus.ps1 -Action doctor
.\scripts\windows-prometheus.ps1 -Action up
.\scripts\windows-prometheus.ps1 -Action status
```

默认地址为 `http://127.0.0.1:9090`，停止和查看日志：

```powershell
.\scripts\windows-prometheus.ps1 -Action logs -Tail 120
.\scripts\windows-prometheus.ps1 -Action down
```

性能用例的 `default_options` 或运行覆盖参数可以配置目标指标查询；查询地址必须在性能节点出口白名单内：

```json
{
  "target_metrics": {
    "prometheus_url": "http://127.0.0.1:9090",
    "queries": {
      "backend_up": "up{job=\"atp-backend\"}",
      "request_count": "sum(http_requests_total)",
      "slow_queries": "sum(atp_slow_queries_total)"
    },
    "timeout_seconds": 2
  }
}
```

该采样器最多执行 8 条 PromQL，单次响应有大小上限，采样失败只记录在该样本的 `errors` 中，不会把目标指标故障伪装成压测成功。当前 Windows 真实闭环证据见 [`performance-windows-local-prometheus-target-metrics-2026-08-12.json`](evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json)；它证明本机 Prometheus 与 ATP run 关联可用，不替代 Linux/Kubernetes、真实外部目标或生产 SLO 历史验收。

### Windows 性能节点配置

性能中心页面的“注册节点”负责保存节点名称、队列、执行器能力、容量和出口约束；Worker 是否在线仍由 Worker 心跳决定。Windows 本地 Worker 使用同一个节点 ID 和队列即可接管该节点：

```env
PERFORMANCE_NODE_ENABLED=true
PERFORMANCE_NODE_ID=worker-a
PERFORMANCE_NODE_NAME=Windows Worker A
PERFORMANCE_NODE_QUEUE=performance.worker-a
PERFORMANCE_NODE_MAX_VUS=100
PERFORMANCE_NODE_MAX_CONCURRENCY=2
PERFORMANCE_NODE_EGRESS_ALLOWLIST=api.example.test
PERFORMANCE_EXECUTORS=k6,jmeter
CELERY_QUEUES=default,android,mobile_special,ios,ai,maintenance,performance
```

`windows-local.ps1` 会自动把共享 `performance` 队列和 `PERFORMANCE_NODE_QUEUE` 加入本机 Worker 的监听列表，因此 `performance.worker-a` 这类带点号的专用队列不会被过滤。页面已注册节点时，Worker 心跳只刷新在线状态和实际心跳；节点名称、队列、执行器能力、容量和出口白名单以页面配置为准。若页面队列与 `.env` 中的 `PERFORMANCE_NODE_QUEUE` 不一致，节点会保持离线并在页面显示错误，避免任务被静默投递到无人消费的队列。纯环境变量启动且数据库中尚无同 ID 节点时，Worker 会自动创建一个由环境变量管理的节点。

修改 `.env` 或启动档案后先执行：

```powershell
.\local-dev.cmd doctor
.\local-dev.cmd restart
```

然后在性能中心刷新节点列表，确认状态为在线、队列和执行器能力与 Worker 配置一致。

在项目根目录执行：

```powershell
Set-Location $RepoRoot
.\local-dev.cmd
```

默认等价于：

```powershell
.\local-dev.cmd up
```

脚本会按顺序启动：

- Backend API
- Celery Worker
- Celery Beat
- Frontend Vite

同时会自动：

- 把运行日志写入项目根目录下的 `.local-run`
- 为每个服务写入 PID 文件，避免重复拉起
- 在 `status` / `down` 时优先按 PID 托管进程

## 常用命令

启动：

```powershell
.\local-dev.cmd up
```

停止：

```powershell
.\local-dev.cmd down
```

重启：

```powershell
.\local-dev.cmd restart
```

查看状态：

```powershell
.\local-dev.cmd status
```

查看日志：

```powershell
.\local-dev.cmd logs
```

启动前预检：

```powershell
.\local-dev.cmd doctor
```

`doctor` 不会启动或停止服务；它会检查 `.env`、Python/Node、端口、PostgreSQL/Redis/MinIO 连通性、ADB 和已配置的性能执行器。ADB 与性能工具缺失只会给出 warning，不会阻塞 API/Web 日常开发。

## Windows 核心端到端冒烟

服务启动后，可以执行一次 Windows 全量本地冒烟，自动验证真实后端健康、管理员登录及认证读接口、前端登录页、Playwright mock E2E、Chromium/Firefox/WebKit 登录页矩阵、临时 Web 文件上传/清理，以及已有执行记录的 HTML/JUnit 报告生成：

```powershell
Set-Location $RepoRoot
.\scripts\windows-local-smoke.ps1
```

如果希望由冒烟脚本负责启动本地服务：

```powershell
.\scripts\windows-local-smoke.ps1 -StartServices
```

冒烟脚本默认读取仓库根目录 `.env`；如果检测到正在运行的 `windows-local-runtime.json`，会自动使用运行元数据中的实际档案。如果当前进程是通过启动档案运行但需要明确指定，也可以传入 `-EnvFile`，避免诊断使用另一套 PostgreSQL/Redis/MinIO 地址：

```powershell
.\scripts\windows-local-smoke.ps1 -EnvFile .\config\startup-profiles\remote-infra.env
.\scripts\windows-local-smoke.ps1 -EnvFile .\config\startup-profiles\remote-infra.env -SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload -SkipReports
```

`-EnvFile` 会同时用于本地 doctor、登录凭据读取以及 `-StartServices`/`-StopServicesAfter` 的子进程启动，不会修改根目录 `.env` 或当前 PowerShell 会话。

脚本会在 `.local-run/windows-smoke-*.json` 生成脱敏结果报告，不会把登录密码或 access token 写入终端和报告。当 `.env` 使用 `ADB_SCAN_MODE=worker`、配置了 `ANDROID_WORKER_ID` 或传入 `-RequireAndroid` 时，还会要求 `/api/v1/devices/workers` 返回在线 Agent，并发起一次设备扫描、轮询扫描任务回调；普通 `local` 模式会跳过该检查。可按场景跳过检查：

脚本的状态变更请求会统一携带 `X-Requested-With: XMLHttpRequest` 以满足平台 CSRF 防护；文件上传使用登录会话的 `CookieContainer` 传递 HttpOnly access cookie，避免手工拼接 Cookie 导致 401。2026-08-12 在当前 Windows 环境实际验证通过管理员登录、10 项 Playwright、三浏览器矩阵、文件上传和临时对象清理。

同日使用 `-SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload -SkipReports` 完成自包含闭环：临时项目/用例创建、审核、Worker 执行、下载对象校验和终态清理均通过。该次报告为 `.local-run/windows-smoke-20260812-003448.json`，不依赖用户现有业务用例。

```powershell
# 只验证服务和真实登录，不执行 Playwright
.\scripts\windows-local-smoke.ps1 -SkipPlaywright -SkipBrowserMatrix

# Android 设备在线时，增加 ADB 网络诊断；没有设备时保持可选
.\scripts\windows-local-smoke.ps1 -AndroidTarget '<device-ip>:5555'

# 将 Android 诊断设为必需项
.\scripts\windows-local-smoke.ps1 -RequireAndroid -AndroidTarget '<device-ip>:5555'

# 执行一个已有的 Web 低代码用例，并强制检查 download 对象证据
.\scripts\windows-local-smoke.ps1 -WebCaseId 123 -RequireWebDownload -WebRunTimeoutSeconds 180

# 首次没有现成用例时，自动创建临时 Web 下载用例并在完成后清理
.\scripts\windows-local-smoke.ps1 -SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload -SkipReports
```

`-ReportPath` 可以指定自定义报告路径；传入相对路径时按项目根目录解析。默认会选择最近的历史执行记录生成 HTML/JUnit 报告；如果当前没有历史执行记录，报告检查会失败，避免冒烟结果误报为已验证。首次使用临时 Web 用例时可显式使用 `-SkipReports` 跳过这项与历史记录相关的检查。临时 Web 文件上传成功后会调用存储清理接口删除测试对象；如果上传响应异常但已返回对象引用，脚本仍会执行补偿清理。

其中 `npm run e2e` 使用仓库现有的 mock API fixture，验证前端关键交互；真实后端链路由健康检查、管理员登录、`/auth/me`、项目列表、文件上传/清理和报告导出负责。该入口不会默认停止当前服务；如需验证服务生命周期，可显式执行：

```powershell
.\scripts\windows-local-smoke.ps1 -StopServicesAfter
```

如果同时使用 `-StartServices -StopServicesAfter`，脚本会负责启动并在验证结束后停止服务。传入 `-WebCaseId` 后，脚本会先校验该 ID 对应的是 `active/approved`、可自动执行的 Web 低代码用例，再使用当前管理员会话触发并轮询 `/runs/{id}`；增加 `-RequireWebDownload` 后，如果运行步骤没有 download 对象引用会直接失败。不传用例 ID 时该项保持跳过。`-SeedWebDownloadCase` 会在当前项目下创建带有仓库下载夹具步骤的临时 Web 项目、模块和用例，并自动触发执行；运行进入终态后删除临时项目。若轮询超时或运行状态未知，脚本会保留临时项目并在报告中写出项目/运行 ID，避免删除仍可能运行中的资源。Android 扫描仍需连接真实设备；Linux/Kubernetes 性能验收也不在 Windows 本地冒烟范围内。

仓库内置了一个不依赖公网的下载验收页面：启动前端后访问
`http://127.0.0.1:5173/atp-windows-download.html`。可以在 Web 低代码用例中配置以下步骤，再把用例 ID 传给冒烟脚本：

```json
[
  {"action":"goto","name":"打开下载夹具","params":{"url":"http://127.0.0.1:5173/atp-windows-download.html"}},
  {"action":"download","name":"下载冒烟文件","params":{"selector":"#atp-download-link"}}
]
```

```powershell
.\scripts\windows-local-smoke.ps1 -WebCaseId 123 -RequireWebLowcode -RequireWebDownload
```

页面和文件属于仓库测试夹具；脚本仍会使用真实浏览器、Worker、MinIO 和执行记录校验下载对象，不会把页面点击结果伪装成通过。

如果不想手工创建项目、模块和用例，可直接使用自包含模式。该模式会自动提交并批准临时用例后再执行，需要管理员登录配置；没有历史运行记录时请保留 `-SkipReports`：

```powershell
.\scripts\windows-local-smoke.ps1 -SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload -SkipReports
```

临时项目只用于本次冒烟，正常完成后会自动删除，并清理本次运行产生的截图、录像和下载对象；超时或状态查询异常时不会删除项目或对象，需根据报告中的项目 ID 和运行 ID 手工确认后清理。seed 用例使用浏览器网络守卫允许的内联 `data:` 下载页面，不会为了测试而放开 loopback/内网 HTTP 访问；手工用例仍可使用仓库 HTTP 夹具。

## 启动后检查

正常情况下可以直接访问：

- 后端健康检查：`http://127.0.0.1:8000/health`
- 前端登录页：`http://127.0.0.1:5173/login`

也可以再执行：

```powershell
.\local-dev.cmd status
```

## 日志与 PID 文件

脚本会在项目根目录下的 `.local-run` 生成：

- `backend.pid`
- `worker.pid`
- `beat.pid`
- `frontend.pid`
- `backend-*.out.log` / `backend-*.err.log`
- `worker-*.out.log` / `worker-*.err.log`
- `beat-*.out.log` / `beat-*.err.log`
- `frontend-*.out.log` / `frontend-*.err.log`

说明：

- PID 文件用于稳定识别当前脚本启动的进程
- `logs` 命令默认读取每个服务最新一份日志
- 即使日志文件滚动，旧日志也会保留，方便排查历史问题

## 常见问题

### 1. `up` 提示缺少依赖

按报错信息补齐：

- `backend\.venv\Scripts\python.exe` 不存在：先完成后端虚拟环境安装
- `frontend\node_modules\vite\bin\vite.js` 不存在：先在 `frontend` 执行 `npm ci`
- `node.exe` 不存在：安装 Node.js 20+

### 2. 端口被占用

如果 `8000` 或 `5173` 被其他进程占用，脚本会直接报错并打印 PID。先释放端口，再重试：

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue | Select-Object LocalPort, OwningProcess
```

### 3. 远端基础设施连不通

优先检查 Windows 到 WSL / Linux 主机网络是否可达：

```powershell
$RemoteHost = '<server-host>' # 替换为当前 Linux 主机地址，例如 172.31.27.133
Test-NetConnection $RemoteHost -Port 5432
Test-NetConnection $RemoteHost -Port 6379
Test-NetConnection $RemoteHost -Port 9000
```

### 4. Android 真机不显示

```powershell
adb devices
```

如果看不到设备，再重启 ADB：

```powershell
adb kill-server
adb start-server
adb devices
```

如果你准备让 Docker Worker 连接真机，建议继续切到 ADB over TCP：

```powershell
adb tcpip 5555
adb connect <device-ip>:5555
adb devices
```

确认设备状态为 `device`，且 serial 变成 `<device-ip>:5555` 后，再回到 ATP 中执行"扫描设备"。

复杂网络场景下优先使用 PowerShell 诊断脚本：

```powershell
.\scripts\android-network-doctor.ps1 -Target '<device-ip>:5555'
```

如果共享 ADB Server，避免脚本重启它：

```powershell
.\scripts\android-network-doctor.ps1 -Target '<device-ip>:5555' -SkipServerRestart -SkipConnect
```

原 Bash 版本仍可用于 Git Bash 或 WSL：

```bash
bash scripts/android-network-doctor.sh <device-ip>:5555
```

更完整说明见：`docs/android-device-debugging.md`

## Windows 端仍需完善的内容

当前 Windows 启动链已经可以完成日常开发，但以下内容仍列为 Windows 主线任务：

- [x] 启动前预检：`local-dev.cmd doctor` 自动检查 `.env`、Python/Node、Python Playwright/Chromium、Web 录制模式、Worker 参数、8000/5173 端口，以及 PostgreSQL、Redis、MinIO 的连通性；`windows-android-worker.ps1 doctor` 额外检查 Celery/Redis Python 依赖和 ADB。
- [x] 性能依赖检测：doctor 检查 k6、Locust、grpcio/grpcio-tools；JMeter 仍需 Windows Java/JMeter 5.6.3，并在 `PERFORMANCE_EXECUTORS` 中显式加入 `jmeter`。Windows Worker 会自动解析 PATH 中的 `jmeter.bat`/`jmeter.exe`，无需手工改成 Unix 命令名。
- [x] Android 网络诊断：新增 `android-network-doctor.ps1`，原 `android-network-doctor.sh` 继续保留给 Git Bash/WSL。
- [~] Windows 全量本地冒烟：`windows-local-smoke.ps1` 已自动执行服务预检、真实登录、认证读接口、API 健康、Web 登录页、Playwright mock E2E、三浏览器页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务，并生成脱敏 JSON 报告；Web 低代码新增 `-SeedWebDownloadCase` 自包含创建/执行/清理链路，已在当前运行环境留下真实 Worker/MinIO 下载对象证据并自动清理，Android 扫描仍需真实设备。
- [x] Worker 边界：Windows 使用 Celery `--pool=solo` 适合功能联调，不用于判断生产级并发、吞吐或多节点性能；相关结论转到 Linux/Kubernetes 目标环境。

Windows 本地回归建议执行：

```powershell
Set-Location $RepoRoot
& (Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe') -m pytest backend/tests -q --ignore=backend/tests/integration
Set-Location (Join-Path $RepoRoot 'frontend')
npm test -- --run
npm run type-check
npm run build
```

## 推荐用法

日常开发建议固定使用下面这一组命令：

```powershell
Set-Location $RepoRoot
.\local-dev.cmd up
.\local-dev.cmd doctor
.\local-dev.cmd status
.\local-dev.cmd logs
.\local-dev.cmd down
```

### Windows 性能 Agent

如果性能节点页面已经登记了节点，但压测任务需要在另一台 Windows 主机执行，可使用专用性能 Worker：

```powershell
Copy-Item .\config\startup-profiles\performance-agent.env.example .\config\startup-profiles\performance-agent.env
# 修改远程 PostgreSQL/Redis/MinIO、PERFORMANCE_NODE_ID、PERFORMANCE_NODE_QUEUE 和出口白名单
.\startup.cmd -Profile performance-agent -Action doctor
.\startup.cmd -Profile performance-agent -Action up
.\startup.cmd -Profile performance-agent -Action status
.\startup.cmd -Profile performance-agent -Action logs -Tail 200
```

该模式只消费配置的专用节点队列（例如 `performance.worker-a`），并通过 Redis/数据库心跳把节点置为在线；共享 `performance` 队列仍由普通性能 Worker 消费。`doctor` 会阻止缺少 Python/Celery/Redis 依赖、服务端口不可达、节点 ID/队列非法或误使用共享队列的启动；k6、Locust、gRPC、JMeter 等执行器缺失只会作为可选能力警告。页面登记的节点 ID 和 `PERFORMANCE_NODE_QUEUE` 必须与配置文件一致，否则节点会显示离线并给出队列不一致原因。

这样能保持本地启动链路稳定、可回收、易排障。
