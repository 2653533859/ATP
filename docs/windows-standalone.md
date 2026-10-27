# Windows 本地轻量模式

本地模式直接在 Windows 运行 Backend，前端可使用 Vite 开发入口或 Backend 提供的静态页面。新安装默认选择空余空间不少于 20 GB 的非 C 盘固定磁盘，在盘根目录创建 `ATP_resources`：其下的 `atp.sqlite3` 保存业务数据，`objects/` 保存附件，`sessions/` 保存 API 会话密文。可在首次 `init` 或 `up` 时用 `-DataDir 'D:\ATP_resources'` 指定其他本地绝对路径；没有合适磁盘时必须手工指定。已存在的 `local-lite.env` 继续使用其中的 `ATP_LOCAL_DATA_DIR`，旧 `.local-data/` 不会自动迁移或覆盖。不需要 WSL、Docker、PostgreSQL、Redis 或 MinIO。服务器部署仍使用原有基础设施；两套数据和登录账号独立，项目及附件不自动同步到云端，仅启用云端结果同步时发送测试结果和报告摘要。新架构的分阶段计划见 [Windows 独立数据与云端结果汇总开发计划](windows-desktop-cloud-result-sync-plan-2026-10-26.md)。

## 启动

当前功能与验收缺口见 [`current-capability-baseline-2026-10-07.md`](current-capability-baseline-2026-10-07.md)，剩余任务见 [`development-task-plan-2026-10-07.md`](development-task-plan-2026-10-07.md)。本地已接入 Web 录制、手动串行套件/计划、需求、缺陷、知识、资产、AI 配置、协议测试、Hermes 与单机性能。AI 需要自行配置联网模型；计划/性能不支持定时或远程节点。当前代码 SQLite 版本为 14，启动时显式升级；版本 8 增加资源身份，版本 9 增加套件投递意图，版本 10 增加首次接受凭据及套件队列/租约 UUID，版本 11 增加计划 UUID、取消时间及子归属记录，版本 12 移除冗余表并加固备份完整性，版本 13 接入 AutoDroid 远程 Agent 隧道与设备表，版本 14 加入 API Key 表。套件/计划执行记录展开后可查询恢复状态和请求协作取消。旧命令/旧运行不自动猜测或补投；已接受但失联的运行须核对，不能自动重跑。详见 [N1.5 记录](group-recovery-development-2026-10-08.md) 与 [N3.1~N3.3 记录](evidence/windows-sqlite-upgrade-backup-restore-2026-10-12.md)。实现接入与业务验收分别记录。

需要 Python 3.12、Node 20+、`backend/.venv` 和 `frontend/node_modules`。首次使用先安装后端依赖：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

页面地址为 <http://127.0.0.1:5174/>，后端监听 `127.0.0.1:8001`。独立端口避免覆盖当前连接服务器的 `5173` 页面。首次 `up` 创建 Git 忽略的 `config/startup-profiles/local-lite.env`，其中保存数据目录、随机生成的初始管理员密码和应用密钥。初始用户名为 `admin`，首次登录密码查看该文件的 `FIRST_ADMIN_PASSWORD`。密码在页面修改后，配置文件中的初始值不会自动更新。现有安装不要直接改写配置中的数据目录；应先做备份并使用经验证的迁移流程。桌面窗口模式使用后端虚拟环境中的 `pywebview` 和 Windows WebView2；升级现有虚拟环境时需重新安装 `backend/requirements.txt`。

云端结果同步需在本机私有 profile 中配置 `CLOUD_SYNC_ENABLED=true`、`CLOUD_SYNC_URL` 和 `CLOUD_SYNC_API_KEY`。API Key 必须属于云端管理员账号；云端汇总接口不接受匿名请求。本机仅显示待同步队列，跨电脑汇总在云端 Web 端查看。错误原文保留在本机报告，云端只接收固定提示。后台每 20 秒扫描一次待发及到期重试项；手动同步会立即重试失败项。

在线远程访问使用 Windows 向云端发起的 WebSocket 通道，云端不直接连接 Windows 的 `127.0.0.1`。可将 `CLOUD_SYNC_URL` 配为可从 Windows 访问的 HTTPS 云端地址；当前生产部署使用受限 SSH 密钥建立私有本地转发，配置 `REMOTE_NODE_SSH_HOST`、`REMOTE_NODE_SSH_PORT`、`REMOTE_NODE_SSH_USER`、`REMOTE_NODE_SSH_KEY_FILE`、`REMOTE_NODE_SSH_KNOWN_HOSTS`、`REMOTE_NODE_TUNNEL_PORT`，并将 `CLOUD_SYNC_URL` 设为对应的 `http://127.0.0.1:<转发端口>`。仅回环地址允许明文 HTTP，连接实际由 SSH 加密传输；非回环 HTTP 地址不会启用远程通道。两种方式都需要云端管理员的私有 API Key。当前跨端代理只授权云端管理员，单次请求或响应上限为 8 MiB；本机项目权限与多用户映射、较大录像的流式传输仍需现场验收。云端收到请求后只转发受控 API 路径和必要内容头，本机以本机签发的短时身份执行请求。旧心跳地址不再作为代理目标。

历史迁移脚本从本机私有 profile 读取本机签名密钥和初始密码；SSH 主机、用户、端口及可选密码由 `ATP_MIGRATION_SSH_HOST`、`ATP_MIGRATION_SSH_USER`、`ATP_MIGRATION_SSH_PORT`、`ATP_MIGRATION_SSH_PASSWORD` 提供。优先使用已登记主机密钥和 SSH Agent；脚本不会接受未知主机密钥。发现明文凭据曾保存在未跟踪脚本后，应先轮换相关生产 SSH 凭据与本机签名密钥，再发布或共享这些脚本；轮换会使现有登录会话失效。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
```

`down` 只停止本地进程，不删除数据。日志位于 `.local-run/standalone/`。本地 SQLite 使用独立版本管理；现有完整原型库可接管升级，未知或不完整结构会拒绝启动，避免静默覆盖。服务器 PostgreSQL 仍由 Alembic 管理。

若已在 `frontend/` 安装 Node 依赖，可先以 `VITE_ATP_LOCAL_MODE=true` 和 `VITE_BACKEND_ORIGIN=http://127.0.0.1:8001` 执行 `npm run build`，再运行 `windows-standalone.ps1 -Action up -Frontend static`。此时页面与 API 同在 <http://127.0.0.1:8001/>，运行时不需要 Vite/Node 进程。默认 `-Frontend dev` 保持 `5174` 开发入口。

统一入口 `scripts/windows-mode.ps1` 支持 `-Action status` 查看两套页面状态、`-Action local` 启动并打开本地页面、`-Action server` 打开现有服务器页面；`-Action open -Mode local/server` 只打开已运行的对应页面。服务器页面默认 `127.0.0.1:5173`，不在此脚本中启动或改写服务器后端；其他地址可用 `-ServerUrl` 指定。切换仅打开目标页面，两套进程和数据可以并行保留。

## 当前范围

本地模式面向单人、单进程的日常核心流程。首次启动创建默认项目和模块；现已允许创建、导入、复制、归档、恢复和删除额外项目，现有多个项目可在重启后保留，启动时只补齐本地管理员缺失的项目归属，不改动已有多项目的模块。归档或删除不能移除最后一个活动项目，删除也不能移除最后一个项目；项目成员管理仍限服务器模式，完整多项目执行验收列在新计划 D1。执行任务写入 SQLite 加密队列，未开始的任务会在重启后继续；执行中断的任务会标记错误，不自动重放。API 与 Web 用例真实手动运行、API 请求文件上传/签名下载、Web 取消、排队任务重启继续、含运行数据的报告与趋势 CSV 已验收；截图、运行中断恢复及完整附件矩阵仍待验收。

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

将仓库及备份目录复制到新电脑，安装依赖后，在尚无 `local-lite.env` 和目标数据目录的环境恢复。备份使用配置里的实际数据路径，恢复可用 `-DataDir` 改写目标路径，例如：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action restore -ArchiveDir 'E:\ATP-backup\snapshot-001' -DataDir 'D:\ATP_resources'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up
```

恢复拒绝覆盖现有本地配置或数据，并在复制前核对备份内每个文件的 SHA-256 清单（`manifest.json`）。备份复制当前文件，不提供加密归档或自动同步；包含密钥与账号，应妥善保管。同机独立目录恢复已通过文件校验和 SQLite 完整性检查。此外，仓库提供 `scripts/package-windows-standalone-bundle.ps1` 脚本，可快速构建包含 600+ 核心运行文件的绿色免编译便携交付包。

## 2026-10-15 交付状态

当前本地 SQLite 版本为 13；以静态模式运行，页面和 API 均由 `8001` 提供。开发模式可另启 `5174` Vite。全套 CI 对应门禁（Ruff 规范/格式、Mypy 188 源码文件、Bandit SAST、vue-tsc 与生产构建）均已通过。统一交付证据索引见 [`evidence-index-2026-10-15.md`](evidence-index-2026-10-15.md)。
