# ATP 发布收口状态（2026-08-25）

> 这是当前发布候选的状态索引。它只汇总已经存在的代码/自动化证据和真实环境证据，不把本地 mock、协议桩或“代码已实现”写成生产通过。

## 发布结论

当前结论：**暂不具备无条件发布资格**。

本地代码、回归和 Windows/q19 API/Web/性能链路已经形成可复核证据；以下外部门禁仍未关闭，因此发布只能按“部分实现/待环境验收”处理：

- Android Worker/真机：当前 `adb devices -l` 为 `172.16.102.91:5555 offline`，不能执行单设备用例验收。
- 性能生产环境：真实 Kubernetes 多节点、容量限制、生产 Prometheus、MinIO 生命周期和跨主机恢复未验收。
- 通知供应商：当前只有回环 SMTP 的 `local_link_only` 证据，没有真实 SMTP/企业微信/钉钉送达回执。
- 外部缺陷平台：没有可使用的临时 Jira/禅道/GitHub/GitLab 项目和凭据，创建、同步和脱敏链路未做真实验收。

## 2026-08-25 P0-A 本地 E2E 回归复核

- 本地 Playwright 共享 fixture 已修复中文登录按钮自动空格，以及主布局 `/workbench/overview`、运行详情 `/defects` 未隔离导致的真实 401；登录定向 `3 passed`、运行详情定向 `1 passed`、全量 Playwright `12 passed`。
- 前端 Vitest `66 files / 265 tests passed`，`vue-tsc --noEmit`、生产构建和 `git diff --check` 通过。
- 这不改变发布结论：Windows 完整 smoke 仍需使用当前有效账号重跑；认证读接口、文件传输和报告导出在账号未通过前保持未验收，不记录任何密码或 Token。

## 2026-08-25 P0-B Android 单设备验收前置复核

- `scripts/windows-android-acceptance.ps1` 已执行；`adb.exe` 可用且命令响应正常，但设备统计为 `online=0, unauthorized=0, offline=1, other=0`，必需检查失败。
- 脱敏本地报告：`.local-run/android-acceptance-current-20260825.json`。脚本在离线状态下不会继续执行设备命令、包管理、日志读取或创建 Android 运行任务。
- 这不改变发布结论：ADB 恢复到 `device` 后，仍需完成扫描、租约、截图、APK 包名、低代码、专项任务和证据回传；`offline` 只能作为阻塞项记录。

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
- 发布边界：当前没有真实 Android 录屏采集证据，ADB 仍为 `offline`；这项改动不关闭 Android 真机发布门禁。

## 2026-08-25 P1-D 外部缺陷平台错误安全收口

- 连接测试、创建缺陷和刷新状态入口已统一脱敏供应商异常，覆盖 Token、密码、Webhook 查询参数和 URL 用户信息；创建/状态刷新返回 502，连接测试返回 `ok=false`。
- 缺陷跟踪入口的 mypy 变量复用问题已修复，成功创建、重复检测、状态同步和附件上传路径保持不变。
- 本地证据：提交 `31df065`，外部缺陷定向 `40 passed`、完整后端非集成 `2234 passed`，Ruff、格式、mypy 和 diff-check 通过；详见 [`external-tracker-error-safety-2026-08-25.json`](evidence/external-tracker-error-safety-2026-08-25.json)。
- 发布边界：没有真实外部缺陷平台项目与凭据，本模块不关闭 Jira/禅道/GitHub/GitLab 的环境验收门禁。

## 2026-08-25 P1-D q19 运行态部署

- q19 已重建到 `cec8eaf`，复用 `atp-q19-acceptance-20260824` Compose 项目名，迁移为 `20260824_0065 (head)`。
- 运行验证通过：Backend `200`、Redis `PONG`、Prometheus ready 且 `4` 个 target 为 `up`；通用 Worker、性能 Worker、Beat、Web Recorder 正常运行，最近 3 分钟 Backend/Worker 错误匹配数为 `0`。
- 发布边界：q19 Compose 不是 Kubernetes 多节点或生产外部平台证据；真实 Jira/禅道/GitHub/GitLab、Android 真机和生产性能验收仍待独立完成。详见 [`q19-external-tracker-deployment-2026-08-25.json`](evidence/q19-external-tracker-deployment-2026-08-25.json)。

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
| Windows API/Web | 本地与 q19 证据已形成，当前账号页面冒烟通过 | [`windows-full-readiness-2026-08-24.json`](evidence/windows-full-readiness-2026-08-24.json)、[`windows-browser-smoke-2026-08-25.json`](evidence/windows-browser-smoke-2026-08-25.json)、[`q19-migration-web-worker-readiness-2026-08-24.json`](evidence/q19-migration-web-worker-readiness-2026-08-24.json) | 目标发布环境仍需按版本重放并归档 |
| Web Worker/录制 | q19 持久 Worker、Chromium/Firefox/WebKit 录制和跨 API 停止快照已验证 | [`q19-web-recorder-readiness-2026-08-24.json`](evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recording-cross-api-2026-08-24.json`](evidence/q19-web-recording-cross-api-2026-08-24.json) | Linux/Xvfb、跨副本和目标部署拓扑仍需独立复验 |
| Android | 代码、配置配对、doctor 门禁和录屏结果展示已完成；真实执行阻塞 | [`windows-android-worker.ps1`](../scripts/windows-android-worker.ps1)、[`windows-android-acceptance.ps1`](../scripts/windows-android-acceptance.ps1)、[`android-recording-evidence-2026-08-25.json`](evidence/android-recording-evidence-2026-08-25.json) | ADB 必须恢复为 `device`，然后完成扫描、租约、截图、APK、低代码、专项任务、设备端录屏和证据回传 |
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
2. 将 ADB 设备恢复到 `device`，执行 `scripts/windows-android-acceptance.ps1`；任何 `offline`、`unauthorized` 或无设备结果都保持阻塞。
3. 在目标 Linux/Kubernetes 环境执行 `scripts/performance-environment-smoke.py`，补齐真实节点、目标服务、Prometheus、取消和资源采样证据。
4. 注入不落库的临时通知供应商凭据，按渠道取得供应商侧送达回执后清理目标和凭据。
5. 使用临时外部缺陷项目验证创建、重复识别、状态同步、权限、错误脱敏和清理。
6. 汇总新的带日期证据后，再更新本文件、能力矩阵、Q18 状态和发布说明；在此之前保持“部分实现/待环境验收”。

## 禁止事项

- 不把 `offline` 设备、无凭据跳过、回环 SMTP、localhost 目标或 Docker Compose 契约测试写成生产通过。
- 不在仓库、证据 JSON、日志或截图中保存密码、Token、Webhook、MinIO 密钥或外部平台凭据。
- 不用 GitHub Actions 绿灯替代真实设备、真实供应商和真实目标服务证据；当前 Actions 触发策略以 [`docs/ci-workflows.md`](ci-workflows.md) 为准。
