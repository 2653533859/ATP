# ATP 发布收口状态（2026-08-25）

> 这是当前发布候选的状态索引。它只汇总已经存在的代码/自动化证据和真实环境证据，不把本地 mock、协议桩或“代码已实现”写成生产通过。

> 当前开发顺序与模块状态以 [`development-plan-2026-08-25.md`](development-plan-2026-08-25.md) 为准；本文件只维护发布证据、环境边界和收口结论。

> API 受控目标、显式会话复用、gRPC TLS Unary、OpenAPI/Postman 解析和导入落库证据：[`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)。这些证据不代表生产 API、GraphQL/WebSocket/流式 gRPC 或完整报告验收通过。

> N1 协议执行边界已补齐：GraphQL、WebSocket、gRPC 的缺失/空 `config.steps` 会 fail-fast 为 `error`，避免产生零步骤的虚假通过；该项有本地回归，不替代真实协议目标验收。

> N1 保存边界已补齐：协议用例创建/更新会在写入快照前校验最小可执行配置，失败返回 `422`；该项有本地回归，不替代真实 GraphQL/WebSocket/流式 gRPC 和完整报告验收。

## 发布结论

当前结论：**暂不具备无条件发布资格**。

## 2026-08-25 当前执行计划与新增阻塞

当前执行顺序为：运行基础/账号初始化 → Android 单设备真实闭环 → Windows API/Web 复核 → 真实通知 → 外部缺陷平台 → 生产性能 → 发布收口。

### 2026-08-25 API gRPC TLS 受控目标验收

- 已补齐 API gRPC TLS 的自签名/私有 CA 配置：用例表单支持公有 PEM 根证书和 SNI 服务名，执行器限制证书大小、拒绝私钥，并且只在步骤快照记录“已配置”状态，不保存证书内容。
- q19 已按 `96c7db0` 重建 Backend/Worker；临时项目完成 gRPC Unary TLS 用例创建、评审、审批、执行、`grpc_status=OK`、响应断言、JSONPath 提取和清理，运行 `17` 通过。
- 本地回归：gRPC Worker `69 passed`，Ruff、前端类型检查、生产构建和配置工具测试 `6 passed`；脱敏证据见 [`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)。
- 发布边界：这只关闭 q19 受控 gRPC TLS Unary 证据；OpenAPI/Postman 导入、GraphQL/WebSocket/流式 gRPC、生产目标和完整报告仍待验收。

### 2026-08-25 API OpenAPI/Postman 导入解析验收

- q19 已按 `75ed756` 重建 Backend/Worker；当前账号调用 `/api/v1/ai/cases/parse-schema` 的 OpenAPI 与 Postman 样例均返回 `200`，分别解析出 `1/1` 和 `1/3`（接口/参数）。
- 本地解析与端点回归 `38 passed`，Ruff 和差异检查通过；证据见 [`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)。
- 发布边界：本项只关闭解析层；导入预览/落库闭环见下节，GraphQL/WebSocket/流式 gRPC、生产目标和完整报告仍待验收。

### 2026-08-25 API 导入预览与落库验收

- q19 已按 `a8f6e26` 重建 Backend/Worker；受控流程完成 OpenAPI 解析（成功响应码 `201`）、临时项目/模块创建、导入预览 `valid=1/invalid=0`、用例落库 `201`、回读断言/步骤预期和项目删除清理 `204`。
- 验收中发现并修复 `Module.project` 异步懒加载导致的 `MissingGreenlet` 500：导入预览读取模块时预加载所属项目；定向回归 `42 passed`，后端非集成全量 `2270 passed`，Ruff/diff-check 通过。
- 脱敏证据见 [`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)。发布边界：仅关闭 OpenAPI 导入预览/落库/回读/清理；其他协议和完整报告仍待验收。

### 当前剩余阻塞

- q19 Backend 的管理员 bootstrap 启动缺陷已按 `65eef50` 修复并完成真实复验：初始化按用户名/邮箱幂等识别，不覆盖已有账号密码或角色；当前账号登录、依赖 readiness、Worker registry 和设备扫描均已通过。
- Android 前置证据仍有效：Windows ADB 有 2 台 `device`，Worker doctor、PostgreSQL、Redis、MinIO 和 logcat 检查通过；两台设备均未发现 Karing，真实 APK/package name、低代码或专项操作仍未执行。
- 仍需取得或上传 Karing APK 并以设备包管理确认真实包名，才能继续单设备闭环；不能用其他应用替代 Karing 关闭门禁。

本节计划与 [`docs/product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md) 的 0.7 节、[`Task.md`](../Task.md) 和 [`MEMORY.md`](../MEMORY.md) 同步维护。

### 2026-08-25 P0-0 管理员初始化幂等修复（本地证据）

- 已修复 `backend/app/main.py::_init_admin` 按用户名/邮箱幂等识别和并发唯一键复查逻辑，避免管理员改名后 q19 Backend 因默认邮箱重复进入重启循环。
- 新增管理员初始化回归；定向 `2 passed`，后端非集成全量 `2262 passed`，Ruff、格式检查和 `git diff --check` 通过。
- q19 已按 `65eef50` 更新 Backend，迁移 `20260824_0065 (head)`，Backend `running/healthy`，当前账号登录、依赖 readiness、Web/Android Worker registry 和 2 台设备扫描通过，最近 2 分钟无启动错误；脱敏证据见 [`q19-admin-bootstrap-2026-08-25.json`](evidence/q19-admin-bootstrap-2026-08-25.json)。
- P0-0 的启动与认证阻塞已关闭，但 Android 真实 APK/package name、低代码、录屏、专项任务和报告媒体仍未验收；远端 Compose 的端口映射等现场改动已保留，不能用仓库文件覆盖。

### 2026-08-25 P0-B.3 单设备运行与 APK 上传问题

- 已在真实在线设备 `172.16.102.214:5555` 上用已安装包 `com.microsoft.emmx` 完成临时低代码、步骤截图、设备信息、logcat 和录屏回传；3/3 步骤通过，临时业务数据已清理。该证据只覆盖平台执行链路，不代表 Karing 包存在。
- 真实上传约 262 MB APK 时发现 q19 MinIO multipart 分片使用 5 秒读超时并返回 HTTP 500；已在本地修复为独立 `MINIO_READ_TIMEOUT_SECONDS` 和并发连接池，前端配置/示例/文档已同步。
- q19 已按 `e1dc113` 重建并健康运行；262,615,229 字节 APK 上传、标准 `ResXMLTree` Manifest 解析出 `com.microsoft.emmx`/版本信息、项目对象绑定、列表回读和临时记录/对象/项目清理均通过。证据见 [`android-apk-upload-2026-08-25.json`](evidence/android-apk-upload-2026-08-25.json)。
- 本项仍不关闭 Android 总门禁：当前设备包列表没有 Karing，Karing 专项动作、APK 下载端点、异常回放和完整报告下载仍需真实 Karing APK/设备复验。

本地代码、回归和 Windows/q19 API/Web/性能链路已经形成可复核证据；以下外部门禁仍未关闭，因此发布只能按“部分实现/待环境验收”处理：

- Android Worker/真机：ADB、Agent/Backend Redis 配对、Worker registry、扫描回调、租约绑定控制和 APK 资产选择/包名传递已通过；专项任务包名一致性、应用启动/Monkey/动作失败终态已完成本地回归，但真实 APK 上传、低代码、录屏、专项任务和结果回传仍不能验收。
- 性能生产环境：真实 Kubernetes 多节点、容量限制、生产 Prometheus、MinIO 生命周期和跨主机恢复未验收。
- 通知供应商：当前只有回环 SMTP 的 `local_link_only` 证据，没有真实 SMTP/企业微信/钉钉送达回执。
- 外部缺陷平台：没有可使用的临时 Jira/禅道/GitHub/GitLab 项目和凭据，创建、同步和脱敏链路未做真实验收。

### 2026-08-25 P0-A Windows API/Web 完整 smoke

- 使用当前有效账号运行完整 `scripts/windows-local-smoke.ps1 -SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload`：Backend/Frontend HTTP 200、HttpOnly Cookie 登录、PostgreSQL/Redis/MinIO readiness、Web Worker、Playwright `12 passed`、浏览器矩阵无失败请求/错误响应、文件上传/清理、Web 低代码下载和 HTML/JUnit 报告导出均通过。
- 修复了空历史数据库中的阶段顺序缺陷：临时 Web run 现在先于报告导出，run 9 报告 HTML/JUnit 分别为 18,715/317 bytes；临时项目 24 与 5 个产物已清理。脱敏证据见 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)。
- P0-A 仍保留 `[~]`：环境/认证复用和真实 API 协议目标需要单独验证；本次不替代 Karing Android、真实通知、外部缺陷平台或生产性能验收。

## 当前开发计划

当前按参考导航的五组结构推进：工作台、测试能力、测试资产、智能中枢、系统。旧设备/APK/专项任务、Mock、数据集和治理页面保留兼容 URL，但从所属工作台或配置中心进入；“入口可见”不作为业务闭环通过条件。

当前优先关闭 Android P0-B.3 单设备执行闭环，拆分为：真实 APK 上传/包名识别与选择、低代码最小执行、录屏与异常回放、专项任务、事件/日志/报告回传。每一项都必须同时具备代码、回归测试、代码审查修复和脱敏证据；没有 APK、包名或在线 `device` 时，只记录阻塞，不创建脏运行。

P0-B.3.5 事件、日志与报告回传已完成本地实现，并已用通用 APK 完成低代码录屏、设备信息、logcat、截图和结果回传验证；Karing 专项动作、APK 下载端点、异常回放和完整报告下载仍待真实 Karing APK。下一步是补 Karing 包验证，再按 P0-A → P1-C → P1-D → P1-E → P1-F 推进。

Android 闭环完成后，按 P0-A → P1-C → P1-D → P1-E → P1-F 继续复核 Windows API/Web、真实通知供应商、外部缺陷平台、性能生产环境和发布收口。详细依赖、出口和状态见 [`product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md) 的“0.5 当前开发计划与跟踪台账”，执行勾选见 [`Task.md`](../Task.md)。

### 2026-08-25 Android 设备前置验收复核

- 两台 ADB 设备均为 `device`，选定 `172.16.102.15:5555` 完成命令、属性、包管理和 logcat 检查；Windows Android Worker 正在消费 `android,mobile_special`，PostgreSQL/Redis/MinIO doctor 通过。
- 当前在线设备第三方包列表没有 Karing，且 `.env` bootstrap 账号登录返回 HTTP 401；因此未调用认证 Worker registry/扫描接口，也未创建 Android 运行记录。
- 脱敏证据见 [`android-device-control-preflight-2026-08-25.json`](evidence/android-device-control-preflight-2026-08-25.json)。这项证据只关闭设备前置检查，不关闭 Android 真实执行门禁。

## 2026-08-25 Android 低代码最小执行本地交付

- 单设备执行现在按设备 serial 查询注册设备、申请/释放租约；租约冲突会在执行步骤前结束为 error。设备矩阵保持每个子运行独立租约。
- Worker 按 `apk_id` 查询项目 APK 资产并校验模块项目归属，执行前复用 Android preflight 下载/安装 APK；步骤结果、截图和完成事件继续回传。
- Android 相关回归 `145 passed`，后端非集成全量 `2245 passed`，Ruff 和 `git diff --check` 通过；脱敏证据见 [`android-lowcode-execution-2026-08-25.json`](evidence/android-lowcode-execution-2026-08-25.json)。
- 发布边界：本地代码链路已完成，但当前没有真实 APK 文件，尚未完成在线设备低代码执行、录屏、专项任务和完整事件/日志/报告回传，因此 Android 真机门禁仍未关闭。

## 2026-08-25 P0-B.3.3 录屏与异常回放可观测性本地交付

- 低代码录屏启动失败现在写入 `result_summary.android_artifacts.screen_recording_error`；专项异常回放写入 `summary_json.incident_replay`，包含是否请求、是否保存和失败原因。
- 报告详情页展示异常回放不可用告警；如果后续录屏轮换成功并保存回放，会清除过时的启动失败告警，避免与可播放视频同时出现矛盾提示。
- Android 执行器定向 `64 passed`，后端非集成全量 `2248 passed`，前端 Vitest `66 files / 269 tests passed`，类型检查、生产构建、Ruff 和差异检查通过；脱敏证据见 [`android-recording-observability-2026-08-25.json`](evidence/android-recording-observability-2026-08-25.json)。
- 发布边界：没有真实 APK 和在线设备录屏/Crash/ANR 证据，MinIO 视频上传、设备权限和专项回放仍待真实环境验收；本地回归不关闭 Android 真机门禁。

## 2026-08-25 P0-B.3.4 Android 专项任务本地交付

- 任务新建、编辑和手工触发现在统一校验项目内 APK 的已确认 `package_name`；缺少包名或手工包名与 APK 不一致时返回 `400`，默认任务 APK 也会被解析并写入运行快照。
- 性能、稳定性和流畅度执行器在应用启动失败、Monkey 启动/异常退出或流畅度动作失败时写入 `summary_json.error_message` 并终态为 `failed`；完成事件会携带失败状态和错误摘要，正常取消仍为 `stopped`。
- 定向回归 `86 passed`，4 个受影响文件独立运行 `28/25/19/14 passed`，后端非集成全量 `2255 passed`；前端 Vitest `66 files / 269 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。脱敏证据见 [`android-special-task-2026-08-25.json`](evidence/android-special-task-2026-08-25.json)。
- 发布边界：未获得真实 APK 和在线 `device` 执行证据前，不关闭真实安装/启动、专项动作、超时取消、Crash/ANR logcat、录屏、MinIO 或报告回传门禁；Karing 仍需先通过包管理确认真实包名。

## 2026-08-25 P0-B.3.5 事件、日志与报告回传本地交付

- Worker 收尾阶段按任务配置采集结束时的设备 logcat 和 PNG 截图，分别限制在 5 MB/10 MB；上传成功登记 `MobileRunArtifact`，摘要记录 `requested/saved/file_name/file_size/error`，采集、上传或 ADB 失败不会覆盖专项原始状态。
- 专项任务配置页已增加设备日志/结束截图开关；报告详情页展示产物状态，报告文件表通过受保护的 artifact URL 下载；已有性能 CSV、异常日志、录屏和异常回放不改变原有路径。
- 事件记录器与 JSON 报告导出统一脱敏常见 Authorization、Cookie、密码、Token、Secret、API Key 以及 URL 查询凭据；事件达到上限时仍会提交产物行和摘要。
- 定向 84 项、后端非集成 `2260 passed`，前端 Vitest `66 files / 269 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过；脱敏证据见 [`android-event-artifact-reporting-2026-08-25.json`](evidence/android-event-artifact-reporting-2026-08-25.json)。
- 发布边界：真实 APK、在线 `device`、MinIO 上传/下载/清理、三类专项端到端日志/截图和性能录屏/异常回放仍待真实环境验收，本地证据不关闭 Android 真机门禁。

## 2026-08-25 P0-A 本地 E2E 回归复核

- 本地 Playwright 共享 fixture 已修复中文登录按钮自动空格，以及主布局 `/workbench/overview`、运行详情 `/defects` 未隔离导致的真实 401；登录定向 `3 passed`、运行详情定向 `1 passed`、全量 Playwright `12 passed`。
- 前端 Vitest `66 files / 265 tests passed`，`vue-tsc --noEmit`、生产构建和 `git diff --check` 通过。
- 这不改变发布结论：Windows 完整 smoke 仍需使用当前有效账号重跑；认证读接口、文件传输和报告导出在账号未通过前保持未验收，不记录任何密码或 Token。

## 2026-08-25 P0-B Android 单设备验收前置复核（历史记录）

- 早期执行 `scripts/windows-android-acceptance.ps1` 时，设备统计为 `online=0, unauthorized=0, offline=1, other=0`，必需检查失败；该结果只代表当时的设备状态。
- 脱敏本地报告：`.local-run/android-acceptance-current-20260825.json`。脚本在离线状态下不会继续执行设备命令、包管理、日志读取或创建 Android 运行任务。
- 后续设备已恢复在线，当前阻塞已转为 Worker 注册 Redis 通道配对，见下方最新记录；历史 `offline` 不能被重新解释为当前通过。

## 2026-08-25 P0-B Android ADB 在线但 Worker 注册未配对

- ADB 通过 mDNS 发现在线目标；目标 `172.16.102.15:5555` 的授权、shell、属性、包管理和 logcat 基础检查通过。
- Windows Android Worker 的 Redis DB 2 中存在心跳注册，但 q19 Backend 通过 SSH 隧道使用 q19 Compose 内部 Redis，因此 `/devices/workers` 返回没有在线 Android Worker。
- 发布边界：这不是 ADB 失败，而是 Agent/Backend 注册通道配置不一致。完成同实例、DB、注册前缀配对并重新验证 Worker registry、扫描和结果回传之前，Android 发布门禁仍保持未关闭。
- 当前重新发现的设备未确认存在 Karing 包名；任何 Karing 专项任务必须先通过设备包管理确认真实包名。

## 2026-08-25 P0-B Android Redis 配对与 Worker 注册复核（扫描回调修复前快照）

- Windows Agent 与 q19 Backend 已通过受控临时 SSH 隧道共用同一 Redis 实例、DB、认证、队列和注册前缀；配置配对校验、Worker doctor 和 `/devices/workers` 查询通过，在线 Worker 为 `android-win-HPS`。
- ADB 基础检查仍通过；本条记录保留的是修复前扫描 smoke 未在 10 秒窗口内收到完成回调的历史状态，后续已定位并修复 `scan_adb_devices` 丢弃 Celery 结果的问题，当前结论以紧随其后的 P0-B.2 验收记录为准。
- 本机复验命令为 `adb devices -l`；只有明确显示目标为 `device` 才能继续 Android 单设备链路，`offline` 或 `unauthorized` 仍保持阻塞。
- 为避免 Beat 继续生成维护任务，q19 Beat 当前保持受控停用；恢复前必须确认队列已清理、只保留预期任务，并重新取得扫描回调证据。
- 发布边界：Worker registry 在线和基础控制通过仍不等于 Android 单设备闭环通过；APK 包名、低代码真实运行、录屏、专项任务、事件和报告回传仍保持未验收。当前设备是否安装 Karing 仍须以 `pm list packages` 为准。

## 2026-08-25 P0-B.2 Android 扫描回调修复与验收（控制门禁前基线）

- 修复 `scan_adb_devices` 声明 `ignore_result=True` 的问题。任务此前已经在 Windows Worker 成功执行，但 API 读取不到 Celery 结果，导致 `scan_id` 长时间保持 `queued`；现已保留任务结果并新增契约回归。
- 重新启动单个受控 Worker 后，配置配对、ADB、Worker registry 和扫描回调均通过；扫描返回 2 台在线设备，扫描后 `mobile_special` 队列长度为 `0`。
- 定向测试 `24 passed`，三份受影响测试文件独立运行 `4/17/3 passed`，完整后端非集成 `2237 passed`，Ruff 和 `git diff --check` 通过。脱敏证据见 [`android-worker-scan-2026-08-25.json`](evidence/android-worker-scan-2026-08-25.json)。
- 发布边界：本项只关闭 Worker 配对和扫描回调门禁；租约、控件属性、截图/录屏、APK 包名、Android 低代码、专项任务、事件和报告回传仍待 P0-B.3。

## 2026-08-25 P0-B.3 Android 租约绑定控制验收

- 修复设备点击/滑动接口缺少租约校验的问题；现在必须通过 `X-Device-Lease-Token` 携带当前有效设备租约，缺少或过期令牌返回 `409`。
- Android 低代码抽屉会在选择设备后自动申请租约并定时续租，切换设备、切换脚本模式、保存关闭或卸载时释放；截图读取保持兼容，控件属性读取继续用于生成定位器。
- 定向后端 `43 passed`，前端 Android 抽屉 `3 passed`，类型检查、Ruff 和差异检查通过；脱敏真实证据见 [`android-control-lease-2026-08-25.json`](evidence/android-control-lease-2026-08-25.json)。
- Windows Worker/q19 依赖上的真实链路：设备 ID `1`、扫描 2 台；租约申请成功，截图 `29,099` bytes，UI 属性响应，点击/滑动 `200`，无租约点击 `409`，释放 `204`。
- 发布边界：APK 包名、Android 低代码真实运行、设备录屏、专项任务、事件/日志/报告回传仍保持未验收。

## 2026-08-25 P0-B.3 APK 资产选择与包名传递验收

- APP 自动化工作台选择 APK 后现在传递 `apk_id`；后端校验 APK 属于当前项目，并将 APK ID、包名写入手工触发运行的记录和配置快照，Worker 可据此取得安装资产。
- 任务默认 APK 的 ID 会继续进入运行快照；跨项目 APK 选择返回 `400` 且不写入运行记录。
- 定向后端 `53 passed`，前端 APP 工作台 `3 passed`，类型检查、Ruff 和差异检查通过；脱敏证据见 [`android-apk-selection-2026-08-25.json`](evidence/android-apk-selection-2026-08-25.json)。
- 发布边界：当前没有真实 APK 文件可上传，连接设备的包管理结果也未发现 Karing 包名；真实 APK 上传/包名识别、低代码、录屏、专项任务和事件/报告回传仍待验收。

## 2026-08-25 工作台任务状态枚举隔离修复

- q19 日志暴露工作台将 Android `stopped`、性能 `cancelled` 混入普通 `TestRun`/套件/计划状态查询，可能导致 PostgreSQL `runstatus` enum 错误。
- 已按任务域限制状态过滤，空交集显式无匹配，重试状态按域恢复；工作台定向 `8 passed`，完整后端非集成 `2229 passed`，Ruff/diff-check 通过。
- q19 已按 `36cacb9` 受控重建，迁移 `20260824_0065`、Backend `200`、Prometheus 4 targets `up`、Celery 2 节点在线，重启后未出现新的 enum 错误；脱敏证据见 [`q19-workbench-status-filter-2026-08-25.json`](evidence/q19-workbench-status-filter-2026-08-25.json)。鉴权工作台请求仍因缺少当前有效账号未执行，发布结论不因此提前关闭。

## 2026-08-25 Android 录屏证据展示补齐

- Android Worker 产生的 `result_summary.android_artifacts.screen_recording` 现在可在运行详情页直接播放；`screen_recording_error` 会以告警形式展示。
- HTML 报告会在开启录像选项时嵌入 Android 录屏；通用 `video_url` 仍优先，PDF 不嵌入视频的既有行为不变。
- 运行详情在收到 WebSocket 完成事件后自动刷新，避免执行页面必须手动刷新才能看到录屏。
- 本地证据：提交 `279b254`，后端导出 `13 passed`、RunDetail `6 passed`、前端全量 `66 files / 268 tests passed`，类型检查和构建通过；详见 [`android-recording-evidence-2026-08-25.json`](evidence/android-recording-evidence-2026-08-25.json)。
- q19 已从 `origin/main` 的 `257c479` 独立工作树重建并启动；迁移 `20260824_0065 (head)`、健康 `200`、Prometheus 4 个 target `up`、Celery 2 节点响应、后端最近 3 分钟错误匹配数为 0；详见 [`q19-android-recording-deployment-2026-08-25.json`](evidence/q19-android-recording-deployment-2026-08-25.json)。
- 发布边界：当前没有真实 Android 录屏采集证据，且 Worker 注册通道尚未配对；这项改动不关闭 Android 真机发布门禁。

## 2026-08-25 P1-D 外部缺陷平台错误安全收口

- 连接测试、创建缺陷和刷新状态入口已统一脱敏供应商异常，覆盖 Token、密码、Webhook 查询参数和 URL 用户信息；创建/状态刷新返回 502，连接测试返回 `ok=false`。
- 缺陷跟踪入口的 mypy 变量复用问题已修复，成功创建、重复检测、状态同步和附件上传路径保持不变。
- 本地证据：提交 `31df065`，外部缺陷定向 `40 passed`、完整后端非集成 `2234 passed`，Ruff、格式、mypy 和 diff-check 通过；详见 [`external-tracker-error-safety-2026-08-25.json`](evidence/external-tracker-error-safety-2026-08-25.json)。
- 发布边界：没有真实外部缺陷平台项目与凭据，本模块不关闭 Jira/禅道/GitHub/GitLab 的环境验收门禁。

## 2026-08-25 P1-D q19 运行态部署

- q19 已重建到 `cec8eaf`，复用 `atp-q19-acceptance-20260824` Compose 项目名，迁移为 `20260824_0065 (head)`。
- 运行验证通过：Backend `200`、Redis `PONG`、Prometheus ready 且 `4` 个 target 为 `up`；通用 Worker、性能 Worker、Beat、Web Recorder 正常运行，最近 3 分钟 Backend/Worker 错误匹配数为 `0`。
- 发布边界：q19 Compose 不是 Kubernetes 多节点或生产外部平台证据；真实 Jira/禅道/GitHub/GitLab、Android 真机和生产性能验收仍待独立完成。详见 [`q19-external-tracker-deployment-2026-08-25.json`](evidence/q19-external-tracker-deployment-2026-08-25.json)。

## 2026-08-25 P1-C 通知验收脚本错误脱敏修复

- 通知供应商验收脚本已改为复用统一异常脱敏逻辑，Token、密码和 URL 用户信息不会进入终端或 JSON 报告；全量测试下的历史模块桩污染也已隔离。
- 本地证据：提交 `9852387`，通知定向 `12 passed`、完整后端非集成 `2236 passed`，改动文件 Ruff、格式和 diff-check 通过；详见 [`notification-acceptance-redaction-2026-08-25.json`](evidence/notification-acceptance-redaction-2026-08-25.json)。
- 发布边界：未连接真实 SMTP、企业微信或钉钉供应商，本模块不关闭真实投递、供应商侧送达、限流和重复投递门禁。
- 追加提交 `8fd129b` 补齐通知 Smoke 对 `access_token`、`sign` 和 URL 用户信息的错误脱敏；定向 `12 passed`、后端非集成 `2236 passed`，详见 [`notification-smoke-redaction-2026-08-25.json`](evidence/notification-smoke-redaction-2026-08-25.json)。

## 2026-08-25 Windows 已认证浏览器冒烟复核

- 复用当前已登录的 Windows 浏览器会话，实际加载统计看板、工作台概览、我的待办、用例管理、执行记录、测试套件、存储管理和 API 契约资产；页面均保持在业务页，未回到登录页，用户菜单显示为 `admin`。
- q19 Backend 最近 5 分钟日志未发现 `Traceback`、`ERROR` 或 `invalid input value for enum`；这轮验证确认前端到远端后端的已认证页面链路可用。
- 脱敏证据见 [`windows-browser-smoke-2026-08-25.json`](evidence/windows-browser-smoke-2026-08-25.json)。本轮复用了已有会话，未记录密码/Token；文件传输、报告导出、浏览器矩阵和 Web 低代码仍沿用既有完整 readiness 证据，不因本轮页面冒烟重复通过。

## 2026-08-25 P1-E.4 性能多节点分片容量校验

- 多节点压测现在先按节点数拆分总负载，再用每个节点的 `max_vus`、执行器能力和出口 allowlist 校验分片；总负载 10、两台节点上限 6 时生成 5/5 分片，上限 4 时返回 400 且不写入运行记录。
- 代码审查未发现问题；性能 API `72 passed`、性能服务/Worker `24 passed`、完整后端非集成 `2231 passed`，Ruff 和 `git diff --check` 通过。脱敏证据见 [`performance-shard-capacity-2026-08-25.json`](evidence/performance-shard-capacity-2026-08-25.json)。
- 这只完成本地分片校验，不代表真实 Kubernetes 多节点调度、生产 Prometheus/MinIO 生命周期或跨主机恢复已通过。
- q19 已按 `ca79937` 重建并启动，迁移 `20260824_0065 (head)`、Backend `200`、Prometheus 4 targets `up`、Celery 2 节点 `pong`；重启后 Backend 无 enum/Traceback/ERROR。脱敏证据见 [`q19-performance-shard-deployment-2026-08-25.json`](evidence/q19-performance-shard-deployment-2026-08-25.json)。

## 能力与证据索引

| 能力域 | 当前结论 | 主要证据 | 未关闭边界 |
|---|---|---|---|
| Windows API/Web | 本地与 q19 证据已形成，当前账号页面冒烟通过 | [`windows-full-readiness-2026-08-24.json`](evidence/windows-full-readiness-2026-08-24.json)、[`windows-browser-smoke-2026-08-25.json`](evidence/windows-browser-smoke-2026-08-25.json)、[`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json) | GraphQL/WebSocket/流式 gRPC、完整报告和目标发布环境仍需验收 |
| Web Worker/录制 | q19 持久 Worker、Chromium/Firefox/WebKit 录制和跨 API 停止快照已验证 | [`q19-web-recorder-readiness-2026-08-24.json`](evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recording-cross-api-2026-08-24.json`](evidence/q19-web-recording-cross-api-2026-08-24.json) | Linux/Xvfb、跨副本和目标部署拓扑仍需独立复验 |
| Android | 代码、配置配对、Worker registry、扫描回调、租约控制和 APK 选择传递已完成；真实 APK 上传和设备执行仍待验收 | [`android-worker-scan-2026-08-25.json`](evidence/android-worker-scan-2026-08-25.json)、[`android-control-lease-2026-08-25.json`](evidence/android-control-lease-2026-08-25.json)、[`android-apk-selection-2026-08-25.json`](evidence/android-apk-selection-2026-08-25.json) | 继续完成真实 APK 包名识别、低代码、录屏、专项任务和事件/报告回传 |
| 性能 | P1-E.1～P1-E.4 本地闭环完成，q19 已按最新提交重建 | [`q19-performance-worker-smoke-2026-08-24.json`](evidence/q19-performance-worker-smoke-2026-08-24.json)、[`performance-shard-capacity-2026-08-25.json`](evidence/performance-shard-capacity-2026-08-25.json)、[`q19-performance-shard-deployment-2026-08-25.json`](evidence/q19-performance-shard-deployment-2026-08-25.json) | 真实 Kubernetes 多节点、生产 Prometheus、MinIO 生命周期和跨主机恢复 |
| 通知 | 本地 SMTP 链路已验证 | [`notification-smtp-link-check-2026-08-24.json`](evidence/notification-smtp-link-check-2026-08-24.json) | 真实供应商送达、重试、限流和重复投递 |
| 外部缺陷平台 | 本地适配器和脱敏逻辑已实现 | [`docs/capability-baseline-2026-08-07.md`](capability-baseline-2026-08-07.md) | 临时项目、权限、创建/去重/状态同步和清理 |

## 当前本地质量证据

- P1-E.3 性能运行记录清理：后端定向 `24 passed`，完整非集成后端 `2226 passed`，3 个受影响测试文件独立运行 `3 passed, 0 failed`。
- 前端全量 Vitest：`66 files / 265 tests passed`；`vue-tsc --noEmit` 和生产构建通过。
- 本次模块的 Ruff、格式检查和 `git diff --check` 通过。
- 这些结果证明当前代码变更的本地质量，不替代下表中的外部环境门禁。

## 发布前复验顺序

1. 在 Windows 上使用当前有效账号重跑完整 API/Web smoke，并记录同一提交 SHA。
2. 先统一 Windows Agent 与 q19 Backend 的 Redis 实例、DB 和注册前缀，确认 `/devices/workers` 能看到在线 Worker；再执行 `scripts/windows-android-acceptance.ps1` 并完成 Android 单设备链路，任何 `offline`、`unauthorized`、无 Worker 或无设备结果都保持阻塞。
3. 在目标 Linux/Kubernetes 环境执行 `scripts/performance-environment-smoke.py`，补齐真实节点、目标服务、Prometheus、取消和资源采样证据。
4. 注入不落库的临时通知供应商凭据，按渠道取得供应商侧送达回执后清理目标和凭据。
5. 使用临时外部缺陷项目验证创建、重复识别、状态同步、权限、错误脱敏和清理。
6. 汇总新的带日期证据后，再更新本文件、能力矩阵、Q18 状态和发布说明；在此之前保持“部分实现/待环境验收”。

## 禁止事项

- 不把 `offline` 设备、无凭据跳过、回环 SMTP、localhost 目标或 Docker Compose 契约测试写成生产通过。
- 不在仓库、证据 JSON、日志或截图中保存密码、Token、Webhook、MinIO 密钥或外部平台凭据。
- 不用 GitHub Actions 绿灯替代真实设备、真实供应商和真实目标服务证据；当前 Actions 触发策略以 [`docs/ci-workflows.md`](ci-workflows.md) 为准。
