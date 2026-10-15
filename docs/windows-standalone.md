# Windows 本地轻量模式

本地模式直接在 Windows 运行 Backend，前端可使用 Vite 开发入口或 Backend 提供的静态页面。业务数据保存在仓库下 `.local-data/atp.sqlite3`，附件保存在 `.local-data/objects/`，API 会话密文保存在 `.local-data/sessions/`。不需要 WSL、Docker、PostgreSQL、Redis 或 MinIO。服务器部署仍使用原有基础设施；两套数据和登录账号独立，不自动同步。

## 启动

当前功能与验收缺口见 [`current-capability-baseline-2026-10-07.md`](current-capability-baseline-2026-10-07.md)，剩余任务见 [`development-task-plan-2026-10-07.md`](development-task-plan-2026-10-07.md)。本地已接入 Web 录制、手动串行套件/计划、需求、缺陷、知识、资产、AI 配置、协议测试、Hermes 与单机性能。AI 需要自行配置联网模型；计划/性能不支持定时或远程节点。当前代码 SQLite 版本为 13，启动时显式升级；版本 8 增加资源身份，版本 9 增加套件投递意图，版本 10 增加首次接受凭据及套件队列/租约 UUID，版本 11 增加计划 UUID、取消时间及子归属记录，版本 12 移除冗余表并加固备份完整性，版本 13 接入 AutoDroid 远程 Agent 隧道与设备表。套件/计划执行记录展开后可查询恢复状态和请求协作取消。旧命令/旧运行不自动猜测或补投；已接受但失联的运行须核对，不能自动重跑。详见 [N1.5 记录](group-recovery-development-2026-10-08.md) 与 [N3.1~N3.3 记录](evidence/windows-sqlite-upgrade-backup-restore-2026-10-12.md)。实现接入与业务验收分别记录。

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

API 用例编辑器可在保存前点击“发送请求”，按当前方法、URL、参数、请求头、Cookie、正文和认证发送一次请求，并查看状态码、耗时、响应大小、响应头和正文。该操作会真实访问目标接口，但不创建用例或运行记录，也不执行场景编排、断言或前后置动作。响应正文最多展示 1 MB；本地模式允许本机和局域网目标，服务器模式限制为公网 URL。2026-10-08 在本地开发入口用只读 `/health` 请求确认了 200 响应；服务器模式尚未做交互验收。

接口测试工作台采用请求集合、请求编辑、响应区与自动化场景编排布局：左侧按模块浏览已保存用例，右侧可填写 HTTP 方法、URL、Params、Headers、Body、Auth、Cookies 并直接发送；响应区显示状态、耗时、大小、正文与响应头。“保存为新用例”会把当前请求带入用例编辑器，保存前需选定左侧模块。右上角集合操作支持一键将多个已保存用例批量编排为自动化场景（`ApiScenarioOrchestrator`），支持步骤依赖链（`depends_on: [i - 1]`）、单步调试与增量状态合并（保存时不重置活动步骤与调试结果）。非 HTTP 协议用例通过专属执行器（GraphQL、WebSocket、gRPC）进行调度执行。Vite 开发代理仅转发 `/api` 和 `/ws` 路径段，避免将 `/api-workbench` 页面误转发给后端静态站点。

响应区还显示本次实际请求的方法与合并 Params 后的 URL、服务器状态、Content-Type、可用的 Request ID、Location 和 Allow，并为常见 HTTP 错误提供排查方向。目标服务器返回 0 B 时明确标记“未返回响应正文”；诊断文字仅解释状态码，不声称获得服务器未提供的具体错误原因。

响应 Body 可在“字段 / 原文”间切换。JSON、XML、URL 编码表单、CSV 和 TSV 展示字段路径、类型和值，并支持搜索；普通文本和 HTML 源码按行展示，不执行返回的 HTML。字段视图有展示数量与深度限制，原文仍可查看后端返回的内容（预览接口最多保留 1 MB）。

对 `GET /v1/model` 返回 404 的请求，工作台会提示 OpenAI 兼容模型列表通常使用 `/v1/models`，并提供填入建议地址按钮；不会自动重发请求。此提示是路径建议，不能代替目标服务的接口文档或证明认证配置正确。

Android 本地模式使用 Windows 本机 ADB。安装 Android SDK Platform Tools 并把 `adb` 加入 `PATH`，连接设备后在 APP 工作台手动扫描，再选设备、APK、Android 用例或专项任务执行。APP 工作台就地集成了 `AndroidCaseDrawer`，支持直接在工作台新建或编辑 Android 用例，包含设备矩阵、录屏、APK 资产绑定、低代码动作步骤与 UiAutomator2 脚本，并自动解析绑定合法项目根模块（彻底解决 Pydantic `module_id=null` 导致的 HTTP 422 校验失败）；针对 0 用例项目提供标准冷启动引导卡片（Empty State CTA）。同时支持 Scrcpy 60FPS WebCodecs 硬件直解实时流与毫秒级全双工触控控制，鼠标按键强制过滤非左键点击防触控死锁，降级超时具备流资源显式清理机制。

本地启动只从独立 `local-lite.env` 中读取允许的配置，不加载仓库根目录 `.env`。本地认证 Cookie 采用专属名称（`atp_local_access_token` / `atp_local_refresh_token`），登出时仅定向清除本地会话，绝不影响服务器模式会话；WebSocket 仅按激活模式校验专属令牌。前端请求拦截器自动注入 `X-ATP-Client-Mode`，后端全局中间件核对若发现客户端与服务端模式不一致立即熔断返回 HTTP 409 Conflict，防止向错误后端写入脏数据。双模式切换使用 `scripts/windows-mode.ps1`，支持无缝独立切换，两套数据与浏览器状态完全隔离。

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

恢复拒绝覆盖现有本地配置或数据，并在复制前核对备份内每个文件的 SHA-256 清单（`manifest.json`）。备份复制当前文件，不提供加密归档或自动同步；包含密钥与账号，应妥善保管。同机独立目录恢复已通过文件校验和 SQLite 完整性检查。此外，仓库提供 `scripts/package-windows-standalone-bundle.ps1` 脚本，可快速构建包含 600+ 核心运行文件的绿色免编译便携交付包。

## 2026-10-15 交付状态

当前本地 SQLite 版本为 13；以静态模式运行，页面和 API 均由 `8001` 提供。开发模式可另启 `5174` Vite。全套 CI 对应门禁（Ruff 规范/格式、Mypy 188 源码文件、Bandit SAST、vue-tsc 与生产构建）均已通过。统一交付证据索引见 [`evidence-index-2026-10-15.md`](evidence-index-2026-10-15.md)。
