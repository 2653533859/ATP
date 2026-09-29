# Windows 本机独立环境

本方案让 Windows 本机运行 Frontend、Backend、普通 Worker、Beat 与浏览器/ADB 工具，让本机 WSL Docker 运行 PostgreSQL、Redis、MinIO。它和服务器 ATP 是两套独立环境：不共用数据库、对象存储、队列或登录账号，也不自动同步业务数据。服务器环境继续按原有方式运行。

## 首次启动

前置条件：Windows 已安装 Python 3.12、Node 20+、WSL2 Ubuntu 和 WSL 内 Docker Engine/Compose；仓库中 `backend/.venv` 已安装 `backend/requirements.txt`，`frontend/node_modules` 已通过 `npm ci` 安装。使用真机或浏览器录制时，本机仍需对应 ADB/Playwright 浏览器依赖。

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

首次 `up` 会从模板创建 Git 忽略的 `config/startup-profiles/local-all.env`，生成独立的数据库、Redis、MinIO、应用和初始管理员密码，然后启动隔离的 WSL Docker 基础设施、执行本地 Alembic 迁移并启动 Windows 应用进程。默认入口为 `http://127.0.0.1:5173/`。初始用户名为 `admin`，初始密码只保存在本机配置的 `FIRST_ADMIN_PASSWORD`；账号创建后若在页面修改密码，该字段不会自动更新。

本地数据服务仅映射到本机回环：PostgreSQL `15432`、Redis `16379`、MinIO API `19000`、MinIO Console `19001`。这些端口与服务器及旧 WSL/q19 栈分离。Docker 项目和数据卷名均以 `atp-windows-local` 开头；`down` 只停止进程和容器，保留本地数据卷。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
```

切换回服务器页面时，启动单独的 Windows Vite 进程并将 `VITE_BACKEND_ORIGIN` 指向服务器；不要把本地 `local-all.env` 用作服务器 Worker 档案。两套环境的页面地址可以相同，但对应启动进程和数据源必须明确区分。

## 换电脑

在旧电脑上执行备份。此操作会先停止本地应用和三个数据容器，保证卷快照一致；备份完成后可以再次运行 `up`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action backup -ArchiveDir 'E:\ATP-backup\snapshot-001'
```

备份目录包含 `local-all.env`、PostgreSQL/Redis/MinIO 三个卷的 tar 文件及 SHA-256 清单；恢复前会核对每个文件。它包含应用密钥和账号密码，应作为私有资料保管。此卷快照要求新电脑使用相同的 PostgreSQL 主版本和兼容的容器镜像；不要把它当作服务器环境的备份。复制仓库和备份目录到新电脑、安装上述运行依赖后，在**尚未创建本地配置和数据卷**的环境执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action restore -ArchiveDir 'E:\ATP-backup\snapshot-001'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

`restore` 遇到同名配置或数据卷会拒绝覆盖，避免误删新电脑已有数据。若目标机已经运行过本地 ATP，应先明确保存并处理其现有数据，再做恢复。

## 当前机器的启动阻塞

2026-09-29 检查时，Windows 已具备 Node、前后端依赖，服务器 Backend `/health` 为 200；本机 `5432/6379/9000/8000` 未监听。WSL 内 Docker Engine 启动失败，日志为 `error while opening volume store metadata database (/var/lib/docker/volumes/metadata.db): timeout`。因此新独立环境尚未实际启动，本文件中的 `up/backup/restore` 也尚无成功运行证据。先恢复 WSL Docker，再运行 `up` 并验证本地 Backend、登录、Worker 和对象上传；不能把当前仍连接服务器的 Vite 页面当成本地全栈。
