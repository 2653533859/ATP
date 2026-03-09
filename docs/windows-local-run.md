# ATP Windows 本地运行说明

适用场景：

- 前端、后端、Celery Worker 在 Windows 本机运行
- PostgreSQL、Redis、MinIO 通过 Docker Desktop 启动
- Android 真机通过 Windows 本机 `adb` 直连

这种方式比“整套服务都跑在 Docker 容器里”更适合本地开发和真机联调，因为 `worker` 可以直接访问 Windows 上连接的手机。

## 1. 前置准备

请先安装并确认以下命令可用：

- `Docker Desktop`
- `Python 3.12`
- `Node.js 20+`
- `Git`
- `adb`（Android Platform Tools，只有 Android 真机调试时必需）

可用下面的命令快速检查：

```powershell
docker --version
python --version
node --version
npm --version
adb version
```

## 2. 准备项目配置

在项目根目录执行：

```powershell
cd F:\csh\MyProjectAutoTest\ATP
Copy-Item .env.example .env
```

然后编辑根目录 `.env`，至少修改这些值：

- `APP_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `FIRST_ADMIN_PASSWORD`

本地开发时，建议确认以下配置为本机地址：

```env
POSTGRES_HOST=localhost
REDIS_HOST=localhost
MINIO_HOST=localhost
APP_CORS_ORIGINS=http://localhost:5173,http://localhost,http://127.0.0.1:5173
```

## 3. 启动基础设施

本地开发只需要先拉起数据库、Redis、MinIO：

```powershell
docker compose up -d postgres redis minio
```

检查容器状态：

```powershell
docker compose ps
```

常用访问地址：

- MinIO Console: `http://localhost:9001`

## 4. 安装后端依赖

在新的 PowerShell 窗口执行：

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

如果 PowerShell 拒绝执行激活脚本，可临时执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 5. 安装前端依赖

在新的 PowerShell 窗口执行：

```powershell
cd F:\csh\MyProjectAutoTest\ATP\frontend
npm ci
```

如果 `npm ci` 因锁文件或网络问题失败，再执行：

```powershell
npm install
```

## 6. 启动项目服务

建议打开 4 个 PowerShell 窗口，分别启动以下进程。

### 6.1 启动后端 API

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

后端健康检查地址：

- `http://localhost:8000/health`

### 6.2 启动 Celery Worker

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
.\.venv\Scripts\Activate.ps1
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

这里使用 `--pool=solo`，避免当前项目里的异步数据库任务在 Windows 本地开发时出现进程池兼容问题。

### 6.3 启动 Celery Beat

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
.\.venv\Scripts\Activate.ps1
celery -A app.worker.celery_app beat --loglevel=info
```

### 6.4 启动前端

```powershell
cd F:\csh\MyProjectAutoTest\ATP\frontend
npm run dev
```

前端开发地址：

- `http://localhost:5173`

## 7. 数据库初始化

首次使用新数据库时，建议手动执行一次迁移：

```powershell
cd F:\csh\MyProjectAutoTest\ATP\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

当前项目启动时仍保留了建表兜底逻辑，首次启动后也会自动创建管理员账号和默认对象存储 bucket，但开发环境下仍建议显式执行迁移，避免数据库状态不一致。

## 8. Android 真机联调

如果你要在本机开发环境里调 Android 用例，按下面检查：

1. 手机开启开发者选项和 USB 调试
2. 用 USB 连接到 Windows
3. 在 PowerShell 验证：

```powershell
adb devices
```

如果能看到设备序列号，平台里的设备扫描和 Android 执行器才能正常工作。

这种本机运行模式的优势是：

- `worker` 直接调用 Windows 本机 `adb`
- 不需要处理 Docker 容器访问 USB 设备的问题
- 真机联调稳定性通常高于容器方案

## 9. 常见问题

### 9.1 前端构建或类型检查提示缺少 `vue-echarts` / `echarts`

先在 `frontend/` 目录执行：

```powershell
npm ci
```

如果依赖仍不完整，再执行：

```powershell
npm install
```

### 9.2 `adb devices` 看不到手机

优先检查：

- USB 调试是否已授权
- 数据线是否支持传输
- Windows 设备管理器中驱动是否正常
- 是否有其他 ADB 进程占用

必要时可重启 ADB：

```powershell
adb kill-server
adb start-server
adb devices
```

### 9.3 Worker 启动了，但任务一直不执行

先确认：

- `redis` 容器正常
- `worker` 进程确实已启动
- 启动命令带了 `--pool=solo`

### 9.4 MinIO 无法上传文件

检查：

- `MINIO_HOST` 是否为 `localhost`
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 是否正确
- `http://localhost:9001` 是否可访问

## 10. 推荐的本地开发模式

如果你既要改页面，又要联调 Android 设备，推荐采用下面的组合：

- 前端：Windows 本机运行
- 后端：Windows 本机运行
- Worker / Beat：Windows 本机运行
- PostgreSQL / Redis / MinIO：Docker Desktop 运行
- Android 手机：直接接入 Windows，通过本机 `adb` 管理

这也是当前项目在 Windows 环境下最实用、排障成本最低的开发方式。
