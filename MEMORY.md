# MEMORY

- 2026-08-25 P1-E.2 性能基线回归门禁本地交付已完成：性能运行门禁与 Webhook 支持可选 `require_baseline=true` 和 `fail_on_baseline_regression=true`；CLI `scripts/performance-gate.py` 对应新增两个开关，默认调用 URL 不变。只接受同一压测定义/项目下的成功基线；基线缺失返回 `not_configured`，运行本身失败或取消优先保留原状态。代码审查修复 FastAPI `Query(False)` 在直接调用路由单测中表现为 truthy 查询对象的问题，改为普通布尔默认值；报告/API/Webhook/CLI 定向 `88 passed`，完整非集成后端 `2224 passed`，Ruff/格式检查通过。真实多节点、容量、报告留存和 Android 设备仍未完成。

- 2026-08-25 P1-E.1 性能长期趋势本地交付已完成：新增项目级 `GET /api/v1/projects/{project_id}/performance/trend`，支持 1～365 天固定 UTC 日窗口、空日期补齐、项目 viewer 权限、性能场景筛选、完成/开始/创建时间归档、分片父运行去重和摘要指标聚合；`/system/performance` 与 `/performance-workbench` 均支持近 7/30/90 天切换。审查发现并修复项目清空时趋势请求被丢弃后 `trendLoading` 残留，新增回归断言。后端趋势/容量/API 定向 `79 passed`，完整非集成后端 `2220 passed`；前端定向 `15 passed`、全量 `66 files / 265 tests passed`，type-check/build、Ruff、格式检查和 diff-check 通过。真实多节点容量、节点资源限制、长周期报告留存和阈值回归仍未完成，不能用本地 mock 历史替代。

- 2026-08-24 已将参考导航同步为可执行开发计划：主计划为 `docs/product-navigation-roadmap-2026-08-24.md` 的“导航对齐执行版计划”，`Task.md` 维护勾选状态。计划按工作台、测试能力（API/APP/UI/性能/AI）、测试资产、智能中枢、系统和质量发布六阶段跟踪；每个模块必须执行实现 → 定向/全量测试 → 代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送。当前本地工作台和业务模块大多已完成，真实验收仍受 Android ADB `offline`、通知供应商/外部缺陷平台凭据和真实性能多节点环境限制；这些状态不能改记为完成。

- 2026-08-24 P0-B Android Worker 设备状态诊断已完成代码交付：`windows-android-worker.ps1 doctor` 新增 ADB 状态计数，排除 `List of devices attached` 标题，区分 online/unauthorized/offline/other，并对 RSA 授权、USB 重连和 TCP ADB 可达性给出不同提示。当前真实结果为 `online=0, unauthorized=0, offline=1, other=0`；Worker 仍运行且 PostgreSQL/Redis/MinIO 可达，但没有设备执行证据。Windows 脚本契约 `11 passed`、PowerShell AST 解析、doctor 和 `git diff --check` 通过；代码审查发现并修复了标题行被误计为 other 的问题。P0-B 仍标记为“已实现，待真实环境验收”，设备恢复 `device` 后再继续扫描、预约、截图、APK 包名和 Android 用例/专项任务验证。

- 2026-08-24 P0-A Windows smoke 401 诊断已完成代码交付：`scripts/windows-local-smoke.ps1` 现在只提取 HTTP 状态并给出脱敏提示，401 说明当前账号被拒绝且 `FIRST_ADMIN_*` 仅用于首次创建管理员，403 指向 CSRF/Cookie/权限链路，其他异常不输出原始异常文本；文档补充通过当前 PowerShell 进程的 `ATP_USERNAME`/`ATP_PASSWORD` 临时覆盖和清理方式。Windows smoke 契约 `11 passed`、PowerShell AST 解析和 `git diff --check` 通过，代码审查未发现问题。真实有效账号登录、认证读接口、Playwright/浏览器矩阵、文件传输和报告导出尚未重跑，P0-A 标记为“已实现，待环境验收”，不把未知凭据或 401 失败改成通过。

- 2026-08-24 已同步当前开发计划总表：主计划为 `docs/product-navigation-roadmap-2026-08-24.md`，`Task.md` 同步维护勾选状态。当前顺序固定为 P0-A Windows API/Web 可用性复核（先改善 smoke 的 401 安全诊断，再用当前有效账号重跑完整 Windows 验收）→ P0-B Android Worker 单设备真实验收（设备必须从 `offline/unauthorized` 恢复为 `device`）→ P1-C 真实通知供应商 → P1-D Jira/禅道/GitHub/GitLab 外部缺陷平台 → P1-E 性能多节点/容量/长期趋势 → P1-F 发布文档收口。P0-B/P1-C/P1-D 的代码已完成、待真实环境验收；P1-E 的单节点短压已有证据，但多节点/容量/长期趋势仍在开发和验收计划中。不能把 mock、本地 SMTP sink、ADB offline 或无凭据状态记为通过；凭据只能由本机环境变量/临时环境提供，禁止写入仓库、日志和证据。每个模块必须按“实现/调整 → 测试 → 代码审查 → 修复 → 文档与记忆同步 → 提交推送”闭环。

- 2026-08-24 N0 导航分组收口已完成：侧栏按参考导航仅保留工作台、测试能力五项、测试资产五项、智能中枢三项和系统远程工具箱/配置中心；设备、APK、专项任务、报告、Mock、数据集、Web/API 资产及系统治理旧页面保留 URL，并映射到所属工作台或配置中心高亮。配置中心新增按管理员权限显示的用户、审计、保留策略和告警快捷区，避免删掉入口。定向前端 `9 passed`、后端静态契约 `7 passed`，全量前端 `66 files / 263 tests passed`，type-check/build 通过。

- 2026-08-24 N0 导航壳体验收口已完成：新增统一导航状态模块 `frontend/src/layouts/navigation.ts` 和回归测试，主布局新增五组导航面包屑；深层用例/项目路由保持正确选中，Android 专项任务/报告详情使用具体页面标题，系统页和旧 URL 保持兼容。导航定向 `6 passed`，前端全量 `66 files / 262 tests passed`，type-check 通过；本次未改变权限规则或后端执行逻辑。

- 2026-08-24 N6.13 全量质量门禁复核已完成：后端非集成测试 `2215 passed`；前端 `npm run type-check` 和生产 `npm run build` 均通过；`git diff --check`、工作区清洁和远端同步检查通过，配置校验模块基线提交为 `c54a57c`。本轮未把 Android 离线设备、真实通知供应商或外部缺陷平台联调误记为通过；下一步仍按计划先恢复 Android 单设备证据，再补真实通知与外部平台验收。

- 2026-08-24 N6.12 Android Worker 配置配对门禁已完成：新增 `scripts/validate-android-worker-config.py`，只输出字段名/队列状态，不输出 PostgreSQL、Redis、MinIO、APP_SECRET_KEY 或 ENCRYPTION_KEY 值；校验 Backend/Windows Agent 共享基础设施和密钥、`ADB_SCAN_MODE`、Celery 队列、Worker 队列及 Redis 注册前缀。`windows-android-worker.ps1 doctor` 支持 `-BackendEnvFile` 自动执行配对检查，`startup.ps1` 支持透传该参数，Make/CI/pre-commit/部署 readiness 已接入脚本；统一两个示例档案的密钥占位符。配置/Worker/PowerShell/质量门禁定向 `55 passed`，部署门禁通过（仅跳过本机缺少 Docker Compose 的环境检查）。Android 真机仍因 ADB offline 待恢复。

- 2026-08-24 N6.11 通知链路本地安全验收已完成：通过回环 SMTP sink 走生产入口 `send_notification_channel`，12 项检查全部通过，覆盖 SMTP envelope、收件人规范化、MIME multipart、显示名和 RPS/P95/P99/错误率/阈值/触发原因六项正文；报告固定为 `local_link_only`，未触达真实邮箱、未记录凭据，证据见 `docs/evidence/notification-smtp-link-check-2026-08-24.json`。真实 SMTP/企业微信/钉钉仍需管理员提供临时目标和供应商侧送达证据，Android 真机仍因 ADB offline 待恢复。

- 2026-08-24 N6.10 q19 性能节点真实验收已完成：性能 smoke 预检确认 API healthy、k6/Locust/gRPC/JMeter ready，专用节点 `worker-a` online、队列 `performance.worker-a`；临时项目执行一次低并发 k6（1 VU、5 次迭代、目标 `http-target`），运行状态 `success`，产生 1 条 `performance-worker` 资源采样。Prometheus readiness 通过，`atp-backend`、`atp-worker`、`atp-performance-worker` 三个 target 为 up。临时项目、测试、运行和性能脚本对象已清理；脱敏证据见 `docs/evidence/q19-performance-worker-smoke-2026-08-24.json`。Android Worker 已启动并有心跳，但当前 ADB 设备仍为 offline，Android 真机闭环继续待设备恢复；下一步优先补 Android 单设备验收，再验收通知和外部缺陷平台。

- 2026-08-24 N6.9 Firefox/WebKit 与跨 API 副本录制验收已完成并推送提交 `41ff87a`：Linux `WEB_RECORDER_MODE=worker` 下 WebKit 改为无头启动，避免 Xvfb 中 headed WebKit 挂起；新增 Linux Worker WebKit 启动回归，Windows/local 与 Firefox 行为保持不变。q19 使用 `41ff87a` 重建后，Firefox 截图 `19076` bytes、WebKit 截图 `21192` bytes，二者均完成 2 步快照、停止、Trace/HAR/运行报告 URL 和停止后查询；启动临时第二 API 副本后，副本 A 停止的会话可由副本 B 通过共享 Redis 查询为 `stopped`。后端目标回归 `45 passed`，Ruff/diff-check 通过；证据见 `docs/evidence/q19-web-recording-firefox-2026-08-24.json`、`docs/evidence/q19-web-recording-webkit-2026-08-24.json` 和 `docs/evidence/q19-web-recording-cross-api-2026-08-24.json`。临时项目、18 个录制对象和第二副本已清理。下一步优先验收 Android Worker/真机，再验收真实性能节点、通知和外部缺陷平台。

- 2026-08-24 N6.8 Web 录制证据链已完成并推送提交 `9e93379`：`WebRecordingSession` 采集 Playwright Trace、HAR、Console、页面异常、请求/失败请求/错误响应事件，持久化前对 URL、请求头、Cookie、请求体、步骤和错误文本脱敏；Trace/HAR/运行报告上传 MinIO，独立 Worker 模式在 Redis 保留脱敏最终快照，停止后可再次查询。前端录制弹窗展示三类证据入口和最近网络事件，smoke 新增证据 URL/停止后报告检查。代码审查修复 JSON 凭据和完整 URL 脱敏边界；后端目标回归 `45 passed`，前端 Web Recorder `3 passed`、type-check/build、Ruff/diff-check 通过。q19 使用 `9e93379` 重建并重启 `web-recorder`，首次和重启后录制均通过，项目及 6 个对象已清理；证据见 `docs/evidence/q19-web-recording-evidence-2026-08-24.json` 与 `docs/evidence/q19-web-recording-evidence-restart-2026-08-24.json`。下一步优先补 Firefox/WebKit 与跨 API 副本一致性，再验收 Android、真实性能、通知和外部缺陷平台。

- 2026-08-24 N6.7 q19 独立 Web 录制 Worker 持久部署与真实录制验收：提交 `3ddf4f1` 新增独立 `web-recorder` 编排，`7a94e62` 修复 Xvfb 重启残留锁，`dfe86b1` 为主 Compose 与 q19 录制服务启用 `init: true` 回收 Chromium 子进程。q19 Backend 固定为 Worker 模式，录制服务使用同一 Redis 路由前缀、Xvfb `:99` 和健康文件；Backend、录制 Worker、通用 Worker、性能 Worker、Prometheus 及依赖服务正常，Prometheus targets 均为 up。真实临时项目完成 Chromium 录制、2 步快照、PNG 截图、停止和删除，录制 Worker 重启后再次通过，`active_sessions=0`、容器 `zombie_count=0`。脱敏证据为 `docs/evidence/q19-web-recorder-readiness-2026-08-24.json`、`docs/evidence/q19-web-recorder-restart-readiness-2026-08-24.json` 和 `docs/evidence/q19-web-recorder-init-readiness-2026-08-24.json`。本地相关回归 `61 passed`，Ruff 和 diff-check 通过；下一步补 Trace/HAR/Console/网络日志/运行报告完整链路，再验收 Android、真实性能节点、通知和外部缺陷平台。

- 2026-08-24 N6.6 q19 持久通用 Web Worker 部署与恢复验收：提交 `f1473d2` 在 q19 Compose 新增独立 `worker` 服务，固定监听 `default,maintenance`，与性能 Worker 的 `performance.worker-a,performance` 队列隔离；Worker 指标加入 Prometheus `atp-worker:9091`，Backend、Worker、性能 Worker 和 Prometheus targets 均为 up。q19 首次 Web 低代码下载 `run 4`、Worker 重启后 `run 5` 均通过并回传 1 个下载对象，临时项目和对象清理通过。脱敏证据为 `docs/evidence/q19-persistent-web-worker-readiness-2026-08-24.json`、`docs/evidence/windows-persistent-web-worker-readiness-2026-08-24.json` 和 `docs/evidence/windows-persistent-web-worker-restart-readiness-2026-08-24.json`。当前独立录制 Worker、Android 真机、真实性能节点、通知和外部缺陷平台仍待验收；下一步先补独立录制 Worker 的持久部署和 Trace/报告链路。

- 2026-08-24 N6.5 q19 真实迁移与 Web Worker 临时验收：从最新 `main`（`5179826`）构建并部署 q19 Backend/性能 Worker/Beat/迁移镜像，目标数据库从 `20260814_0059` 升级到 `20260824_0065`；Backend、PostgreSQL、Redis、MinIO、性能 Worker 和 Beat 健康，Backend `/health` 返回 200。项目 API 删除临时项目返回 204，项目/环境/模块残留为 0；临时默认队列 Worker 完成 Web 低代码下载执行 `run 3`，下载对象和清理通过，验收后已移除临时 Worker。脱敏证据为 `docs/evidence/q19-migration-web-worker-readiness-2026-08-24.json` 和 `docs/evidence/windows-web-worker-readiness-2026-08-24.json`。q19 持久编排尚未加入通用 Web Worker；Android 因 ADB offline 未执行，真实性能节点、通知和外部缺陷平台仍待验收。下一步先固化持久 Web Worker，再做 Android/性能/通知/外部平台证据。

- 2026-08-24 N6.4 Windows 完整 API/Web 验收与项目删除级联修复：在当前 Windows 运行档案和远端 q19 PostgreSQL/Redis/MinIO 上，管理员登录、认证读接口、Web Recording 状态、Playwright `12 passed`、Chromium/Firefox/WebKit 矩阵、47 bytes 文件上传/清理及 HTML/JUnit 报告导出通过，脱敏证据为 `docs/evidence/windows-full-readiness-2026-08-24.json`，必需失败数为 0；Web 低代码真实执行和 Android 因未指定用例/未启用 Worker 保持 optional skip。清理临时项目时发现 `environments_project_id_fkey` 阻断删除，已新增 Alembic `20260824_0065`，同步 APK、环境、模块、计划、套件项目级 `CASCADE`，环境变量级联删除，计划环境引用 `SET NULL`；项目路由/迁移定向 `34 passed`、迁移目录 `66 passed`、Alembic head `20260824_0065`、Ruff/diff-check 通过，远端 q19 临时项目已清理。下一步是目标数据库真实迁移升级/降级，再进行 Android Worker/真机、真实性能节点、通知和外部缺陷平台验收；严格 readiness 仍受 Windows 缺少 Docker Compose 工具影响。

- 2026-08-24 N6.3 Windows 发布 readiness 与远端依赖恢复已完成部分环境收口：172.31.27.133 的 Redis 因旧容器网络/6379 发布状态残留导致 Windows 连接拒绝，已在保留挂载数据目录的前提下清理异常容器状态、重启 Docker 网络层并恢复 Redis；q19 验收栈的 PostgreSQL、Redis、MinIO 和 Backend 依赖链也已恢复，Backend `/health` 返回 200，其他 Worker/目标服务仍需单独复核。Windows `windows-local-smoke.ps1 -SkipPlaywright -SkipBrowserMatrix -SkipFileTransfer -SkipReports -SkipLiveLogin` 通过 doctor、后端/前端健康、三项远端依赖、ADB、k6/Locust/gRPC 和性能队列检查，脱敏证据为 `docs/evidence/windows-release-readiness-2026-08-24.json`。本次显式跳过登录、认证读接口、Playwright/浏览器矩阵、文件/报告、Android 执行；Android 无在线设备 warning，严格 readiness 因本机缺少 Docker Compose 工具失败。该证据只代表 Windows API/Web 最小链路和远端依赖恢复，不代表完整发布、Android 真机、性能节点、通知或外部缺陷平台已验收；下一步先补完整 Windows 登录/Web/报告，再按环境完成剩余证据。
- 2026-08-24 N6.2 发布文档、能力矩阵与操作手册已同步：`docs/capability-baseline-2026-08-07.md` 新增五组导航、远程工具箱、配置中心和发布质量门禁状态；`docs/user-operation-manual.md` 修正旧七组导航，补充工作台/任务中心、远程工具箱、配置中心的入口、权限、脱敏和精确 `ROLLBACK` 边界；`docs/q18-latest-status-2026-08-07.md` 与 `docs/q18-implementation-log-2026-08-07.md` 已增加 N6.2 记录。文档审查明确区分本地代码/自动化证据与真实环境验收，下一步是按环境补齐数据库迁移、生产密钥、Android/Windows Worker、性能节点、通知和外部缺陷平台证据。
- 2026-08-24 N6.1 配置中心浏览器回归已完成本地实现、代码审查和质量门禁：新增 `frontend/e2e/configuration-center.spec.ts`，用脱敏接口桩覆盖管理员查看配置资源/历史版本/字段差异、精确 `ROLLBACK` 回退提交，以及普通测试角色访问 `/system/config` 被权限守卫拦截到 `/dashboard`。首次执行发现选择器严格模式命中同名摘要文本，已收紧为资源标题定位；审查未发现产品逻辑、权限或敏感信息问题。定向 E2E `2 passed`，全量 Playwright `12 passed`；前端 Vitest `65 files / 258 tests passed`，type-check、生产构建和 git diff-check 通过。真实配置数据、数据库迁移、生产密钥和外部依赖仍待环境验收，下一入口为 N6.2 发布文档、能力矩阵和环境证据收口。
- 2026-08-24 N5.2.6 配置中心质量收口已完成本地实现、代码审查和回归：新增空历史、跨项目差异拒绝、资源/环境变量行锁、提交前刷新失败事务回滚和 `20260824_0064` 迁移链/外键/索引/降级契约测试。配置中心 API/迁移定向 `24 passed`，后端非集成 `2201 passed`，独立文件隔离扫描 `290 passed / 0 failed`，Ruff check/全量 format-check、mypy（151 个源文件）、Bandit、git diff-check 均通过；此前前端全量 `65 files / 258 tests passed`、type-check/生产构建也通过。代码审查未发现业务或安全问题，并收口原有 `backend/app/api/v1/workbench.py` 纯格式遗留。N5.2 已进入“已实现，待真实环境验收”，下一阶段为 N6 质量收口与发布验收。
- 2026-08-24 N5.2.5 配置中心前端工作台已完成本地实现、代码审查和回归：`/system/config` 替换导航占位页，仅管理员/工程师可见；聚合配置域、资源列表、项目筛选、原页面深链接、当前状态和脱敏摘要，提供历史版本时间线、字段差异、影响提示、快照保存与精确 `ROLLBACK` 回退确认。保留旧配置页面/API，补齐加载失败、无权限、无历史、缺失资源、敏感字段、窄屏、键盘焦点和 reduced-motion 状态；资源/版本请求加入序列保护，普通角色不再看到受限菜单。前端定向与导航 `6 passed`，全量 `65 files / 258 tests passed`，type-check/生产构建/diff-check 通过。真实角色、配置数据、生产密钥和三方依赖仍待环境验收，下一开发入口为 N5.2.6 质量收口。
- 2026-08-24 N5.2.4 单资源可控回滚已完成本地实现、代码审查和回归：新增 `POST /api/v1/configuration-center/revisions/{revision_id}/rollback`，必须精确提交 `confirmation=ROLLBACK`；回滚前复核历史 HMAC、版本域/资源 ID、资源存在性、当前项目范围和写权限，支持环境/变量、全局变量、AI、存储、通知和性能节点，启动配置仍只读。目标资源及环境变量行使用行锁，恢复在同一事务中完成，环境密钥、全局变量、AI Key 和通知配置重新加密，成功后生成“配置回滚”新版本并写入只含域/资源 ID/指纹的脱敏审计；唯一冲突、权限、篡改历史、刷新或其他失败均回滚，viewer 不可恢复。代码审查将新版本刷新提前到提交前，并补充篡改版本事务回滚回归。回滚/路由定向 `15 passed`，后端非集成全量 `2195 passed`，前端 type-check/生产构建、Ruff、改动文件格式检查和 `git diff --check` 通过；全量格式扫描剩余仓库原有 `backend/app/api/v1/workbench.py`，留待 N5.2.6 质量收口；真实数据库、角色、密钥轮换和生产配置仍待环境验收。下一开发入口为 N5.2.5 `/system/config` 前端统一工作台。
- 2026-08-24 N5.2.3 配置差异与影响提示已完成本地实现、代码审查和回归：新增 `GET /api/v1/configuration-center/revisions/{revision_id}/diff`，比较历史 Fernet 快照与当前资源，返回字段级新增/删除/变更、当前资源状态、历史/当前 HMAC 指纹和最多 500 项变更保护。普通字段只返回脱敏前后值；密钥、Token、密码、Endpoint、Webhook、URL、secret 变量及性能节点出口/能力只返回路径、类型和 `changed=true`，不返回前后值；历史快照先校验 HMAC 指纹，资源已删除时保留历史并明确无法计算当前差异。按环境执行、变量引用方、AI 生成/诊断、对象保留、通知投递和性能调度提供影响提示。审查修复性能节点无项目范围权限误拒绝、项目 viewer 查看差异误要求 editor、敏感变量名脱敏遗漏和 dataclass 响应转换问题。差异/路由定向 `11 passed`，后端非集成全量 `2191 passed`，Ruff/mypy/格式/diff-check 通过；真实角色、密钥轮换和生产配置差异仍待环境验收。下一开发入口为 N5.2.4 单资源可控回滚。
- 2026-08-24 N5.2.2 配置版本快照与变更审计已完成本地实现、代码审查和回归：新增 `configuration_revisions` 与 Alembic `20260824_0064`，按环境、全局变量、AI、存储、通知和性能节点保存单资源 Fernet 加密原始快照、脱敏快照、HMAC 指纹、创建人、原因和时间；启动配置仍只读且不生成资源版本。新增 `POST/GET /api/v1/configuration-center/revisions`，沿用管理员/工程师/项目角色权限，响应只返回脱敏版本，审计只记录 domain/resource_id/fingerprint，不记录原因、密钥、密码、Token、连接串或原始配置。审查修复普通明文环境变量被错误标记为密文、存储策略未统一脱敏的问题。配置版本/迁移定向 `7 passed`，后端非集成全量 `2185 passed`，Ruff/格式检查通过；真实数据库迁移、不同项目角色、密钥轮换和生产审计数据仍待环境验收。下一开发入口为 N5.2.3 配置差异与影响提示。
- 2026-08-24 N5.2 进度已更新：N5.2.1 只读聚合、N5.2.2 版本快照/审计、N5.2.3 差异/影响提示、N5.2.4 单资源回滚、N5.2.5 `/system/config` 前端工作台与 N5.2.6 质量收口已进入“已实现，待真实环境验收”，后续进入 N6 质量收口与发布验收；`Task.md`、路线图和本记忆同步遵循每模块实现→测试→审查→修复→文档→提交推送顺序。
- 2026-08-24 N5.2.1 配置只读聚合与权限边界已完成本地实现、代码审查和回归：新增 `GET /api/v1/configuration-center/overview`，统一聚合启动档案、项目环境、全局变量、AI 模型、存储策略、通知配置和性能节点，返回配置域、资源摘要、更新时间、原页面深链接和资源级可管理标记。启动档案只展示安全运行开关且只读；AI/存储仅管理员可见；项目资源沿用 viewer/editor/owner 权限；环境变量、全局变量、通知、API Key、Endpoint、Webhook、连接信息和任意 capabilities 内容不回显，只保留计数/状态/执行器名称等安全摘要。审查改用标准路由注册，补充路由回归与历史测试隔离的 `get_project_role` fill-missing-only 桩。配置中心定向 `4 passed`、路由 `1 passed`，后端非集成全量 `2181 passed`，Ruff/格式/diff-check 通过；真实数据库、项目角色、AI/通知/性能节点仍待环境验收。下一开发入口为 N5.2.2 版本快照与变更审计。
- 2026-08-24 已为 N5.2 配置中心同步开发计划，N5.2.1 只读聚合、N5.2.2 版本快照/审计、N5.2.3 差异/影响提示和 N5.2.4 单资源回滚已完成本地实现、审查和回归；后续交付顺序为：N5.2.5 `/system/config` 前端统一入口；N5.2.6 代码审查、回归和文档收口。范围覆盖启动配置、环境、全局变量、AI 模型、存储、通知和性能节点，保留旧页面/API 兼容。启动配置只读、不通过 Web 直接重启服务；原始快照加密，响应/日志/文档只允许脱敏值；不做批量删除重建。当前下一开发入口为 N5.2.5，完成一个子模块后才可推进后续子模块。
- 2026-08-24 N5.2 验收边界已记录：管理员/工程师应能从统一入口查看有权限配置的脱敏摘要、历史版本和差异；普通角色不得越权读取或回滚；回滚只影响选中的单个资源并写入审计；异常不得产生半更新或敏感信息泄露。真实数据库、生产密钥、三方 AI、通知、Worker 和性能节点联调继续单独作为环境证据，不把本地实现标记为真实环境完成。
- 2026-08-24 N5.1 远程工具箱已完成本地实现、代码审查和回归：新增 `/api/v1/remote-toolbox/overview` 与 `/system/toolbox`，统一检查 PostgreSQL、Redis、MinIO、Android Worker/ADB、Web Worker/本地录制模式和性能节点；结果只包含状态、原因码、检查时间、延迟、队列/能力等脱敏元数据，支持前端导出脱敏 JSON。复用既有健康探针、Android/Web 注册中心和性能节点查询，未新增模型/迁移/执行器；管理员/工程师权限边界与前端处理入口已接入。审查还修复性能节点 capabilities 原样回显潜在敏感字段，仅保留字符串执行器名称。后端全量非集成 `2177 passed`，前端全量 `64 files / 254 tests passed`，定向远程工具箱后端 `6 passed`、前端 `3 passed`，type-check/build/Ruff/格式/diff-check 通过。真实数据库、Redis、MinIO、Windows Android Worker/ADB、Web Worker 和性能节点仍待环境验收，下一开发入口为 N5.2 配置中心。

- 2026-08-24 N4.4 知识中枢已完成本地实现、代码审查和回归：新增 `knowledge_entries` / Alembic `20260824_0063`，支持全局/项目知识、来源类型、草稿/发布/归档、版本、标签、来源引用和项目删除级联清理；新增 `/knowledge` 统一搜索 API 与独立工作台，按项目/关键词/来源/状态筛选并展示来源、项目边界、命中词和可编辑状态。搜索聚合手工知识、需求、内部缺陷和失败/错误运行，内置来源只读并跳转对应需求/缺陷/运行，手工条目支持管理员/项目 editor 创建、编辑、删除；全局知识只在发布后对普通用户可见，所有写入与返回的文本/标签/来源引用统一脱敏。审查修复项目筛选漏掉全局条目、全局草稿可见、标签未脱敏，以及需求/缺陷来源只能打开默认列表项；前端补充精确深链接打开。知识/需求/迁移回归 `15 passed`，前端定向 `3 files / 9 tests passed`，全量 `63 files / 251 tests passed`，vue-tsc/build/Ruff/diff-check 通过；真实知识数据、项目角色、生产迁移和大数据量检索仍待环境验收。已进入 N5 远程工具箱环境验收。
- 2026-08-24 N4.3 需求与用例追踪已完成本地实现、代码审查和回归：新增 `test_requirements` / `requirement_case_links` 与 Alembic `20260824_0062`，需求按项目隔离并支持状态、优先级、来源、版本、负责人和 JSON 验收标准；新增 `/requirements` 项目范围列表、详情、创建/编辑/删除、规则化文本解析草稿、需求—用例关联/解除、验收覆盖率和标题/描述/标签影响候选分析。负责人必须是有效项目成员，读写分别要求 viewer/editor，跨项目用例、未知验收标准和越权负责人会被拒绝；前端占位入口替换为需求追踪工作台，支持项目/状态/关键词筛选、版本/覆盖率、验收标准状态、关联维护、未覆盖标准和影响雷达，解析结果始终先进入可编辑草稿。审查修复需求列表无效条件表达式、创建响应未回填 ORM 默认版本、负责人越权指派及前端项目/详情异步边界；后端需求/迁移/零状态回归 `10 passed`，前端定向 `1 file / 3 tests passed`，前端全量 `62 files / 248 tests passed`，type-check/build/ruff/diff-check 通过；真实需求数据、项目角色、用例联动、审计和生产迁移仍待环境验收。下一开发入口为 N4.4 知识中枢。
- 2026-08-24 N4.2 Hermes 助手已完成本地实现、代码审查和回归：新增 `/hermes` 项目级助手工作台，聚合模块、用例、失败任务、报告和失败热点；提供失败任务查询、失败解释、质量指标汇总和测试计划草稿四类意图，支持快捷提问和中文/英文关键词识别。失败解释复用 `runApi.generateFailureDiagnosis`，只对 Case 运行触发既有诊断链路，其他任务类型保留原始错误并跳转专属详情；消息、诊断摘要和计划建议均保留任务/运行/报告/统计来源。测试计划只生成可编辑草稿，支持覆盖点维护并跳转 `/plans` 确认保存，不静默写入。审查修复项目清空 selected project 未更新、项目切换旧响应覆盖和诊断失败无降级反馈；全量前端 `61 files / 245 tests passed`，type-check/build/diff-check 通过；未新增后端模型/迁移/执行器，真实项目数据、Case 诊断模型、任务权限和生产审计仍待环境验收。下一开发入口为 N4.3 需求与用例追踪。
- 2026-08-24 N4.1 AI 智能测试工作台已完成本地实现、代码审查和回归：新增 `/ai-workbench`，按项目聚合模型绑定、模块、用例自动化覆盖缺口、测试数据集、Mock 规则、质量总览、失败热点和失败任务；提供用例草稿、测试数据、Mock 响应三个生成通道，分别复用现有 `/cases`、`/system/datasets`、`/mock-rules` 的可编辑预览链路。失败任务跳转既有任务/运行详情，管理员可见 AI 生成漏斗和全平台自愈反馈，查看者只读，未绑定/禁用模型时阻止生成，模型密钥不展示。审查修复项目清空 loading 残留、刷新并发旧响应覆盖、项目级数据清理和管理员统计降级边界；定向导航/工作台 `2 files / 6 tests passed`，补充权限/模型门禁后工作台 `5 passed`，全量前端 `60 files / 240 tests passed`，type-check/build/diff-check 通过；未新增后端模型/迁移/执行器，真实三方模型、调用限额/审计和生产 AI 结果仍待环境验收。下一开发入口为 N4.2 Hermes 助手。
- 2026-08-24 N3.4 性能测试工作台已完成本地实现、代码审查和回归：新增 `/performance-workbench`，按项目聚合性能场景、环境、执行节点、执行器、运行队列和资源证据；支持快速新建脚本型场景、环境/多节点发起、options 覆盖、活动运行 2.5 秒轮询、停止运行、RPS/P95/P99/错误率、阈值门禁、Worker/Prometheus/ATP 资源采样时间线、基线对比、设置基线和 JSON/CSV 报告导出。复杂可视化场景、压力阶段、PromQL、调度和容量分析复用 `/system/performance`，旧入口保持兼容且读取 `project_id` 查询参数。审查修复执行器 API 失败误放行、辅助接口失败阻断场景、资源来源标签映射、证据请求竞态和新旧入口项目上下文不一致；查看者只读，创建/执行/基线按项目编辑权限控制。定向工作台 `4 passed`、性能中心/导航联动 `11 passed`，全量前端 `59 files / 235 tests passed`，type-check/build/diff-check 通过；未新增后端模型/迁移/执行器，真实性能 Worker、节点容量、Prometheus、Locust/JMeter/gRPC 和生产报告仍待环境验收。下一开发入口为 N4 智能中枢。
- 2026-08-24 N3.3 UI 自动化工作台已完成本地实现、代码审查和回归：新增 `/ui-workbench`，按项目/模块聚合 Web 用例、Playwright Worker 状态、元素库、页面对象、视觉基线、最近运行和 Trace 状态；支持 Web 用例详情、关键词筛选、低代码步骤预览、录制步骤带入新用例草稿、视觉基线截图采集和运行详情跳转。新建/编辑复用 `WebCaseDrawer`，录制复用 `WebRecorderModal`，执行复用 `caseApi.run`，资产页支持 `tab` 查询参数切换目标标签；未重复实现后端模型、迁移或执行器。代码审查修复项目清空状态残留、项目切换异步覆盖、空项目模块筛选和资产页标签响应式问题。定向 `3 files / 10 tests passed`，全量前端 `58 files / 230 tests passed`，type-check/build/diff-check 通过；真实 Web Worker、浏览器录制、截图上传、Trace/网络日志、定位器修复和运行报告仍待环境验收。下一开发入口为 N3.4 性能测试工作台。
- 2026-08-24 N3.2 APP 自动化工作台已完成本地实现、代码审查和回归：`/mobile-special/workbench` 聚合项目设备池、Android Worker 状态、Android 用例、专项任务、APK 资产、最近运行和兼容性概览；设备支持扫描、预约/心跳/释放和截图轮询预览，Android 用例复用 `caseApi.run`，专项任务复用 `mobileSpecialApi.triggerTask` 并支持显式目标设备与可选 APK 包名覆盖。预约期间锁定项目/设备焦点，专项任务执行前要求释放 UI 租约，避免与 Worker 执行租约冲突；查看者只读，扫描/预约/执行按项目编辑权限控制。定向 `2 files / 4 tests passed`，全量前端 `57 files / 225 tests passed`，type-check/build/diff-check 通过；未新增后端模型/迁移/执行器，真实 Windows Worker/ADB、在线真机、截图回传、报告和 APK 数据仍待环境验收。N3.3 UI 与 N3.4 性能工作台已继续完成，下一开发入口为 N4 智能中枢。
- 2026-08-24 N3.1 API 测试工作台已完成本地实现、代码审查和回归：`/api-workbench` 从占位入口升级为项目/模块/协议组织的 API 工作台，支持 HTTP/REST、GraphQL、WebSocket、gRPC 用例筛选、详情、最近运行、环境选择执行和运行详情跳转；新建/编辑复用 `CaseFormDrawer`，OpenAPI/Postman/cURL/样例导入与 AI 生成复用 `AIGenerateDrawer`，通过 `allowedCaseTypes` 限制 API 工作台只生成接口协议。只读项目隐藏写操作，执行要求项目编辑权限且用例可执行；刷新重复请求和 AI 类型推断问题已在审查中修复。前端定向/导航 `4 passed`，全量 `56 files / 223 tests passed`，type-check/build/diff-check 通过；未新增后端模型/迁移，真实项目角色、环境变量、协议服务和运行结果仍待环境验收。N3.2 APP、N3.3 UI 与 N3.4 性能工作台已继续完成，下一开发入口为 N4 智能中枢。
- 2026-08-24 N2.5 外部缺陷兼容已完成本地实现、代码审查和回归：新增 `defect_external_links` 与迁移 `20260824_0061`，内部缺陷支持 Jira/禅道/GitHub/GitLab 的手工映射、外部 Issue 创建、重复查询、状态同步和可选内部状态回写；创建内容脱敏、外部 URL 安全校验、错误信息不泄露凭据。缺陷详情支持关联卡片和操作弹窗，查看者仅可读；创建、手工关联、同步和解除关联四个后端写接口统一要求管理员/工程师。后端非集成 `2156 passed`，前端 `55 files / 221 tests passed`，缺陷详情定向 `3 passed`，type-check/build/ruff/diff-check 通过；真实外部平台凭据、网络、项目权限和状态差异仍待环境验收。N3.1 API、N3.2 APP、N3.3 UI 与 N3.4 性能工作台已继续完成，下一入口为 N4 智能中枢。
- 2026-08-24 N2.4 用例评审工作台已完成本地实现、代码审查和回归：新增 `/case-reviews` 队列/统计/筛选/分页、批量通过/驳回、评论、评审审计历史和版本快照兼容；前端新增独立评审工作台、详情抽屉、评审时间线、版本历史/差异入口和原用例跳转。定向后端 `8 passed`，前端全量 `55 files / 219 tests passed`，type-check/build/ruff/diff-check 通过；真实项目角色、审计数据、版本差异和生产数据仍待环境验收。N2.5 已继续完成，下一开发入口为 N3 API 测试工作台。
- 2026-08-24 已根据参考导航重新固化产品信息架构：工作台只放首页/待办/项目中心/任务中心；测试能力按接口、APP、UI、性能、AI 分组；测试资产按用例、计划、缺陷、报告、评审分组；智能中枢放 Hermes、需求与用例、知识；系统只放远程工具箱、配置中心和存储/通知/用户/审计等平台治理。测试业务不再继续堆到系统管理下。
- 2026-08-24 已将后续开发拆为 N2.1 内部缺陷、N2.2 失败证据关联、N2.3 报告中心、N2.4 用例评审工作台、N2.5 外部缺陷兼容、N3.1 API、N3.2 APP、N3.3 UI、N3.4 性能、N4.1 AI 智能测试工作台、N4.2 Hermes 助手、N4.3 需求与用例追踪、N4.4 知识中枢、N5.1 远程工具箱和 N5.2 配置中心；N5.1 已完成本地实现、审查和回归，当前开发入口切换为 N5.2 配置中心，真实数据库/权限/套件计划联动/审计、外部平台、协议服务、Windows Worker/ADB、Web Worker、性能 Worker、三方模型、需求/知识数据、远程依赖和生产数据仍待环境验收。完整计划与验收口径见 `docs/product-navigation-roadmap-2026-08-24.md`。
- 2026-08-24 文档同步规则继续有效：每个子模块完成实现、测试、代码审查和问题修复后，必须同步 `Task.md`、`MEMORY.md` 与路线图，再提交并推送；未做真实联调只能标记为“已实现，待环境验收”。
- 2026-08-24 已建立新的产品导航与能力扩展路线，计划文档为 `docs/product-navigation-roadmap-2026-08-24.md`。目标导航分为“工作台、测试能力、测试资产、智能中枢、系统”五组，按 N0 导航壳、N1 工作台/任务中心、N2 测试资产闭环、N3 API/APP/UI/性能工作台、N4 AI/Hermes/需求/知识、N5 远程工具箱/配置中心、N6 质量收口执行。
- 2026-08-24 当前状态：N0 基础导航已实现为五层菜单（工作台、测试能力、测试资产、智能中枢、系统）；N1 工作台/任务中心、N2.1/N2.2/N2.3/N2.4/N2.5 测试资产闭环、N3.1 API、N3.2 APP、N3.3 UI、N3.4 性能、N4.1 AI 智能测试工作台、N4.2 Hermes 助手、N4.3 需求与用例追踪、N4.4 知识中枢和 N5.1 远程工具箱已完成本地实现、代码审查和回归，均标记为“已实现，待真实环境验收”。当前下一入口为 N5.2 配置中心。
- 2026-08-24 N0/N1/N2.1/N2.2/N2.3/N2.4/N2.5 回归：前端 Vitest `55 files / 220 tests passed`，后端非集成 `2155 passed`；type-check、生产 build、ruff、迁移 head `20260824_0061` 和 `git diff --check` 已通过。N2.5 新增外部缺陷映射、创建、状态同步、脱敏和查看者只读边界。
- 2026-08-24 文档跟踪规则：代码完成但未联调必须标记“已实现，待环境验收”；每阶段先审查和回归，再同步 `Task.md`、`MEMORY.md` 与路线文档；旧 URL 和已有 API 保持兼容。
- 2026-08-24 导航路线跟踪：主计划为 `docs/product-navigation-roadmap-2026-08-24.md`；N1/N2.1/N2.2/N2.3/N2.4/N2.5/N3.1/N3.2/N3.3/N3.4/N4.1/N4.2/N4.3/N4.4/N5.1 已进入环境验收，当前下一入口为 N5.2 配置中心。单模块必须完成实现、测试、代码审查、问题修复、文档/记忆同步后才可提交推送；不得把工作区中的半成品标记为完成。
- 2026-08-24 N1 验收边界：本地证据已齐，但仍需真实数据库和项目角色、Android Worker/ADB、性能节点环境验证聚合数据和操作权限；完成环境验收后再把 N1 从 `[E]` 改为 `[x]`。

- 2026-08-17 GitHub Actions 第一轮修复后继续发现并处理 Bandit 的 3 处 XML 告警、独立测试 `test_mobile_special_events.py` 的模型注册隔离问题，以及 Worker Trivy 对 k6/JMeter 上游组件的漏洞命中。JMeter 漏洞已清零；k6 镜像仍使用 Go `1.26.5`，现改为固定 digest 的 Go `1.26.6` 构建并校验 k6 `v2.2.0` commit。第二轮远端 CI/Security 全部通过，第三轮仅因 k6 入口应为 `./cmd` 而非 `./cmd/k6` 构建失败，已修正。
- 2026-08-17 GitHub Actions 已调整为低频运行：主 CI/Security 每周日 UTC 02:00（北京时间 10:00）运行一次并保留手动 `workflow_dispatch`，不再由 push/PR 触发；integration、E2E、Release readiness 仍仅手动运行，Dependabot 继续每周检查。
- 2026-08-17 第 1/2/4 项推进完成代码与可执行环境收口：`172.31.27.133:/opt/atp-q18-acceptance-20260817` 隔离 Compose 栈使用 28080/28090/28092，Backend、Prometheus、performance Worker、Beat、PostgreSQL、Redis、MinIO 和目标服务健康，PromQL 的 Backend/Worker targets 均为 up；旧 q17 栈保持运行。
- 2026-08-17 备份验收发现 Worker 通用 `postgresql-client` 为 15.x、不能连接 PostgreSQL 16，已在 `backend/Dockerfile.worker` 固定安装 `postgresql-client-16` 并补契约测试；最终 `pg_dump 16.15` 日备份上传 MinIO，恢复到临时库验证 53 张 public 表后清理。证据：`docs/evidence/performance-linux-q18-acceptance-2026-08-17.json`。
- 2026-08-17 Helm 专用 performance Worker 增加默认关闭的 `performanceWorker.autoIdentity`；多副本开启时按 Pod hostname 生成节点 ID/名称和 `performance.<pod>` 队列，配合 metrics Service/ServiceMonitor 做节点级采集，Helm lint/template 通过。
- 2026-08-17 通知代码/API/验收脚本定向回归通过 45 项，部署/Compose/通知契约回归通过 28 项；真实 SMTP/企业微信/钉钉仍因当前数据库无配置、未提供临时外部目标而待现场验收，不能把本地回归当作送达证据。
- 2026-08-16 Kubernetes 前置审计：172.31.27.133 只有 Docker 容器栈，没有 kubectl/Helm/k3s/microk8s/minikube；本次仅只读检查，未安装或修改远端环境。Kubernetes、多节点和生产 Prometheus 仍待目标集群准备，证据为 `docs/evidence/kubernetes-readiness-audit-2026-08-16.json`。
- 2026-08-15 20:37 实时 Windows smoke 通过：后端/前端、登录、项目读取、PostgreSQL/Redis/MinIO readiness、47 bytes 文件上传与清理均通过；本次跳过 Playwright、浏览器矩阵和报告导出，Android 仍无授权在线设备。脱敏证据为 `docs/evidence/windows-smoke-live-2026-08-15-2037.json`。
- 本轮质量门禁重新通过：后端非集成 `2082 passed`，前端 `50 files / 209 tests passed`，type-check 与生产 build 通过。
- 远端 PostgreSQL/Redis/MinIO 恢复监听后，Windows API/Web smoke 重新通过：依赖 readiness、登录、项目读取、浏览器矩阵、47 bytes 文件上传和清理均通过；脱敏证据为 `docs/evidence/windows-smoke-current-2026-08-15.json`，Android 仍只有无设备 warning。

## 2026-08-15 Windows/远端依赖与性能环境复核

- Windows Android Worker doctor 通过；从 Windows 到 `172.31.27.133` 的 PostgreSQL `5432`、Redis `6379`、MinIO `9000` 可达，实时依赖 API 也返回 `ok`。本次只记录状态，不保存地址以外的凭据。
- Windows local smoke 通过后端健康、登录、用户/项目读取、Web Worker 状态、MinIO 文件上传清理和 Chromium 登录矩阵；Android 设备检查因 `adb devices -l` 没有在线设备而保持 warning/blocked。
- `scripts/windows-local-smoke.ps1` 新增显式 Android 低代码验收：`-AndroidCaseId` 校验 `active/approved`、自动化状态、`config.steps` 和设备绑定后触发 `/cases/{id}/run` 并轮询终态；`-RequireAndroidEvidence` 要求步骤截图或 Android 附件。未传 ID 时保持跳过，未连接设备不计为通过。
- Android Worker 低代码验收在 `ADB_SCAN_MODE=worker` 下会先要求 Worker 注册和设备扫描均通过，前置失败直接阻断，不创建待执行 Run。
- 性能 readiness 通过 ATP API、k6/Locust/gRPC 执行器、专用队列 `performance.worker-local`、目标 allowlist 和 Prometheus readiness/query；节点 `perf-node-local-01` 已在线。
- 真实低流量 Locust smoke run `1` 完成 957 次请求、错误率 0，产生 2 条 `performance-worker` 采样；run `2` 取消链路验证通过并进入 `cancelled`。
- Android Agent 已按当前远端配置重新注册，`/devices/workers` 返回 `android-win-HPS` online、队列 `mobile_special` 和 `adb/android` 能力；当前 ADB 无在线设备，不能把 Agent 在线当作设备执行通过。
- Android 无真机安全回归定向通过 `258 passed`；`windows-android-acceptance.ps1` 现在安全区分未连接、未授权和离线设备，并把状态计数写入脱敏报告；真实设备数据面仍待授权在线设备。
- 最新完整非集成后端回归为 `2082 passed`；发布 readiness 仓库检查通过，Docker Compose/Helm 工具缺失仅作为 `SKIP`，不能替代真实部署证据。
- 最新前端质量门禁为 `50 files / 209 tests passed`，type-check 和生产 build 通过；当前 ADB 仍无在线设备。
- `windows-android-worker.ps1` 在 doctor 前先调用 `Add-AtpOptionalToolPath`，因此使用 `ATP_ADB_HOME`、`ANDROID_HOME` 或 `ANDROID_SDK_ROOT` 时不要求修改系统 PATH；新增顺序回归。
- 根 `.env` 当前仍是 `ADB_SCAN_MODE=local` 的 Windows 全栈 Android 模式；公网后端+Windows Android Worker 验收必须使用单独的 `ADB_SCAN_MODE=worker` 配置，避免把后端本机 ADB 与 Worker 路由混用。
- 已补充受版本控制的 `config/deployment-profiles/android-worker-backend.env.example` 和说明文档：服务端模板使用 `ADB_SCAN_MODE=worker`、普通 Linux Worker 排除 `android,mobile_special`；Windows Agent 仍使用独立 `config/startup-profiles/android-agent.env` 并在本机用 ADB 执行。真实队列隔离和设备回调仍待授权在线设备验收。
- Helm 同步提供 `deploy/helm/atp/values-android-worker.example.yaml`，默认引用外部 `atp-runtime-secrets`，开启 `ADB_SCAN_MODE=worker` 并保持 Linux Worker 不消费 Android 队列；此前本机缺少 Helm，真实集群部署仍待验收。
- 后续补装 Helm `v4.2.4` 后，`helm lint deploy/helm/atp` 与 Android Worker overlay `helm template` 均通过；渲染结果确认 `ADB_SCAN_MODE=worker`、`mobile_special` 专用路由、普通 Worker 队列隔离和外部 Secret 引用。该证据不等同于真实 Kubernetes rollout。
- `scripts/validate-deployment-readiness.py` 现在会校验 Compose/Helm Android Worker 模板的扫描模式、开关、路由和队列隔离；本地 readiness 已通过仓库检查，Docker Compose/Helm 工具缺失仍按 SKIP 记录。

## 2026-08-15 Linux Docker 性能验收

- Linux MCP 已恢复连接 `172.31.27.133`；独立性能验收 Compose 栈的 PostgreSQL、Redis、MinIO、Backend、专用 Worker、Prometheus 和 HTTP/gRPC 目标健康。
- Locust run `1` 通过（36 次迭代、错误率 0），gRPC TLS run `2` 通过（5 次迭代、错误率 0），Locust run `3` 的取消链路从运行态进入 `cancelled`；脱敏证据已归档到 `docs/evidence/performance-linux-*-2026-08-15.json`。
- 该证据只覆盖 Linux Docker Compose 隔离栈，不代表 Kubernetes、多节点生产 Prometheus、外部通知、备份恢复或 Android 真机门禁已完成。

## 2026-08-15 Web Worker 控制面与备份恢复

- 修复 Web 录制控制面 Redis `BLPOP` 的读超时竞态：API 命令等待和 Worker 心跳等待均显式使用大于等待窗口的 `socket_timeout`；定向回归 `18 passed`。
- Windows Worker 模式真实录制 smoke 通过：Worker 注册/可用、Chromium 启动、2 个步骤、PNG 截图和停止录制均成功；脱敏证据为 `docs/evidence/web-recording-worker-local-2026-08-15.json`。
- Linux Docker 隔离栈的 PostgreSQL 备份/临时库恢复与 MinIO 临时对象镜像/恢复校验通过，临时资源已清理；证据为 `docs/evidence/backup-restore-linux-docker-2026-08-15.json`。
- 这些结果不替代 Kubernetes 多节点、生产 MinIO 生命周期/灾备策略、外部通知或 Android 真机验收。
- 远端 Linux acceptance 镜像具备 Xvfb/Playwright，临时 Web Worker 可注册但旧 API 镜像缺少当前 `/web-recordings/workers` 路由；临时进程已清理，不能作为当前版本 Linux/Xvfb 录制验收，证据为 `docs/evidence/web-recording-linux-remote-2026-08-15.json`。
- 当前仓库 `Dockerfile.worker` 已从 HEAD 完整构建成功；同一镜像的 Linux/Xvfb Chromium（17117 bytes）、Firefox（19076 bytes）和 WebKit（21192 bytes）录制通过，容量切换重试、无 Worker 503 拒绝以及副本 A 启动/副本 B 查询截图并停止的 Redis 路由也通过；临时资源已清理，证据为 `docs/evidence/web-recording-linux-current-2026-08-15.json`。当前 Windows 前端浏览器矩阵另有三浏览器 Trace/HAR、Console、失败请求和 HTTP 错误摘要证据 `docs/evidence/web-browser-trace-network-2026-08-15.json`。

## 2026-08-15 MinIO 生命周期部署契约

- 新增 `app.ops_minio_lifecycle` 显式运维命令；只有 `MINIO_LIFECYCLE_APPLY=true` 才会执行，且只替换 `atp-managed-*` 规则，保留其他系统的生命周期配置。
- Helm `storageLifecycle` hook 和 Docker Compose `storage-lifecycle` profile 默认关闭；默认只设置未完成 multipart upload 的清理，过期规则要求非空相对前缀。
- 生命周期解析/边界/规则合并与部署契约回归 `23 passed`；生产 bucket 规则、引用关系和保留周期仍需管理员确认后才能启用。
- 已对 `172.31.27.133` 的 `atp` bucket 做只读审计：当前无 lifecycle 规则，版本控制/对象锁/复制未启用；数据库仍有截图、报告、APK、脚本保留策略和对象引用，证据见 `docs/evidence/minio-lifecycle-audit-2026-08-15.json`。

## 2026-08-15 外部通知验收前置检查

- 目标 `atp` 数据库当前没有通知配置，也没有通知投递记录；SMTP/企业微信/钉钉真实投递无法在无测试目标和凭据时验收，证据见 `docs/evidence/notification-readiness-audit-2026-08-15.json`。

## 2026-08-14 通知 Webhook 查询参数脱敏

- `_safe_delivery_error` 新增 URL 查询参数脱敏，覆盖企业微信 `key`、钉钉 `access_token/sign` 以及常见 `api_key`、`token`、`secret`、`authorization`、`cookie` 参数；服务端日志、`NotificationDelivery.error_message` 和测试发送 API 错误共用该处理。
- `scripts/notification-channel-smoke.py` 的 `_safe_error` 同步覆盖 Webhook 查询参数，避免验收终端输出和 JSON 报告泄露凭据。
- 新增企业微信 `?key=...` 回归断言；通知服务与验收脚本定向测试 `23 passed`，Ruff check/format 和 `git diff --check` 通过。
- 真实供应商投递、消息到达和密钥轮换仍待目标环境验收，不能以本地测试替代。

## 2026-08-14 项目成员 owner 权限完整性

- 项目成员角色更新现在会锁定当前项目的 owner 行；如果目标成员是最后一个 owner 且被降级，API 返回 400 并保持原角色，避免项目失去可管理者。
- 本轮项目路由定向回归 `25 passed`，完整非集成后端 `2030 passed`，Ruff format/check 通过；前端全量 `50 files / 207 tests passed`，type-check/build 通过。

## 2026-08-13 性能压测停止竞态与自动阶梯边界

- `stop_performance_run` 读取父运行和分片时使用 `with_for_update=True`，把状态检查、取消信号和状态写回串在同一事务中，避免并发完成更新覆盖取消状态。
- Worker 执行器返回后再次检查取消标记；如果停止请求发生在执行器刚完成之后，最终状态落为 `cancelled`，不会错误落为成功。自动阶梯对 `max_vus=Infinity` 等溢出值返回配置错误。
- 本轮性能 API/Worker/自动阶梯定向回归 `87 passed`，完整非集成后端 `2029 passed`，Ruff format/check 通过。
- Linux MCP 对 `172.31.27.133` 的只读检查仍为 `Transport closed`，没有新增真实性能环境验收证据。

## 2026-08-13 性能压测时长边界防绕过

- `performance._parse_duration_seconds` 现在拒绝布尔值、负数和非有限浮点数；性能 API 额外校验顶层与分阶段时长字段。
- 这样不会因为 `NaN/Infinity` 与上限比较结果为 false 而绕过最大运行时长；定向回归 `69 passed`，完整非集成后端 `2027 passed`。
- Linux MCP 对 `172.31.27.133` 的只读检查仍为 `Transport closed`，没有新增远端验收证据。

## 2026-08-13 通知策略异常范围安全隔离

- `notifier.validate_notification_channel_config` 现在校验通知范围、状态筛选和套件/计划目标 ID 列表；未知策略在保存时返回 422。
- `should_send_notification` 对历史或手工写入的未知 `scope` 采用 fail-closed，避免错误配置扩大通知范围；相关服务/API 回归 `35 passed`，完整非集成后端 `2026 passed`。

## 2026-08-13 API Cookie 属性安全恢复

- `apply_cookies` 现在通过 `http.cookiejar.Cookie` 恢复 domain/path/secure/expires，避免恢复项目登录态时丢失安全标记和过期时间。
- API 会话测试已覆盖安全 Cookie 属性、空会话覆盖旧值和旧密钥无效密文降级为空。

## 2026-08-13 API 登录态清理闭环

- `save_project_api_session` 不再跳过空 Cookie；服务端登出后会加密保存空列表并覆盖项目旧会话，后续复用用例不会继续带旧 Cookie。
- `backend/tests/services/test_api_session.py` 已覆盖“保存有效会话后清空”的回归。
- 本轮 API 会话/HTTP 家族定向 `70 passed`，完整非集成后端回归 `2023 passed`。

## 2026-08-13 通用用例数据集配置隔离

- `CaseFormDrawer.vue` 的通用协议配置只有在 `dataset_id` 存在时才写入 `dataset_*` 字段；清空绑定后不会把旧参数化策略或准备 Hook 残留到用例配置。
- 新增 `test_generic_case_drawer_drops_dataset_execution_config_when_unbound` 静态回归。

## 2026-08-13 启动依赖诊断原因展示

- 启动配置页依赖检查现在显示 `ok/timeout/unreachable/bucket_missing` 的本地化原因，用户能直接区分连接超时、服务不可达和 MinIO 桶缺失。
- 本轮前端全量 `50 files / 207 tests passed`，type-check、生产 build 和 `git diff --check` 通过。
- 对 `172.31.27.133` 的只读检查：Windows 到 PostgreSQL `5432` 可达，Redis `6379`、MinIO `9000` 不可达；Linux MCP 仍为 `Transport closed`，未形成远端验收证据。

## 2026-08-13 数据集绑定异步请求隔离

- `CaseDatasetBinding.vue` 在项目或数据集被清空时会立即结束对应 loading，并清空旧选项；旧请求返回不会覆盖新的请求序列。
- 新增 2 个前端回归用例，验证项目切换和数据集解绑期间不会留下卡住的 loading 状态。
- 本轮证据：前端 `50 files / 207 tests passed`，type-check、生产 build 和 `git diff --check` 通过。

## 2026-08-13 通用用例数据集版本固定

- `CaseFormDrawer.vue` 已补 `dataset_version` 选择、版本列表加载和失效版本清理；创建/编辑会将版本传给 Case API。
- 未固定版本时保持 `null`，Worker 按后端逻辑解析当前最新版本；切换或清空数据集不会遗留旧版本号。
- 回归证据更新为后端非集成 `2022 passed`、前端 `49 files / 205 tests passed`，type-check/build 通过。

## 2026-08-13 Web/Android 数据集绑定

- WebCaseDrawer 和 AndroidCaseDrawer 现在共用 `CaseDatasetBinding.vue`，支持按项目选择数据集、固定版本、严格 Schema、组合策略、最大迭代数、随机种子和脱敏字段。
- 创建/编辑都会传递 `dataset_id`、`dataset_version`；清空数据集时不保留旧版本或旧参数化配置，避免 Worker 继续按已解除的绑定执行。
- 回归证据：前端 `49 files / 205 tests passed`，type-check 和生产 build 通过；真实 Web/Android Worker 及目标环境数据集执行仍未验收。

## 2026-08-13 发布前部署校验

- 部署 readiness 校验新增 `--strict` 和 `make validate-deployment-readiness ARGS=--strict`；默认模式会显式报告环境缺失为 `SKIP`，严格模式才将缺失依赖判为失败，不能替代真实部署验收。
- 本次继续尝试配置 Linux 主机 `172.31.27.133` 的只读 MCP 检查仍返回 `Transport closed`；未取得远端系统或性能验收证据。

## 2026-08-13 Web/Android 入口一致性

- 通用 `CaseFormDrawer` 已移除 Web/Android 类型和占位提示；CaseList 的 Web/Android 创建/编辑统一走专用抽屉，避免保存进入不可配置页面。
- 本轮验证：后端非集成 `2021 passed`，前端 `49 files / 203 tests passed`，type-check/build 和 Ruff 通过。

## 2026-08-13 审计日志保留策略

- 新增 `AUDIT_LOG_CLEANUP_ENABLED`（默认 `false`）和 `AUDIT_LOG_RETENTION_DAYS`（默认 365，范围 1-3650）；审计数据未确认合规策略前不会自动清理。
- `cleanup_old_audit_logs` 已接入 maintenance 队列和 Beat 每日调度；过期记录删除与 `audit_log_cleanup` 审计事件同事务提交，失败会回滚。
- 启动配置 UI、`.env.example`、启动配置文档和用户手册已同步；清理任务、配置边界和 Celery 路由回归已补充。
- 生产归档、保留周期和合规访问策略仍待确认。

## 2026-08-13 审计日志时间范围查询

- 管理员审计日志 API 支持 `created_from` / `created_to` ISO-8601 起止时间，结束早于开始时返回 `422`；前端审计日志页已增加带时间范围选择器。
- 既有权限、项目/用户/动作筛选和分页保持兼容；新增 API 契约和前端回归，门禁更新为后端 `2018 passed`、`269` 个测试文件逐文件独立通过、前端 `47 files / 199 tests passed`。

## 2026-08-13 审计日志 CSV 导出

- 管理员审计日志页支持按当前项目、用户、动作和时间范围导出 CSV；页面默认限制 5000 条，服务端限制 10000 条，并复用同一权限/筛选边界。
- 导出使用 UTF-8 BOM，对以 `=`, `+`, `-`, `@` 开头的文本增加保护前缀，降低表格软件公式注入风险；已补充 API 契约、权限/边界和前端下载回归。
- 成功导出写入 `audit_log_export` 审计事件，使用 JSON 编码记录操作者、筛选摘要、上限和导出条数，不写入日志正文、敏感信息或未转义控制字符；生产导出审批、归档和进一步脱敏仍待确认。
- 审计页面动作筛选已补齐 `audit_log_cleanup` / `audit_log_export`，可直接定位自动清理与人工导出行为。
- 最新完整门禁更新为后端 `2018 passed`、覆盖率 `82.03%`（门禁 82%）、`269` 个测试文件逐文件独立通过、前端 `47 files / 199 tests passed`，type-check/build、Ruff、format-check 和 mypy 通过；生产导出审批、留痕、归档和进一步脱敏仍待确认。

## 2026-08-13 存储治理自定义前缀

- `preview_storage_cleanup` 返回的自定义 StoragePolicy 前缀现在由 API、StorageManagementView 和 `cleanup_expired_files` 透传到 `execute_storage_cleanup`，执行阶段不会只扫描默认前缀而误报对象缺失。
- 新增自定义前缀删除回归；存储 API/服务/维护任务定向测试 `29 passed`，Ruff 通过。

## 2026-08-13 项目级运行记录清理范围

- 全局运行记录预览会排除设置了 retention override 的项目；RunRetentionView 现在主预览同时加载项目级预览，确认按钮的记录数量、对象估算和抽样提示覆盖完整执行范围。
- 修复了“只有项目覆盖策略命中时清理按钮置灰”的问题；页面回归 `2 passed`，type-check/build 通过。

## 2026-08-13 性能节点删除并发保护

- `DELETE /api/v1/performance/nodes/{node_id}` 现在使用 `with_for_update=True` 锁定节点行，再检查活动运行和启用的定时任务；与派发路径的节点锁保持一致，避免并发创建运行后被外键 `ON DELETE SET NULL` 脱离节点。
- 性能 API 定向回归 `68 passed`，Ruff 通过。

## 2026-08-13 启动配置依赖检查

- `GET /api/v1/health/dependencies` 并行检查当前 Backend 的 PostgreSQL、Redis、MinIO；只返回 `ok/degraded`、耗时和 `timeout/unreachable/bucket_missing` 等通用码，不返回敏感配置或异常原文。
- 依赖诊断路由只允许管理员；公开 `/health` 继续作为轻量存活检查，避免匿名请求触发 Redis/MinIO/数据库连接。
- StartupConfigView 的“检测当前连接”按钮调用该接口，适合区分“字段已填”与“服务实际可达”；当前 172 环境实测 PostgreSQL 可用、Redis/MinIO 不可达。
- 重启 Backend 后运行态验证：未认证请求返回 `401`，管理员 Windows 冒烟可以读取脱敏状态；该冒烟因 Redis/MinIO 不可达按预期失败。
- 后端定向回归 `4 passed`，前端 StartupConfigView `6 passed`。
- 最新完整门禁为后端 `2018 passed`，覆盖率 `82.03%`（门禁 82%），`269` 个测试文件逐文件独立通过，前端 `47 files / 199 tests passed`，type-check/build、Ruff、format-check 和 mypy 通过。

## 2026-08-13 发布前质量门禁复核

- Python 3.12.11 下完整后端回归、覆盖率、逐文件隔离扫描、Ruff、格式检查、mypy 和 pre-commit 全量通过。
- Python 3.14.3 条件依赖环境下完整非集成后端回归同样为 `2018 passed`；覆盖率门禁仍以 Python 3.12.11 为准。
- Bandit、npm audit、pip-audit（锁定 requirements 的 `--disable-pip --no-deps` 模式）未发现已知安全问题；部署配置校验通过。
- 当前 Windows 未安装 Docker Compose/Helm，因此相关真实工具检查按约定跳过，不代表 Linux/Kubernetes 集群已经验收。

## 2026-08-13 Windows 冒烟依赖检查

- `scripts/windows-local-smoke.ps1` 登录后调用 `/api/v1/health/dependencies`，对 PostgreSQL、Redis、MinIO 分项记账；整体 `degraded` 会在后续文件/Worker 检查前明确失败。
- 报告只保存 `status/code/latency_ms`，不把连接地址、账号、密码或异常原文写入证据。

## 2026-08-13 Windows Mock E2E 选择器

- 选择 Ant Design 项目下拉项时应限定 `.ant-select-dropdown .ant-select-item-option`，避免已选值和下拉选项同名造成 Playwright strict mode 冲突；页面目标文本与项目名称分开传递。
- 修复后 Chromium Mock E2E 全量 `10 passed`。

## 2026-08-13 Windows 启动档案与冒烟超时

- 远端基础设施档案下，登录可能因 PostgreSQL 公网/跨网延迟超过 10 秒；Windows 冒烟脚本使用 `-LiveRequestTimeoutSeconds`（默认 30 秒，5-300 秒）覆盖认证、认证读接口和 Web Worker 状态检查，避免固定超时误报。
- 当前根 `.env` 已切换到 `172.31.27.133`；重启后登录、`/auth/me`、项目列表和 `/web-recordings/workers` 通过，但 Redis `6379` 和 MinIO `9000` 从 Windows 不可达，仍需远端服务/防火墙验收。

## 2026-08-13 仪表盘 iOS 类型筛选

- 仪表盘 `caseTypeOptions` 必须包含 `ios`，否则后端已有的 iOS 用例执行数据无法通过类型筛选查看。
- 新增筛选项回归测试；前端全量回归 `46 files / 194 tests passed`，type-check/build 和 `git diff --check` 通过。

## 2026-08-13 性能节点删除保护

- 删除性能节点前必须确认没有 `pending/running/cancelling` 运行，也没有启用的定时任务绑定；否则返回 `409`，避免运行因外键 `SET NULL` 失去节点约束或定时任务静默回退到共享队列。
- 无活动引用时仍允许删除，已完成运行记录保留；后端定向回归 `68 passed`，完整非集成回归 `2008 passed`、覆盖率 `82.12%`，前端全量回归 `46 files / 193 tests passed`。

## 2026-08-13 通知渠道配置校验补强

- `validate_notification_channel_config` 在 API 新建/切换渠道和统一发送入口执行：email 必须有非空收件人列表，WeCom/DingTalk 必须有非空 `webhook_url`，`******` 不能作为新凭据。
- 发送入口先校验再重试/调用 provider，避免空配置产生虚假的 `sent` 投递历史；仅修改旧配置的名称或启用状态不强制重写历史无效配置。
- API/服务定向测试 `32 passed`；NotificationList `5 passed`，全量前端 `46 files / 192 tests passed`，type-check/build 通过。
- 通知页面测试发送完成或失败后会自动刷新最近投递历史，避免结果写入后页面仍显示旧数据。

## 2026-08-13 运行记录清理预览刷新

- `RunRetentionView` 执行清理后同时刷新全局和项目级预览，页面不会继续显示清理前的项目数量。
- 新增 `RunRetentionView.spec.ts` 回归；全量前端 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 运行记录清理对象安全顺序

- `app.services.run_retention._batched_delete_runs` 现在先提交运行记录删除，再清理关联 MinIO 对象；数据库提交失败时不会删除对象，避免不可恢复的引用丢失。
- 对象删除失败会保留为可治理的孤儿对象；服务定向回归 `10 passed`，后端全量 `2005 passed`、覆盖率门禁 `82.10%`。

## 2026-08-13 运行记录清理对象数语义补强

- `preview_old_runs` 和按项目全局预览新增 `estimated_objects_sampled`；当候选 TestRun 或 MobileRun 超过 `batch_size` 时为 `true`，明确对象数只统计首批候选记录。
- RunRetentionView 在全局/按项目预览和确认提示中展示抽样提示；不会为了预览强行加载全部附件引用，避免大数据量下预览拖慢数据库和 MinIO。
- 后端完整非集成回归 `2005 passed`、覆盖率门禁 `82.10%`；前端 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 按项目清理预览补全

- `preview_old_runs_by_project` 现在为每个 retention override 项目返回 TestRun/MobileRun 数量、对象估算和 `estimated_objects_sampled`，不再只展示 Plan/Suite。
- RunRetentionView 的按项目表格已展示四类运行记录和对象数；项目级对象统计沿用首批抽样边界，抽样时显示明确提示。

## 2026-08-13 按项目预览 API 契约收口

- `/admin/runs/retention/per-project-preview` 现在启用 `RunRetentionPerProjectOut` 响应模型；`global_` 通过 Pydantic alias 映射为 JSON 的 `global`，与前端类型一致。
- API 回归验证项目 TestRun 数量、对象估算和抽样标记不会因响应模型丢失或字段命名不一致。

## 2026-08-13 通知配置响应脱敏补强

- 通知配置新建/更新接口不再直接返回 ORM 对象，统一通过 `_mask_notification` 返回；数据库仍保存 Fernet 密文，客户端只看到 `******`，与列表/详情行为一致。
- 回归覆盖响应脱敏和底层密文仍被保留；`backend/tests/api/test_notifications.py` 定向 `14 passed`。

## 2026-08-13 通知渠道真实环境验收入口

- 新增 `scripts/notification-channel-smoke.py`：读取 `ATP_TOKEN` 或 `ATP_USERNAME`/`ATP_PASSWORD`，调用 `POST /api/v1/notifications/{config_id}/test`，再轮询 `GET /api/v1/notifications/deliveries` 核对新投递记录。
- 脚本的 URL、错误文本和 JSON 报告均做脱敏处理，不接受 `--token`/`--password` 参数，也不导出环境变量；目标渠道真实可达性仍必须由外部环境证明。
- 操作手册为 `docs/notification-channel-acceptance.md`；验收报告建议放在 `docs/evidence/`，不要提交真实凭据或供应商密钥。

## 2026-08-13 通知服务测试隔离修复

- `backend/tests/services/test_notifier.py` 和 `test_notifier_report_email.py` 原先只有在完整测试套件中、被其他模块提前导入模型时才稳定；单独运行会在创建 `NotificationDelivery` 时找不到 `Project`/其他关系模型。
- 两个测试现在显式调用 `app.models.bootstrap.load_all_models()`，与应用启动的模型注册路径一致；services 独立扫描 `74 passed`，worker 独立扫描 `42 passed`。
- 当时 API 独立扫描 `90 passed`、其余目录和根测试 `61 passed`；随着后续审计和验收回归加入，当前非集成后端全量为 `2018 passed`，共 `269` 个测试文件逐文件通过。
- 新增通知验收脚本必须同时加入 Makefile、`.github/workflows/ci.yml` 和 `.pre-commit-config.yaml` 的 Ruff/格式清单，`test_quality_gate_consistency.py` 会校验三处一致。

## 2026-08-13 通知错误信息脱敏

- 通知发送失败路径统一使用 `_safe_exception_message`：重试日志、SMTP/企业微信/钉钉日志、`NotificationDelivery.error_message` 和测试发送 API 的 HTTP detail 都不会输出 URL 用户信息或 Token/Key/Secret/Password/签名/Cookie 值。
- 错误摘要还会清理 CR/LF/NUL，避免将供应商返回文本直接写成多行日志。

## 2026-08-13 通知历史清理审计

- 通知投递历史清理任务删除记录时写入 `notification_delivery_cleanup` / `notification_delivery` 审计事件，包含删除数量和保留天数；审计与删除在同一同步事务中提交，任一失败会回滚。

## 2026-08-13 通知投递记录写入容错

- `send_notifications` 和 `persist_notification_delivery` 现在把 ORM `add/add_all`、commit、rollback 放在同一异常边界内；投递历史写入失败不会覆盖原执行/测试发送结果。
- 新增写入异常回归；通知服务定向测试 `16 passed`。

## 2026-08-13 历史投递记录读取脱敏

- `GET /api/v1/notifications/deliveries` 读取 `error_message` 时再次调用统一脱敏函数，防止脱敏策略上线前的旧历史记录通过查询 API 暴露 Token 或换行日志内容。
- API/通知服务定向测试更新为 `30 passed`。

## 2026-08-13 覆盖率门禁复核

- 后端非集成覆盖率门禁通过 `82.10%`（阈值 `82%`），同次回归 `2005 passed`；当前 notifier 覆盖率 `81%`，run_retention 覆盖率 `89%`，tasks_cleanup `79%`。
- 相关 API/通知服务回归 `36 passed`；完整非集成后端回归更新为 `1992 passed`。

## 2026-08-13 外部目标连接复核

- 已多次尝试对配置的 Linux 目标执行只读 MCP 系统概览，最近一次仍返回 `Transport closed`；未将本机结果写成 Linux/Kubernetes 外部验收证据，待连接恢复后继续。

## 2026-08-13 Web 录制 Worker 心跳容错

- `backend/app/web_recording_worker.py` 的初始注册和持续心跳现在同时捕获底层 Redis 客户端的普通异常；持续心跳失败会清理 `WEB_RECORDER_HEALTH_FILE` 并保留重试循环，避免异常退出后健康探针继续显示旧状态。
- 新增心跳异常和启动残留标记回归；Web 录制 API、Transport 和部署契约定向回归 `55 passed`，Ruff/格式检查通过。

## 2026-08-13 Web Worker 外部验收入口

- 新增 `scripts/web-recording-worker-smoke.py`：默认只验证 Worker 模式和可用容量；显式 `--run-recording` 后才执行一次真实录制启动、状态查询、可选截图和停止。
- 脚本只读取 `ATP_TOKEN` 或 `ATP_USERNAME`/`ATP_PASSWORD`，不接受命令行凭据，报告会脱敏 URL、错误和输入；已同步 Makefile、CI、pre-commit 和 Web Worker Runbook。
- 脚本契约与质量门禁一致性回归 `14 passed`；真实 Linux/Xvfb、Firefox/WebKit 和跨副本证据仍待目标环境。

## 2026-08-13 Linux/Kubernetes 性能栈完善（代码阶段完成）

- 修复手动、Webhook 和定时任务的性能节点容量分布式竞态：选择节点时使用 `with_for_update=True` 锁定节点行，直到运行记录提交，避免超卖 `max_concurrency`。
- 性能节点选择、队列派发、draining/心跳状态、容量限制和幂等触发回归已通过；定向性能回归 `91 passed`，完整非集成后端 `1988 passed`，前端 `45 files / 189 tests passed`。
- 手动压测和 Webhook 支持 `idempotency_key`；同键同请求复用已有 Run，同键不同请求返回 `409`，数据库唯一约束处理并发插入，PerformanceCenter 手动触发会生成并复用本次提交键。
- `scripts/performance-environment-smoke.py` 已接入幂等键：支持显式基值和 CI 运行号复用，smoke/cancel 自动分作用域；本地未指定时每次生成新键，避免验收网络重试重复创建 Run。
- 性能验收脚本新增 `--require-metric-source`，可分别核验 `performance-worker` 与 `target-service-prometheus` 的非空指标样本；只有错误或空 metrics 的样本不会通过来源校验。
- 性能验收脚本新增 `--require-baseline`/`--fail-on-baseline-regression`，可验证基线对比响应并在核心指标回归时失败；未设置基线时不会静默降级为通过。
- 真实 Linux/Kubernetes 专用 Worker、Prometheus、TLS、目标服务和资源采样仍需目标环境验收，不能用本地测试替代。

## 2026-08-13 通知渠道可靠性收口

- `backend/app/services/notifier.py` 新增统一 `send_notification_channel` 发送入口；执行通知和“测试发送”都复用同一有限重试策略。
- 通知配置支持 `retry_attempts`（0-3，默认 0）和 `retry_backoff_seconds`（0-30，默认 1）；只对网络超时/连接失败、HTTP 5xx、429 重试，供应商拒绝和配置错误不重试。
- 前端通知配置页增加重试参数和中英文说明；后端对历史/不可信 JSON 配置做边界裁剪，不新增数据库字段或迁移。
- NotificationList 页面回归 `4 passed`；完整非集成后端 `1988 passed`；真实 SMTP、企业微信、钉钉公网联调仍待目标环境。

## 2026-08-13 通知投递结果可观测性

- 新增 `NotificationDelivery` / `notification_deliveries`，保存项目、可选通知配置、渠道、`sent/failed`、实际尝试次数、非敏感摘要和脱敏错误；配置删除后历史记录仍保留。
- `send_notifications` 和通知测试发送都会记录投递结果；新增 `GET /api/v1/notifications/deliveries`，按项目、配置、状态和数量查询，仍使用工程师权限和项目可见范围。
- 通知配置页增加最近 20 条投递记录，展示渠道、状态、尝试次数、时间和失败原因；新增迁移 `20260813_0057`。
- 相关服务/API/迁移回归 `29 passed`，NotificationList 页面 `4 passed`；真实供应商返回码、重复投递与历史保留周期仍待环境验收。

## 2026-08-13 通知投递历史保留策略

- 新增 `NOTIFICATION_DELIVERY_CLEANUP_ENABLED`（默认 true）和 `NOTIFICATION_DELIVERY_RETENTION_DAYS`（默认 30，范围 1-3650）。
- `cleanup_old_notification_deliveries` 已接入 maintenance 队列和 Beat 每日调度，按 `created_at` 删除过期 `notification_deliveries`；关闭开关会直接返回，不建立数据库连接。
- 当时启动配置 UI 字段数为 119；随后新增审计日志保留配置，当前字段数已更新为 121，相关文档和回归均已同步。
- 生产环境需结合合规要求选择保留周期或关闭自动清理后做数据库归档。

## 2026-08-12 本轮开发收口

- 完成 Mock 条件匹配与多规则确定性优先级；数据集准备动作增加公网 URL/DNS 安全校验，显式拒绝非数组配置。
- 完成 MinIO 数据集元数据响应、存储表格行模型和项目导入导出存储模式支持；大数据集按 50MB 校验并在导入失败时清理已上传对象。
- 最终验证：非集成后端 `1967 passed`；前端 `45 files / 188 tests passed`；type-check、build、Ruff、格式检查和 `git diff --check` 通过。

## 2026-08-12 Mock 条件响应增强

- `MockMatchConditions` 现在支持历史精确值以及 `$exists`、`$contains`、`$in` 三种受控操作符，Query/Header/Body 均可使用；条件组最多 50 个字段，`$in` 最多 20 个标量值。
- 未知操作符、多个操作符、复杂嵌套值和超长 `$contains` 会在创建/编辑/导入边界拒绝；运行时对遗留异常 JSON 安全返回不匹配，不执行表达式或正则。
- 多条规则命中时按 HTTP 方法精确匹配、路径静态段、占位符数量、条件字段数量、规则 ID 的顺序确定优先级；规则变更继续复用项目级缓存失效，避免旧通用规则抢先命中。
- 数据集准备请求现在使用 `validate_public_http_url` 在请求前解析并限制公网 HTTP(S) 地址，拒绝本机/内网/链路本地/保留地址；非列表动作配置会失败而不是空跑。
- MinIO 数据集元数据更新会回读当前对象并在响应中返回 rows；存储治理页面把孤儿对象名称映射为 `object_name` 行，避免表格显示空白。
- Mock 页面类型、操作符说明和中英文提示已同步；Mock 服务、规则 API、回归测试定向 `34 passed`，完整非集成后端 `1967 passed`，前端 Mock 页面 `5 passed`、全量前端 `45 files / 188 tests passed`、type-check/build、Ruff 与差异检查通过。

## 2026-08-12 存储容量告警入口

- `StorageManagementView` 已接入既有 `storageApi.getAlert()`，在容量正常/告警状态条中展示当前占用 GB、阈值和触发时间，支持单独刷新。
- 告警 API 失败只显示错误提示，不影响统计、清理策略、数据集对象核对和孤儿清理；新增中英文文案和页面回归。
- 存储页面定向测试 `8 passed`，前端全量 `45 files / 185 tests passed`，type-check 通过；Android 真机仍按当前安排暂缓。

## 2026-08-12 测试套件并行会话隔离

- `backend/app/worker/tasks.py` 的并行套件现在为每个子用例创建独立 `AsyncSession`，修复多个并发用例共享数据库会话可能导致的事务交叉；顺序套件仍沿用父会话。
- 套件配置/执行链回归 `43 passed`，Ruff 通过；Android 真机连接仍暂缓。

## 2026-08-12 API 登录态复用与并行套件边界

- `backend/app/api/v1/suites.py` 创建/编辑套件时检查 API 用例的 `session_lifecycle`；并行套件拒绝开启项目 Cookie 登录态复用的用例，串行套件仍允许按用例选择复用。
- `frontend/src/views/suite/SuiteList.vue` 保存失败会显示 Axios/FastAPI 返回的具体 `detail`；后端套件校验 `20 passed`、SuiteList `6 passed`、type-check/Ruff 通过。

## 2026-08-12 MinIO 数据集对象生命周期治理

- `backend/app/services/dataset_storage.py` 新增项目范围对象核对：扫描 `datasets/{project_id}/`，比较 MinIO 清单与数据库保存的当前/版本对象引用；默认 dry-run，`purge=True` 才删除孤儿对象。
- `POST /api/v1/projects/{project_id}/datasets/storage/reconcile` 仅管理员可调用；响应包含扫描、引用、孤儿、删除、截断和逐项错误信息，删除失败不会影响仍被引用的对象。
- MinIO 更新/上传/回滚在已有当前对象时使用唯一的新对象名，数据库提交成功后才清理旧引用；快照或提交失败会清理本次新对象，保留旧对象可读。
- 每次核对/清理写入 `dataset_storage_reconcile` 审计事件；对象名严格限制在当前项目前缀内，不暴露对象内容或凭据。真实 MinIO 备份恢复、提交失败补偿和定期治理任务仍待环境验收。
- 本轮对象服务/API 回归已通过 `33 passed`；完整后端 `1944 passed`、独立扫描 `264 passed, 0 failed`、前端 `45 files / 183 tests passed`、type-check/build 通过。

## 2026-08-12 执行记录清理预览一致性

- `backend/app/services/run_retention.py` 的 `preview_old_runs` 支持 `project_id` / `exclude_project_ids`，通过与实际删除相同的四类运行 ID 查询生成统计。
- `preview_old_runs_by_project` 的全局统计会排除所有 retention override 项目；因此项目级统计和全局兜底不会重复，前端提示已同步。
- 执行完成结果中的 `projects` 明细现在在 `RunRetentionView.vue` 展示各项目四类运行记录和已删除对象数，便于核对实际清理结果。
- 定向服务/API 回归 `18 passed`；真实生产保留策略仍需结合备份、审计和发布 Runbook 验收。

## 2026-08-12 性能 Run 通知闭环

- `backend/app/worker/tasks_performance.py` 新增统一的提前终止收口 helper；测试定义缺失、执行器未启用、节点不匹配/不可用/不支持执行器、容量不足和启动前取消，都会在落库后进入 `_notify_performance_run`。
- 性能通知仍由项目级 `NotificationConfig` 按 `scope`/`status_filters` 过滤；正文现在按中英文展示 RPS、P95/P99、错误率、阈值状态和触发原因。通知失败只记录 Worker 日志，不影响 Run 已保存的终态。缺失测试和启动前取消已补通知回归。
- 性能 Worker/通知定向回归 `14 passed`；外部 SMTP、企业微信、钉钉真实渠道联调仍需目标环境验收。

## 2026-08-12 Q18 发布就绪清单补强

- `docs/q9-release-checklist.md` 已升级为 Q18 扩展版：覆盖率门禁同步为 82%，并加入 MinIO reconciliation、run retention、性能通知、Windows Android、Linux/Kubernetes 性能、Web/iOS 外部验收要求。
- `docs/q9-release-evidence.md` 增加本地门禁快照（后端 `1944 passed`、独立 `264 passed`、前端 `45 files / 183 tests`）和外部证据清单；这些结果不替代真实目标环境验收。
- 发布/灾备文档契约回归 `23 passed`；真实 staging、备份恢复和外部 Worker/通知渠道仍未关闭。

## 2026-08-12 运行级数据准备 Hook

- 新增 `backend/app/services/dataset_preparation.py`，以受限 DSL 执行数据准备：`set_variable`、`delete_variable`、`assert` 和 HTTP `request`；request 支持变量渲染、JSON/raw body、状态/响应断言以及 `post_actions` 提取变量，限制最多 20 个动作、单请求 60 秒、响应 1MB，拒绝 Python/JavaScript。
- `backend/app/worker/tasks.py` 的参数化执行会在创建 child run 前执行一次 `config.dataset_prepare_actions`。准备结果只作用于本次运行，提取变量共享给所有行，行数据覆盖同名变量；失败会停止创建 child run，并把无请求体的摘要写入 parent `result_summary`。
- CaseFormDrawer 已在关联数据集的 API 用例配置中提供 JSON 入口；操作说明已同步到 `docs/dataset-v2.md` 与 `docs/user-operation-manual.md`。服务/Worker 定向回归 `16 passed`；真实 seed 服务、MinIO 集群大数据量和对象生命周期仍需环境验收。
- 发现并修复 MinIO 上传/预览入口误用数据库 500 行限制的问题；现在按数据集当前存储模式校验，501 行 MinIO 上传与预览回归已通过。

## 2026-08-12 后续开发路线同步

- 后续开发顺序已统一记录到 `docs/next-development-plan-2026-08-12.md`：Windows 真实 Android 设备验收 → Linux/Kubernetes 性能栈 → Web 专用 Worker → macOS/iOS/Appium → 产品化收口。
- 当前先实现 Windows ADB 设备验收入口；`scripts/windows-android-acceptance.ps1` 已通过脚本契约和 PowerShell 解析检查。本机实际执行因无授权在线设备而失败，不能把 Worker 在线、API 健康或旧设备列表当成 Android 真机验收证据。
- Linux/Kubernetes 性能栈下一步已补充 Prometheus readiness/PromQL 验收入口：`scripts/performance-environment-smoke.py --prometheus-url ...` 会验证 `/-/ready` 和 `/api/v1/query`，拒绝带凭据或查询参数的 Prometheus URL；真实集群证据仍需目标环境产生。
- Web 专用 Worker 已补充 `WEB_RECORDER_HEALTH_FILE`：只有 Redis 注册/心跳成功才更新时间，Compose/Helm 探针据此判断录制 Worker 是否真正可用；Docker 容器和 Linux/Xvfb 跨副本仍需目标环境验收。
- `frontend/tools/browser-matrix-smoke.mjs` 已支持显式 artifact 目录，按浏览器输出 Trace/HAR、Console、失败请求和 HTTP 错误摘要；报告 URL 去除查询参数，默认仍只输出轻量 JSON。
- Windows 本机三浏览器矩阵真实通过，汇总证据为 `docs/evidence/web-browser-matrix-local-smoke-2026-08-12.json`；Linux/Xvfb Worker 和跨副本路由仍未宣称完成。
- iOS/Appium 已新增 `scripts/ios-appium-acceptance.py` 与 `docs/ios-appium-acceptance.md`：默认只验 Appium `/status`，`--session-smoke` 才创建/销毁 XCUITest 会话，可选执行步骤并生成截图/录屏/syslog 哈希证据；相关脚本、Worker、路由、任务和租约回归共 `90 passed`，真实 macOS/Xcode/WDA/设备环境仍待验收。

## 2026-08-12 大型测试数据集 MinIO 引用模式

- 测试数据集现在支持 `database` / `minio`：数据库模式保持 500 行 / 256KB 限制，MinIO 模式允许最多 50MB JSON，数据库只保存对象引用和行数。
- `backend/app/services/dataset_storage.py` 是统一读写边界；用例参数化、性能数据集、AI 样例、项目导出和 Dataset Library CRUD/版本回滚均可解析 MinIO 引用。
- 项目导入导出快照新增 `storage_mode`；MinIO rows 可超过 500 行并按 50MB 对象上限传输，导入时上传到目标项目对象前缀，事务失败会按数据集前缀清理已上传对象。
- migration `20260812_0055_add_dataset_minio_storage.py` 已加入 `test_datasets` 与 `test_dataset_versions` 的存储元数据；真实 MinIO 大数据量、对象生命周期和数据准备 Hook 仍未验收。
- 本轮完整非集成后端回归 `1944 passed`，264 个测试文件独立运行 `264 passed, 0 failed`；前端全量 `45 files / 183 tests passed`，type-check/build 通过。

## 2026-08-12 Windows Android SDK/ADB 路径发现

- `scripts/windows-process-env.ps1` 的统一工具路径发现现在支持 `ATP_ADB_HOME`、`ANDROID_HOME`/`ANDROID_SDK_ROOT`、`%LOCALAPPDATA%\Android\Sdk\platform-tools` 和 `%LOCALAPPDATA%\ATP\tools\platform-tools`；路径只注入当前启动进程及子 Worker，不修改系统 PATH。
- `windows-local.ps1`、`windows-android-worker.ps1` 和 `android-network-doctor.ps1` 复用该逻辑；Android Worker 加载所选 `.env` 后会再次刷新路径，因此启动档案中的 SDK 路径会立即生效。
- Windows 合约回归 `12 passed`，PowerShell 解析通过。当前仍未连接在线 Android 设备，未宣称 Android 执行链路完成。

## 2026-08-12 性能目标指标 UI

- `frontend/src/views/system/PerformanceCenterView.vue` 现在提供目标服务指标配置区：可选择 Prometheus 直连 URL 或环境变量来源，填写 0.2-10 秒查询超时和多条 PromQL；保存时安全合并 `default_options.target_metrics`，关闭开关会移除旧配置。
- 压测详情的指标时间线增加来源选择器，按 `performance-worker`、`target-service-prometheus` 和其他来源筛选，并动态展示未知目标指标键名；不再把目标样本混入 Worker 资源指标图。
- 定向页面回归 `5 passed`；前端全量 `44 files / 180 tests passed`，`vue-tsc --noEmit` 与生产构建通过。浏览器抽查时当前会话已在登录页，未代填密码。

## 2026-08-12 Windows 本地 Prometheus 目标指标闭环

- 安装并校验官方 Prometheus Windows amd64 `v3.13.1` 到 `%LOCALAPPDATA%\ATP\tools\prometheus`，SHA-256 已按官方发布值校验；未修改系统 PATH。
- 新增 `config/prometheus/windows-local.yml` 和 `scripts/windows-prometheus.ps1`。脚本支持 `doctor/up/down/restart/status/logs`，只监听 `127.0.0.1:9090`，抓取本机 ATP Backend `/metrics`，数据目录位于用户工具目录而非仓库。
- Prometheus readiness=200，`atp-backend` scrape target 为 `up`；带 `target_metrics` 的 k6 run `11` 成功，20 次迭代、错误率 0、6 条指标采样，其中 3 条 `target-service-prometheus` 样本包含 `backend_up=1`、`request_count=20`、`slow_queries=3`，无采样错误。
- 证据见 [`docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json`](docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json)。这只证明 Windows 本机 Prometheus 与性能 run 的关联采集，不替代真实外部目标、Linux/Kubernetes 或生产 SLO 历史验收。
- 完整非集成后端回归 `1899 passed`；259 个测试文件独立扫描 `259 passed, 0 failed`。Linux MCP/SSH 目标仍不可连接，本地回归结果不作为远端环境证据。
- `scripts/windows-local-smoke.ps1` 新增 `-EnvFile`，doctor、登录、服务启停和 Web seed 都能使用实际运行档案；使用 `remote-infra.env` 的最新真实冒烟通过 10 项 Playwright、三浏览器矩阵、Web 下载对象验证和清理，证据见 [`windows-local-smoke-remote-infra-web-seed-2026-08-12.json`](docs/evidence/windows-local-smoke-remote-infra-web-seed-2026-08-12.json)。
- 未传 `-EnvFile` 时会读取 `.local-run/windows-local-runtime.json` 自动对齐当前档案；不传参数的轻量回归已通过。

## 2026-08-12 Windows k6 executable discovery

- Installed the official Windows `k6 v2.2.0` binary under `%LOCALAPPDATA%\ATP\tools\k6`. `scripts/windows-process-env.ps1` now discovers that directory, or an optional `ATP_K6_HOME`, and prepends it only to the current launcher process and its child Workers.
- `windows-local.ps1 doctor` now reports `Performance executor k6` as available even when the current PowerShell session was opened before the user PATH was updated. The machine PATH is not changed by the repository scripts.
- Standalone `k6.exe version` and the Windows doctor passed. This confirms binary discovery only; a real k6 target run still requires the external target environment.

## 2026-08-12 Windows 本地 k6/Locust 真实平台执行

- 使用本机 ATP `/health` 作为明确的本地目标，主 Worker 节点 `perf-node-local-01` 在线并声明 `k6,locust,grpc`；性能 Agent `performance-win-worker-a` 继续独立消费 `performance.worker-a`，只声明 `jmeter,grpc`。
- k6 测试定义 `7` 的真实 run `8` 成功：`20` 次迭代、错误率 `0`、资源指标 `3` 条，证据为 [`performance-windows-local-k6-smoke-2026-08-12.json`](docs/evidence/performance-windows-local-k6-smoke-2026-08-12.json)。
- Locust 测试定义 `8` 首次暴露 Windows `WinError 2`：Worker 使用裸 `locust` 命令时找不到虚拟环境脚本；已改为 `sys.executable -m locust`，重启 Worker 后真实 run `10` 成功，`168` 次请求、错误率 `0`，证据为 [`performance-windows-local-locust-smoke-2026-08-12.json`](docs/evidence/performance-windows-local-locust-smoke-2026-08-12.json)。
- 以上证明 Windows 本地节点的 k6/Locust 平台执行、队列投递、摘要回传和资源采样链路；本地 Prometheus 目标指标另有最新证据，不替代 Linux/Kubernetes、真实外部目标或 Android 设备验收。

## Windows Locust 依赖与运行态回退（2026-08-12）
- 停止本机 Backend、普通 Worker、Beat 和独立性能 Agent 后，补装 `locust 2.32.10` 及 Windows 依赖；临时工作目录执行 `python -m locust --version` 通过，Windows doctor 的 Locust 检查已变为通过。
- 恢复服务时发现根目录 `.env` 指向的 `172.31.27.133:5432` 仍在 PostgreSQL 握手阶段超时。为避免本机项目停机，当前 Backend/Worker/Beat/Frontend 使用已验收的 `config/startup-profiles/remote-infra.env`（163.192.40.209）运行；根目录 `.env` 未被改写。
- 独立性能 Agent 已按原 `performance-agent.env` 恢复在线；当前仍只声明 `jmeter,grpc`，Locust 已安装但未加入该专用节点能力列表。
- `scripts/windows-local.ps1 status` 现在读取脱敏的 `.local-run/windows-local-runtime.json`，显示实际运行档案、数据库/Redis/MinIO 主机和队列；停止服务时会清理该元数据，避免把当前运行态误看成另一个 `.env`。

## 外部基础设施文档去敏（2026-08-12）
- 清理 `docs/external-infra-run.md` 中旧公网地址、管理员账号和明文密码，改为 `.env`/启动档案占位符与安全部署说明。
- 文档现在明确：真实数据库、Redis、MinIO 和初始管理员凭据不得进入 Git；使用前必须替换占位符并执行启动预检。

## 启动配置档案移除环境特定用户名（2026-08-12）
- 启动配置页面的远端、Android Agent 和性能 Agent 档案不再预置某台服务器的 PostgreSQL/MinIO 用户名；统一使用 `<database-user>` 和 `<minio-user>` 占位符。
- `POSTGRES_HOST`、`POSTGRES_USER`、`MINIO_HOST`、`MINIO_ROOT_USER` 以及已有密钥示例值都会进入必填未完成列表，避免复制档案后误连旧环境。
- `StartupConfigView.spec.ts` 定向回归 `5 passed`，前端全量回归 `44 files / 178 tests passed`，类型检查通过；当前 Windows 根 `.env` 和被忽略的性能 Agent 实际配置不被改写。

## Windows 全量本地冒烟与数据源核对（2026-08-12）
- 根目录 `.env` 的 `local-all` 当前使用 `172.31.27.133`，Windows 全量本地冒烟通过：健康、管理员登录、认证读接口、项目列表、10 条 Playwright E2E、文件上传/清理和 HTML/JUnit 报告均通过。
- 证据：[`docs/evidence/windows-local-smoke-2026-08-12.json`](docs/evidence/windows-local-smoke-2026-08-12.json)。Android 设备、k6、Locust 和浏览器矩阵属于可选 warning/skip。
- 独立 `config/startup-profiles/performance-agent.env` 仍指向 `163.192.40.209`，不能直接视为当前 `172.31.27.133` 项目的性能 Agent；若切换使用，先同步地址与凭据，再重启并重新验收。

## Windows JMeter 执行链路修复与验收（2026-08-12）
- Windows 下 JMeter 使用 `jmeter.bat` 时会形成 `cmd.exe -> Java` 进程树；`backend/app/services/performance_process.py` 的 `_terminate_process` 现在在 Windows 使用 `taskkill /PID /T /F` 回收整棵树，避免取消/超时后 Java 继续占用临时日志文件。
- 回归测试位于 `backend/tests/services/test_performance_process.py`，覆盖 Windows 进程树分支以及 Unix graceful/force 分支；目标运行 `run=6` 在 `performance-win-worker-a` / `performance.worker-a` 上成功执行 JMeter，1 次请求、错误率 0、12 条资源样本无错误，临时目录已清理。
- 取消路径真实验收：run `7` 进入 `running` 后通过 Redis 控制信号停止，最终为 `cancelled`，JMeter 进程树和临时目录均已清理；证据见 [`docs/evidence/performance-windows-jmeter-cancel-2026-08-12.json`](docs/evidence/performance-windows-jmeter-cancel-2026-08-12.json)。
- JMeter/性能相关测试 `90 passed`，完整 Worker 测试 `427 passed`，非集成后端总回归 `1897 passed`，Ruff 与 `git diff --check` 通过。
- 证据：[`docs/evidence/performance-windows-jmeter-smoke-2026-08-12.json`](docs/evidence/performance-windows-jmeter-smoke-2026-08-12.json)。k6/Locust、外部目标、Prometheus/Kubernetes 和真实 Android 设备仍属于后续环境验收范围。

## Windows 性能 Agent gRPC 执行验收与指标修复（2026-08-12）
- 通过平台 API 创建临时 gRPC 性能定义，绑定 `performance-win-worker-a` 的 `performance.worker-a` 队列；本机目标 `127.0.0.1:50052` 完成 5 次 Unary 请求，`OK=5`、错误率为 0，临时测试定义、运行记录和 MinIO 对象已清理。
- 运行期间发现 Windows 环境未安装 psutil 时，系统采样器错误读取 Linux `/proc` 并产生 `system:FileNotFoundError`。现已增加 Windows 原生 `GetSystemTimes` 与 `GlobalMemoryStatusEx` fallback，Linux `/proc` fallback 保持不变；指标回归 `8 passed`，Ruff 通过。
- 证据文件：`docs/evidence/performance-windows-grpc-smoke-2026-08-12.json`。这证明 Windows 节点可真实消费 gRPC 任务并采集资源指标，不代表 k6/Locust、外部目标、Prometheus/Kubernetes 或 Android 已完成验收。
- 取消链路也已通过：运行中的 gRPC 任务调用 `/performance/runs/{id}/stop` 后最终状态为 `cancelled`，临时定义、运行记录和对象已清理；证据文件为 `docs/evidence/performance-windows-grpc-cancel-2026-08-12.json`。

## Windows 性能 Agent 运行验收（2026-08-12）
- 已从现有远程基础设施配置派生被 `.gitignore` 忽略的 `config/startup-profiles/performance-agent.env`，仅用于本机运行，不把凭据提交到仓库。
- `scripts/windows-performance-worker.ps1 doctor` 通过，PostgreSQL/Redis/MinIO 均可达；当前 Windows 环境可用 `grpc` 与 `jmeter`，因此节点只声明这两类执行器。
- 独立 Worker 已 ready，专用队列为 `performance.worker-a`；首次 `heartbeat_performance_node` 成功，数据库节点 `performance-win-worker-a` 状态为 `online`，能力为 `grpc,jmeter`。
- 这只证明节点注册/心跳和队列消费通路，不等同于真实压测结果；真实目标服务、k6 指标、Prometheus/Kubernetes 和 Android 设备仍需后续环境验收。**该次性能 Agent 验收使用** `163.192.40.209`，不能作为当前根 `.env` 数据源的结论。

## PostgreSQL 启动连接超时（2026-08-12）
- 发现远端 PostgreSQL `172.31.27.133:5432` TCP 可达，但 psycopg2 握手超时，导致 Backend 的同步 Alembic head 检查无限停在 `Waiting for application startup`。
- 已新增 PostgreSQL、Redis、MinIO 三类 `*_CONNECT_TIMEOUT_SECONDS`，默认 5 秒、允许 1-120 秒；asyncpg 使用 `timeout`，psycopg2 使用 `connect_timeout`，Redis/Celery 和 MinIO 客户端也使用统一配置，前端启动配置和四套 Windows profile 同步提供字段。
- 该修复只负责有界失败和明确诊断，不替代远端 PostgreSQL 防火墙、监听地址、认证或资源状态修复。当前 `remote-infra` 配置实际使用 `163.192.40.209`，已恢复并完成迁移；此前指定的 `172.31.27.133` 仍无法完成数据库握手，不能将两台主机混为同一数据源。
- 本机连接参数回归为 `2 passed`，核心目录回归为 `4 passed`，Ruff、Python 编译和配置档案覆盖检查通过；前端工具链最初因 Vite ESM 配置问题表现为无输出，修复后已补跑完整前端门禁。

## 前端工具链与性能目标回归（2026-08-12）
- 修复 `frontend/vite.config.ts` 在 ESM/runner 配置加载器下依赖未定义 `__dirname` 的问题，改用 `fileURLToPath(import.meta.url)`；默认 Vite 生产构建和 `vue-tsc --noEmit` 均通过。
- 性能验收目标的 gRPC smoke 测试增加 `wait_for_ready`，修复 Windows 慢机在 `server.start()` 后立即调用导致的启动竞态；定向测试通过。
- 完整非集成后端回归为 `1893 passed`，前端为 `44 files / 178 tests passed`；真实远端 PostgreSQL 仍握手超时，Linux MCP 仍传输层关闭。
- Vite 配置修复后的 Playwright E2E 为 `10 passed`，开发服务器和 mock 流程可正常启动；本机 WSL relay 端口仍无法完成 PostgreSQL 握手，未把运行态服务标记为恢复。

## 远程基础设施迁移与运行恢复（2026-08-12）
- **历史迁移记录**：`remote-infra` profile 曾连接 `163.192.40.209`；执行 `alembic upgrade head` 成功，从 `20260807_0053` 迁移到 `20260811_0054`。该记录不代表当前根 `.env` 的数据源。
- 重启后 Backend、Celery Worker、Beat、Frontend 均处于运行状态；Backend `/health` 与 `/openapi.json` 返回 200，未认证访问项目接口返回 401，前端 `/login` 返回 200。
- `172.31.27.133` 是此前指定的另一台目标主机，当前 PostgreSQL 握手仍超时；除非该主机恢复并重新确认配置，不得把当前 163 主机的运行证据当成 172 主机验收。

## Windows 性能 Agent 启动入口（2026-08-12）
- 新增 `scripts/windows-performance-worker.ps1` 与 `performance-agent` 启动档案。该模式只启动 Windows 性能 Worker，强制消费 `PERFORMANCE_NODE_QUEUE` 专用队列（例如 `performance.worker-a`），通过 `PERFORMANCE_NODE_ID` 注册/刷新节点心跳，不会抢走共享 `performance` 队列的未绑定任务。
- `system/startup-config` 页面现在提供 `local-all`、`remote-infra`、`android-agent`、`performance-agent` 四档启动方式；选择档案会回填并可复制/下载 `.env`，草稿和当前档案只保存在浏览器，真正启动仍由 `startup.cmd` 完成。
- 页面回归为 StartupConfigView `5 passed`，`vue-tsc --noEmit` 与 Vite production build 通过；本轮未修改远端数据源。当前 172.31.27.133:5432 TCP 可达但 PostgreSQL 连接超时，Backend/Worker/Beat 暂不能恢复，待远端数据库响应后再启动。
- `doctor` 已覆盖 Python/Celery/Redis 依赖、PostgreSQL/Redis/MinIO TCP 连通性、节点 ID/队列格式、共享队列误配置和可选执行器提示；PowerShell 解析与 `backend/tests/scripts/test_windows_local_contract.py` 为 `7 passed`。
- 该入口已完成 Windows 本地启动编排以及主 Worker 的真实节点心跳/消费、k6/Locust 指标回传；Linux/Kubernetes、Prometheus 和真实外部目标仍需目标环境证明，独立性能 Agent 继续只声明 gRPC/JMeter。

## Worker 测试外部依赖隔离修复（2026-08-12）
- 修复 `test_tasks_mobile_special_dispatch.py` 与 `test_tasks_performance.py` 未隔离同步 Redis 取消控制客户端的问题；新增 Fake control client，避免单文件或完整 Worker 测试连接本机真实 Redis 后无限等待，同时保留显式取消场景的独立 mock。
- Worker 测试全量通过 `427 passed`；完整非集成后端门禁通过 `1889 passed`，Python 3.12 覆盖率 `82.13%`，超过 82% 门槛。
- Linux 远程隔离栈的 API/节点 smoke 证据仍有效；本轮 SSH/MCP 会话恢复失败，真实 k6、metrics、其余协议、取消、Kubernetes/Prometheus 和 Android 外部验收继续保持 pending，不能将旧工具镜像的失败报告记为通过。

## 性能验收栈首次 Linux 部署与验收脚本修复（2026-08-12）

- Windows 生成的性能验收 bundle 已使用可移植 ZIP 条目路径重新打包；本次本地 bundle 包含 323 个文件，SHA-256 为 `7a2cd58fcb1762f38c91f2b1d6b98e02cabf4a783ba20f3ed98828370a29e853`，未包含真实 `.env`、证书或私钥。
- bundle 已传输并解压到 Linux 主机 `172.31.27.133:/opt/atp-q17-acceptance`，远端校验通过，Docker 镜像构建成功；Compose 栈使用独立的 PostgreSQL/Redis/MinIO、Backend、性能 Worker 和验收目标，未修改主机已有服务。
- 远端 `/health` 返回 `{"status":"ok"}`；性能 Worker 已加载 k6、Locust、gRPC、JMeter，并报告 `worker-a` online、队列 `performance.worker-a`、allowlist 和四类执行器能力。API/节点验收报告保存在远端 `docs/evidence/performance-api-node-2026-08-12.json`。
- 真实 k6 run 首次执行发现验收脚本自身两个问题：`Path` 报告参数不可 JSON 序列化，以及 POST/stop/run 没有自动携带 `X-Requested-With` 导致 CSRF 403。已修复 `scripts/performance-environment-smoke.py`，本地脚本回归为 `17 passed`；远端脚本已同步，真实 run 需在 SSH 会话恢复后重建/挂载验收工具并重跑。
- 当前外部验收仍保持未完成：真实 k6/gRPC/Locust/JMeter、取消、资源采样完整证据，以及 Kubernetes/Prometheus/真实 Android 设备仍需后续目标环境证明；不要把本次 API/节点 smoke 误记为完整压测通过。

## Web 录制浏览器选择（2026-08-12）
- Web 录制 API 与 `WebRecorderModal` 现在支持选择 Chromium、Firefox 或 WebKit，选择会随启动请求传给 Playwright Worker；默认仍为 Chromium，录制进行中不能切换浏览器。
- 录制会话快照现在回传实际使用的浏览器，跨 Worker 查询和停止录制后的结果仍可追溯浏览器配置。
- 前端提示所选浏览器必须安装在 Worker 镜像中；缺少对应浏览器时由 Worker 返回明确错误，不会静默回退到其他浏览器。
- 本轮回归：Web 录制 API/传输层定向 `33 passed`；完整非集成后端 `1886 passed`、Python 3.12 覆盖率 `82.13%` 且门禁通过；前端全量 `44 files / 177 tests passed`，覆盖率为 statements/branches/functions/lines `36.25% / 31.37% / 28.58% / 37.83%`，type-check/build 通过。

## Windows 性能验收 bundle（2026-08-12）
- 新增 `scripts/package-performance-acceptance.ps1`，使用显式文件/目录 allowlist 收集性能 Compose、Backend/Worker 构建上下文、目标服务夹具、验收工具和 Runbook；排除真实 `.env`、启动档案、虚拟环境、测试缓存、前端依赖和 `.local-run`。
- bundle 内含 `bundle-manifest.json`，逐文件记录大小和 SHA-256；包旁生成 `.sha256` 校验文件，并记录源 commit 与 `worktree_dirty`，覆盖已有输出必须显式 `-Force`。
- 本机实测生成 323 个文件的 zip，包校验成功且未发现密钥/证书条目；真实 Linux 部署和性能 smoke 仍待目标环境执行。

## Web 录制 Worker 并发路由补强（2026-08-12）
- `RemoteWebRecordingManager.start` 继续使用心跳活动会话数做候选排序，但将 Worker 的最终容量检查作为权威结果；收到明确 `busy`/`not_ready` 时切换到其他可用 Worker。
- 超时或未知错误不会自动重试，避免命令已执行但响应丢失时创建重复浏览器会话。
- 新增 `backend/tests/services/test_web_recording_transport.py` 的多 Worker fallback、超时不重试和启动响应异常清理回归，录制传输层测试 `13 passed`；真实 Linux 多副本/Xvfb/Firefox/WebKit 仍待环境验收。
- Worker 启动返回成功但缺少有效快照时，API 会发送停止命令清理可能已创建的浏览器会话，避免残留会话占满 Worker 容量。
- `WebRecorderModal` 停止接口失败时不再自动导入停止前的步骤或关闭弹窗；新增组件回归覆盖失败状态，前端全量为 `44 files / 177 tests passed`，type-check/build 通过。

## 2026-08-12 Web 录制 Worker 状态预检
- 新增 `GET /api/v1/web-recordings/workers`，只返回认证用户可见的脱敏状态：模式、不可逆 Worker 编号摘要、活动会话数、容量和可用数，不返回原始 Worker ID、主机名或进程号。
- `WebRecorderModal` 打开时会预检 Worker 状态：`local` 模式明确提示 API 进程本地录制；`worker` 模式展示注册/可用容量，全部 Worker 满载或未注册时禁用开始按钮，并支持手工刷新。
- 回归：Web 录制 API/传输定向 `36 passed`，`WebRecorderModal` `3 passed`，前端 type-check/build 通过。Linux/Xvfb、真实 Firefox/WebKit 和跨副本 E2E 仍待外部环境验收。

## 2026-08-12 Windows Web 录制状态冒烟预检
- `scripts/windows-local-smoke.ps1` 登录后调用 `/api/v1/web-recordings/workers`，local 模式验证 API 本地录制 ready，worker 模式验证注册节点和空闲容量；worker 模式无可用节点时必需检查失败。
- 报告只记录 mode/registered/available 摘要，PowerShell 解析和脚本契约 `10 passed`；未执行 Android 真机验收，也未把 Linux/Xvfb 或真实多副本结果写成通过。

## API gRPC 流式调用（2026-08-12）
- API gRPC 执行器现根据 Proto 方法声明支持 Unary、Server Streaming、Client Streaming 和 Bidi Streaming；客户端流式请求使用非空 JSON 数组，服务端流式响应以 JSON 数组进入统一 body、提取和断言流程。
- 用例编辑器补充请求格式提示；`backend/tests/worker/test_http_family_executors.py` gRPC/HTTP 家族回归为 `68 passed`，完整非集成后端为 `1886 passed`、Python 3.12 覆盖率 `82.13%`；前端 `44 files / 177 tests passed`，type-check/build 通过。
- 真实 gRPC 服务、TLS 和跨环境验收仍需外部目标服务，不能以本地桩测试代替。

## gRPC Proto 文件读取（2026-08-12）
- gRPC 用例编辑器支持从本地选择 `.proto` 文件并直接回填协议源码；协议源码不作为请求文件上传到 MinIO。
- gRPC 现在可以单独添加 import 文件，Worker 在临时编译目录重建安全文件包，拒绝绝对路径和 `..` 路径。
- `frontend/src/utils/grpcProtoFile.ts` 在浏览器端校验 `.proto` 扩展名、非空内容、单文件 1MB 和文件包 8MB/64 文件上限，回归 `5 passed`；真实服务/TLS 联调仍需外部环境。

## Windows 本地冒烟 CSRF/HttpOnly 会话修复（2026-08-12）
- 修复 `scripts/windows-local-smoke.ps1` 文件上传 403/401：所有 POST/DELETE 写请求统一复用 `X-Requested-With: XMLHttpRequest`，multipart 上传通过目标 URL 的 `CookieContainer` 复用 HttpOnly access cookie。
- 静态合约测试 `5 passed`、PowerShell 解析通过；修复后真实 Windows 冒烟 10 项 Playwright、Chromium/Firefox/WebKit 矩阵、管理员登录、文件上传和 MinIO 清理均通过，报告为 `.local-run/windows-smoke-20260812-003248.json`。
- 随后自包含 Web 下载 seed 也通过：临时项目 9/用例 5 审核、Worker 执行和 1 个下载对象证据成功，终态清理删除项目、1 个环境和 5 个运行产物；报告为 `.local-run/windows-smoke-20260812-003448.json`。

## Windows Worker 模式隔离（2026-08-12）
- `scripts/windows-local.ps1` 的普通 Worker 进程识别现在排除 `--hostname android-win-*` 和 `--hostname performance-win-*`，不会再把专用 Android/性能 Worker 写入普通 `worker.pid` 或在重启时误操作它。
- 当本地配置的 `CELERY_QUEUES` 同时包含 `android`/`mobile_special`，且检测到专用 Android Worker 正在运行时，`windows-local.ps1 up/restart` 会在停止现有本地服务前失败；反向地，`windows-android-worker.ps1 up/restart` 也会检测已运行的普通 Worker 是否消费 Android 队列并拒绝冲突启动。这样不会让两个 Worker 竞争同一 Android 队列。`local-all` 适合完整本地栈，`android-agent` 适合远程后端加本机 ADB，两种模式不要同时启用。
- 已通过 `backend/tests/scripts/test_windows_local_contract.py`（5 passed）和 PowerShell 语法检查；当前已停止专用 Agent 并恢复 `local-all` 的 Backend、普通 Worker、Beat、Frontend。`/health` 返回 ok，`/api/v1/devices/workers` 已出现在运行中的 OpenAPI，ADB 当前无设备。

## Linux 目标主机只读审计（2026-08-12）
- 配置的 Linux 主机已有 Docker/Compose、PostgreSQL、Redis、MinIO，但 `/opt/testhub_platform` 是独立 Django 项目；其 `8001` 服务没有 ATP 的 `/health` 或 `/api/v1/health`，不能把它当作当前 ATP 后端或 Q17 验收环境。
- 未发现 ATP 性能隔离栈或 Prometheus；本次只读探测，没有远程部署、重启或修改。真实性能节点、Linux/Kubernetes、Prometheus 和外部目标服务仍需单独隔离环境。

## 性能验收启动竞态修复（2026-08-12）
- `docker-compose.performance-acceptance.yml` 为 Backend 增加 `/health` 健康检查，并让性能 Worker/验收工具等待 `service_healthy`，不再只依赖容器进程已启动。
- `scripts/performance-environment-smoke.py` 新增 `--node-ready-timeout-seconds`（默认 60 秒），节点检查会在有限时间内等待 Redis 心跳把节点状态刷新为 `online`；新增离线→在线回归覆盖该启动竞态。
- 定向性能部署/验收回归 `27 passed`，Compose YAML 解析通过；真实 Linux 镜像和外部目标服务仍需实际环境验收。

## Windows 部署 readiness 解码修复（2026-08-12）
- `scripts/validate-deployment-readiness.py` 的子进程输出使用 `errors="replace"`，并对 `stdout/stderr` 做空值归一，修复 Windows 系统代码页遇到 shell UTF-8/二进制输出时的 `UnicodeDecodeError` 与后续 `NoneType` 拼接崩溃。
- 当前 Windows 实际运行 readiness 检查通过；Docker/Helm 缺失仅作为明确的 SKIP。部署文档回归 `13 passed`，Ruff 通过。

## 性能中心 JMeter 配置入口（2026-08-11）
- 后端已支持 JMeter 执行器后，性能中心前端执行器切换逻辑现已接受 `jmeter`，自动切换到脚本模式，并根据能力列表使用 `.jmx` 上传类型；修复此前选择 JMeter 无反应的问题。
- 新增组件回归通过；前端全量 `42 files / 169 tests passed`，`vue-tsc --noEmit` 和生产构建通过。
- Windows 实际解析到 `E:\csh\software\jemeter\apache-jmeter-5.6.3\bin\jmeter.bat` 并成功执行 `--version`；后端 Makefile 口径全量非集成回归 `1871 passed`，覆盖率 `82.08%`，门禁通过。

## 性能压测节点注册与配置（2026-08-11）
- 性能中心现可直接注册、编辑和删除性能节点，配置节点 ID、队列、启用状态、支持的执行器、最大 VU、最大并发和目标出口 allowlist。
- 节点卡片和运行节点选择会展示执行器能力；写操作复用现有后端接口并由工程师权限保护，在线状态仍以 Worker Redis 心跳为准。
- 页面管理节点的容量/出口配置不会再被 Worker `.env` 默认值覆盖；Worker 队列不一致时会报告离线，Windows 启动脚本会自动监听共享和专用节点队列。
- 新增节点表单、payload、队列和心跳隔离回归；后端全量非集成 `1871 passed`、覆盖率 `82.08%`，前端全量 `42 files / 169 tests passed`，type-check/build 通过。真实节点消费和 Linux/Kubernetes 分布式压测仍需目标环境验收。
- 性能节点卡片现展示后端 `last_error` 诊断信息，队列不一致时可直接查看 Worker 与节点配置差异；新增前端回归后全量为 `42 files / 170 tests passed`，type-check/build 通过。

## Windows Web 低代码冒烟入口（2026-08-11）
- `scripts/windows-local-smoke.ps1` 新增 `-WebCaseId`、`-SeedWebDownloadCase`、`-RequireWebLowcode`、`-RequireWebDownload` 和 `-WebRunTimeoutSeconds`；传入已有 Web 用例 ID 后，脚本先校验类型、低代码 steps、active/approved 和自动化状态，再使用认证 Cookie 触发 `/cases/{id}/run`，轮询 `/runs/{run_id}`，并可强制检查 download 步骤是否产生对象引用。
- Windows 启动档案：`scripts/windows-local.ps1 -EnvFile` 和 `scripts/windows-android-worker.ps1 -EnvFile` 会在 `Start-Process` 前临时注入选中的 `.env`，启动后恢复当前 PowerShell 环境；因此直接调用底层脚本也不会误读根目录 `.env`。
- Android Agent 启动：`windows-android-worker.ps1 up/restart` 会先执行 doctor；服务端点、Python/Celery 或 ADB 缺失会阻止启动，未连接设备仍仅为 warning。
- 不传 `-WebCaseId` 且不传 `-SeedWebDownloadCase` 时该检查保持 skipped；传入 `-SeedWebDownloadCase` 后脚本会创建临时 Web 项目、模块和低代码用例，自动提交审核并批准为 `active/approved` 后执行内联 `data:` 下载夹具，终态后删除临时项目。内联页面不绕过网络守卫，也不开放 loopback/内网访问。
- 如果临时运行超时或未进入终态，脚本不会删除项目，而是在报告中保留项目 ID/运行 ID，便于确认状态后手工清理；终态清理会同时删除环境、项目和截图/录像/下载对象，避免留下 MinIO 孤儿对象。首次环境没有历史运行记录时，配合 `-SkipReports` 使用自包含模式。
- 前端新增 `public/atp-windows-download.html` 和 `atp-windows-smoke.txt` 本地下载夹具；低代码步骤使用 `goto` 访问页面，再用 `download` 配置 `#atp-download-link`，可在不依赖公网业务页面的情况下准备真实验收数据。
- 夹具 Playwright 回归已通过 `1 passed`；最近一次聚焦真实 seed 冒烟已在当前 Windows 环境通过：临时项目 8/用例 4/运行 4 创建、审批、Worker 执行和 1 个下载对象证据均成功，终态清理删除 1 个环境和 5 个运行产物；报告为 `.local-run/windows-seed-smoke-latest.json`。
- PowerShell 解析、Windows 合约测试 `4 passed`、Ruff 和 `git diff --check` 已通过。

## Windows 启动与性能本地验收（2026-08-11）
- `windows-local.ps1 -EnvFile` 与 `windows-android-worker.ps1 -EnvFile` 会仅向新启动的子进程临时注入所选配置，随后恢复当前 PowerShell 环境；缺少配置档案或 Android Worker 基础依赖时会明确失败。
- JMeter 5.6.3 已执行 `deploy/performance-acceptance/jmeter_smoke.jmx`，本地 `/login` 1 请求、0 错误，并生成 `.local-run/jmeter-smoke-20260811-233647/` 下的 JTL/HTML 报告。该结果仅证明 Windows 本机 JMeter 可用，不替代 Docker/Kubernetes Worker、真实性能节点或 Prometheus 验收。

## 三方 OpenAI 兼容模型配置（2026-08-11）
- AI 模型配置新增 `openai_compatible` 供应商协议，面向 Open WebUI、One-API、LiteLLM 等暴露 OpenAI-compatible `/v1` 接口的三方服务；不再要求用户把它们误选成 Ollama 或 OpenAI。
- 创建/更新时 Endpoint 必填，API Key 仍通过 Fernet 加密保存；模型发现请求 `GET {Endpoint}/models`，生成/诊断请求 `POST {Endpoint}/chat/completions`。
- 前端配置页已新增供应商选项、协议提示和模型拉取入口；真实服务的 Token、模型能力和多模态/思考参数仍需按服务端文档确认，不能只依据名称提示。
- 回归：AI LLM 客户端、模型发现和配置 API 定向测试 `31 passed`；完整回归需在本轮代码稳定后复跑。

## 数据集 AI 生成入口（2026-08-11）
- 测试数据集页新增“AI 生成数据”：新建或选择已有数据集后填写生成要求和行数，调用项目绑定的 AI 配置生成合成 JSON 行。
- 后端入口为 `POST /api/v1/datasets/ai-generate`；结果只返回编辑器草稿，不直接写库，用户确认后仍走现有 Schema 校验、软/硬策略和版本快照。
- AI 服务限制单次最多 200 行，并复用 256KB 序列化上限；没有 Schema 时按结果推断字段类型。模型返回不合法 JSON、未配置模型、配额和网络错误均明确返回失败。
- 验证：数据集后端定向回归 `24 passed`，数据集页面 Vitest `7 passed`，type-check 通过；随后完整非集成回归 `1867 passed`、Python 3.12 覆盖率 `82.05%`，256 个测试文件单独运行通过，前端 `41 files / 167 tests passed`，coverage `33.13% / 28.49% / 25.73% / 34.52%`。

## Mock 规则 AI 生成入口（2026-08-11）
- Mock 服务页现在有独立“AI 生成 Mock”入口；原有“AI 生成用例”仍保留，前者生成 Mock 响应规则，后者生成测试用例草稿。
- 后端入口为 `POST /api/v1/mock-rules/ai-generate`，可按业务要求生成，也可带当前选中的规则作为参考；最多 20 条，项目权限、AI 配置和参考规则归属会在服务端校验。
- 生成结果只进入可编辑 JSON 预览，不直接写库；用户确认后前端复用普通 Mock 创建接口保存，失败时不会把 AI 响应直接当作已生效规则。
- 服务层只接受对象数组，规范化方法、路径、状态码、响应头、条件和延迟，并限制 256KB；提示词明确不生成密钥、Cookie、Token 或真实个人信息。
- 验证：Mock AI 服务/API/UI 定向回归 `14 passed`（含原有 Mock 回归），前端 type-check 通过；完整门禁需在合并后复跑。

## Worker 测试隔离收口（2026-08-11）
- 根级 `backend/tests/conftest.py` 采用 fill-missing-only 的公共 stub 策略，并在测试模块收集和每个测试 setup 阶段刷新缺失符号，避免历史测试直接替换 `sys.modules` 后污染后续 Worker 测试。
- 当前 `backend/tests/worker` 全量为 `415 passed`；全仓非集成回归 `1865 passed`，256 个测试文件独立运行通过。此前记录的 8 个 MinIO/数据库测试桩隔离失败已不再复现。

## Web 录制 Worker 服务化（2026-08-11）
- Web 录制新增 Redis 控制面与独立入口 `python -m app.web_recording_worker`；API 只负责认证、项目权限和资产持久化，Playwright 浏览器对象留在 Worker 内，默认 `WEB_RECORDER_MODE=local` 仍保持 Windows 单进程行为。
- `WEB_RECORDER_MODE=worker` 时，Windows `local-dev.cmd up/status/logs/down` 会自动托管录制 Worker；Docker Compose profile `web-recorder` 与 Helm `webRecorder.enabled` 提供容器部署入口，Linux Worker 使用 Xvfb/`WEB_RECORDER_DISPLAY`。
- Redis 心跳、容量选择、命令回复、会话路由 TTL 刷新、所有者校验和 Worker 退出清理已覆盖回归；随后后端非集成 `1865 passed`、Python 3.12 覆盖率 `82.05%`，256 个测试文件单独运行通过，前端 `41 files / 167 tests passed`；真实 Linux/Xvfb、Firefox/WebKit 和跨 API 副本 E2E 仍属于外部验收，不把本地模拟结果当作完成证据。

## Windows Worker 启动前诊断（2026-08-11）
- `scripts/windows-local.ps1 doctor` 现在会校验 `WEB_RECORDER_MODE`、Python Playwright、Chromium 浏览器、Worker 入口、Redis 队列前缀和正整数并发上限；`local` 与 `worker` 两种模式都会在启动前暴露缺少浏览器依赖的问题。
- `scripts/windows-android-worker.ps1 doctor` 新增 Celery/Redis Python 依赖检查。当前 Windows 实机 doctor 通过，仅保留未连接 Android 设备这一可选警告；k6/Locust 已安装并完成本机真实执行。
- 验证：PowerShell 两个脚本解析通过，Windows 合约测试 `10 passed`；未进行真实 Android 设备或 Linux/Xvfb Worker 验收。

## Android Agent 扫描状态回传（2026-08-11）
- `POST /devices/scan` 在 `ADB_SCAN_MODE=worker` 时返回 `queued`、Celery task ID 和旧列表；新增 `GET /devices/scan/{scan_id}` 查询队列状态与 Worker 写回后的最新设备列表，限制 task ID 为 UUID 并要求工程师权限。
- Android Worker 设备操作已闭环：`ADB_SCAN_MODE=worker` 时截图、屏幕流、tap、swipe 和 UIAutomator 坐标控件识别通过 `ANDROID_WORKER_QUEUE` 派发，公网 API 不再直接执行本机 ADB；任务只开放受控操作并返回 JSON/Base64 结果。
- Windows Android Worker 由 `scripts/windows-android-worker.ps1` 注入 `ANDROID_WORKER_ID=android-win-$COMPUTERNAME`，通过 Redis TTL 心跳写入 `atp:android-worker:workers:*`；设备页调用 `/devices/workers` 展示在线 Agent。心跳任务使用 `ignore_result=True`，避免每 15 秒污染 Celery 结果库。
- `scripts/windows-local-smoke.ps1` 在 `ADB_SCAN_MODE=worker`、配置 Worker ID 或 `-RequireAndroid` 时会强制校验 `/devices/workers`，再调用 `/devices/scan` 并轮询 `/devices/scan/{scan_id}`；普通 local Web/API 冒烟跳过这两项。
- 实时运行事件 channel 按 `case` / `mobile` 类型隔离为 `atp:run:{run_type}:{run_id}`，避免普通用例与 Android 专项运行使用相同自增 ID 时互相收到消息；移动专项前端订阅 `run_type=mobile`。
- Android 性能异常回放按 5-1800 秒滚动分段录制，最多在设备端保留前一段和当前段，异常时上传当前回放；带千分位的 `dumpsys meminfo` 以及设备租约冲突事件均有回归覆盖，移动报告事件时间线按 5000 条加载上限刷新。
- `scan_adb_devices` 的手动投递使用 `ignore_result=False`，Beat 周期扫描仍保持 `ignore_result=True`，避免周期任务制造结果键；前端设备页轮询最多 10 秒，超时明确提示，不再误报“扫描完成”。
- 验证：设备/Worker API、任务、Redis 注册和启动档案回归 `23 passed`，设备页 Vitest `6 passed`，随后完整后端 `1867 passed`、覆盖率 `82.05%`，256 个测试文件独立运行通过；Ruff、格式检查、mypy、type-check/build 通过；真实 Android 设备数据面仍待现场验收。

## 项目工作台扩展（2026-08-11）

- 已完成项目总览、项目级配置中心、`active / archived` 生命周期、归档/恢复接口，以及成员管理只读状态提示。
- 项目状态通过 Alembic 迁移 `backend/alembic/versions/20260811_0054_add_project_status.py` 落库；当前数据库已执行 `alembic upgrade head`。
- 新增前端项目总览路由和项目资源入口；项目卡片不再直接跳转用例列表，归档项目仍可查看已有资源。
- 本轮已验证项目相关后端回归 `53 passed`、前端 `npm run type-check` 和 `npm run build`；Windows 本地服务重启后健康检查与 OpenAPI 路由正常。
- 当前未提交工作区仍包含此前账号/用户管理等改动，不能覆盖或回滚；项目模板和基础复制首批已完成，后续再做脱敏导入导出和归档约束。
- 项目模板与复制首批已完成：支持 blank/API/Web/Android/full 模板，自动创建基础模块、环境和可替换示例数据；复制只迁移项目基础信息与模块树，并生成独立项目编码和当前操作者 owner 关系。
- 脱敏项目导入导出已完成：导出项目基础信息、模块、环境、非敏感变量和脱敏数据集；支持导入预览及 `fail / rename` 冲突策略，导入后当前操作者成为 owner，成员、密钥、执行记录和外部资源不导入。
- 归档约束已落地：项目资源的 editor/owner 写入与执行断言在 archived 状态返回 409，viewer 读取和导出不受影响，restore 后恢复；权限回归更新为 `72 passed`。
- 项目模板/复制/导入导出/归档验证通过，Ruff check/format、前端 `npm run type-check` 与 `npm run build` 均通过；后续可细化归档前端按钮状态、审计事件和成员策略。
- 完整非集成后端回归最终为 `1827 passed`；Python 3.12/3.14 覆盖率门禁分别达到 `82.50%`/`82.05%`，Windows 服务重启后健康检查 200，项目归档/复制/导出/导入预览/导入路由均在 OpenAPI 中可见。
- 归档增强已完成：前端禁用归档项目复制、项目编辑和成员调整，后端 `require_project_writable_access` 防止绕过 UI，项目复制/导入/归档/恢复/成员变更均记录审计事件；项目编辑接口也拒绝 archived 写入，项目相关回归补充为后端 `36 passed`、前端项目列表 `4 passed`。
- Q18 API 高级认证本地实现已完成：`backend/app/services/api_auth.py` 提供 Digest 与 OAuth2 Client Credentials（`client_secret_basic` / `client_secret_post`、scope、audience、变量渲染、单场景 token 缓存），API 与 GraphQL Worker 已接线，CaseFormDrawer 已提供配置入口；token 响应错误只返回安全摘要，不把 client secret 写入执行证据。
- 高级认证回归覆盖服务层、API/GraphQL 执行器接线、token 缓存和 Digest auth 传递；真实 Provider/Consumer、OAuth2 Token Endpoint、Digest challenge、超时和凭据轮换仍需外部环境验收，尚未提交或推送。
- Android 兼容矩阵已从共享数据库会话串行执行改为每个子运行独立 `AsyncSessionLocal`、独立设备租约并通过 `asyncio.gather` 并行执行；结果保留逐子运行状态/错误摘要，真实设备池抢占与故障恢复仍待验收。
- 运行详情页已读取 `device_matrix_results`，展示 Android 矩阵总数、通过/失败/异常统计、设备级耗时和错误，并支持跳转子运行；新增 `RunDetail.spec.ts` 回归后，随着本轮项目/用户页面测试补齐，前端全量为 `40 files / 161 tests passed`。
- HTML/PDF 单运行报告和 JUnit 导出已同步读取 Android 矩阵结果；每台设备在报告中有独立状态/耗时/错误，JUnit 以独立 testcase 输出。
- Web 网络隔离已补齐到浏览器上下文：低代码执行器和录制器共享 Playwright 路由守卫，逐请求校验导航、重定向、WebSocket 与子资源的公网/DNS 地址，阻止内网 egress，并只保存脱敏阻断证据；新增 DNS 变化、协议、脱敏和两条浏览器入口回归。
- 覆盖率补强已完成：新增 iOS Appium 协议动作、JMeter/Prometheus 性能边界、资源采样、Android/iOS 租约生命周期、iOS 租约任务、API 总路由注册以及前端项目/用户/个人资料页面回归；Python 3.12 `--cov-fail-under=82` 和前端现有覆盖率门禁均已通过。
- Python 3.14 兼容性复验已完成：为 `asyncpg 0.31.0`、`psycopg2-binary 2.9.12`、`PyYAML 6.0.3` 准备可用二进制依赖；Python 3.14.3 完整非集成回归 `1827 passed`、覆盖率 `82.05%`，Python 3.12.11 对照为 `1827 passed`、`82.50%`，252 个测试文件独立运行全部通过。后续仍是 Linux/Kubernetes、真实 Android/iOS、专用 Worker、Prometheus 和外部服务验收。
- Web/Android Python 脚本生成已补齐：Web 低代码生成器现在能输出文件上传/下载、Pillow 视觉差异断言、元素资产定位器和页面对象公共动作；Android 生成器覆盖旋转、权限、网络配置、前后台切换；未加载资产、空页面对象或未知动作会在生成脚本中显式失败，避免误生成可运行但漏步骤的脚本。前端全量回归更新为 `40 files / 161 tests passed`，coverage statements/branches/functions/lines 为 `31.94% / 27.09% / 24.94% / 33.21%`。

## Recent Fixes (2026-07-08)

- Fixed the manual bug-link API so `POST /runs/{run_id}/link-bug` now verifies the caller has `editor` access to the run's project before mutating `run.result_summary`.
- Added the previously untracked AI governance and failure diagnosis service modules to the working diff so clean checkouts include imports used by run failure diagnosis and AI case generation.
- Fixed a bug-status audit log regression that referenced an undefined `body.bug_id`; it now records the existing linked bug id from `bug_info`.
- Added static regression coverage for manual bug linking permissions.
- Fixed Python 3.14 local backend setup by installing Homebrew `libpq`, exporting the keg-only `libpq` / `openssl@3` build flags, and adding Python-version-specific dependency pins for SQLAlchemy, grpcio/grpcio-tools, Playwright, and OpenTelemetry.
- Validation: `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration` passed (`823 passed`); targeted bug/diagnosis tests passed (`10 passed`); `py_compile` and `git diff --check` passed.
- Validation update: Docker `python:3.12-slim-bookworm` target-runtime backend regression passed (`823 passed`), confirming the Python 3.14 conditional pins do not break the Python 3.12 deployment baseline.
- Frontend quality update: `npm run type-check` and `npm run build` passed; build only reports the known `ant-design-icons -> ant-design -> ant-design-icons` circular chunk warning.
- Release closeout update: added `docs/release-evidence-2026-07-06.md` with PR grouping, test evidence, known warning, and risk notes; targeted compatibility regression passed (`18 passed`).
- Q10 Phase 1 started: added `ruff==0.8.4` dev tooling, root `pyproject.toml` ruff config, `make lint`, a CI `backend-lint` job, and `docs/code-quality.md`. The first gate checks F821/F822/F823 and passes locally.
- Q10 coverage gate started: added pytest-cov tooling, coverage config, `make test-backend-coverage`, CI coverage XML artifact upload, and a 52% `--cov-fail-under` gate based on the current 53.47% local baseline.
- Frontend unit testing started: added Vitest/jsdom/test-utils/coverage-v8, `npm run test`, `npm run test:coverage`, CI frontend unit-test step, and first specs for auth store, HTTP interceptors, permissions utilities, WebSocket reconnect/message handling, and `BatchOperationBar`.
- Pre-commit baseline added: `.pre-commit-config.yaml` now runs YAML/EOF/trailing whitespace hooks, backend ruff, and frontend Vitest. Helm templates are excluded from plain YAML parsing; initial EOF hook fixes were applied to existing files.
- Mypy baseline added for `backend/app/core`, `backend/app/schemas`, and `backend/app/services` (`76` files). Fixed low-risk Optional handling and variable-reuse type issues, added `types-PyYAML`, and wired mypy into CI/pre-commit.
- Bandit SAST baseline added with `bandit==1.9.4`, `make security-bandit`, pyproject config, CI execution, and `docs/security-scanning.md`. The only high finding was fixed by marking report-cache MD5 as `usedforsecurity=False`; medium/high gate now passes with 63 low findings visible.
- Dependency audit baseline added with `pip-audit==2.9.0`, `make security-pip-audit`, `make security-npm-audit`, and `make security-deps`. The initial baseline had backend 6 vulnerable packages / 25 records and frontend 16 npm audit records (`9` moderate, `5` high, `2` critical).
- Dependency audit remediation completed on 2026-07-08: upgraded FastAPI/Starlette, python-multipart, pytest/pytest-asyncio, Jinja2, cryptography, prometheus-fastapi-instrumentator, Vite/Vitest, Axios, ECharts, vue-i18n, jsdom, vue-tsc, and npm overrides for `brace-expansion`, `form-data`, `lodash`, and `lodash-es`. Q11-02 replay then replaced `python-jose` with `PyJWT[crypto]==2.13.0` to remove the vulnerable transitive `ecdsa` chain. `make security-pip-audit` and `make security-npm-audit` now both pass with zero known vulnerabilities.
- Ruff format baseline completed on 2026-07-08: ran `ruff format backend/app backend/tests` (`217` files reformatted, `115` unchanged), added `make format` / `make format-check`, wired `ruff format --check` into CI and pre-commit, and added `.git-blame-ignore-revs` instructions for the future format-only commit SHA.
- Security automation added on 2026-07-08: `.github/workflows/security.yml` now runs Gitleaks, backend `pip-audit`, frontend high/critical `npm audit`, and Trivy image scans for backend/worker/frontend. `.github/dependabot.yml` now covers pip, npm, Docker, and GitHub Actions weekly.
- Frontend unit testing expanded on 2026-07-08 with `stores/theme` and `utils/chartTheme` specs. Vitest now has 7 files / 18 tests and full-source coverage visibility is 1.8%.
- Docker Python 3.12 target-runtime regression was rerun after dependency remediation. The first attempt exposed `pytest-playwright==0.5.2` requiring `pytest<9`; `pytest-playwright` / `playwright` pins were unified to the 0.8.0 / 1.61.0 line, and the Docker Python 3.12 backend suite then passed (`823 passed`).
- Q10 Phase 5 integration expansion started: added `backend/tests/integration/test_suite_plan_flow.py` for project/module/API case approval -> suite run -> plan run. The first real-infra run exposed a missing Alembic column for `test_suites.config`; added migration `20260529_0039_add_suite_config.py` plus migration regression coverage. Fresh Postgres/Redis/MinIO integration environment now passes (`8 passed`).
- Q10 Phase 5 integration expansion continued: added `backend/tests/integration/test_notification_bug_flow.py` for notification masking/test-send failure handling and bug tracker connection/dedup/create/status/manual-link flows. The real-infra run exposed `bug_trackers.tracker_type` still being varchar in Alembic-created databases; added `20260529_0040_convert_bug_tracker_type_enum.py` plus migration regression coverage. Integration tests now pass on fresh real infra and repeat runs (`10 passed`).
- Q10 Phase 5 frontend E2E expansion continued: added suite / plan mock fixtures and `frontend/e2e/suite-plan.spec.ts`, covering suite load -> trigger run -> history drawer and plan load -> manual run -> execution history. Also added a shared `/api/v1/runs` mock to remove dashboard proxy noise after login. Targeted suite-plan E2E passed (`2 passed`), full Playwright E2E passed (`9 passed`), `npm --prefix frontend run type-check` passed, and Vitest remained green (`18 passed`).
- Q10 Phase 5 SLO thin slice completed: added `atp_run_outcomes_total{entity_type,status}` for terminal case/suite/plan outcomes, recorded outcomes in standalone case, parameterized case, suite, and plan worker paths, expanded `ATP Overview` with API availability, API P95, run success rate, and API error-budget panels, and added `docs/slo-guide.md` plus observability-guide updates.
- Q10 Phase 5 flaky governance completed: added `pytest-rerunfailures==16.4`, registered a `flaky` pytest marker, enabled one bounded retry for scheduled/manual backend integration CI, documented Playwright CI retry boundaries, and added `docs/flaky-governance.md`.
- Q10 acceptance closure completed: added `docs/q10-acceptance-summary.md`, updated README with a Q10 quality/stability index, and synced Task / MEMORY / CONTEXT / release evidence.
- Q11 optimization roadmap started: added `docs/optimization-roadmap-2026-q11.md` with Phase 0 release packaging, Phase 1 SLO calibration, Phase 2 frontend coverage growth, Phase 3 runbooks, and Phase 4 runtime polish.
- Q11-00 completed: added `docs/q11-pr-split-plan.md` with nine recommended review units covering dependency compatibility, runtime fixes, quality gates, Ruff format baseline, security automation, integration, frontend E2E, SLO/flaky governance, and documentation closure. Next action is Q11-01 release notes with risk / rollback notes.
- Q11-01 completed: added `docs/q10-release-notes.md` with Q10 release summary, major change groups, verification snapshot, risk notes, rollback plan, and release checklist. Next action is Q11-02 final CI matrix evidence collection.
- Q11-02 completed on 2026-07-09: `docs/q11-ci-matrix-evidence.md` now archives local and GitHub runner evidence. The final `main` matrix at `c1ef60c` passed CI (`28998360621`), Security (`28998360606`), Integration (`28998366738`), Release readiness (`28998368776`), and E2E (`28998370798`). Follow-up fixes included `types-redis`, a typed Redis async-close helper, Trivy action `v0.36.0`, scoped Gitleaks allowlists, observability wording alignment, worker k6 refresh to `grafana/k6:2.1.0`, and frontend runtime `apk upgrade --no-cache`.
- Q11-10 completed on 2026-07-09: `docs/slo-guide.md` now records the current pre-production evidence window, the missing production Prometheus-history caveat, 7-day initial and 14-day stable production calibration windows, target rationale for API availability / P95 / run success rate, and deferred decisions for paging alerts, monthly error budgets, release-blocking SLO policy, and endpoint-class SLOs.
- Q11-11 completed on 2026-07-09: `docs/slo-guide.md` now includes a SLO triage runbook with first-five-minute checks, availability / latency / run-success / error-budget playbooks, escalation points, and an incident record template.
- Q11-12 completed on 2026-07-09: `docs/slo-guide.md` now explicitly defers paging-grade SLO alerts until production Prometheus history exists, keeps the existing platform health alerts as the active alert layer, and records draft thresholds / enablement criteria for future availability, P95, error-budget, and run-success alerts.
- Q11-20 completed on 2026-07-09: added `frontend/src/utils/caseNavigation.ts` and `caseNavigation.spec.ts` to cover route id parsing, review status parsing, case-list query building, project -> cases navigation, case detail navigation, and query-vs-param precedence. `ProjectList.vue` and `CaseList.vue` now reuse these helpers. Frontend validation passed: Vitest `8` files / `22` tests, `npm --prefix frontend run type-check`, and `npm --prefix frontend run build`.
- Q11-21 completed on 2026-07-09: added `frontend/src/utils/suiteList.ts`, `suiteList.spec.ts`, `planList.ts`, and `planList.spec.ts`; `SuiteList.vue` / `PlanList.vue` now reuse pure helpers for config normalization, status / schedule colors, duration / percent formatting, cron validation / preset parsing, run summaries, failure extraction, and suite run progress. Frontend validation passed: Vitest `10` files / `30` tests, `npm --prefix frontend run type-check`, and `npm --prefix frontend run build`; backend static frontend checks passed for aggregate report and dashboard route contracts.
- Q11-22 completed on 2026-07-10: added `frontend/src/views/system/EnvironmentList.spec.ts` covering project-selection, loading, empty, and API-error states with component stubs; corrected the CaseList E2E `/cases` mock to return the backend's array contract. Validation passed: Vitest `11` files / `33` tests, frontend type-check, build, and targeted case/project/suite/plan E2E (`4 passed`). Next action is Q11-30 release-readiness runbook updates.
- Q11-30 completed on 2026-07-10: upgraded `docs/q9-release-checklist.md` into the active Q11 release-readiness runbook covering same-SHA evidence, Q10 quality/security gates, real-infra integration, E2E, SLO JSON, image/migration/Helm/staging/rollback checks; expanded workflow and backend static contracts. Validation passed: release/deployment docs `10 passed`, five workflow YAML files parsed, Grafana JSON and four SLO panels verified. Next action is Q11-31 scheduled-plan incident drill checklist.
- Q11-31 completed on 2026-07-10: added `docs/scheduled-plan-incident-drill.md` and a static implementation contract covering Beat/Celery, Redis DB 0/1/2 roles, `plan_runs`/child state reconciliation, notification strategy/log evidence, auto-bug outcomes, duplicate-safe recovery, staging fault drills, and incident exit criteria. Validation passed: scheduled-plan/lifecycle/release contracts `12 passed`, Ruff check/format and `git diff --check` passed. Next action is Q11-32 dependency/security rollback documentation.
- Q11-32 completed on 2026-07-10: added `docs/dependency-security-rollback.md` and static contracts for backend requirements/dev tools, paired frontend manifest/lockfile rollback, clean environment validation, immutable image rollback, Gitleaks/Trivy/audit policy, schema compatibility, staging, and vulnerability exceptions. Changed `frontend/Dockerfile` from `npm install` to reproducible `npm ci`. Validation passed: rollback/release/incident contracts `10 passed`, clean `npm ci`, Vitest `33 passed`, type-check/build, frontend Docker image build, pip-audit/npm audit zero vulnerabilities, Ruff and diff checks. Local Trivy CLI was unavailable; the Security workflow remains the image-scan gate. Next action is Q11-40 ResizeObserver warning investigation.
- Q11-40 completed on 2026-07-10: isolated the ResizeObserver loop error to Ant Design Vue measuring the empty CaseList table while horizontal scroll was forced. `CaseList.vue` now enables `scroll.x` only when rows exist, and `case-list.spec.ts` rejects the exact page error. Validation passed: targeted case-list E2E, full Playwright `9 passed` without the warning, Vitest `33 passed`, type-check/build, and backend frontend-static tests `10 passed`. Next action is Q11-41 bundle warning decision.
- Q11-41 completed on 2026-07-10: added `docs/frontend-bundle-decision.md`, retained separate Ant Design/icon chunks after a merge experiment produced a 1541.24 kB warning, and replaced two full ECharts namespace imports with modular core/chart/component registrations. ECharts fell from 1126.62 kB (374.44 gzip) to 563.41 kB (191.53 gzip), with no circular/large chunk warning. Validation passed: bundle contracts `3 passed`, Vitest `33 passed`, type-check/build, full E2E `9 passed`, and diff checks. Next action is Q11-42 Android Docker worker connectivity rehearsal.
- Q11-42 completed on 2026-07-10: added `docs/android-worker-connectivity-rehearsal.md`, corrected the false assumption that host `adb connect` is automatically reused, distinguished direct device TCP from `ADB_SERVER_SOCKET` host-server mode, documented 5037/device-5555/Flower-5555 roles and platform constraints, added host-gateway mappings, and made the doctor safe for shared servers. Worker ADB and Docker Desktop host-server control path were verified; no physical device was attached, so shell/data-plane verification remains environment-specific. Android connectivity/resilience tests `34 passed`; script, Compose, Ruff, and diff checks passed.
- Q12-00 completed on 2026-07-10: removed all 41 `PytestCollectionWarning` messages by aliasing imported application models and schemas in test modules, then made collection warnings fatal in `pyproject.toml`. Full backend regression passed with `840 passed` and zero collection warnings. Q12 roadmap is now active; next action is Q12-01 coverage baseline refresh.
- Q12-01 completed on 2026-07-10: refreshed backend coverage to `53.46%` (`840 passed`, 52% gate) and frontend coverage to statements `3.66%`, branches `4.06%`, functions `2.26%`, lines `3.92%` (`33 passed`). Vitest now enforces initial 3%/3%/2%/3% thresholds, main CI runs `test:coverage`, and the frontend HTML/JSON report is uploaded as an artifact. Next action is Q12-02, starting with LoginView behavior.
- Q12-02 authentication slice completed on 2026-07-10: added four LoginView component tests for required rules, credentials, loading, query/default redirects, and API failure. Frontend now has `37 passed`; full-source coverage rose to statements `4.07%`, branches `4.22%`, functions `2.60%`, lines `4.33%`, and gates rose to 3.75%/3.75%/2.25%/4%. Type-check and production build passed. Next slice is case execution.
- Q12-02 case execution slice completed on 2026-07-10: CaseList and CaseDetail now share tested helpers for environment option mapping, optional `env_id` payloads, case-run API invocation, failure propagation, and run-detail locations. Frontend reached `41 passed` and coverage 4.13%/4.26%/2.73%/4.40%; gates rose to 3.85%/4%/2.45%/4.1%. Next slice is plan scheduling.
- Q12-02 scheduling slice completed on 2026-07-10: PlanList now reuses tested save validation and mutation payload helpers, covering required name/suite, cron rejection, deterministic suite ordering, manual cron clearing, environment, and execution config. Existing Playwright coverage retains the manual-trigger path. Frontend reached `43 passed`, coverage 4.23%/4.49%/2.81%/4.47%, and gates rose to 3.95%/4.2%/2.55%/4.2%. Next slice is reporting.
- Q12-02 completed on 2026-07-10: reporting helpers now cover active query filters, date-picker values, an exclusive next-day boundary (fixing the former midnight over-include), task-name fallback, and trend summaries. All four auth/case/scheduling/reporting slices are complete. Frontend reached `47 passed`, coverage 4.44%/4.88%/3.01%/4.66%, and gates rose to 4.15%/4.55%/2.75%/4.35%. Next action is Q12-03 dependency deprecation cleanup.
- Q12 review cleanup completed on 2026-07-10: replaced the Q12-00 per-file `Test*` aliases with a central `pytest_pycollect_makeitem` hook in `backend/tests/conftest.py` (tests import application classes by real names again); centralized echarts `use([...])` registration in `chartTheme.ts` (5 views cleaned); `caseExecution.ts` now exposes `buildRunPayload`/`buildRunDetailLocation` (named route) without the `executeCaseRun` wrapper and SuiteList reuses the payload helper; `mobileReport.ts` timestamps via dayjs; shared e2e fixture fails on unexpected pageerrors; release-readiness workflow runs the pytest checklist contract instead of duplicating greps; bundle-decision test no longer freezes byte counts; `repo_root`/`repo_file` fixtures replace per-file `ROOT`/`_read`. Frontend `46 passed`, coverage 4.38%/4.81%/2.96%/4.61%, gates adjusted to 4.1%/4.55%/2.7%/4.35% per baseline policy.
- Q12-03 completed on 2026-07-10: retired both dependency deprecations. Upgraded vue-i18n `9.14.5` -> `11.4.6` (project already uses `legacy:false` Composition mode + Vue 3, so v10/v11 removals do not apply; `src/locales/index.ts` unchanged in behavior). Forced transitive glob to `13.0.6` via an npm `overrides` entry (chain `@vue/test-utils > js-beautify > glob`, dev-only). Clean `npm ci` now emits zero `npm warn deprecated`. Added a dedicated `i18n` manualChunk in `vite.config.ts`. Validation: `46 passed`, coverage 4.38/4.81/2.96/4.61, type-check, build, and full Playwright `9 passed`. Side effect: the ant-design chunk crossed 1500 kB (1502.45) from module-graph reshuffle, firing the Q12-04 bundle follow-up trigger; threshold intentionally held. Next action is Q12-04 chunk-boundary evidence.
- Q12-04 completed on 2026-07-10: adopted automatic on-demand Ant Design registration (unplugin-vue-components + AntDesignVueResolver, importStyle:false, dts:false) replacing global app.use(Antd), and removed the synchronous chartTheme import from main.ts (it referenced the full echarts module set, making echarts an entry dependency since UI Phase 1). Measured with vite preview + Chrome: /login gzip transfer 773.9 -> 510.1 kB (-34%), ant-design chunk 1502.45 -> 1246.41 kB (387.71 gzip), zero build warnings. Validation: 46 unit tests (specs mock antd directly), vue-tsc clean, full E2E 9 passed with the shared pageerror guard confirming no missing registrations. Deferred: enabling components dts exposes ~112 pre-existing a-* prop type mismatches; typing hardening is a separate item. Typing hardening completed same day: components dts enabled and committed, all 112 pre-existing a-* prop type errors fixed (per-table asXxx record assertion helpers, inline v-model null assertions, narrowed badge/handler return types); functions coverage gate nudged 2.7 -> 2.65 to keep the 0.25pt headroom policy after refactors. Validation: vue-tsc clean, 46 unit tests, build, E2E 9 passed, backend 841 passed. Q12-05 local scoping completed same day: docs/q12-external-readiness-evidence.md freezes both capture formats (SLO 7/14-day history: absolute-date windows, per-SLO achieved-vs-target, breach triage notes, alert/release-gate decision; device rehearsal: topology + doctor output + run identity + data volume + artifact list, pass criteria) with a 3-test contract guarding the spec against platform drift. Remaining Q12 work is capture execution only, blocked on a long-lived scraped deployment and a physical Android device. All locally executable Q12 roadmap items are now complete.
- Q13 roadmap published on 2026-07-10 (docs/optimization-roadmap-2026-q13.md), planned from measured gaps: backend execution chain (tasks.py 362 missed + nine executors ~1450 missed, TOTAL 53%), zero-coverage frontend workbench views (CaseList 587 / RunDetail 539 / SuiteList 537 / DashboardView 513 statements), ant-design chunk dominance (374.7 of 510.1 kB gzip on /login), and AI healing iter5 phase 2 pending. Seven items Q13-00..06; execution starts with Q13-01 executor unit seams + a new coverage-baseline-2026-q13.md; Q12-05 captures carry over as Q13-00 and interrupt on environment arrival.
- Q13-01 slice 1 completed on 2026-07-10: test_tasks_execution_chain.py (34 tests) drives the Celery task bodies synchronously (run_async -> asyncio.run stub) against a FakeDB keyed by (model, pk), covering run_test_case (missing-run/happy/dispatch-false/dispatch-raise/parameterized routing), run_test_suite (missing/error/notify+HTML/notify-failure), run_test_plan (sequential/fast-fail-skip/parallel/auto-bug-error/notify-failure/cron reschedule), _execute_plan_suite, check_cron_plans (trigger/skip/invalid-cron-disable/env-merge), check_dashboard_alerts. tasks.py 35% -> 86% (remaining: auto-bug success path 745-822, owned by Q13-02), backend TOTAL 53% -> 55.65%, 878 passed. Seam conventions recorded in docs/coverage-baseline-2026-q13.md; executor families follow the same fake-transport shape. Gate stays 52% until TOTAL hits 60%.
- Q13-01 completed on 2026-07-10 (slice 2, HTTP-family executors): test_http_family_executors.py (46 tests) fakes only the transport boundary (scripted httpx.AsyncClient shared by api+graphql, websockets.connect fake with incoming queues, FakeChannel for grpc.aio) while assertion matrices, auth injection (bearer/basic/apikey), cross-step variable extraction, timeout/transport-error paths, and StepResult persistence run the real implementations. grpc tests compile a real 3-line proto through grpc_tools.protoc. Found and fixed a live production break: protobuf 5+ removed message_factory.GetPrototype, so grpc_executor failed on every run since the dependency refresh — replaced with GetMessageClass. Executor coverage: api 3%->94%, graphql 3%->90%, websocket 3%->89%, grpc 8%->88%. Backend TOTAL 60.03% (924 passed), CI gate raised 52%->56%. Lesson: per-test monkeypatch of module-bound collaborators (api_executor.apply_healing_hook) instead of sys.modules stubs — a setdefault stub raced with test_tasks_healing over the real ai_healing module depending on collection order. Next action is Q13-02 service/API coverage.
- Q13-02 slice 1 completed on 2026-07-10: test_bug_reporter_unit.py (38 tests, one scripted httpx fake drives all four trackers — Jira/ZenTao/GitHub/GitLab create/connect/status/duplicate/attachment, JQL escaping, field mappings, product-map overrides, wrapped-response shapes) and test_failure_diagnosis.py (15 tests — category matrix, repair-suggestion mapping by status code, rule diagnosis, prompt assembly, generate_failure_diagnosis rule/llm/rule_fallback/daily-limit/skipped states with late-imported llm_client injected via monkeypatch.setitem). bug_reporter 20% -> 95%, failure_diagnosis 12% -> 97%, backend TOTAL 63.35% (962 passed). Remaining Q13-02: ai_healing, exports, mobile_special API.
- Q13-02 slice 2 completed on 2026-07-10: test_ai_healing_run_level.py (23 tests) covers run_diagnosis_for_run across idempotency/missing-case/no-config/below-threshold/cache-hit/daily-limit/decrypt-failure/llm-success+failure states, order-insensitive run cache keys, text+vision daily limits (zero=unlimited, first-call expire, redis-degradation), screenshot base64 loading, and run-hook threshold + enqueue broker-failure swallowing. Note: patch app.core.encryption via an explicit module import (it may not be in sys.modules yet). ai_healing 46% -> 89%, TOTAL 64.50% (985 passed). Remaining Q13-02: exports, mobile_special API.
- Q13-02 slice 3 completed on 2026-07-10: test_exports_junit_reports.py (18 tests) drives the route functions directly with a (model, pk)-keyed FakeDB — three-level JUnit export (per-step outcomes, stepless run-level failure/error/skipped synthesis, suite summary counts with actual TestRun duration lookups, plan-level missing-suite error cases and ghost-suite skips), _normalize_status/_format_duration/_merge_summary helpers, MinIO cache read/write error swallowing, suite/plan aggregate HTML builders (case rows, environments, missing-suite sections), export_run_html cache hit/miss headers, and all PDF routes behind a faked _render_pdf_from_html. exports 36% -> 92%, TOTAL 65.97% (1003 passed). Remaining Q13-02: mobile_special API.
- Q13-02 completed on 2026-07-10 (slice 4, mobile_special API): test_mobile_special_routes.py (16 tests) — task CRUD with access checks and schedule refresh, trigger with config snapshot/device fallback/Celery enqueue boundary, stop-run guards, joined run listing, samples/incidents/artifacts, CSV/JSON export assembly. Found and fixed the second live break exposed by coverage work: create_task raised TypeError (500) on every call because MobileSpecialTaskCreate.created_by collided with the explicit created_by kwarg — fixed with model_dump(exclude={'created_by'}). mobile_special 45% -> 91%, TOTAL 66.98% (1019 passed), CI gate 56% -> 62%. Q13-02 done: bug_reporter 95 / failure_diagnosis 97 / ai_healing 89 / exports 92 / mobile_special 91. Next: Q13-03 frontend workbench slices; Q13-05 unblocked.
- Q13-03 slice 1 completed on 2026-07-10 (CaseList): extracted src/utils/caseList.ts (filterCasesByLevel, countPendingReviews, countFlakyCases, collectActiveFilters, caseWorkflowGuards state machine, flakyTooltipParams, flattenModules) with caseList.spec.ts (5 grouped assertions). CaseList.vue now calls the tested helpers — activeFilterTags keeps only an i18n label-mapping layer, workflow guards dispatch through caseWorkflowGuards. vue-tsc clean, e2e case-list still green, frontend statements 4.38% -> 4.65% (51 passed), gates ratcheted to 4.4/5.1/2.9/4.6. Baseline now tracked in coverage-baseline-2026-q13.md. Remaining Q13-03: RunDetail, SuiteList, DashboardView.
- Q13-03 slice 2 completed on 2026-07-10 (RunDetail): extracted src/utils/runDetail.ts (summarizeStepStatuses, failedOrErrorSteps, countScreenshotSteps, computeExpandedKeys, readIterationStats/isParameterizedParent, runStatusColor/healingTagColor maps, normalizeRunHealing, normalizeFailureDiagnosis returning the @/api FailureDiagnosisResult type, primaryErrorText, truncateText) with runDetail.spec.ts (7 grouped assertions). RunDetail.vue rewired to the helpers. vue-tsc clean, run-detail e2e green, frontend statements 4.65% -> 5.10% (58 passed), gates ratcheted to 4.85/6.35/3.35/4.95. Remaining Q13-03: SuiteList, DashboardView.
- Q13-03 slice 3 completed on 2026-07-10 (SuiteList): extended src/utils/suiteList.ts with buildModuleDescendantMap (module id -> self+descendant id set), buildModuleTreeOptions (tree-select pruning of empty branches), caseExecutionReasonKey (returns i18n key or null by status/review/automation precedence), and passesSuiteCaseStructuralFilter (module/type/ready/selection-scope predicate; keyword search stays in the view since it needs i18n labels). suiteList.spec.ts +4 grouped assertions. SuiteList.vue dropped its local buildModuleDescendantMap/buildModuleTreeOptions/ModuleTreeOption copies and inline filter chain, calling the util. vue-tsc clean, suite-plan e2e green, frontend statements 5.10% -> 5.54% (62 passed), gates ratcheted to 5.3/7.15/3.45/5.35. Remaining Q13-03: DashboardView.
- Q13-03 slice 4 completed on 2026-07-10 (DashboardView), all four workbench slices done: extracted src/utils/dashboardView.ts (generateDateRange inclusive daily range; fillTrendGaps generic gap-fill with injectable today for deterministic tests and weekly-skip, replacing the duplicated pass-rate/duration fillers; normalizeDashboardLayout + cloneDefaultDashboardLayout + DEFAULT_DASHBOARD_LAYOUT) with dashboardView.spec.ts (6 groups). One test pins a subtle real contract: a known layout key present-but-malformed (missing visible) is dropped and NOT re-appended because seenKeys already contains it. DashboardView.vue rewired, local copies removed. vue-tsc clean, dashboard e2e green, production build clean, frontend statements 5.54% -> 5.95% (68 passed), gates 5.7/7.5/3.7/5.7. Q13-03 workbench tier complete (4.38% -> 5.95%); the 8% acceptance target needs a follow-up form-drawer slice (CaseFormDrawer/PlanList). Remaining Q13: 8%-target slice, Q13-04 chunk evidence, Q13-05 apply-loop (unblocked), Q13-06 deps.
- Q13-03 CaseFormDrawer slice completed on 2026-07-10: extracted src/utils/caseFormConfig.ts (isRecord/asStringMap, getFirstStep for steps[]-or-bare config, parseFormBody for edit-load, resolveRequestBody by body_type, parseGraphqlVariables, normalizeWsMessage) with caseFormConfig.spec.ts (6 groups). CaseFormDrawer.vue dropped its local isRecord/asStringMap/getFirstStep and the inline body/graphql/ws parsing. Note: the ws-message input started as a discriminated union but `action:'send'` narrowing broke against the `{action:string}` catch-all member — widened to a single optional-field interface. vue-tsc clean, case-list e2e green, build clean, frontend statements 5.95% -> 6.33% (branches past 8%, 74 passed), gates 6.05/8.05/3.9/6.1. One more PlanForm-config slice should carry statements over 8% to close Q13-03.
- Q13-03 PlanList cron slice completed on 2026-07-10: added buildCronExpression (daily/weekly assemble time fields, custom = trimmed input) and formatCronTime (zero-padded HH:MM) to src/utils/planList.ts with 3 spec groups; PlanList.vue cronPreviewExpression/cronDescription call them. Frontend statements 6.33% -> 6.40%, branches 8.4% (77 passed), gates 6.15/8.15/3.95/6.15. KEY ASSESSMENT: helper extraction has hit diminishing returns for STATEMENT coverage — six slices only moved statements 4.38% -> 6.40% because each workbench view is ~1000+ lines dominated by template wiring/reactive glue that pure-function tests can't reach. Branch coverage already passed 8%. Reaching the 8% STATEMENT target needs component-mount tests (@vue/test-utils, as LoginView.spec already does), not more helper slices. Recorded in roadmap with two options: treat the helper phase as done, or run one focused mount-test slice. Remaining Q13: Q13-04 chunk evidence, Q13-05 apply-loop (unblocked), Q13-06 deps; Q13-00 on environment access.
- Q13-06 dependency hygiene completed on 2026-07-10: reviewed the three transitive install-script packages (core-js postinstall = funding notice in try/catch; fsevents = darwin-only native binding, no real script; vue-demi postinstall = Vue2/3 entry switch required by pinia) and pinned them in frontend/package.json `allowScripts`. npm ci now emits zero allow-scripts warnings (already zero deprecations post-Q12-03), npm audit 0 vulnerabilities. Added docs/dependency-hygiene.md (per-package verdict table + quarterly refresh policy) and backend/tests/frontend/test_dependency_hygiene.py (3 tests pinning the allowlist to the doc and the glob^13/vue-i18n^11 overrides). Also fixed test_dashboard_routes static contract that my Q13-03 slice-4 refactor had broken (DEFAULT_DASHBOARD_LAYOUT moved from DashboardView.vue to utils/dashboardView.ts) — a pre-existing string-match contract lagging the move. Backend 1022 passed. Remaining Q13: Q13-04 chunk evidence, Q13-05 apply-loop (unblocked); Q13-00 on environment; Q13-03 8% statement line needs a mount-test pass.
- Q13-04 completed on 2026-07-10 (Ant Design route-level chunk, GO decision): confirmed the on-demand-registered antd was still forced into one 1246 kB chunk by manualChunks(id)=>'ant-design', so /login pulled the whole monolith (374.7 of 510.1 kB gzip first paint, 73%). Ran a measured experiment removing that manual chunk: Rolldown splits the tree-shaken components into lazy route chunks; /login first paint 510.1 -> 335.8 kB (-34%, -174 kB, far over the 15% roadmap threshold), cost is +~35 kB total dist JS (2771->2806) as antd's shared runtime duplicates into a few route chunks (count 45->80), no large-chunk warning. Adopted it (removed the 'ant-design' manualChunks line), tightened chunkSizeWarningLimit 1500->600 (echarts ~563 is the new ceiling). Verified: vue-tsc clean, 77 unit tests, full Playwright 9 passed in real browser navigation, bundle contract test updated. Evidence in docs/frontend-bundle-decision.md. Remaining Q13: Q13-05 apply-loop (unblocked); Q13-00 on environment; Q13-03 8% statement line needs a mount-test pass.
- Q13-05 completed on 2026-07-10 (AI healing apply-loop, iter5 phase 2): apply-loop backend (snapshot+audit+whitelist+optional regression) already existed but had NO feature flag and only static string-match tests (~0% real endpoint coverage). Added settings.AI_HEALING_APPLY_ENABLED (default False) gating apply_healing_patch — 403 when off (apply is the only healing path that mutates a case); preview stays open as read-only gate. Added test_ai_healing_apply_loop.py (7 behavioral tests). iter5 API 0%->72%. FIXED a third latent production bug: endpoint used ProjectRole.engineer which doesn't exist (owner/editor/viewer only) -> every apply/preview would 500; changed to editor. Hardened two pre-existing sys.modules isolation fragilities the test exposed (test_tasks_execution_chain, test_db_backup now importlib force-reimport, immune to collection order). Full suite 1029 passed, TOTAL 67.76%. ALL locally-executable Q13 items complete (Q13-01/02/04/05/06 done, Q13-03 substantially done); only Q13-00 (Q12-05 SLO+device captures) remains, blocked on environment. Q13 coverage work found+fixed 3 production bugs total.
- Q13-03 closed on 2026-07-10 with a mount-test slice: after the helper-extraction assessment showed diminishing statement returns, added ApkList.spec.ts (4 tests) and DeviceList.spec.ts (5 tests) using @vue/test-utils mount + stubbed antd components + hoisted API/message mocks (same shape as LoginView.spec), covering on-mount load, keyword filtering, summary stats/status badges, scan/CRUD row actions via a TableStub that renders the bodyCell action slot, and failure toasts. ApkList 0->56%, DeviceList 0->62%; frontend statements 6.40% -> 8.51%, CROSSING the 8% acceptance line — a mount test moved +1pt each vs +0.07pt per helper slice, exactly as predicted. Gates 8.2/9.6/6.2/8.15; vue-tsc/build/full-E2E green. Q13-03 complete. ALL locally-executable Q13 items now done (01-06); only Q13-00 (Q12-05 captures) remains, blocked on environment.- Q13-01 web-family executor follow-up completed on 2026-07-10: after HTTP-family (slice 2) the browser/device executors were still near-zero. Added test_web_executor.py (8 tests: fake subprocess.run that writes the --json-report-file and returns a scripted proc, faked MinIO download/upload/presign, per-test monkeypatched ai_healing hooks — covers missing-script error, timeout, no-test-functions, pass/fail/skip step mapping with screenshot upload, chromium fallback for unsupported browser, healing enqueue, safe-publish swallow) and test_web_lowcode_executor.py (8 tests: a _FakePage recording Playwright action calls drives _execute_step across goto/click/fill/select/hover/press-with-and-without-selector/assert_text-with-body-fallback/assert_visible/wait/screenshot/unknown, plus _replace_vars recursion). web_executor 13%->84%, web_lowcode_executor 15%->51%, backend TOTAL 67.76%->69.29% (1045 passed). Both test files defensively backfill app.core.minio_client symbols (upload_bytes/upload_file/download_file/presigned_url) before importing the executor, since another test replaces that module with a field-incomplete stub — same cross-file sys.modules fragility class as before. android/android_lowcode executors remain the next candidates if more executor coverage is wanted.
- Q13-01 android-family executor follow-up completed on 2026-07-10: extended test_android_lowcode_executor.py (+11 tests: a fake _adb_cmd records adb args and scripts (ok, output), driving _execute_step_sync across click-by-coords/find-click-fail, long_click swipe-sim, swipe direction/unknown/custom-coords, input escaping+clear, press_key named+raw keymap, start_app with/without activity, stop_app, assert_text/assert_element via uiautomator dump, wait/screenshot/unknown; plus _replace_vars recursion) and test_android_executor.py (+3 tests: run_android_case guard branches for missing script, missing device, unreachable device — monkeypatching _safe_publish since the file's module-level redis stub is non-async). android_lowcode_executor 15%->53%, android_executor 12%->23% (the remaining gap is the async create_subprocess_exec pytest orchestration, heavier to seam). Backend TOTAL 69.29%->70.23% (1059 passed). ALL NINE executors (api/graphql/websocket/grpc/web/web_lowcode/android/android_lowcode + the earlier android perf/stability/fluency) now have behavioral coverage; the execution chain — the platform's core value path and previously its least-tested code — is no longer a near-blind spot. Only Q13-00 (Q12-05 env captures) remains.
- Backend coverage extension on 2026-07-10 (environments API): a data-driven scan of the largest remaining gaps flagged two 0%-covered modules (api/v1/environments.py 72 miss, api/v1/ws.py 98 miss). Chose environments (clean CRUD, highest value-per-effort) over ws (WebSocket, harder to seam). Added test_environments_routes.py (11 tests driving the route fns with the (model,pk) FakeDB seam): list/create/update/delete with viewer-vs-editor project-access assertions and 404s, get_variables secret masking (****** for is_secret), save_variables bulk-delete-then-insert with per-item encrypt for secrets and masked return, and the batch-save duplicate-key validator. api/v1/environments.py 0% -> 100%. Backend TOTAL 70.23% -> 70.92% (1070 passed); CI gate raised 62% -> 66% (kept ~5pt headroom). Since Q13-01 the coverage push has: covered all nine executors, closed a fully-untested API, and taken backend TOTAL from the Q13-start 53% to 70.92% (gate 52 -> 66). Next 0% candidates if continued: api/v1/ws.py (98 miss, WebSocket), services/mobile_special/collectors.py (85 miss). Only Q13-00 (Q12-05 env captures) is a real acceptance blocker, still on environment.
- Backend coverage extension continued on 2026-07-10 (WebSocket endpoint): covered api/v1/ws.py (the second-largest 0% module, 98 miss) with test_ws_routes.py (15 tests) — _get_ws_user token validation (missing/invalid/non-access-type/missing-or-inactive-user/valid via faked AsyncSessionLocal + decode_token), the _can_subscribe_run authorization ladder across all five allow branches (admin, run triggerer, case creator, project member via UserProject, project owner) plus deny paths (missing run, missing case, unrelated user), and ws_run_events handshake (1008 Unauthorized close, 1008 Forbidden close, accept) -> pubsub message forward -> server-initiated close on a completed payload -> finally unsubscribe/aclose, all via a _FakeWebSocket + _FakePubSub + _FakeRedis. ws.py 0% -> 89% (remaining is the WebSocketDisconnect/error-log exception paths). Needed defensive backfill of app.core.database (AsyncSessionLocal) and app.core.redis_client (get_async_redis) before import, same cross-file stub-pollution class. Backend TOTAL 70.92% -> 71.62% (1085 passed). The two largest 0%-covered modules (environments API, ws endpoint) are now both covered; backend TOTAL 53% (Q13 start) -> 71.62%, gate 52 -> 66.
- Backend coverage extension on 2026-07-10 (mobile_special collectors): covered services/mobile_special/collectors.py (0%, 85 miss — the Android special-test metric sampling core) with test_mobile_special_collectors_sampling.py (10 tests) faking run_adb_shell + the parse_* functions. Covers SamplingSession PID resolve (with/without output) and __aenter__ auto-resolve, all four samplers routing raw to the correct parser plus empty-output->None, PeriodicSampler yielding only the selected metric_types with sample_time, skipping None samples, defaulting to cpu+memory, and stop(); plus validate_device_ready / validate_package_installed. collectors.py 0% -> 92%. Backend TOTAL 71.62% -> 72.26% (1095 passed). NOTE: a narrow --cov=<that module> run trips a mass SQLAlchemy mapper collection error (coverage import-timing quirk), but the CI-shape --cov=backend/app run and the plain suite are both fully green — the narrow-target run is never used by CI. Backend TOTAL since Q13 start: 53% -> 72.26%.
- Backend coverage extension on 2026-07-10 (mobile-special dispatch): covered worker/tasks_mobile_special.py (26%, 89 miss) with test_tasks_mobile_special_dispatch.py (15 tests) reusing the tasks.py seam pattern (stub celery/redis/bootstrap + run_async=asyncio.run before import, restore + load_all_models, FakeDB behind AsyncSessionLocal, executor routing injected via sys.modules). Covers run_mobile_special_task (missing run, missing task, executor routing parametrized over performance/stability/fluency with config-merge + device/app resolution, executor-exception -> failed + completed publish, device-serial resolution from Device), check_mobile_special_schedules (due-task trigger with schedule TriggerType + cron reschedule, invalid-cron disable), cleanup_stale_mobile_special_runs (bulk update), and the pure helpers _merge_run_config/_resolve_run_device_id/_resolve_run_app_package/_get_device_serial precedence. tasks_mobile_special.py 26% -> 97%. Backend TOTAL 72.26% -> 72.87% (1110 passed). The entire mobile-special vertical (API/tasks/collectors/parsers) now has behavioral coverage. Backend TOTAL since Q13 start: 53% -> 72.87%.
- Backend coverage extension on 2026-07-10 (plans API): covered api/v1/plans.py (55%, 79 miss) with test_plans_routes.py (16 tests). Covers _validate_plan_suite_ids (duplicate 400, missing-suite 400, wrong-project 400, empty ok), _validate_plan_environment (None ok, 404, wrong-project), create_plan cron next_run_at computation + webhook secret generation + project 404, update_plan next-run-cleared-when-not-cron + 404, trigger_plan_run env-var merge (decrypt_env_vars + extra_vars) with Celery run_test_plan.delay boundary + empty-suites/404 guards, and webhook_trigger secret-auth ladder (404, non-webhook plan 400, bad-secret 403, empty-suites 400, success with triggered_by=None + webhook TriggerType). api/v1/plans.py 55 -> 80%. Backend TOTAL 73.76 -> 74.16% (1154 passed). Backend TOTAL since Q13 start: 53 -> 74.16%.
- Q14 roadmap published on 2026-07-11 (docs/optimization-roadmap-2026-q14.md), planned from a fresh measured baseline (backend TOTAL 74% / 1154 passed / gate 66; frontend statements 8.51% / 86 passed): seven items — Q14-00 carries the environment-blocked Q12-05 captures, Q14-01 Android/ADB executor coverage (android_executor async-subprocess seam, stability/fluency/perf, web_lowcode, adb_service; TOTAL >=78%, gate 66->70), Q14-02 API-router sweep (TOTAL >=80%), Q14-03 workbench mount tests (statements >=12%), Q14-04 per-project retention REAL cleanup (execute_old_runs_cleanup at services/run_retention.py:236 still global-only; per-project preview punts test/mobile at line 342), Q14-05 gitleaks pre-commit hook (CI uses gitleaks-action@v2 + existing .gitleaks.toml; also fix Makefile --cov-fail-under=52 vs CI 66 drift), Q14-06 q13-acceptance-summary.md. Execution: Q14-01 + Q14-03 parallel first.
- Backend coverage extension on 2026-07-10 (bug_trackers API): covered api/v1/bug_trackers.py (55%, 90 miss) with test_bug_trackers_routes.py (13 tests). Faked encrypt_config/decrypt_config/mask_config/write_audit_log to test the ROUTE orchestration: create encrypts config + masks output, list/get mask secrets, update runs _merge_sensitive_config so a masked (******) or omitted secret preserves the existing value (real invariant preventing accidental secret wipe when editing other fields), CRUD 404s, and test_bug_tracker_connection (inline config, tracker_id saved-secret merge, tracker-type mismatch caught -> ok=False, backend RuntimeError swallowed -> ok=False). Tested _merge_sensitive_config as pure logic. api/v1/bug_trackers.py 55 -> 75%. Backend TOTAL 73.41 -> 73.76% (1138 passed). The bug-report subsystem (bug_reporter service, already covered, + this API layer) is now behaviorally covered end to end. Backend TOTAL since Q13 start: 53 -> 73.76%.
- Backend coverage extension on 2026-07-10 (projects API): covered api/v1/projects.py (41%, 93 miss, root of the permission system) with test_projects_routes.py (15 tests). Covers non-admin list scoping, create_project auto-owner + auto code + owner UserProject row, get/update/delete 404 + code backfill, _build_tree nesting + root sort ordering, module CRUD with injected access checks, member list mapping, add_project_member (404/409/create), role update + 404, and critically remove_project_member last-owner invariant (blocks at owner count <= 1, allows non-last owner and regular member). api/v1/projects.py 41 -> 79%. Backend TOTAL 72.87 -> 73.41% (1125 passed). Since Q13 start: 53 -> 73.41%.

## Recent Fixes (2026-06-03)

- Unified several system settings pages onto the shared `page-shell` / `page-hero` visual pattern and added missing zh-CN/en-US subtitle copy for environment, notification, global variable, and bug tracker pages.
- Hardened FastAPI startup against transient or misconfigured MinIO by using short MinIO client timeouts and logging bucket bootstrap failures as warnings instead of blocking app startup.
- Added `scripts/dev_mock_backend.py` as a lightweight local UI-preview backend for cases where external PostgreSQL / Redis / MinIO dependencies are unavailable.
- Verified the real FastAPI service can start successfully on `http://127.0.0.1:8000` after the MinIO startup hardening; `/health` returned `{"status":"ok"}`.

## Recent Fixes (2026-03-08)

- Completed Phase 4.5 notification integration across backend, frontend, migration, and docs.
- Added notification config model/schema/API/service, notification settings UI, and SMTP-related environment documentation.
- Added regression tests for notification dispatch, notification API test-send behavior, startup model loading, and migration coverage.
- Fixed notification read-path credential exposure by requiring engineer-level access for notification detail/list endpoints.
- Fixed WeCom and DingTalk delivery handling so non-200 responses or non-zero `errcode` values now raise errors instead of being reported as success.
- Fixed project deletion regression by cascading `notification_configs` on project delete at both ORM and migration/foreign-key levels.
- Restored frontend type-check by installing missing `vuedraggable` / `sortablejs` dependencies.
- Updated `Task.md` to mark 4.5 notification integration complete and recorded the security/correctness hardening items.

## Previous Fixes (2026-03-06)

- Fixed device mirror auth flow by loading screenshots through Axios with token and rendering `Blob` URLs in frontend polling.
- Added `android-tools-adb` to backend runtime image so mirror screenshot endpoints can run in container deployments.
- Fixed Android low-code `clear=true` input behavior by sending repeated valid delete key events (`keyevent 67`).
- Switched APK upload path to chunked tempfile streaming to avoid loading large APK files fully into memory.
- Added regression tests for Android low-code clear behavior and APK streaming size guard.

## Validation Snapshot

- `backend/.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/integration` passed on local Python 3.14 (`825 passed`).
- Docker `python:3.12-slim-bookworm` with `gcc libpq-dev` installed ran `python -m pytest backend/tests -q --ignore=backend/tests/integration` successfully (`823 passed`).
- `npm --prefix frontend run type-check` and `npm --prefix frontend run build` passed; build has only the known Ant Design icons circular chunk warning.
- `backend/.venv/bin/python -m pytest backend/tests/services/test_device_sync.py backend/tests/api/test_ai_llm_configs_api.py backend/tests/worker/test_async_runner.py backend/tests/worker/test_suite_execution_config.py -q` passed (`18 passed`).
- `make lint PYTHON=backend/.venv/bin/python` passed (`ruff check backend/app backend/tests`).
- `make mypy PYTHON=backend/.venv/bin/python` passed (`Success: no issues found in 76 source files`).
- `make security-bandit PYTHON=backend/.venv/bin/python` passed (`Medium: 0`, `High: 0`, `Low: 63`).
- `make security-pip-audit PYTHON=backend/.venv/bin/python` passed (`No known vulnerabilities found`).
- `make security-npm-audit` passed (`found 0 vulnerabilities`).
- `make format-check PYTHON=backend/.venv/bin/python` passed (`336 files already formatted`).
- YAML parse validation passed for `.github/workflows/security.yml`, `.github/dependabot.yml`, `.github/workflows/ci.yml`, and `.pre-commit-config.yaml`.
- `make pre-commit PYTHON=backend/.venv/bin/python` passed all hooks.
- Q11-02 GitHub runner final matrix passed on `main` commit `c1ef60c`: CI, Security, Integration, Release readiness, and E2E were all successful. Details and run links are archived in `docs/q11-ci-matrix-evidence.md`.
- Q11-10 SLO calibration is documented in `docs/slo-guide.md`; current targets remain pre-production guardrails until continuous production Prometheus history is available.
- Q11-11 SLO triage runbook is documented in `docs/slo-guide.md`; it maps each current SLO breach to first checks and escalation criteria.
- Q11-12 alert threshold decision is documented in `docs/slo-guide.md`; SLO-specific paging alerts are deferred until production Prometheus history exists.
- Q11-20 frontend navigation utility tests passed: `npm --prefix frontend run test` (`8` files / `22` tests), `npm --prefix frontend run type-check`, and `npm --prefix frontend run build`.
- Q11-21 suite / plan helper tests passed: `npm --prefix frontend run test` (`10` files / `30` tests), `npm --prefix frontend run type-check`, `npm --prefix frontend run build`, and `backend/.venv/bin/python -m pytest backend/tests/frontend/test_aggregate_report_frontend.py backend/tests/frontend/test_dashboard_routes.py -q` (`10 passed`).
- Q11-22 system page smoke test passed: `npm --prefix frontend run test` (`11` files / `33` tests), `npm --prefix frontend run type-check`, `npm --prefix frontend run build`, and targeted E2E (`4 passed`).
- Q11-30 release-readiness runbook validation passed: `backend/.venv/bin/python -m pytest backend/tests/worker/test_q9_release_readiness.py backend/tests/worker/test_deployment_ops_docs.py -q` (`10 passed`), workflow YAML parse passed, and Grafana SLO JSON/panel checks passed.
- Q11-31 incident drill validation passed: scheduled-plan, worker-lifecycle, and release-readiness contracts `12 passed`; targeted Ruff check/format and `git diff --check` passed.
- Q11-32 rollback validation passed: dependency rollback/release/incident contracts `10 passed`; clean frontend install, `33` tests, type-check/build and Docker image build passed; pip/npm audits found zero vulnerabilities.
- Q11-40 ResizeObserver regression validation passed: targeted CaseList and full `9` E2E passed without the former warning; frontend `33` tests, type-check/build, and backend static frontend tests passed.
- Q11-41 bundle validation passed: modular ECharts reduced minified/gzip size by about half; bundle contracts `3 passed`, frontend `33` tests, type-check/build and full `9` E2E passed without build warnings.
- Q11-42 Android worker validation passed: worker ADB binary and shared host-server path verified, Android connectivity/resilience tests `34 passed`, doctor shell syntax and two Compose configurations validated.
- `make test-backend-coverage PYTHON=backend/.venv/bin/python` passed (`823 passed`, total coverage `53.47%`, required `52%` reached).
- Docker `python:3.12-slim-bookworm` with `gcc libpq-dev` installed ran `python -m pytest backend/tests -q --ignore=backend/tests/integration` successfully after dependency remediation (`823 passed`).
- `npm --prefix frontend run test` passed (`18 passed`); `npm --prefix frontend run test:coverage` passed with current frontend full-source coverage baseline `1.8%`; `npm --prefix frontend run type-check` and `npm --prefix frontend run build` passed.
- `npm --prefix frontend run e2e -- suite-plan.spec.ts` passed (`2 passed`), and full `npm --prefix frontend run e2e` passed (`9 passed`) after adding suite / plan workflow coverage.
- SLO thin-slice validation passed: `python3 -m json.tool docker/grafana/dashboards/atp-overview.json`, `backend/.venv/bin/python -m ruff check backend/app/core/metrics.py backend/app/worker/tasks.py backend/tests/worker/test_run_outcome_metrics.py`, and `backend/.venv/bin/python -m pytest backend/tests/worker/test_run_outcome_metrics.py backend/tests/worker/test_dataset_parameterized.py backend/tests/worker/test_plan_execution_config.py backend/tests/worker/test_suite_execution_config.py -q` (`23 passed`).
- Flaky governance validation passed: installed `backend/requirements-dev.txt`, `pytest --markers` shows both project `flaky` marker and rerunfailures marker, `pytest backend/tests/worker/test_run_outcome_metrics.py -q --reruns 1 --reruns-delay 1` passed (`2 passed`), and CI workflow YAML parsing passed.
- Q10 acceptance closure is documented in `docs/q10-acceptance-summary.md`; README now links Q10 implementation and acceptance artifacts.
- Fresh real-infra integration run passed with temporary local services on Postgres `55432`, Redis `6380`, and MinIO `19000`: `alembic upgrade head` succeeded and `backend/tests/integration -m integration` passed (`10 passed`); a second run against the same database also passed (`10 passed`).
- `pytest backend/tests/api/test_notifications.py backend/tests/services/test_notifier.py backend/tests/migrations/test_notification_config_migration.py backend/tests/services/test_notification_bootstrap.py backend/tests/plans/test_plan_regressions.py backend/tests/api/test_webhook_exports_regressions.py -q` passed (`20 passed`).
- `npm --prefix frontend run type-check` passed after restoring missing frontend dependencies.

## Related Commits

- `a970cd2`: notification integration, security fixes, Task update, and supporting docs/tests.
- `b7f7698`: mirror/auth + clear/upload regressions.
- `c6df8fc`: latest feature repairs and task doc updates.
- 2026-08-11 覆盖率收口：补充 `ProjectList`、`UserManagementView`、`AccountSettingsView` 组件级行为回归，覆盖项目导入成功后的弹窗清理、用户新增/编辑及八位密码校验、个人资料保存与错误提示；前端全量 `40 files / 157 tests passed`，覆盖率 statements/branches/functions/lines 达到 `31.54% / 26.53% / 24.73% / 32.76%`，超过现有 `31.5 / 26.5 / 24.5 / 32.5` 门禁；type-check 和生产构建通过。
- 2026-08-12 Android 真机工作顺序调整：当前先不连接真实 Android 设备，ADB/Worker 真实验收保持 pending；继续开发不依赖真机的 API、Web、性能、数据集和发布闭环，不把无设备状态写成通过。
- 2026-08-12 存储治理 UI：`StorageManagementView` 增加项目下拉选择、MinIO 数据集对象 dry-run 核对、孤儿对象明细/截断/错误展示，以及仅允许基于当前核对结果发起的二次确认 `purge=true` 清理；新增 API 类型和中英文文案，页面回归 `7 passed`，type-check 通过。
- 2026-08-13 Web/Android 低代码关键流程收口：新增 `WebCaseDrawer.spec.ts` 与 `AndroidCaseDrawer.spec.ts`，覆盖创建/编辑时 `config.steps`、Android 标准步骤和关键配置保存；发现并修复 Web 编辑时浏览器被无条件重置为 Chromium 的问题。前端全量回归当前为 `49 files / 203 tests passed`，type-check 通过；真实 Worker/Android 设备仍保持外部验收边界。
