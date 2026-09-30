# Windows 本地轻量模式

本地模式直接在 Windows 运行 Backend 与 Vite。业务数据保存在仓库下 `.local-data/atp.sqlite3`，附件保存在 `.local-data/objects/`，API 会话密文保存在 `.local-data/sessions/`。不需要 WSL、Docker、PostgreSQL、Redis 或 MinIO。服务器部署仍使用原有基础设施；两套数据和登录账号独立，不自动同步。

## 启动

需要 Python 3.12、Node 20+、`backend/.venv` 和 `frontend/node_modules`。首次使用先安装后端依赖：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

页面地址为 <http://127.0.0.1:5174/>，后端监听 `127.0.0.1:8001`。独立端口避免覆盖当前连接服务器的 `5173` 页面。首次 `up` 创建 Git 忽略的 `config/startup-profiles/local-lite.env`，其中保存随机生成的初始管理员密码和应用密钥。初始用户名为 `admin`，首次登录密码查看该文件的 `FIRST_ADMIN_PASSWORD`。密码在页面修改后，配置文件中的初始值不会自动更新。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
```

`down` 只停止本地进程，不删除数据。日志位于 `.local-run/standalone/`。本地 SQLite 使用独立版本管理；现有完整原型库可接管升级，未知或不完整结构会拒绝启动，避免静默覆盖。服务器 PostgreSQL 仍由 Alembic 管理。

若已在 `frontend/` 安装 Node 依赖，可先以 `VITE_ATP_LOCAL_MODE=true` 和 `VITE_BACKEND_ORIGIN=http://127.0.0.1:8001` 执行 `npm run build`，再运行 `windows-standalone.ps1 -Action up -Frontend static`。此时页面与 API 同在 <http://127.0.0.1:8001/>，运行时不需要 Vite/Node 进程。默认 `-Frontend dev` 保持 `5174` 开发入口。

统一入口 `scripts/windows-mode.ps1` 支持 `-Action status` 查看两套页面状态、`-Action local` 启动并打开本地页面、`-Action server` 打开现有服务器页面；`-Action open -Mode local/server` 只打开已运行的对应页面。服务器页面默认 `127.0.0.1:5173`，不在此脚本中启动或改写服务器后端；其他地址可用 `-ServerUrl` 指定。切换仅打开目标页面，两套进程和数据可以并行保留。

## 当前范围

本地模式面向单人、单项目、单进程的日常核心流程。首次启动创建唯一默认项目和模块；新增用户或额外项目会被后端拒绝。执行任务写入 SQLite 加密队列，未开始的任务会在重启后继续；执行中断的任务会标记错误，不自动重放。API 与 Web 用例真实手动运行、API 请求文件上传/签名下载、Web 取消、排队任务重启继续、含运行数据的报告与趋势 CSV 已验收；截图、运行中断恢复及完整附件矩阵仍待验收。

Android 本地模式使用 Windows 本机 ADB。安装 Android SDK Platform Tools 并把 `adb` 加入 `PATH`，连接设备后在 APP 工作台手动扫描，再选设备、APK、Android 用例或专项任务执行。专项任务仅支持手动触发和停止；运行排队、失败与中断恢复保存在 SQLite，停止信号由本进程处理。当前机器 ADB 可用但无已连接设备，因此 Android 真机执行、APK 安装、截图/报告和停止时序仍待验收。iOS、分布式 Worker、性能节点、录制、定时计划和依赖 Redis 的部分 AI 功能仍不在本地范围内。

本地启动只从独立 `local-lite.env` 中读取允许的配置，不加载仓库根目录 `.env`。本地认证 Cookie 使用独立名称；页面启动时读取后端模式并拒绝错误后端。服务器当前后端尚无 `/runtime`，旧版服务器页面保持兼容，正式双向切换验收未完成。旧的 `local-all.env` 不用于本地轻量启动。进度见 [`windows-dual-mode-development-plan-2026-09-29.md`](windows-dual-mode-development-plan-2026-09-29.md)。

## 转移与备份

先执行 `down`，再备份。目录包含 SQLite、附件、密钥和初始密码，应作为私有资料保管：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action backup -ArchiveDir 'E:\ATP-backup\snapshot-001'
```

将仓库及备份目录复制到新电脑，安装依赖后，在尚无 `local-lite.env` 和 `.local-data/` 的环境恢复：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action restore -ArchiveDir 'E:\ATP-backup\snapshot-001'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

恢复拒绝覆盖现有本地配置或数据，并在复制前核对备份内每个文件的 SHA-256 清单。备份复制当前文件，不提供加密归档或自动同步；包含密钥与账号，应妥善保管。同机独立目录恢复已通过文件校验和 SQLite 完整性检查，异机恢复尚未完成验收。

## 2026-09-29 进度

本地 SQLite 已升级到版本 4；当前以静态模式运行，页面和 API 均由 `8001` 提供。开发模式可另启 `5174` Vite。API 与 Web 用例创建、批准、执行、步骤结果与临时数据清理已通过真实接口验证；后端非集成回归 2789 passed/2 skipped、覆盖率 82.04%，前端构建通过。新删除路径会清理对应运行的本地附件；历史孤儿文件暂保留。`5173` 服务器页面本次复查不可达，剩余验收见双模式计划。
