# Q18 实施记录

## 2026-08-25 参考导航开发计划同步

- [x] 在主路线图新增当前跟踪版计划，明确五组导航、入口职责、模块边界、验收出口和剩余开发顺序。
- [x] 同步 `Task.md`、`MEMORY.md` 和 Q18 最新状态，统一记录旧 URL 兼容、真实环境验收边界和单模块交付门禁。
- [x] 计划顺序固定为 Windows API/Web 复核、Android 单设备、真实通知、外部缺陷平台、生产性能和发布收口；未提供真实环境时只推进可独立验证的代码/回归，不修改通过结论。

## 2026-08-25 P0-A Windows 本地 E2E 回归修复

- [x] 修复中文登录按钮自动空格选择器，补齐 `/workbench/overview` 和 `/defects` 的隔离 mock。
- [x] 代码审查确认未改变生产认证、路由或执行逻辑；登录定向 `3 passed`、运行详情定向 `1 passed`、全量 Playwright `12 passed`。
- [x] 前端 Vitest `66 files / 265 tests passed`，type-check、生产构建和 `git diff --check` 通过。
- [ ] Windows 真实 API/Web smoke 仍需当前有效账号；mock 回归不替代真实认证、文件传输和报告导出证据。

## 2026-08-25 P0-B Android 单设备验收前置复核

- [x] 运行 `scripts/windows-android-acceptance.ps1`，确认 `adb.exe` 和 ADB 命令正常响应。
- [x] 脱敏报告 `.local-run/android-acceptance-current-20260825.json` 记录 `online=0, unauthorized=0, offline=1, other=0`；脚本在必需检查失败后不再执行设备命令，也不创建 Android 运行任务。
- [x] 代码审查确认离线状态的失败边界和提示正确，没有把诊断通过误记为真机执行通过。
- [ ] ADB 恢复为 `device` 后，继续验证配置配对、Worker 心跳、扫描、预约、截图、APK 包名、Android 低代码、专项任务和结果证据。

## 2026-08-25 工作台任务状态枚举隔离修复

- [x] 根据 q19 运行日志定位并修复工作台跨域状态过滤：`TestRun`/套件/计划不再接收 Android `stopped` 或性能 `cancelled` 等不属于自身 enum 的值。
- [x] 无效状态交集会生成无匹配查询，避免空集合被当作未过滤；重试能力按 case/suite/plan/android/performance 分域判断，并保留 case `skipped` 策略。
- [x] 审查和回归：工作台定向 `8 passed`，完整后端非集成 `2229 passed`，Ruff、差异检查通过；无模型、迁移、权限或执行器改动。
- [ ] 远端 q19 需要基于新提交重建后，重新验证 `/workbench/overview` 和任务中心；当前旧容器日志不作为修复通过证据。

## 2026-08-25 P1-F 本地发布收口状态

- [x] 新增 [`docs/release-status-2026-08-25.md`](release-status-2026-08-25.md)，统一维护当前候选的能力证据、真实环境边界、复验顺序和禁止事项。
- [x] 能力矩阵、Q18 最新状态、用户操作手册、Task、路线图和 MEMORY 已指向同一发布状态索引；文档明确区分本地质量证据与真实环境验收。
- [ ] Android 真机、生产性能多节点/MinIO、真实通知供应商和外部缺陷平台仍待目标环境证据；本次不将缺失项标记为通过。

## 2026-08-24 N6.10 q19 性能节点与真实短压验收

- [x] 性能预检通过：Backend `/health`、k6/Locust/gRPC/JMeter、`worker-a` online 和 `performance.worker-a` 队列均正常。
- [x] 临时项目执行 1 VU、5 次迭代的 k6 真实短压，目标为 q19 `http-target`，运行状态 `success`，产生 1 条 `performance-worker` 采样；Prometheus ready，三个 ATP targets 均为 `up`。
- [x] 临时项目、测试、运行和脚本对象已清理；证据见 [`q19-performance-worker-smoke-2026-08-24.json`](evidence/q19-performance-worker-smoke-2026-08-24.json)。
- [ ] Android Worker/真机、通知和外部缺陷平台仍待独立环境证据；当前 Android 设备为 offline，未创建 Android 运行任务。

## 2026-08-24 N6.11 通知链路本地安全验收

- [x] 回环 SMTP sink 通过生产通知入口完成 12 项检查，覆盖 envelope、收件人规范化、MIME、显示名和六项性能摘要字段。
- [x] 报告固定为 `local_link_only`，未触达真实邮箱或记录凭据；证据见 [`notification-smtp-link-check-2026-08-24.json`](evidence/notification-smtp-link-check-2026-08-24.json)。
- [ ] 真实 SMTP/企业微信/钉钉及外部缺陷平台仍待目标环境证据。

## 2026-08-24 N6.12 Android Backend/Agent 配置配对门禁

- [x] 新增无泄漏配置配对校验器，检查共享 PostgreSQL/Redis/MinIO/密钥、`ADB_SCAN_MODE`、队列、Worker 队列和注册前缀。
- [x] Windows Android Worker doctor/startup、Make、CI、pre-commit 和 deployment readiness 已接入；示例配置配对通过，定向回归 `55 passed`。
- [ ] 真实网络、Worker 心跳和 Android 真机执行仍待目标环境证据。

## 2026-08-24 N6.9 Firefox/WebKit 与跨 API 副本录制验收

- [x] Linux Worker 模式的 WebKit headed 启动挂起已修复为无头启动；Windows/local 与 Firefox 的 headed 行为保持不变，并补充启动参数回归。
- [x] 代码审查和定向回归通过：后端 Web Recording/传输/smoke/部署目标 `45 passed`，Ruff 和 `git diff --check` 通过，提交 `41ff87a` 已推送。
- [x] q19 Firefox 与 WebKit 均完成真实录制、2 步快照、PNG 截图、停止、三类证据 URL 和停止后查询；跨 API 副本读取共享 Redis 停止快照通过。证据见 [`q19-web-recording-firefox-2026-08-24.json`](evidence/q19-web-recording-firefox-2026-08-24.json)、[`q19-web-recording-webkit-2026-08-24.json`](evidence/q19-web-recording-webkit-2026-08-24.json) 和 [`q19-web-recording-cross-api-2026-08-24.json`](evidence/q19-web-recording-cross-api-2026-08-24.json)。
- [x] 临时项目、18 个 MinIO 录制对象和第二 API 副本均已清理。
- [ ] Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待后续环境证据。

## 2026-08-24 N6.8 Web 录制证据链交付与 q19 验收

- [x] 录制会话采集 Trace、HAR、Console、页面异常、请求/失败请求/错误响应事件；URL、请求头、Cookie、请求体、步骤和错误文本在持久化前脱敏，响应正文不落盘。
- [x] 停止录制后将 Trace、HAR、运行报告上传 MinIO；独立 Worker 模式在 Redis 保留脱敏最终快照，停止后可查询，重复停止幂等，结束后截图返回 409；前端显示证据入口和网络事件预览。
- [x] 代码审查修复 JSON 凭据和完整 URL 文本脱敏边界；本地后端目标 `45 passed`，前端 Web Recorder `3 passed`，type-check/build、Ruff/diff-check 通过。
- [x] q19 使用 `9e93379` 重建并重启 `web-recorder`，首次和重启后均通过 Worker 注册、2 步快照、PNG 截图、停止、3 类证据和停止后报告查询；测试项目及 6 个录制对象已清理。证据见 [`q19-web-recording-evidence-2026-08-24.json`](evidence/q19-web-recording-evidence-2026-08-24.json) 与 [`q19-web-recording-evidence-restart-2026-08-24.json`](evidence/q19-web-recording-evidence-restart-2026-08-24.json)。
- [ ] Firefox/WebKit、跨 API 副本、Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待后续环境证据。

## 2026-08-24 N6.7 q19 独立 Web 录制 Worker 持久部署与真实录制验收

- [x] q19 Compose 新增独立 `web-recorder` 服务，Backend 固定使用 `WEB_RECORDER_MODE=worker`，共用 Redis 路由前缀；Xvfb `:99` 启动会清理残留锁并等待 socket，就绪后使用 `init: true` 回收 Chromium 子进程。
- [x] 本地 API/传输/smoke/部署契约回归 `61 passed`，Ruff 和 `git diff --check` 通过；代码审查修复 Xvfb 重启锁和 Chromium 僵尸进程两个问题，提交 `3ddf4f1`、`7a94e62`、`dfe86b1` 已推送。
- [x] q19 真实临时项目完成 Worker 注册、Chromium 录制、2 步快照、PNG 截图、停止、项目删除和 Worker 重启恢复；Backend `/health` 与 Prometheus targets 正常，`active_sessions=0`、容器 `zombie_count=0`。
- [x] 脱敏证据归档为 `docs/evidence/q19-web-recorder-readiness-2026-08-24.json`、`docs/evidence/q19-web-recorder-restart-readiness-2026-08-24.json` 和 `docs/evidence/q19-web-recorder-init-readiness-2026-08-24.json`。
- [x] N6.7 基础 Worker 部署范围已完成；Trace/HAR/Console/网络日志/运行报告证据链在 N6.8 单独完成。

## 2026-08-24 N6.6 q19 持久通用 Web Worker 部署与恢复验收

- [x] q19 Compose 新增独立 `worker` 服务，固定监听 `default,maintenance`；性能 Worker 保持 `performance.worker-a,performance`，Prometheus 新增 `atp-worker:9091` target。
- [x] 本地部署契约回归 `24 passed`，YAML、代码审查和 `git diff --check` 通过；提交 `f1473d2` 已推送。
- [x] q19 真实重建后 Celery ping、队列隔离、服务健康和 Prometheus targets 通过；首次 `run 4` 与 Worker 重启后的 `run 5` Web 低代码下载均通过，清理均通过。
- [x] 脱敏证据归档为 `docs/evidence/q19-persistent-web-worker-readiness-2026-08-24.json`、`docs/evidence/windows-persistent-web-worker-readiness-2026-08-24.json` 和 `docs/evidence/windows-persistent-web-worker-restart-readiness-2026-08-24.json`。
- [ ] 独立录制 Worker、Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待后续环境证据。

## 2026-08-24 N6.5 q19 真实迁移与 Web Worker 临时验收

- [x] 从最新 `main` 构建 q19 Backend、性能 Worker、Beat 和迁移镜像，目标数据库真实执行 `20260814_0059 -> 20260824_0065`，服务健康且 Backend `/health` 返回 HTTP 200。
- [x] 通过项目删除 API 回归：临时项目返回 `204`，项目、环境、模块残留均为 `0`；确认项目资源级联迁移已在目标数据库生效。
- [x] 启动临时默认队列 Worker 完成 Web 低代码下载执行 `run 3`，下载对象回传和清理通过；验收后移除临时 Worker。脱敏证据见 `docs/evidence/q19-migration-web-worker-readiness-2026-08-24.json` 与 `docs/evidence/windows-web-worker-readiness-2026-08-24.json`。
- [x] 将通用 Web Worker 加入 q19 持久 Compose/部署编排并验证注册、队列隔离、低代码执行和重启恢复；Android 因 ADB offline 本轮未执行，真实性能节点、通知和外部缺陷平台仍待独立证据。

## 2026-08-24 N6.4 Windows 完整 API/Web 验收与项目删除级联修复

- [x] 完整 Windows smoke 通过管理员登录、认证读接口、Web Recording 状态、Playwright `12 passed`、Chromium/Firefox/WebKit 页面矩阵、47 bytes 文件上传/清理和 HTML/JUnit 报告导出；脱敏证据归档为 `docs/evidence/windows-full-readiness-2026-08-24.json`，必需失败数为 `0`。
- [x] 代码审查修复项目删除被 `environments_project_id_fkey` 阻断的问题：补齐项目直接资源外键 `CASCADE`，环境变量改为 `CASCADE`，计划环境引用改为 `SET NULL`，新增 `20260824_0065` 及回归契约。
- [x] 项目路由/迁移定向 `34 passed`，迁移目录 `66 passed`，Alembic head `20260824_0065`，Ruff 和 `git diff --check` 通过；远端 q19 临时验收项目/环境已清理。
- [x] `20260824_0065` 已在 q19 目标数据库真实升级并验证项目删除回归；Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待独立环境证据；严格 readiness 仍因 Windows 缺少 Docker Compose 工具未通过。

## 2026-08-24 N6.3 Windows 发布 readiness 与远端依赖恢复

- [x] 远端复核定位到 Redis 6379 的旧 Docker 代理/容器网络残留；仅清理 Redis 异常容器状态并保留挂载数据目录，重启 Docker 网络层后恢复 6379 发布，再按 q19 compose 项目补齐 PostgreSQL、Redis、MinIO、迁移和 Backend 依赖。
- [x] Windows 最小 smoke 通过：`scripts/windows-local-smoke.ps1 -SkipPlaywright -SkipBrowserMatrix -SkipFileTransfer -SkipReports -SkipLiveLogin` 的 doctor、Backend `/health`、Frontend `/login`、PostgreSQL/Redis/MinIO、ADB、k6/Locust/gRPC 和性能队列检查通过；脱敏报告归档为 `docs/evidence/windows-release-readiness-2026-08-24.json`。
- [x] `scripts/validate-deployment-readiness.py` 默认仓库检查通过；严格模式仅因当前 Windows 缺少 Docker Compose 命令失败，保留为本机工具缺口，不修改代码绕过门禁。
- [ ] 完整管理员登录、认证读接口、Playwright/浏览器矩阵、文件上传、报告导出、Android Worker/真机、性能节点、通知和外部缺陷平台仍未由本轮命令覆盖，必须在后续环境证据中单独确认。

## 2026-08-24 N6.2 发布文档、能力矩阵与操作手册收口

- [x] 将产品导航、能力矩阵、用户操作手册、Task 和 MEMORY 统一到五组导航：工作台、测试能力、测试资产、智能中枢、系统；保留原有 URL、API 和领域页面兼容。
- [x] 在能力矩阵中补充远程工具箱、配置中心和发布质量门禁，明确区分“本地代码/自动化证据”和“真实环境验收”；配置中心记录 `/system/config`、脱敏聚合、版本差异、影响提示和精确 `ROLLBACK` 边界。
- [x] 在用户手册中补充工作台/任务中心、远程工具箱和配置中心的入口、权限、脱敏和回退操作说明，并修正旧的七组导航描述。
- [x] N6.1 浏览器回归证据已归档：配置中心定向 E2E `2 passed`、全量 Playwright `12 passed`，前端 Vitest `65 files / 258 tests passed`，type-check 和生产构建通过。
- [ ] 真实配置数据、数据库迁移、生产密钥、Android/Windows Worker、性能节点、通知和外部缺陷平台仍需按目标环境生成带日期证据；本地 mock 和协议桩不能替代发布验收。

## 2026-08-11 归档项目配置只读补充

- 项目编辑接口改用可写项目依赖，归档项目的配置修改与测试资产写入保持一致，统一返回 409；前端禁用归档项目编辑按钮并显示恢复提示。
- 增加路由契约和项目列表回归，后端项目相关 `36 passed`，前端项目列表 `4 passed`；`vue-tsc` 与生产构建通过。

## 2026-08-11 Windows Web 低代码冒烟入口

- `scripts/windows-local-smoke.ps1` 新增 `-WebCaseId`、`-RequireWebLowcode`、`-RequireWebDownload` 和 `-WebRunTimeoutSeconds`，可从已认证的 Windows 会话触发已有 Web 低代码用例并轮询执行状态。
- 运行完成后，脚本会从 `/runs/{run_id}` 的步骤结果中检查 download 动作是否返回对象引用；不传用例 ID 时保持跳过，不会伪造真实页面或下载结果。
- 回归：PowerShell 脚本解析通过，`backend/tests/scripts/test_windows_local_contract.py` `4 passed`，Ruff 和 `git diff --check` 通过。

## 2026-08-11 Windows Web 下载验收夹具

- 新增 `frontend/public/atp-windows-download.html` 和 `atp-windows-smoke.txt`，页面提供稳定的 `#atp-download-link`，用于构造真实浏览器下载而不依赖公网业务站点。
- 使用 `goto` + `download` 低代码步骤即可配合 `-WebCaseId -RequireWebDownload` 验证执行结果中的 MinIO 对象引用；新增 Playwright 回归 `1 passed`。
- 夹具不替代真实 Worker、MinIO、执行队列和下载对象验收，相关证据仍需在 Windows 本地服务运行后产生。

## 2026-08-11 Windows Web 下载自包含冒烟

- `-SeedWebDownloadCase` 为没有现成用例的 Windows 环境提供显式自包含入口：使用管理员会话创建临时 Web 项目、模块和低代码用例，自动完成提交审核/批准为 `active/approved`，使用浏览器网络守卫允许的内联 `data:` 下载页面后触发真实执行；不会为冒烟放开 loopback/内网 HTTP 访问。
- 运行进入终态后删除临时项目，并通过存储治理接口清理截图、录像和下载对象；轮询超时或状态未知时保留项目/对象并把项目 ID/运行 ID写入结果，避免清理仍可能执行的资源。该模式与 `-WebCaseId` 互斥。
- 首次环境没有历史运行记录时，建议使用 `-SkipReports`；真实下载对象仍必须由 Worker/MinIO 运行链路产生，不能由脚本直接伪造。
- 实测：Windows 聚焦 seed 冒烟最近一次通过，临时项目 8/用例 4/运行 4 产生 1 个下载对象，清理阶段删除 1 个环境和 5 个运行产物；此前失败尝试的 6 个遗留对象也已完成补偿清理。

## 2026-08-11 数据集页面 AI 生成

- 新增 `POST /datasets/ai-generate`：使用项目绑定的 AI 配置按业务要求生成合成 JSON 行；已有数据集使用持久化 Schema，新数据集无 Schema 时从结果推断字段类型。
- AI 生成不直接提交数据库，前端将结果回填到 DatasetLibrary 编辑器，用户确认后复用普通保存流程，确保版本历史和校验策略一致。
- 服务层过滤非对象数组、解析模型 JSON 围栏/`rows` 包装、限制最多 200 行和 256KB；调用配额使用独立 `ai_dataset_generation` 能力名，敏感信息不写入提示词或响应审计。
- 回归：`backend/tests/api/test_datasets_crud.py` 与 `backend/tests/services/test_ai_dataset_generator.py` 共 `24 passed`；`DatasetLibrary.spec.ts` `7 passed`；前端 type-check、后端 Ruff/format 通过。
- 合并回归：后端非集成 `1865 passed`、Python 3.12 覆盖率 `82.05%`，256 个测试文件单独运行 `256 passed`；前端 `41 files / 167 tests passed`，coverage statements/branches/functions/lines 为 `33.13% / 28.49% / 25.73% / 34.52%`，type-check/build 通过。

## 2026-08-11 Mock 规则 AI 生成

- Mock 页面新增独立的“AI 生成 Mock”流程；原有“AI 生成用例”仍跳转到用例生成抽屉，两个能力入口明确区分。
- `POST /mock-rules/ai-generate` 接受项目、可选参考规则、生成数量和自然语言要求，服务端校验 editor 权限、AI 配置和参考规则项目隔离；输出只包含可编辑规则草稿，不直接写库。
- 前端先展示可编辑 JSON 预览，用户确认后逐条调用普通 Mock 创建接口，保存后刷新列表；生成失败、预览 JSON 无效和保存失败均有明确提示。
- 服务层对模型输出做对象数组解析、方法/路径/状态/延迟规范化、条件值字符串化和 256KB 限制，提示词明确禁止密钥、Cookie、Token 和真实个人信息。
- 定向回归：后端 Mock AI 服务/API `9 passed`，前端 Mock 页面 `5 passed`；`vue-tsc --noEmit`、Ruff check/format 通过。

## 2026-08-11 Worker 测试隔离收口

- `backend/tests/conftest.py` 对历史测试替换的公共模块实行缺失字段补齐，不覆盖测试自己的 hard-set 值；模块收集前和每个测试启动前都会再次刷新，避免 `sys.modules` 污染跨文件传播。
- 完整 Worker 测试套件 `backend/tests/worker` 已验证 `415 passed`；此前 8 个 MinIO/数据库测试桩隔离失败不再复现。该验证与全仓非集成 `1865 passed`、独立测试 `256 passed` 一致。

## 2026-08-11 Android Agent 扫描状态回传

- `POST /devices/scan` 在 `ADB_SCAN_MODE=worker` 时使用 `ignore_result=False` 投递到 `mobile_special`，返回 Celery task ID；新增状态接口读取 queued/running/completed/failed 并返回 Worker 写回的设备列表。
- Windows Android Worker 启动脚本自动注入 `ANDROID_WORKER_ID`；新增 Redis TTL 注册服务、心跳任务、`GET /devices/workers` 接口和设备页在线提示，用于区分“本机 Agent 在线”和“仅有数据库设备记录”。
- 设备页新增最多 10 秒轮询和明确的排队/超时/失败提示；`local` 模式仍保持同步扫描。Beat 周期扫描仍忽略结果，避免产生无用的结果键。
- 定向回归：设备/Android Worker 后端 API、任务、Redis 注册和启动档案 `23 passed`，前端设备页 `6 passed`；合并后完整后端 `1853 passed`、Python 3.12 覆盖率 `82.01%`，255 个测试文件独立运行通过，前端 `40 files / 164 tests passed`、type-check/build 通过。

## 2026-08-11 Web 录制 Worker 服务化

- 增加 `backend/app/services/web_recording_transport.py`，用 Redis 保存 Worker 心跳和会话所有权，通过短命令回复队列路由 start/snapshot/screenshot/stop；会话轮询会刷新路由 TTL，避免录制时间较长时元数据提前过期。
- 增加 `backend/app/web_recording_worker.py`，Worker 内部持有 Playwright 会话并通过心跳报告容量；API 仍负责认证、项目权限、录制步骤和 Web 资产持久化。
- 增加 Compose profile、Helm Deployment、Windows `local-dev.cmd` 托管和启动配置字段；默认 local 行为不变，worker 模式需要 API/Worker 共享 Redis，Linux 需要 Xvfb。
- 本轮已补充传输层、API 远程模式、Worker 生命周期、部署契约和 Windows 启动脚本回归；后端非集成 `1839 passed`、Python 3.12 覆盖率 `82.12%` 门禁通过，253 个测试文件单独运行通过，前端 `40 files / 161 tests passed`、type-check/build 通过；真实 Linux/Xvfb、Firefox/WebKit、跨副本 E2E 仍需外部环境证据。

最新前后实现对比和剩余任务统一见 [`docs/q18-latest-status-2026-08-07.md`](./q18-latest-status-2026-08-07.md)。

## 2026-08-11 继续开发

### 三方 OpenAI 兼容模型配置

- 新增 `openai_compatible` provider，明确区分原生 Ollama、OpenAI 官方和三方 OpenAI-compatible 服务。
- 三方配置必须填写 Endpoint；模型列表从 `{Endpoint}/models` 拉取，生成调用沿用 `{Endpoint}/chat/completions`，API Key 仅用于请求头并加密存储。
- AI 模型配置 UI 增加协议选项、Endpoint 用途说明和兼容服务模型拉取入口，模型能力提示仍只作为辅助信息。
- 定向回归：`test_ai_case_llm_client.py`、`test_ai_model_discovery.py`、`test_ai_llm_configs_api.py` 共 `31 passed`。

- Android 设备兼容矩阵从共享会话串行执行改为每个子运行独立 `AsyncSessionLocal`、独立设备租约，并通过 `asyncio.gather` 并行调度；父运行保存逐设备状态、耗时和错误摘要。
- 运行详情页新增 Android 设备矩阵结果卡片，展示总数、通过/失败/异常统计、设备状态、耗时和错误，并支持跳转子运行。
- HTML/PDF 单运行报告和 JUnit 导出同步展示设备级矩阵结果，每台设备独立输出状态、耗时和错误。
- Web 低代码执行器和录制器接入共享 Playwright `BrowserContext` 路由守卫，逐请求校验 HTTP/HTTPS/WS/WSS 的公网地址；重定向、页面子资源和录制过程中的内网请求会被中止，并保存脱敏阻断证据。
- 本轮验证：后端非集成 `1827 passed`，Python 3.12/3.14 覆盖率门禁分别为 `82.50%`/`82.05%`，前端 Vitest 已更新为 `40 files / 161 tests passed`，coverage statements/branches/functions/lines 为 `31.94% / 27.09% / 24.94% / 33.21%`，`vue-tsc --noEmit` 和生产构建均通过；真实设备池抢占、故障恢复仍待外部设备验收。

## 2026-08-10 文档同步

- 本地后端非集成回归已复核为 `1724 passed`；前端 Vitest 已复核为 `37 files / 146 tests passed`，前端类型检查与生产构建通过。
- Windows 主线新增 `local-dev.cmd doctor`，覆盖本地配置、运行时、端口、PostgreSQL/Redis/MinIO、ADB 和性能执行器检查；新增 `scripts/android-network-doctor.ps1`，保留 Bash 版本兼容 Git Bash/WSL。
- Windows 全量本地冒烟新增 `scripts/windows-local-smoke.ps1`：真实后端健康、管理员登录和认证读接口通过，Playwright mock E2E `9 passed`，Chromium/Firefox/WebKit 登录页矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务均通过，并生成 `.local-run/windows-smoke-*.json` 脱敏报告；该历史冒烟记录保留当时的 Android/k6/Locust 告警，当前 k6/Locust 已通过独立真实平台执行验收。
- Windows 冒烟新增 Android Worker 注册校验：当 `ADB_SCAN_MODE=worker`、配置 `ANDROID_WORKER_ID` 或使用 `-RequireAndroid` 时，必须从 `/api/v1/devices/workers` 看到在线 Agent；普通 Web/API 本地模式不增加必需检查。
- 同一条件下冒烟会调用 `POST /api/v1/devices/scan`，对 Worker 返回的 task ID 轮询 `GET /api/v1/devices/scan/{scan_id}`，验证最终 `completed/failed` 回调；没有真实设备时仍可验证队列与状态链路，但不会伪造设备数据。
- 本轮修复冒烟边界：相对 `ReportPath` 统一按项目根目录解析；无历史执行记录时报告检查必需失败；文件上传响应异常但已产生对象引用时仍执行补偿清理。修复后 PowerShell 解析、契约测试和完整 Windows 冒烟再次通过。
- 本次同步不把本地 mock、协议桩或浏览器缓存烟测当作真实发布验收；Android/iOS、Linux/Kubernetes 性能节点、Firefox/WebKit Worker、Prometheus、外部通知和 Provider/Consumer 规格仍保留为外部任务。
- 下一阶段按以下顺序推进：先完成 Q17-04 性能隔离栈验收，再并行推进真实设备、Web 专用 Worker、API 契约联调和性能观测/通知验收，最后统一归档发布证据。

## 本轮补齐内容

- API：受限表达式断言、统一执行结果契约、数据集笛卡尔积/Pairwise 组合、输入脱敏、导入预览/冲突/事务回滚。
- Web：项目文件上传下载、视觉基线与差异、POM 执行、浏览器矩阵独立会话并发、定位器候选建议与用户确认写回。
- Android：设备兼容矩阵、设备/日志产物、可选录屏、旋转/权限/网络/前后台系统动作。
- 性能：自动阶梯、目标 Prometheus 指标采样边界、JMeter HTML 报告附件。

这些能力均已增加定向回归测试；真实 Android、macOS/iOS、Prometheus、Firefox/WebKit/JMeter Worker 仍按最新对比文档列为外部验收项。

更新时间：2026-08-11

这份记录用于补充 `docs/implementation-plan-2026-Q18-capability-expansion.md` 和
`docs/capability-baseline-2026-08-07.md`，把“代码已完成”和“真实环境已验收”分开记录。

## 本轮已实现

| 模块 | 前置状态 | 本轮实现 | 验证证据 | 当前状态 |
|---|---|---|---|---|
| API 前置/后置 | 没有 API 专用脚本入口 | 增加受限动作 DSL：`set_variable`、`delete_variable`、`extract`、`assert`；仅能操作请求上下文/响应数据，不执行 Python 或 JavaScript | `backend/app/services/api_hooks.py`；`tests/services/test_api_hooks.py`；`tests/worker/test_http_family_executors.py`；56 项定向测试通过 | 待真实接口验收 |
| API 契约兼容性 | 没有 Provider/Consumer 或 Schema diff | 增加 OpenAPI/Swagger 路径、方法、参数、请求体、响应状态码和响应 Schema 比较；增加 JSON Schema 比较、项目内 `$ref` 展开、Provider/Consumer 资产 CRUD/版本化和资产间比较 | `POST /api/v1/projects/{project_id}/api-contracts/compare`、`compare-assets`；`backend/app/services/api_contracts.py`；`20260807_0052`；7 项新增定向测试通过 | 待真实规格样本与外部引用策略验收 |
| Android 设备调度 | 设备只有在线/离线状态，移动任务没有占用锁 | 增加 `device_leases`、获取/心跳/释放、过期回收；移动 Worker 执行前自动占用、结束后释放；心跳响应不返回令牌 | `20260807_0047_add_device_leases.py`；`tests/api/test_devices_routes.py`；`tests/worker/test_tasks_mobile_special_dispatch.py`；26 项定向测试通过 | 待真实 ADB 并发验收 |

## 前后对比摘要

| 能力 | 之前 | 现在 |
|---|---|---|
| API 请求编排 | Cookie、JSON/XML/multipart、SSE 等主链已存在，但没有安全的生命周期动作 | 可在每个 API 步骤保存 JSON 前置/后置动作，动作失败会让步骤进入错误状态并保留摘要 |
| API 契约 | 只能导入规格生成/导入用例，不能判断新旧规格是否破坏兼容 | 可以在项目权限范围内提交两份规格并返回兼容标记、破坏项、警告和位置 |
| Android 设备 | 并发任务可能抢到同一设备 | 数据库租约和 Worker 自动释放形成互斥；过期租约由 Beat 任务回收 |

## 追加进度：Web 元素库与页面对象模型

- 新增 `WebElementAsset` 与 `WebPageObject` 数据模型，以及迁移 `20260807_0049_add_web_assets.py`。
- 新增项目级元素库/POM CRUD API：元素定位器、备用定位器、页面 URL、版本、维护人和失效记录；页面对象支持元素引用与公共操作定义，并校验项目边界和编辑权限。
- 新增系统页面 `/system/web-assets`，支持按项目切换、元素/POM 列表、新建、编辑、删除和失效状态查看；菜单、路由和中英文文案已接入。
- 低代码编辑器新增项目元素资产选择器；Worker 执行时校验资产项目归属，主定位器失败后按备用定位器重试，并将失败原因写回资产记录。
- 当前边界：绑定项目的录制默认写入资产、POM 公共操作执行和定位器修复建议闭环已接入；真实浏览器录制 E2E 仍待验收。
- 验证证据：`backend/tests/api/test_web_recordings.py`、`backend/tests/api/test_web_assets_routes.py`、`backend/tests/worker/test_web_lowcode_executor.py`；最终质量数字见文末核验章节。

## 尚未完成

- API：Provider/Consumer 真实规格联调、OAuth2/Digest 等高级认证；外部/远程 `$ref` 的本地发布策略已完成，真实规格联调仍待外部环境。
- Web：关键 UI/E2E，以及真实 Firefox/WebKit Worker 验收。
- Android/iOS：真实设备验收、设备池并行和 iOS/Appium Worker；来电等外部系统事件也需要设备环境。
- 性能：真实 Prometheus、JMeter/Firefox/WebKit Worker、外部通知渠道和 Linux/Kubernetes 节点验收。
- 发布收口：安全扫描和带日期的真实环境证据仍需在目标发布环境补齐。

## 追加进度：JMeter

在性能执行器中新增 `jmeter` 能力：上传 `.jmx`，Worker 以非 GUI 模式执行并解析 CSV JTL，统一产出 RPS、P95/P99、错误率、请求数、收发字节和阈值结果。`backend/Dockerfile.worker` 已加入 Java/JMeter 5.6.3；解析回归位于 `tests/services/test_performance_jmeter.py`，与现有性能 API/执行器回归合计 63 项通过；仍需要配置 `PERFORMANCE_EXECUTORS=k6,locust,grpc,jmeter` 后做真实节点验收。

随后增加性能多节点分片：压测触发接口支持 `performance_node_ids`，按 `vus`/`users`/`concurrency` 均匀分配到子运行；父运行通过 `parent_run_id` 汇聚各节点 RPS、请求数、P95/P99、错误率和字节数，全部子运行结束后自动更新父运行状态。新增迁移 `20260807_0048_add_performance_run_shards.py`，前端运行弹窗已改为多选节点。

## 追加进度：数据集、Android 标准步骤和容量分析

- 数据集参数化新增 `sequential`、`random`、`fixed_count` 三种有界策略，默认仍为顺序执行；随机策略支持固定种子，执行次数上限为 1000，非法策略不会创建半成品子运行。回归位于 `backend/app/services/dataset_execution.py` 和 `backend/tests/services/test_dataset_execution.py`。
- Android 专项任务界面新增执行前安装 APK、卸载旧版本、清理应用数据、启动 Activity，以及执行后卸载；Worker 会校验 APK 项目归属、通过 MinIO 下载 APK、按顺序执行安全 ADB 命令并清理临时文件。回归位于 `backend/app/services/mobile_special/preflight.py` 和 `backend/tests/services/test_mobile_preflight.py`。
- 性能中心新增容量分析入口：选择运行记录后按负载排序，返回最大稳定负载、首个错误率/P95 瓶颈和逐次观察结果；接口为 `POST /api/v1/projects/{project_id}/performance/capacity/analyze`，回归位于 `backend/app/services/performance_capacity.py` 和 `backend/tests/services/test_performance_capacity.py`。
- 性能运行完成后新增统一通知摘要：阈值失败、基线回归、节点错误和资源采样错误会转换为项目已有的邮件/企业微信/钉钉通知契约；通知是 best-effort，发送失败不会改变运行结果，并使用运行摘要标记避免分片父运行重复通知。回归位于 `backend/app/services/performance_notifications.py`。
- 本轮质量验证（历史记录）：后端非集成回归 `1616 passed`；新增能力及性能/Android 定向回归 `89 passed`。

## 历史本地质量核验（2026-08-07）

- 后端非集成测试 `1710 passed`（命令使用 `--ignore=tests/integration`，集成测试仍按环境变量单独运行）；前端 Vitest `37 files / 146 tests passed`。
- `mypy` 检查 `128` 个源文件无错误；Ruff lint、格式检查、Bandit（无高/中风险）、pip-audit（无已知漏洞）、npm audit（0 vulnerabilities）、`vue-tsc --noEmit`、前端生产构建和 `git diff --check` 全部通过。
- 录制/元素资产定向回归 `10 passed`；此前性能/Web 受影响模块定向回归 `27 passed`。
- 本地完成不代表真实环境验收完成：仍需真实 Android/iOS、Prometheus、Firefox/WebKit/JMeter Worker 和外部通知渠道；集成测试仍需 PostgreSQL/Redis/MinIO 运行环境。

## 追加进度：API Schema 资产与场景编排

- 新增项目级 `ApiSchemaAsset` 模型和 `20260807_0051_add_api_schema_assets.py` 迁移，提供列表、新建、更新、删除接口；Schema 受 512KB 限制，名称按项目唯一并递增版本。
- API 用例编辑器的 JSON Schema 断言支持选择已有资产、保存当前 JSON 为资产；执行器按项目校验 `schema_asset_id`，不允许跨项目引用，同时保留内联 Schema 兼容旧用例。
- API 场景新增失败策略、上下文作用域、登录态生命周期配置；多步骤用例展示步骤顺序和 `depends_on` 关系，可从当前请求快速追加步骤，Worker 对依赖失败步骤记录 `skipped` 结果。
- 回归证据：`tests/api/test_api_schema_assets.py`、`tests/services/test_api_scenario.py`、`tests/worker/test_http_family_executors.py`。

## 追加进度：OpenAPI `$ref` 与 Provider/Consumer 契约资产

- `backend/app/services/ai_case/parsers.py` 现在支持 OpenAPI/Swagger 项目内 JSON Pointer `$ref`，覆盖参数、请求体、响应 Schema 和嵌套示例；循环引用、缺失引用和外部引用会产生可见告警，解析过程不联网。
- `backend/app/services/api_contracts.py` 的兼容性比较器支持同样的项目内 `$ref` 展开，并对外部/循环引用返回 warning，避免把未解析的引用误判为兼容。
- 新增 `ApiContractAsset`、`20260807_0052_add_api_contract_assets.py` 和 `/projects/{project_id}/api-contract-assets` CRUD；资产区分 `provider`/`consumer`，按项目、角色、名称唯一并递增版本。
- 新增 `POST /projects/{project_id}/api-contracts/compare-assets`，只允许比较当前项目资产，复用统一兼容性结果契约；前端 `/system/api-contract-assets` 已接入菜单、路由、Provider/Consumer 资产 CRUD、角色筛选、版本摘要和资产比较流程，并复用 `apiContractApi.compareAssets` / `apiContractAssetApi`。
- 新增契约资产、解析器和 `$ref` 比较回归，完整非集成后端回归提升至 `1710 passed`。

## 追加进度：Provider/Consumer 契约资产管理 UI

- 新增项目级契约资产管理页面 `/system/api-contract-assets`：按项目查看 Provider/Consumer 资产、角色统计、最新版本、描述和格式；支持新建、编辑、删除及 JSON 定义校验。
- 新增资产比较面板：选择基线版本与当前版本后调用项目隔离比较接口，展示兼容状态、破坏性变更和警告，避免把“资产已保存”误认为“版本兼容”。
- 页面已接入主菜单、中英文文案和响应式/减少动效样式；组件回归覆盖加载摘要、JSON 校验/保存和破坏性变更展示。
- 验证：`ApiContractAssetsView.spec.ts` `3 passed`；前端全量 `37 files / 146 tests passed`；`vue-tsc --noEmit` 和生产构建通过。真实浏览器登录后项目列表异步加载出“数字人管理平台”，新建按钮可用，抽屉、JSON 定义输入和中文文案正常，控制台无错误；未在真实数据库中创建测试资产。
- 前端 Playwright E2E 追加验证：`npm run e2e` 共 `9 passed`，覆盖登录、Dashboard、用例、执行详情、套件和计划主流程；配置仍为 mock API + Chromium，不能替代发布环境真实 API 联调。

## 追加进度：iOS/Appium 本地执行边界

- 新增 `IosDevice`、`IosDeviceLease` 和 `IosApp` 模型及 `20260807_0053_add_ios_appium_assets.py` 迁移；iOS 设备支持 UDID、型号、iOS 版本、Appium 地址、WDA 端口和在线状态，IPA 资产支持项目归属、Bundle ID、版本和签名描述信息。
- 新增 `/ios-devices` 与 `/ios-apps` 资产/租约 API，包含项目权限、IPA 扩展名与 500MB 大小限制、MinIO 对象引用、租约心跳/释放/过期回收；Celery 新增 `ios` 队列和回收任务。
- 新增 `ios_executor.py`：通过标准 W3C Appium HTTP 协议启动 XCUITest 会话，支持 click、input、assert_text、assert_element、wait、screenshot、tap、swipe、back、start_app、stop_app，按统一 `StepResult` 写入截图、录屏和 syslog 产物。
- 用例管理增加 iOS 类型和 JSON 低代码编辑入口；`CaseType.ios` 会进入专用 `ios` 队列，未伪造本地 Windows 的真实 XCUITest 能力。
- 回归证据：`tests/api/test_ios_routes.py tests/worker/test_ios_executor.py` 共 `7 passed`；Alembic `current` 为 `20260807_0053 (head)`；真实 macOS/Appium/WDA/iPhone/Simulator 仍待外部验收。iOS 租约心跳接口只返回续租状态，不重复返回租约密钥。

## 2026-08-07 外部验收环境探测

- 当前 Windows 开发机有 ADB 37.0.0 但无在线 Android 设备；JMeter 5.6.3 和 Playwright 1.61.1/Chromium/Firefox/WebKit 缓存可用。本轮 Chromium、Firefox、WebKit 均访问本地 `/login` 返回 HTTP 200。
- 当前开发机没有 Docker 命令，Prometheus `127.0.0.1:9090`/`localhost:9090` 未就绪，因此 Docker Worker、分布式压测节点和真实目标指标链路不在本轮本地结论内。
- 已对已授权 Linux 主机完成只读探测：ARM64 + Docker 29.3.0，现有 PostgreSQL/Redis/MinIO 容器运行中，但没有 ATP 验收栈或 Prometheus 9090；没有在该主机写入、部署或重启服务，避免影响现有业务。
- Worker 发布边界补齐：`Dockerfile.worker` 现在安装并校验 Chromium、Firefox、WebKit、JMeter、k6、Locust 和 gRPC 依赖；性能验收 Compose 示例启用 `k6,locust,grpc,jmeter`，验收脚本同步检查这些运行时依赖。
- iOS 仍需要 macOS、Xcode、Appium/XCUITest、签名 IPA 与 iPhone/Simulator；已实现的 W3C HTTP Worker 不替代该环境验收。

## 2026-08-07 JMeter 本地真实烟测

- 新增 [`deploy/performance-acceptance/jmeter_smoke.jmx`](../deploy/performance-acceptance/jmeter_smoke.jmx)，只访问本地 ATP `/login`，不包含用户名、密码或其他敏感数据。
- 使用 JMeter 5.6.3 非 GUI 模式执行 1 次请求，HTTP 200、错误数 0，并生成 JTL 和 HTML 报告目录；该证据验证本机 JMeter 执行器和报告生成链路。
- Docker Worker 中的 JMeter、Firefox、WebKit 以及远程 Linux 节点仍需隔离环境重新验收。

## 2026-08-07 三浏览器本地真实烟测

- 新增 `frontend/tools/browser-matrix-smoke.mjs`，对 Chromium、Firefox、WebKit 统一等待登录页输入元素挂载后再判定页面可用，避免把 WebKit 的异步渲染时序误判为失败。
- 本轮三浏览器均访问本地 `/login` 返回 HTTP 200、页面标题正确，并检测到 4 个输入框；证据见 `docs/evidence/web-browser-matrix-local-smoke-2026-08-07.json`。
- 该结果验证本机浏览器运行时和页面加载，不替代 Docker Worker 中的真实 Firefox/WebKit 验收。

## 2026-08-07 OpenAPI 外部 `$ref` 发布策略

- AI Schema 解析接口新增 `external_ref_policy`，支持 `warn` 和 `reject` 两种模式；默认 `warn`，外部/远程引用只记录警告且不发起网络请求，`reject` 作为发布安全模式会直接返回错误。
- 用例 AI 生成抽屉在 OpenAPI 来源下增加策略选择和说明，非 OpenAPI 来源固定使用 `warn`，避免把无关参数传入其他解析器。
- 回归覆盖外部引用拒绝、API 入参传递、前端静态入口和中英文文案；完整非集成后端回归更新为 `1711 passed`。
- 真实 Provider/Consumer 规格联调仍需外部提供可访问的 Provider、Consumer 规格和发布流程；本地实现不联网拉取远程 `$ref`。
## 2026-08-11 前端覆盖率门禁收口

- 新增 `ProjectList.spec.ts`、`UserManagementView.spec.ts`、`AccountSettingsView.spec.ts`，覆盖项目导入成功状态清理、用户新增/编辑/密码长度校验、个人资料保存/改密和异常提示。
- 修复 `ProjectList.vue` 导入成功后未释放 `importing` 保护，导致 `resetImport()` 提前返回、导入弹窗无法按预期关闭的问题。
- 验证结果：前端 `40 files / 157 tests passed`；coverage statements/branches/functions/lines `31.54% / 26.53% / 24.73% / 32.76%`；type-check、生产构建通过。后端 Python 3.12 非集成 `1827 passed`、coverage `82.50%`，Python 3.14 非集成 `1827 passed`、coverage `82.05%`，单文件扫描 `252 passed`。

## 2026-08-11 Python 3.14 兼容性与覆盖率复验

- 为 Python 3.14 准备独立虚拟环境并验证运行时依赖；`asyncpg 0.31.0`、`psycopg2-binary 2.9.12` 和 `PyYAML 6.0.3` 均使用可用二进制包，`pip check` 通过。
- 新增覆盖录制会话生命周期、录制路由异常、资产持久化冲突、用户查询/角色/重复数据/管理员保护等边界回归，避免通过降低覆盖率阈值掩盖新增路径。
- Python 3.14.3 完整非集成回归 `1827 passed`、覆盖率 `82.05%`；Python 3.12.11 对照回归 `1827 passed`、覆盖率 `82.50%`；252 个测试文件在 Python 3.14 下单独运行全部通过。

## 2026-08-11 低代码 Python 脚本生成补齐

- `frontend/src/utils/pythonScriptGenerator.ts` 的 Web 生成器新增上传、下载、视觉基线断言，并可使用项目元素资产和页面对象数据展开定位器与公共动作；Android 生成器补齐旋转、权限、网络配置和前后台切换。
- 生成脚本使用 `ATP_WEB_UPLOAD_N`、`ATP_WEB_DOWNLOAD_N` 和 `ATP_VISUAL_BASELINE_N` 环境变量连接脱离平台后的文件/基线输入；视觉断言使用 Pillow 计算像素变化比例并生成差异图。
- 对缺少定位器、资产未加载、页面对象无动作和未知动作统一生成显式 `pytest.fail`，避免用户保存一个看似完整但实际跳过步骤的脚本。
- 验证：生成器定向 `6 passed`；前端全量 `40 files / 161 tests passed`；coverage statements/branches/functions/lines `31.94% / 27.09% / 24.94% / 33.21%`；`vue-tsc --noEmit` 和生产构建通过。
