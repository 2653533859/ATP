# Windows 本地轻量模式

本地模式直接在 Windows 运行 Backend，前端可使用 Vite 开发入口或 Backend 提供的静态页面。业务数据保存在仓库下 `.local-data/atp.sqlite3`，附件保存在 `.local-data/objects/`，API 会话密文保存在 `.local-data/sessions/`。不需要 WSL、Docker、PostgreSQL、Redis 或 MinIO。服务器部署仍使用原有基础设施；两套数据和登录账号独立，不自动同步。

## 启动

当前功能与验收缺口见 [`current-capability-baseline-2026-10-07.md`](current-capability-baseline-2026-10-07.md)，剩余任务见 [`development-task-plan-2026-10-07.md`](development-task-plan-2026-10-07.md)。本地已接入 Web 录制、手动串行套件/计划、需求、缺陷、知识、资产、AI 配置、协议测试、Hermes 与单机性能。AI 需要自行配置联网模型；计划/性能不支持定时或远程节点。当前代码 SQLite 版本为 11，启动时显式升级；版本 8 增加资源身份，版本 9 增加套件投递意图，版本 10 增加首次接受凭据及套件队列/租约 UUID，版本 11 增加计划 UUID、取消时间及子归属记录。套件/计划执行记录展开后可查询恢复状态和请求协作取消。旧命令/旧运行不自动猜测或补投；已接受但失联的运行须核对，不能自动重跑。详见 [N1.5 记录](group-recovery-development-2026-10-08.md)。历史扩展记录见 [`windows-local-feature-extension-2026-09-30.md`](windows-local-feature-extension-2026-09-30.md)。实现接入与业务验收分别记录。

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

接口测试工作台采用请求集合、请求编辑和响应区布局：左侧按模块浏览已保存用例，右侧可填写 HTTP 方法、URL、Params、Headers、Body、Auth、Cookies 并直接发送；响应区显示状态、耗时、大小、正文与响应头。“保存为新用例”会把当前请求带入用例编辑器，保存前需选定左侧模块。非 HTTP 协议用例仍通过详情与高级编辑器处理。Vite 开发代理仅转发 `/api` 和 `/ws` 路径段，避免将 `/api-workbench` 页面误转发给后端静态站点。

响应区还显示本次实际请求的方法与合并 Params 后的 URL、服务器状态、Content-Type、可用的 Request ID、Location 和 Allow，并为常见 HTTP 错误提供排查方向。目标服务器返回 0 B 时明确标记“未返回响应正文”；诊断文字仅解释状态码，不声称获得服务器未提供的具体错误原因。

响应 Body 可在“字段 / 原文”间切换。JSON、XML、URL 编码表单、CSV 和 TSV 展示字段路径、类型和值，并支持搜索；普通文本和 HTML 源码按行展示，不执行返回的 HTML。字段视图有展示数量与深度限制，原文仍可查看后端返回的内容（预览接口最多保留 1 MB）。

对 `GET /v1/model` 返回 404 的请求，工作台会提示 OpenAI 兼容模型列表通常使用 `/v1/models`，并提供填入建议地址按钮；不会自动重发请求。此提示是路径建议，不能代替目标服务的接口文档或证明认证配置正确。

Android 本地模式使用 Windows 本机 ADB。安装 Android SDK Platform Tools 并把 `adb` 加入 `PATH`，连接设备后在 APP 工作台手动扫描，再选设备、APK、Android 用例或专项任务执行。专项任务仅支持手动触发和停止；运行排队、失败与中断恢复保存在 SQLite，停止信号由本进程处理。9 月 29/30 日记录未连接真机，本轮没有重新检查设备；真机执行、APK 安装、截图/报告和停止时序仍待验收。Web 录制和单机性能已接入；iOS、分布式 Worker、远程性能节点、定时计划及部分依赖 Redis 的 AI 专项入口不在本地范围内。

本地启动只从独立 `local-lite.env` 中读取允许的配置，不加载仓库根目录 `.env`。本地认证 Cookie 使用独立名称；页面启动时读取后端模式并拒绝错误后端。当前源码在两种模式都有 `/api/v1/runtime`；实际服务器部署是否包含该接口须现场核实，旧版服务器兼容路径继续保留，正式双向切换验收未完成。旧的 `local-all.env` 不用于本地轻量启动。进度见 [`windows-dual-mode-development-plan-2026-09-29.md`](windows-dual-mode-development-plan-2026-09-29.md)。

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
