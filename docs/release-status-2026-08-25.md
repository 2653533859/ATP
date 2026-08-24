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

## 能力与证据索引

| 能力域 | 当前结论 | 主要证据 | 未关闭边界 |
|---|---|---|---|
| Windows API/Web | 本地与 q19 证据已形成 | [`windows-full-readiness-2026-08-24.json`](evidence/windows-full-readiness-2026-08-24.json)、[`q19-migration-web-worker-readiness-2026-08-24.json`](evidence/q19-migration-web-worker-readiness-2026-08-24.json) | 目标发布环境仍需按版本重放并归档 |
| Web Worker/录制 | q19 持久 Worker、Chromium/Firefox/WebKit 录制和跨 API 停止快照已验证 | [`q19-web-recorder-readiness-2026-08-24.json`](evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recording-cross-api-2026-08-24.json`](evidence/q19-web-recording-cross-api-2026-08-24.json) | Linux/Xvfb、跨副本和目标部署拓扑仍需独立复验 |
| Android | 代码、配置配对和 doctor 门禁已完成；真实执行阻塞 | [`windows-android-worker.ps1`](../scripts/windows-android-worker.ps1)、[`windows-android-acceptance.ps1`](../scripts/windows-android-acceptance.ps1) | ADB 必须恢复为 `device`，然后完成扫描、租约、截图、APK、低代码、专项任务和证据回传 |
| 性能 | P1-E.1/P1-E.2/P1-E.3 本地闭环完成，q19 单节点 k6 短压已有证据 | [`q19-performance-worker-smoke-2026-08-24.json`](evidence/q19-performance-worker-smoke-2026-08-24.json)、[`product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md) | 多节点/容量、生产 Prometheus、MinIO 生命周期和跨主机恢复 |
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
