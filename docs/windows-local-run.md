# ATP Windows 本地单命令启动

本文档说明如何在 Windows 本地用一条命令启动 ATP 的前后端开发栈，同时连接运行在 WSL / Linux Docker 主机上的 PostgreSQL、Redis、MinIO。

## 适用场景

- 前端、后端、Celery Worker、Celery Beat 运行在 Windows 本机
- PostgreSQL、Redis、MinIO 运行在 WSL / Linux Docker 主机
- 当前已验证的远端主机地址：`163.192.40.209`
- Android 真机通过 Windows 本机 `adb` 直连

这种模式适合本地开发与联调：Windows 侧进程直接访问真机与浏览器，基础设施继续复用 Linux Docker 环境。

## 一次性准备

### 1. 后端依赖

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
playwright install chromium
```

### 2. 前端依赖

```powershell
cd F:\csh\MyProjectAutoTest\ATP\frontend
npm ci
```

如果锁文件和当前环境不一致，再执行：

```powershell
npm install
```

### 3. 本地环境变量

先复制本地环境文件：

```powershell
cd F:\csh\MyProjectAutoTest\ATP
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
cd F:\csh\MyProjectAutoTest\ATP
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

- 把运行日志写入 `F:\csh\MyProjectAutoTest\ATP\.local-run`
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

## 启动后检查

正常情况下可以直接访问：

- 后端健康检查：`http://127.0.0.1:8000/health`
- 前端登录页：`http://127.0.0.1:5173/login`

也可以再执行：

```powershell
.\local-dev.cmd status
```

## 日志与 PID 文件

脚本会在 `F:\csh\MyProjectAutoTest\ATP\.local-run` 下生成：

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

复杂网络场景下可直接跑诊断脚本（需 Git Bash 或 WSL）：

```bash
bash scripts/android-network-doctor.sh <device-ip>:5555
```

更完整说明见：`docs/android-device-debugging.md`

## 推荐用法

日常开发建议固定使用下面这一组命令：

```powershell
cd F:\csh\MyProjectAutoTest\ATP
.\local-dev.cmd up
.\local-dev.cmd status
.\local-dev.cmd logs
.\local-dev.cmd down
```

这样能保持本地启动链路稳定、可回收、易排障。
