# ATP Windows 本地单命令启动

本文档说明如何在 Windows 本地用一条命令启动 ATP 的前后端开发栈，同时连接运行在 WSL / Linux Docker 主机上的 PostgreSQL、Redis、MinIO。

## 适用场景

- 前端、后端、Celery Worker、Celery Beat 运行在 Windows 本机
- PostgreSQL、Redis、MinIO 运行在 WSL / Linux Docker 主机
- 当前已验证的远端主机地址：`163.192.40.209`
- Android 真机通过 Windows 本机 `adb` 直连

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
POSTGRES_HOST=163.192.40.209
REDIS_HOST=163.192.40.209
MINIO_HOST=163.192.40.209
APP_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
APP_AUTO_CREATE_TABLES=false
```

如果你的 Redis、PostgreSQL、MinIO 端口不是默认值，再同步补齐：

```env
POSTGRES_PORT=5432
REDIS_PORT=6379
MINIO_PORT=9000
```

说明：

- 默认要求先执行 `alembic upgrade head` 完成建表或迁移
- 应用启动时会做一次 Alembic head 校验，DB revision 与 head 不一致会在日志输出 WARNING
- `APP_AUTO_CREATE_TABLES=true` 只建议用于本地临时排障，不建议作为日常启动路径

## 单命令启动

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

脚本会在 `.local-run/windows-smoke-*.json` 生成脱敏结果报告，不会把登录密码或 access token 写入终端和报告。可按场景跳过检查：

```powershell
# 只验证服务和真实登录，不执行 Playwright
.\scripts\windows-local-smoke.ps1 -SkipPlaywright -SkipBrowserMatrix

# Android 设备在线时，增加 ADB 网络诊断；没有设备时保持可选
.\scripts\windows-local-smoke.ps1 -AndroidTarget '<device-ip>:5555'

# 将 Android 诊断设为必需项
.\scripts\windows-local-smoke.ps1 -RequireAndroid -AndroidTarget '<device-ip>:5555'
```

`-ReportPath` 可以指定自定义报告路径；传入相对路径时按项目根目录解析。默认会选择最近的历史执行记录生成 HTML/JUnit 报告；如果当前没有历史执行记录，报告检查会失败，避免冒烟结果误报为已验证。仅在明确不需要报告验证时使用 `-SkipReports`。临时 Web 文件上传成功后会调用存储清理接口删除测试对象；如果上传响应异常但已返回对象引用，脚本仍会执行补偿清理。

其中 `npm run e2e` 使用仓库现有的 mock API fixture，验证前端关键交互；真实后端链路由健康检查、管理员登录、`/auth/me`、项目列表、文件上传/清理和报告导出负责。该入口不会默认停止当前服务；如需验证服务生命周期，可显式执行：

```powershell
.\scripts\windows-local-smoke.ps1 -StopServicesAfter
```

如果同时使用 `-StartServices -StopServicesAfter`，脚本会负责启动并在验证结束后停止服务。Android 扫描仍需连接真实设备；Web 低代码页面中的真实下载动作仍需配套页面/用例数据，Linux/Kubernetes 性能验收也不在 Windows 本地冒烟范围内。

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
Test-NetConnection 163.192.40.209 -Port 5432
Test-NetConnection 163.192.40.209 -Port 6379
Test-NetConnection 163.192.40.209 -Port 9000
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

- [x] 启动前预检：`local-dev.cmd doctor` 自动检查 `.env`、Python/Node/Playwright、8000/5173 端口，以及 PostgreSQL、Redis、MinIO 的连通性。
- [x] 性能依赖检测：doctor 检查 k6、Locust、grpcio/grpcio-tools；JMeter 仍需 Windows Java/JMeter 5.6.3，并在 `PERFORMANCE_EXECUTORS` 中显式加入 `jmeter`。
- [x] Android 网络诊断：新增 `android-network-doctor.ps1`，原 `android-network-doctor.sh` 继续保留给 Git Bash/WSL。
- [~] Windows 全量本地冒烟：`windows-local-smoke.ps1` 已自动执行服务预检、真实登录、认证读接口、API 健康、Web 登录页、Playwright mock E2E、三浏览器页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务，并生成脱敏 JSON 报告；Android 扫描和 Web 低代码真实下载动作仍需真实设备/页面数据。
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

这样能保持本地启动链路稳定、可回收、易排障。
