# ATP 下一阶段开发计划（2026-08-12）

## 2026-08-15 当前验收进度与下一步

- [x] 远端依赖恢复后重新执行 Windows API/Web smoke：PostgreSQL/Redis/MinIO readiness、登录、项目读取、浏览器矩阵、文件上传和清理均通过；Android 仅保留无在线设备 warning，证据见 `docs/evidence/windows-smoke-current-2026-08-15.json`。

本轮先完成 Windows 可执行范围内的真实环境复核，不把“代码测试通过”冒充为真实设备或远端 Worker 验收：

- [x] Windows Worker doctor、PostgreSQL/Redis/MinIO TCP 与实时依赖检查通过。
- [x] Windows API/Web smoke、文件上传清理和 Chromium 登录矩阵通过；Web/API 不依赖 Android 真机即可继续使用。
- [x] 性能 API、k6/Locust/gRPC 执行器、专用节点队列、出口白名单和 Prometheus readiness/query smoke 通过。
- [x] 已完成真实低流量 Locust smoke：run `1` 为 `957` 次请求、错误率 `0`，并产生 `performance-worker` 采样；run `2` 取消链路从运行态进入 `cancelled`。
- [x] Windows Android Agent 已在线注册到当前 Redis，`/devices/workers` 返回 `android-win-HPS` 和 `mobile_special` 队列；后端当前仍是 `ADB_SCAN_MODE=local`，未执行 worker-mode 扫描回调。
- [x] Windows Android Worker doctor 已修复为先加载 `ATP_ADB_HOME`/Android SDK 路径，再检查 `adb.exe`；对应脚本契约回归通过。
- [x] 新增 `config/deployment-profiles/android-worker-backend.env.example`：服务端固定 `ADB_SCAN_MODE=worker`，普通 Linux Worker 排除 `android,mobile_special`，并与 Windows `android-agent` 档案分离；新增配置契约回归和部署说明。
- [x] 新增 Helm overlay `deploy/helm/atp/values-android-worker.example.yaml`，将同一套扫描模式、Android 队列和外部 Secret 约束带入 Kubernetes；部署契约回归 `22 passed`，真实集群 lint/deploy 仍待目标环境。
- [ ] Android 单设备验收等待授权在线设备；当前 `adb devices -l` 为空，性能监控、卡顿、Crash/ANR、屏幕录制和异常回放无法在本机闭环。
- [x] Android 无真机安全回归完成：Worker/性能/事件/回放/API/迁移和 Windows 验收契约定向回归 `258 passed`；`windows-android-acceptance.ps1` 现在区分未连接、未授权和离线设备，并在 JSON 报告中记录状态计数，不会伪造通过。
- [x] Windows 性能节点 `perf-node-local-01` 已在线并完成目标 TCP、allowlist、资源采样和取消验证；Linux/Kubernetes 专用 Worker、TLS 目标和多节点验收仍未关闭外部门禁。

## 2026-08-15 Web Worker 与灾备演练进展

- [x] 修复 Web 录制 API/Worker 的 Redis 阻塞读取超时：`socket_timeout` 会覆盖命令等待和 Worker 心跳窗口，避免健康 Worker 因默认 5 秒读超时被误判为不可用；定向回归 `18 passed`。
- [x] Windows Web Recording Worker 真实 smoke 通过，包含 Worker 可用性、Chromium 录制、2 个步骤、PNG 截图和停止录制；证据见 `docs/evidence/web-recording-worker-local-2026-08-15.json`。
- [x] Linux Docker Compose 隔离栈完成 PostgreSQL 与 MinIO 备份恢复演练，临时资源已清理；证据见 `docs/evidence/backup-restore-linux-docker-2026-08-15.json`。
- [x] 已检查远端 Linux/Xvfb acceptance 资源：旧镜像可启动 Xvfb/Playwright 和临时 Worker，但缺少当前 `/web-recordings/workers` 路由；证据见 `docs/evidence/web-recording-linux-remote-2026-08-15.json`，不计入当前版本录制验收。
- [x] 当前仓库 backend 镜像已从 HEAD 构建并完成 Chromium Linux/Xvfb 录制；当前 Worker 源码挂载到既有多浏览器运行时后，Firefox/WebKit 和跨 API 副本 Redis 会话路由也通过；证据见 `docs/evidence/web-recording-linux-current-2026-08-15.json`。
- [x] `Dockerfile.worker` 已从当前 commit 完整构建成功；同一镜像的 Chromium/Firefox/WebKit Linux/Xvfb 录制、容量切换重试、无 Worker 503 拒绝和跨 API 副本路由均通过，证据见 `docs/evidence/web-recording-linux-current-2026-08-15.json`。
- [x] 当前前端浏览器矩阵已生成三浏览器 Trace/HAR、Console、失败请求和 HTTP 错误摘要；证据见 `docs/evidence/web-browser-trace-network-2026-08-15.json`。Linux acceptance 栈无前端容器，Trace/HAR 采集因此单独记录。
- [ ] 备份恢复仍不是生产灾备签字：MinIO bucket lifecycle/归档策略、生产保留周期与定期恢复任务需明确并在目标环境复核。

## 2026-08-15 MinIO 生命周期实现进展

- [x] 新增显式 `app.ops_minio_lifecycle` 运维命令，采用 `atp-managed-*` 命名空间合并生命周期规则，不覆盖外部系统已有规则；执行必须设置 `MINIO_LIFECYCLE_APPLY=true`。
- [x] Helm hook 与 Docker Compose `storage-lifecycle` profile 已接入，默认关闭；过期规则要求非空相对前缀，默认只处理未完成 multipart upload。
- [x] 生命周期契约回归 `23 passed`，并同步 `.env.example`、Helm values/schema、部署和灾备 Runbook。
- [x] 已对目标 `172.31.27.133` 的 `atp` bucket 完成只读规则、保护能力、对象前缀和数据库引用审计；证据见 `docs/evidence/minio-lifecycle-audit-2026-08-15.json`。
- [ ] 生产启用前仍需核对 bucket 当前规则、数据库引用关系、备份前缀和合规保留周期。

## 2026-08-15 外部通知验收前置检查

- [x] 目标数据库通知配置只读审计完成：当前 `notification_configs=0`、启用配置 `0`、投递记录 `0`；证据见 `docs/evidence/notification-readiness-audit-2026-08-15.json`。
- [ ] 管理员提供临时测试目标后，完成 SMTP/企业微信/钉钉真实投递、失败重试、限流、脱敏和重复投递证据。

## 2026-08-15 Linux Docker 验收进展

- [x] Linux MCP 已恢复；`172.31.27.133` 的隔离性能 Compose 栈健康检查通过，包含 PostgreSQL、Redis、MinIO、Backend、专用 Worker、Prometheus 指标端口和 HTTP/gRPC 目标。
- [x] Locust smoke 通过（run `1`、36 次迭代、错误率 `0`），gRPC TLS smoke 通过（run `2`、5 次迭代、错误率 `0`），取消 smoke 通过（run `3` 进入 `cancelled`）。
- [x] 真实证据已归档：`docs/evidence/performance-linux-locust-smoke-2026-08-15.json`、`performance-linux-grpc-smoke-2026-08-15.json`、`performance-linux-locust-cancel-2026-08-15.json`。
- [ ] Kubernetes Deployment、真实多节点分片、生产 Prometheus、外部目标和外部通知仍未验收；Docker Compose 结果不能替代这些门禁。

下一步按优先级执行：

1. 在真实 Kubernetes 环境复现性能节点 readiness、TLS 目标、取消、资源采样、报告导出和多节点分片证据；当前 Docker Compose 证据只能关闭 Linux 单节点隔离栈部分。
2. 接入并授权 Windows Android 真机，运行 `scripts/windows-android-acceptance.ps1`，再以 `ADB_SCAN_MODE=worker` 验证公网后端到 Android Worker 的注册、设备扫描和操作回调。
3. 在不影响 API/Web 的前提下完成真实 Android 性能任务：设备指标、卡顿/FPS、Crash/ANR、事件时间线、录屏分段和异常回放。
4. 基于已完成的只读审计，由管理员确认 MinIO 保留周期和是否启用 multipart 清理；确认后再显式启用生命周期 hook，补真实恢复演练和清理审计，随后补外部 SMTP/企业微信/钉钉投递证据。
5. 重试从当前 commit 构建完整 Linux/Xvfb Web Worker 镜像，随后补 Trace/网络日志、失败重试和资源恢复证据；本轮已完成浏览器矩阵与跨副本成功链路 smoke。

## 2026-08-14 项目成员 owner 权限完整性（代码阶段完成）

- [x] 成员角色修改与删除统一维护“至少一个 owner”不变量；角色降级会锁定 owner 记录并拒绝最后一个 owner 被改为 viewer/editor。
- [x] 项目成员回归 `25 passed`，完整非集成后端 `2030 passed`，Ruff format/check 通过；前端全量 `50 files / 207 tests passed`，type-check/build 通过。
- [ ] 生产环境仍需结合组织权限策略确认 owner 转移、离职账号停用和管理员接管流程；本地回归不替代权限运营验收。

## 2026-08-13 性能压测停止竞态与自动阶梯边界（代码阶段完成）

- [x] 停止压测时锁定父运行及其分片记录，避免 API 停止请求与 Worker 完成提交产生状态覆盖；保留终态运行不可重复停止的约束。
- [x] Worker 在执行器返回后复核取消标记；自动阶梯拒绝无穷大等溢出 `max_vus` 配置，避免异常值绕过校验或触发服务端错误。
- [x] 定向性能 API/Worker/自动阶梯回归 `87 passed`，完整非集成后端回归 `2029 passed`，Ruff format/check 通过。
- [ ] Linux MCP 仍返回 `Transport closed`；真实 Worker、Prometheus、TLS/目标服务及外部取消链路需在目标环境恢复后验收。

## 2026-08-13 性能压测时长边界防绕过（代码阶段完成）

- [x] 性能 API 拒绝 `NaN`、无穷大、负数和布尔值时长，并覆盖顶层与分阶段配置，避免最大时长门禁被非有限值绕过。
- [x] 性能 API 定向回归 `69 passed`，完整非集成后端 `2027 passed`；Linux MCP 只读主机检查仍返回 `Transport closed`，真实性能 Worker、TLS 目标和 Prometheus 保持外部待验收。

## 2026-08-13 通知策略异常范围安全隔离（代码阶段完成）

- [x] 通知配置保存时校验 `scope`、状态筛选和套件/计划目标 ID，未知策略不会进入发送链路。
- [x] 通知运行时对未知范围采用 fail-closed，避免历史配置或非前端 API 调用把限定通知扩大为全量通知；服务/API 定向回归 `35 passed`，完整非集成后端 `2026 passed`。
- [ ] 真实 SMTP、企业微信和钉钉仍需目标环境联调，供应商返回码、限流和重复投递证据不由本地回归替代。

## 2026-08-13 API Cookie 属性安全恢复（代码阶段完成）

- [x] 项目级 API 会话恢复时保留 Cookie 的安全属性、过期时间和请求作用域，避免复用登录态时发生 Cookie 降级。
- [x] 补充安全 Cookie 序列化/反序列化和旧密钥无效密文降级回归，并继续覆盖空会话清理。

## 2026-08-13 API 登录态清理闭环（代码阶段完成）

- [x] 项目级 API 会话复用在 Cookie 被服务端清空后会显式保存空会话，不再遗留旧登录态。
- [x] 补充加密存储、TTL 和空会话覆盖回归；不改变未勾选复用时的隔离行为。
- [x] API 会话/HTTP 家族定向 `70 passed`，完整非集成后端 `2023 passed`。

## 2026-08-13 通用用例清空数据集后的配置隔离（代码阶段完成）

- [x] 通用用例未绑定数据集时不再写入旧的 Schema、组合策略、迭代上限、脱敏字段或数据准备 Hook 配置。
- [x] 增加前端入口静态回归；保留已绑定数据集时的完整参数化配置行为。

## 2026-08-13 启动依赖诊断原因展示（代码阶段完成）

- [x] 启动配置页现在展示依赖探测的具体错误原因，而不只显示“不可用”；支持连接成功、连接超时、无法连接和 MinIO 存储桶不存在。
- [x] 补充启动配置页回归断言；前端全量 `50 files / 207 tests passed`，type-check 和 build 通过。
- [ ] 当前远端仅 PostgreSQL `5432` 可从 Windows 建立 TCP 连接，Redis `6379`、MinIO `9000` 不可达；Linux MCP 仍返回 `Transport closed`，不能据此标记远端验收完成。

## 2026-08-13 数据集绑定异步请求隔离（代码阶段完成）

- [x] 修复 Web/Android 共享数据集绑定组件在切换项目或清空数据集时的过期请求 loading 卡住问题。
- [x] 切换请求序列后立即清空旧数据集/版本选项；旧响应只能更新仍然有效的请求序列。
- [x] 新增 2 个回归用例；前端全量 `50 files / 207 tests passed`，type-check 和 build 通过。

## 2026-08-13 通用用例数据集版本固定（代码阶段完成）

- [x] API/GraphQL/WebSocket/gRPC/iOS 通用用例抽屉增加数据集版本下拉框，并与后端 `dataset_version` 字段一致。
- [x] 切换或清空数据集时清理旧版本；编辑已有用例会回显固定版本，版本被删除时自动移除失效选择，未固定时仍使用最新版本。
- [x] 本轮验证：后端非集成 `2022 passed`，前端 `49 files / 205 tests passed`，type-check/build 通过。

## 2026-08-13 Web/Android 专用用例数据集绑定（代码阶段完成）

- [x] Web/Android 专用抽屉现在可以选择项目数据集和固定版本，并配置严格 Schema、组合策略、最大迭代数、随机种子和结果脱敏字段。
- [x] 创建、编辑和清空绑定均与后端 `dataset_id` / `dataset_version` 语义一致；共享组件在切换数据集后刷新版本列表，避免保存旧版本号。
- [x] 前端回归更新为 `49 files / 205 tests passed`，type-check/build 通过；真实 Web Worker、Android Worker 和目标数据集大规模执行仍需环境验收。

## 2026-08-13 发布前部署校验严格模式

- [x] `scripts/validate-deployment-readiness.py` 现在区分仓库契约通过与环境依赖缺失：默认模式保留 `SKIP` 并在摘要显示跳过数量，避免把工具不可用误读成完整验收。
- [x] 新增 `--strict` 和 `make validate-deployment-readiness ARGS=--strict`；发布操作员可要求 Docker/Compose、Helm、`.env` 和 POSIX shell 全部可用，任一缺失即失败。
- [x] 补充 Compose 必需/可选分支回归；真实集群、备份恢复和性能/Worker smoke 仍需目标环境证据。
- [ ] 本次继续尝试对 `172.31.27.133` 执行只读 Linux MCP 连通性检查，`ping_host` 与系统概览均仍返回 `Transport closed`；未取得外部验收证据。

## 2026-08-13 Web/Android 专用入口收口

- [x] 通用用例抽屉移除 Web/Android 选项和“后续实现”占位提示，CaseList 继续通过专用 WebCaseDrawer/AndroidCaseDrawer 创建与编辑。
- [x] 增加静态回归确认路由和文案边界；不改变真实 Worker/Android 设备的外部验收要求。
- [x] 本轮验证：后端非集成 `2021 passed`，前端 `49 files / 203 tests passed`，type-check/build 和 Ruff 通过。

## 2026-08-13 Web/Android 低代码关键流程回归收口

- [x] 补充 Web/Android 专用用例抽屉的创建与编辑回归，覆盖低代码步骤写入 `config.steps`、Android 标准步骤生成，以及项目/等级/设备等关键配置保存。
- [x] 修复 Web 用例编辑时无条件重置浏览器为 Chromium 的问题；现在编辑已有用例会保留 Firefox/WebKit 配置，避免保存时静默覆盖用户选择。
- [x] 前端定向回归 `4 passed`，全量前端回归 `49 files / 203 tests passed`，type-check 通过；真实浏览器 Worker 和 Android 真机执行仍按外部验收边界处理。

## 2026-08-13 存储治理自定义前缀执行修复

- [x] 修复 StoragePolicy 自定义前缀在预览可删除、执行却按默认前缀误判缺失的问题；清理执行接口现在接收并校验本次预览使用的前缀。
- [x] 后台定时清理同步透传策略前缀；存储 API/服务/维护任务回归 `29 passed`，Ruff 通过。

## 2026-08-13 项目级运行记录清理按钮范围修复

- [x] 修复运行记录清理页面只按全局预览启用按钮的问题；全局保留策略会排除项目覆盖策略，主预览现在同时加载项目级预览。
- [x] 清理确认数量、对象估算和抽样提示统一覆盖全局范围及所有项目覆盖范围；RunRetentionView 回归 `2 passed`，type-check/build 通过。

## 2026-08-13 性能节点删除并发保护收口

- [x] 删除性能节点前使用行级锁，与手动、Webhook、定时压测的节点锁保持一致，避免检查通过后并发创建运行记录并被 `ON DELETE SET NULL` 脱离节点。
- [x] 性能 API 定向回归 `68 passed`，Ruff 通过；真实 Redis/MinIO、Linux/Kubernetes Worker 和外部通知渠道仍按外部验收项执行。

## 2026-08-13 启动配置依赖连接检查

- [x] 新增只读 `GET /api/v1/health/dependencies`，并行检查 PostgreSQL、Redis 和 MinIO，返回可用性、耗时和通用错误码，不返回地址、账号、密码或异常原文。
- [x] 依赖诊断接口增加管理员权限，公开 `/health` 继续只承担轻量进程存活检查，避免未认证请求反复触发基础设施连接。
- [x] 启动配置页增加“检测当前连接”入口，直接展示正在运行 Backend 实际使用的三项基础设施状态；当前 172 环境实测 PostgreSQL 可用，Redis/MinIO 不可达。
- [x] 后端定向回归 `4 passed`，StartupConfigView 定向回归 `6 passed`；重启后未认证请求 `401`、管理员冒烟可读取脱敏响应，type-check、Ruff 和真实接口检查通过。
- [x] 最新本机门禁：后端非集成 `2018 passed`，覆盖率 `82.03%`（门禁 82%）；`269` 个测试文件逐文件独立通过；前端 `47 files / 199 tests passed`，type-check/build、Ruff、format-check 和 mypy 通过。
- [x] Python 3.14.3 条件依赖环境复跑完整非集成后端 `2018 passed`；覆盖率门禁继续以 CI 使用的 Python 3.12.11 为准。
- [x] 发布前安全/配置门禁：Bandit、npm audit、pip-audit（锁定 requirements 模式）、pre-commit 和部署配置校验通过；Docker/Helm 命令缺失时按约定跳过真实工具检查。

## 2026-08-13 Windows 冒烟接入依赖分项检查

- [x] `scripts/windows-local-smoke.ps1` 登录后调用 `/api/v1/health/dependencies`，分别记录 PostgreSQL、Redis、MinIO 状态、通用错误码和耗时；报告不写入地址、账号或密码。
- [x] 依赖整体为 `degraded` 时冒烟明确失败并保留分项结果，避免在文件上传或 Worker 阶段才间接暴露基础设施不可用。
- [ ] 当前 172 环境仍需 Redis/MinIO 恢复后重跑该冒烟，不能把本机脚本通过当成远端依赖已恢复。

## 2026-08-13 Windows Mock E2E 选择器隔离修复

- [x] 计划/套件 Playwright 测试选择项目时限定可见下拉选项，避免 Ant Design 已选值与下拉项同名触发 strict mode 冲突。
- [x] Chromium Mock E2E 全量 `10 passed`；真实后端、Redis、MinIO 和外部 Worker 仍按环境验收单独核对。

## 2026-08-13 Windows 当前启动档案冒烟复核

- [x] `scripts/windows-local-smoke.ps1` 增加 `-LiveRequestTimeoutSeconds`，认证、认证读接口和 Web Worker 状态检查可适配远端数据库延迟；默认 30 秒，范围 5-300 秒。
- [x] 重启当前项目并确认根 `.env` 已加载 `172.31.27.133`；登录、`/auth/me`、项目列表和 `/web-recordings/workers` 均通过。
- [ ] Windows 到 `172.31.27.133:6379` Redis 和 `:9000` MinIO 仍不可达；需目标主机启动/放通服务后重新执行完整 Windows 冒烟，不把当前结果标记为通过。

## 2026-08-13 仪表盘 iOS 类型筛选补齐（代码阶段完成）

- [x] 仪表盘类型筛选新增 iOS 选项，与后端和用例管理已支持的 iOS 执行类型保持一致。
- [x] 增加筛选项回归测试；前端全量回归 `46 files / 194 tests passed`，type-check/build 和 `git diff --check` 通过。

## 2026-08-13 性能节点删除生命周期保护（代码阶段完成）

- [x] 删除性能节点前检查 `pending/running/cancelling` 运行；存在未结束运行时返回 `409`，避免外键 `SET NULL` 让任务失去节点约束。
- [x] 删除性能节点前检查仍启用的定时任务；存在绑定时返回 `409`，避免定时任务静默回退到共享队列。
- [x] API 定向回归 `68 passed`；后端完整非集成回归 `2008 passed`、覆盖率 `82.12%`；前端回归保持 `46 files / 193 tests passed`，类型检查、构建和差异校验通过。

## 2026-08-13 通知渠道配置校验补强（代码阶段完成）

- [x] API 新建/切换渠道和发送入口校验最小投递字段，空收件人、空 Webhook 或 `******` 占位符不会进入发送/重试链路。
- [x] 对历史无效配置保留名称/启用状态编辑能力；真正发送时记录明确失败，而不是伪造成功投递。
- [x] 通知 API/服务定向回归 `32 passed`，NotificationList `5 passed`，全量前端 `46 files / 192 tests passed`，type-check/build 通过；真实供应商可达性仍需外部渠道验收。
- [x] 测试发送完成或失败后自动刷新最近投递历史，页面可立即核对本次结果；NotificationList 定向回归 `5 passed`。

## 2026-08-13 运行记录清理预览刷新（代码阶段完成）

- [x] 执行运行记录清理后同时刷新全局和项目级预览，避免项目级卡片继续显示旧数量。
- [x] 新增 RunRetentionView 回归；前端全量 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 运行记录清理对象安全顺序（代码阶段完成）

- [x] 清理运行记录时先提交数据库删除，再删除关联 MinIO 对象；数据库提交失败时保留对象，避免运行记录与附件不一致。
- [x] 新增提交顺序/失败保护回归；运行记录服务定向 `10 passed`，后端全量 `2005 passed`，覆盖率门禁 `82.10%`。

## 2026-08-13 运行记录清理对象估算提示（代码阶段完成）

- [x] 预览返回 `estimated_objects_sampled`，候选运行记录超过批大小时显式说明对象数来自首批抽样，避免大数据量下产生精确计数错觉。
- [x] 全局预览、按项目预览和执行确认提示统一展示抽样状态；不在预览阶段扫描全部附件，保留大数据量下的响应边界。
- [x] 后端全量 `2005 passed`、覆盖率门禁 `82.10%`；前端全量 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 按项目清理预览补全（代码阶段完成）

- [x] 按项目表格补齐 Plan、Suite、Test、Mobile 四类运行记录及项目级对象估算，消除服务已统计但页面未展示的范围差异。
- [x] 项目级对象估算复用批量抽样和抽样标识；相关运行记录服务回归 `16 passed`，前端组件测试和 type-check 通过。

## 2026-08-13 按项目预览 API 契约收口（代码阶段完成）

- [x] 为按项目预览路由启用 `RunRetentionPerProjectOut`，将内部 `global_` 显式序列化为前端使用的 `global` 字段。
- [x] API 契约回归覆盖项目 TestRun 数量、对象估算和抽样标记；运行记录相关定向测试 `22 passed`。

## 2026-08-13 通知配置响应脱敏补强（代码阶段完成）

- [x] 新建/更新接口统一复用通知配置脱敏响应，避免将数据库中的加密 webhook、secret 等配置返回给前端。
- [x] 补充 API 回归并确认数据库密文仍保持加密；定向测试 `14 passed`，Ruff/格式检查和差异检查通过。
- [ ] 真实 SMTP、企业微信和钉钉渠道仍需目标环境联调，脱敏修复不替代供应商投递验收。

## 2026-08-13 Linux/Kubernetes 性能栈完善（代码阶段完成）

- [x] 修复手动、Webhook 和定时任务在多 API/Beat 副本同时派发压测时的节点容量竞态：节点选择与 `max_concurrency` 校验在同一数据库行锁事务中完成。
- [x] 补充性能节点容量锁、draining 状态、队列路由、超时心跳和幂等触发回归；定向性能回归 `91 passed`，完整非集成后端 `1988 passed`，前端 `45 files / 189 tests passed`，Ruff/格式检查通过。
- [x] 手动触发和 Webhook 增加显式幂等键；同键同请求复用已有 Run，同键不同请求返回 `409`，并用数据库唯一约束兜底并发提交。
- [x] 外部性能验收脚本同步携带幂等键：支持显式基值/CI 运行号复用，本地默认新键，并为 smoke 与 cancel 自动追加独立作用域。
- [x] 外部性能验收脚本支持按来源校验非空指标样本：可分别要求 Worker 资源和目标 Prometheus 采样，避免弱证据通过。
- [x] 外部性能验收脚本支持基线对比门禁：可要求基线存在，并按需将核心指标 regression 转为失败退出码。
- [ ] 在真实 Linux/Kubernetes 环境继续验收专用 Worker、Prometheus、TLS、HTTP/gRPC/Locust/JMeter 目标、任务取消和资源采样；本地测试不替代外部证据。

## 2026-08-13 通知渠道可靠性收口（代码阶段完成）

- [x] 执行通知和测试发送统一使用有限重试链路；默认 `retry_attempts=0`，不改变已有通知配置行为。
- [x] 仅对网络超时/连接失败、HTTP 5xx 和 429 重试；供应商拒绝、错误 Webhook 和其他配置错误不重复发送；最多额外重试 3 次，指数退避不超过 30 秒。
- [x] 通知配置页面提供失败重试次数与首次等待时间，后端对历史 JSON 配置做有界解析；未增加模型字段和数据库迁移。
- [x] NotificationList 前端回归 `4 passed`，完整非集成后端 `1988 passed`。
- [ ] 真实 SMTP、企业微信、钉钉公网渠道联调、供应商限流和重复投递语义仍需目标环境验收。

## 2026-08-13 通知投递结果可观测性（代码阶段完成）

- [x] 新增 `notification_deliveries`，记录渠道投递状态、实际尝试次数、脱敏摘要和失败原因；通知配置删除后通过 `SET NULL` 保留历史。
- [x] 执行通知和测试发送均记录结果；新增工程师权限的项目范围查询 API，并在通知配置页展示最近 20 条记录。
- [x] 新增迁移 `20260813_0057`，补充服务/API/迁移/前端回归；相关后端 `29 passed`，NotificationList `4 passed`。
- [ ] 真实 SMTP、企业微信、钉钉联调后再确认供应商错误码映射、重复投递语义和历史清理周期。

## 2026-08-13 通知投递历史保留策略（代码阶段完成）

- [x] 新增 `NOTIFICATION_DELIVERY_CLEANUP_ENABLED` 与 `NOTIFICATION_DELIVERY_RETENTION_DAYS`（默认开启、30 天，范围 1-3650）。
- [x] Beat 每日调度 maintenance 任务 `cleanup_old_notification_deliveries`，过期记录按 `created_at` 删除；关闭开关不会建立数据库会话。
- [x] 启动配置 UI、`.env.example`、启动配置文档和用户手册同步；清理任务回归已补充。
- [ ] 生产环境需确认合规保留周期、归档方式和删除审计要求。

## 2026-08-13 审计日志保留策略（代码阶段完成）

- [x] 新增 `AUDIT_LOG_CLEANUP_ENABLED`（默认关闭）和 `AUDIT_LOG_RETENTION_DAYS`（默认 365 天，范围 1-3650），避免未确认合规策略时自动删除审计数据。
- [x] Beat 每日调度 maintenance 任务 `cleanup_old_audit_logs`；删除与 `audit_log_cleanup` 事件在同一事务提交，失败时整体回滚。
- [x] 启动配置 UI、`.env.example`、启动配置文档和用户手册同步；任务、配置边界和队列路由回归已补充。
- [ ] 生产环境仍需确认审计日志的归档、保留周期和合规访问策略。

## 2026-08-13 审计日志时间范围查询（代码阶段完成）

- [x] 管理员审计日志 API 增加 `created_from` / `created_to` ISO-8601 起止时间筛选，默认查询和既有项目/用户/动作筛选保持兼容。
- [x] 结束时间早于开始时间时返回明确的 `422` 参数错误；前端审计日志页增加带时间的范围选择器和重置行为。
- [x] 补充 API 契约与前端回归；完整后端 `2017 passed`，前端 `47 files / 198 tests passed`，type-check/build 通过。

## 2026-08-13 审计日志 CSV 导出（代码阶段完成）

- [x] 管理员可以按当前项目、用户、动作和时间范围筛选导出审计日志 CSV；页面默认最多导出 5000 条，服务端上限为 10000 条。
- [x] 导出复用审计查询权限和筛选条件，使用 UTF-8 BOM，并保护可能被表格软件解释为公式的文本，避免无界全量导出和常见公式注入风险。
- [x] 成功导出写入 `audit_log_export` 审计事件，记录操作者、筛选摘要、上限和条数，不写入日志正文或敏感信息。
- [x] 审计页面动作筛选补齐 `audit_log_cleanup` 和 `audit_log_export`，可直接定位治理任务和导出行为。
- [x] 补充 API 契约、权限/边界和前端下载回归；完整后端 `2018 passed`，前端 `47 files / 199 tests passed`，type-check/build 通过。
- [ ] 生产环境仍需结合合规要求确认导出审批、留痕、归档和进一步脱敏策略。

## 2026-08-13 通知渠道真实环境验收入口（代码阶段完成）

- [x] 新增 `scripts/notification-channel-smoke.py`，使用环境变量凭据调用测试发送接口，并在等待窗口内核对投递历史新记录、渠道、状态和实际尝试次数。
- [x] 验收报告只保留脱敏 URL、配置 ID、渠道和安全错误摘要；新增 `docs/notification-channel-acceptance.md`，明确 SMTP/企业微信/钉钉的真实环境验收标准。
- [x] 新增脚本契约回归 `3 passed`，不连接外部服务即可验证凭据入口和脱敏边界。
- [ ] 真实 SMTP、企业微信、钉钉公网联调、供应商限流和收件人/消息接收证据仍需目标环境执行。

## 2026-08-13 通知服务测试隔离修复（代码阶段完成）

- [x] 修复通知服务测试对其他测试导入顺序的隐式依赖；单文件执行时显式加载完整 ORM 模型注册表。
- [x] Services 独立扫描 `74 passed, 0 failed`，Worker 独立扫描 `42 passed, 0 failed`；这两项结果不替代全量非集成回归，但证明相关测试域可独立收集和运行。
- [x] API 及其余测试文件独立通过；当前全量非集成后端 `2018 passed`，`269` 个测试文件逐文件 `passed`。
- [x] 验收脚本已同步 Makefile、CI 和 pre-commit 的 Ruff/格式门禁，质量一致性测试通过。

## 2026-08-13 通知错误信息脱敏（代码阶段完成）

- [x] 重试、SMTP、企业微信、钉钉和测试发送 API 统一使用脱敏异常摘要，避免供应商 URL 用户信息、Token、Key、Secret、Password、签名或 Cookie 进入日志、接口错误和投递历史。
- [x] 补充异常文本和 API 错误返回回归；相关定向测试 `36 passed`，完整非集成后端 `1992 passed`。
- [ ] 真实供应商返回码和后台消息 ID 仍需外部渠道联调确认，不能用本地异常桩替代。

## 2026-08-13 通知历史清理审计（代码阶段完成）

- [x] 通知历史清理任务在实际删除时写入系统审计事件，记录删除数量和保留天数，并保证删除/审计同事务提交。
- [ ] 生产环境仍需确认审计日志自身的保留、归档和合规访问策略。

## 2026-08-13 通知投递记录写入容错（代码阶段完成）

- [x] 投递记录对象加入、提交和回滚统一处理；历史记录写入失败不会反向改变通知执行或测试发送结果。
- [x] 新增写入失败回归，通知服务定向测试 `16 passed`。

## 2026-08-13 历史投递记录读取脱敏（代码阶段完成）

- [x] 投递历史 API 在返回旧记录时再次脱敏错误摘要，兼容策略上线前已存在的记录。
- [x] 增加旧 Token/换行内容回归，API/通知服务定向测试 `30 passed`。

## 2026-08-13 覆盖率门禁复核（代码阶段完成）

- [x] 后端覆盖率门禁 `82.10%` 通过（要求 `82%`），同次非集成回归 `2005 passed`。

## 2026-08-13 外部目标连接复核

- [ ] 已多次尝试对配置的 Linux 目标执行只读 MCP 系统概览，最近一次仍返回 `Transport closed`；未取得外部主机、性能 Worker、Prometheus 或真实目标证据，连接恢复后继续阶段 2 验收。

## 2026-08-13 Web 录制 Worker 心跳容错（代码阶段完成）

- [x] 初始注册和持续心跳同时捕获底层 Redis 客户端普通异常；心跳失败时清理健康文件并继续重试，使 Compose/Helm 探针不会沿用过期健康状态。
- [x] Web 录制 API、Transport 和部署契约定向回归 `55 passed`，Ruff/格式检查通过。
- [ ] Linux/Xvfb、Firefox/WebKit、跨副本 Redis 路由和真实录制 E2E 仍需目标环境验收。

## 2026-08-13 Web Worker 外部验收入口（代码阶段完成）

- [x] 新增 `scripts/web-recording-worker-smoke.py`，默认做 Worker 模式/容量预检；显式 `--run-recording` 才执行真实录制启动、状态查询、可选截图和停止。
- [x] 验收脚本使用环境变量认证，报告对 URL、错误和输入脱敏，并同步 Makefile、CI、pre-commit 与 Runbook；脚本契约/质量一致性回归 `14 passed`。
- [ ] 真实 Linux/Xvfb、Firefox/WebKit、跨副本 Redis 路由和目标页面录制仍需外部环境证据。

## 本轮开发收口记录

- 已完成 Mock 条件匹配与多规则确定性优先级；数据集准备动作增加公网 URL/DNS 安全校验，显式拒绝非数组配置。
- 已完成 MinIO 数据集元数据响应、存储表格行模型和项目导入导出存储模式支持；大数据集按 50MB 校验并在导入失败时清理已上传对象。
- 最终验证：非集成后端 `1967 passed`；前端 `45 files / 188 tests passed`；type-check、build、Ruff、格式检查和 `git diff --check` 通过。

## 2026-08-12 工作顺序调整：暂缓 Android 真机

- 当前先不连接 Android 真机；Windows ADB 真实设备验收、安装/启动、操作断言、截图/日志回传和多设备并发保持待验收，不把无设备状态伪造成通过。
- 本轮优先完善不依赖真机的产品闭环：存储管理页增加项目级数据集对象核对、孤儿对象明细和二次确认清理；Android 之外的 API、Web、性能、数据集和发布文档继续按计划推进。
- 存储治理 UI 默认只读，只有先对当前项目完成核对并确认存在孤儿对象后才允许发起 `purge=true`；真实 MinIO 集群权限、备份恢复和大数据量仍需环境验收。

## 2026-08-12 Mock 条件响应增强

- 已完成：保留字符串精确匹配，并增加 `$exists`、`$contains`、`$in` 三种受控条件操作符，Query、Header、Body 统一生效。
- 已完成：创建、编辑和导入共用 Pydantic 校验，限制条件数量、操作符形状和 `$in` 标量数量；运行时未知或遗留异常条件安全不命中，不执行用户代码或正则。
- 已完成：多规则选择采用确定性优先级（方法精确、路径静态段、占位符数量、条件字段数量、规则 ID），并补充同路径条件冲突与模板路径冲突回归。
- 已完成：Mock 页面支持 JSON 条件类型并展示操作符用法；后端定向回归 `34 passed`，完整非集成后端 `1967 passed`，前端 Mock 页面 `5 passed`、全量前端 `45 files / 188 tests passed`、type-check/build、Ruff、格式和差异检查通过。
- 下一步：在产品化收口阶段补充真实业务接口的多规则优先级/冲突验收，并继续推进 Linux/Kubernetes、专用 Web Worker 和外部通知渠道验收。

## 2026-08-12 存储容量告警入口

- 已完成：存储管理页接入现有 `GET /api/v1/storage/alert`，展示当前容量告警、占用 GB、阈值和触发时间。
- 已完成：告警状态支持单独刷新；告警读取失败只提示，不阻断统计、清理策略和数据集对象治理。
- 已完成：补充中文/英文文案和页面回归；存储页面定向测试 `8 passed`，前端全量 `45 files / 185 tests passed`，type-check 通过。

## 2026-08-12 测试套件并行会话隔离

- 已完成：并行套件中的每个子用例使用独立 SQLAlchemy `AsyncSession`，避免多个并发用例共享会话造成事务交叉和状态污染。
- 已完成：顺序套件和轻量测试桩保持原有路径；补充会话隔离回归，套件配置/执行链定向测试 `43 passed`。

## 2026-08-12 API 登录态复用与套件边界

- 已完成：创建或编辑并行套件时，后端检查其中的 API 用例；开启项目 API 登录态复用的用例会被明确拒绝，避免 Cookie 登录顺序不可预测。
- 已完成：套件页面保存失败时展示后端具体原因，而不是统一显示“保存失败”；串行套件仍可按用例选择是否复用项目登录态。
- 已完成：补充 API/前端回归，后端套件校验 `20 passed`，SuiteList 页面 `6 passed`，type-check 通过。

## 2026-08-12 本轮推进：运行级数据准备

- 已完成：新增受限 `dataset_prepare_actions`，支持 API seed 请求、共享变量和响应提取；参数化 Worker 在创建子运行前执行一次，失败即阻断。
- 已完成：数据准备 URL 在请求前进行公网/DNS 地址校验，非法动作结构明确失败；MinIO 数据集元数据编辑保持 rows 响应一致，存储核对表格修复孤儿对象展示。
- 已完成：补充 HTTP 方法/动作数量/超时/响应大小限制，CaseFormDrawer JSON 配置入口、服务/Worker 回归和操作文档。
- 已完成：新增管理员 MinIO 数据集对象核对接口；默认只读扫描项目范围内的对象引用，显式 `purge=true` 才清理孤儿对象，删除失败会逐项返回并写入审计日志。
- 已完成：更新/上传/回滚使用唯一当前对象和提交后清理；数据库提交或版本快照失败时清理本次新对象并保留旧引用。
- 已完成：项目导入导出快照携带数据集存储方式；MinIO 大数据集导出不再受 500 行传输限制，导入时写入目标项目对象前缀并在失败时清理已上传对象。
- 已完成：执行记录清理预览复用实际项目过滤范围；全局预览排除 retention override 项目，四类运行记录的预览和执行范围一致。
- 已完成：执行结果在前端展示各项目实际清理明细，补足项目级保留策略的可核对性。
- 已完成：性能 Worker 的提前终止分支统一进入项目通知链路，覆盖测试定义缺失、执行器/节点校验失败、容量不足和启动前取消；性能 Worker/通知定向回归 `14 passed`。
- 已完成：性能通知正文补充 RPS、P95/P99、错误率、阈值状态和触发原因，并覆盖中英文邮件/Markdown 格式回归。
- 已完成：发布就绪清单升级为 Q18 扩展版，补充 MinIO 治理、运行记录清理、性能通知和外部 Worker 验收证据要求；发布/灾备文档契约回归 `23 passed`。
- 待验收：真实测试服务 seed、真实 MinIO 大数据集及对象生命周期清理；不得用本地桩测试替代外部环境结论。

## 目标

当前平台的基础 API、Web UI、Android、AI、Mock、数据集、项目管理和性能测试代码主链已经完成。下一阶段重点从“代码已实现”推进到“真实环境可验收、日常使用闭环完整、可作为发布依据”。

## 开发顺序

| 阶段 | 优先级 | 工作项 | 当前状态 |
| --- | --- | --- | --- |
| 1 | P1 | Windows 真实 Android 设备验收 | 暂缓：ADB 验收脚本、脱敏证据和回归测试已完成；按当前环境暂不连接真机 |
| 2 | P1 | Linux/Kubernetes 性能栈验收 | 待开始：专用 Worker、真实目标、TLS、Prometheus、取消和资源采样 |
| 3 | P1 | Web 专用 Worker 验收 | 待开始：Linux/Xvfb、Firefox/WebKit、Trace、网络日志和跨副本 E2E |
| 4 | P1 | iOS/macOS/Appium 最小闭环 | 进行中：验收脚本、status/session smoke、受控步骤和脱敏附件证据已完成；真实 macOS、Simulator/iPhone、IPA 签名和 XCUITest 待目标环境 |
| 5 | P2 | 产品化收口 | 进行中：大型数据集 MinIO、项目级运行记录清理、性能 Run 通知、通知有限重试和存储治理 UI 已完成；真实治理、外部通知渠道、E2E、覆盖率和发布 Runbook 待推进 |

## 阶段 1：Windows Android 真实设备验收

### 本轮开发内容

- 新增 `scripts/windows-android-acceptance.ps1`。
- 自动发现 `adb.exe`，支持 `ATP_ADB_HOME`、`ANDROID_HOME`、`ANDROID_SDK_ROOT` 和用户级 Android SDK 路径。
- 检查设备是否处于 `device` 状态。
- 检查 ADB shell、设备属性、Package Manager 和 logcat 可读性。
- 支持通过 `-Target` 指定设备序列号或 IP:端口。
- 支持通过 `-AppPackage` 检查指定 APK 包是否已安装。
- 输出不包含日志内容、密码或 Token 的 JSON 验收报告。
- 与 `windows-local-smoke.ps1 -RequireAndroid` 配合验证“真实设备 + 后端 Android Worker”完整链路。

### 验收命令

```powershell
.\scripts\windows-android-acceptance.ps1
.\scripts\windows-android-acceptance.ps1 -Target '<device-ip>:5555'
.\scripts\windows-android-acceptance.ps1 -Target '<serial>' -AppPackage 'com.example.app'
.\scripts\windows-local-smoke.ps1 -RequireAndroid -AndroidTarget '<device-ip>:5555'
```

### 完成标准

- ADB 设备状态为 `device`。
- shell、设备属性、Package Manager 和日志读取通过。
- 指定应用包时能够确认安装状态。
- 生成脱敏 JSON 证据。
- 真实 Android 低代码用例至少完成一次安装/启动、操作、断言、截图或日志回传和执行结果查看。
- 多设备并发和故障恢复需要在真实设备池上单独验收，不能由单设备脚本代替。

## 阶段 2：Linux/Kubernetes 性能栈

### 本轮开发进展（2026-08-12）

- 已为 `scripts/performance-environment-smoke.py` 增加 Prometheus 验收：检查 `/-/ready`、执行安全的 PromQL 查询并记录结果数量。
- Prometheus 地址只允许 HTTP(S)，拒绝用户名、密码、查询参数和片段，避免把凭据混入验收请求或证据。
- 已补充 readiness/query 成功、URL 安全校验和回归测试；真实 Linux/Kubernetes 集群、生产 Prometheus 与外部目标仍需目标环境执行。

- 启动专用 performance Worker 和 Prometheus。
- 使用真实 TLS HTTP/gRPC、Locust、JMeter 目标完成 smoke、取消、allowlist 和资源采样。
- 验证多节点分片、结果聚合、容量分析、基线回归和告警通知。
- 形成带环境、命令、时间、摘要和附件的 JSON/JTL/HTML 证据。

## 阶段 3：Web 专用 Worker

### 本轮开发进展（2026-08-12）

- Web Recording Worker 新增基于 Redis 注册/心跳的健康标记；Compose 和 Helm 已接入 readiness/liveness 探针。
- Worker 停止或心跳持续失败时，健康标记会被删除或超过 30 秒未更新，编排层不会继续把异常 Pod 当作可用录制节点。
- 浏览器矩阵 smoke 新增可选 Trace、HAR、Console、失败请求和 HTTP 错误摘要，且对证据 URL 做脱敏。
- Windows 本机 Chromium/Firefox/WebKit 矩阵已真实通过，汇总证据见 [`docs/evidence/web-browser-matrix-local-smoke-2026-08-12.json`](evidence/web-browser-matrix-local-smoke-2026-08-12.json)。
- 新增 `GET /api/v1/web-recordings/workers` Worker 状态接口；Web 录制弹窗现在会区分 `local` / `worker` 模式，展示已注册数量和可用容量，并在 Worker 无空闲容量时提前禁用开始录制。
- Worker 状态接口只返回脱敏后的容量信息和不可逆 Worker 编号摘要，不暴露原始 Worker ID、主机名和进程号；补充后端路由与前端弹窗回归测试，Web 录制定向后端 `36 passed`、弹窗前端 `3 passed`。
- Windows 全量冒烟新增 Web 录制状态预检：`local` 模式验证 API 本地录制就绪，`worker` 模式验证至少一个注册且有空闲容量的 Worker，并把模式/容量摘要写入脱敏报告。
- 真实 Linux/Xvfb、Firefox/WebKit、Trace/网络日志和跨副本 E2E 仍需目标环境验收。

- 在 Linux/Xvfb 上部署独立 Web 录制和执行 Worker。
- 真实验收 Chromium、Firefox、WebKit、Trace、Console、网络时间线、文件上传下载和视觉基线。
- 验证多副本 Worker 的 Redis 路由、容量切换、超时清理和跨副本 E2E。

## 阶段 4：iOS/Appium

### 本轮开发进展（2026-08-12）

- 新增 `scripts/ios-appium-acceptance.py`：默认检查 Appium `/status`，显式 `--session-smoke` 才创建并销毁 W3C/XCUITest 会话。
- 支持受控步骤、截图、可选录屏和 syslog；报告只写脱敏元数据、附件哈希和步骤状态。
- 已补充 Appium URL 凭据校验、会话清理、截图/录屏顺序和 Runbook 契约回归；相关脚本与 iOS Worker/路由/租约回归共 90 项通过。
- 真实 macOS/Xcode/WDA/iPhone/Simulator 仍需目标环境执行，Windows/Linux 的 status-only 结果不能替代真实 iOS 闭环。

- 准备 macOS Worker、Appium 2、XCUITest 和签名证书。
- 完成 Simulator/iPhone 的 IPA 安装、启动、点击/输入、断言、截图、录屏和日志回传。
- 验证设备租约、专用队列、故障释放和统一报告。

## 阶段 5：产品化收口

### 本轮开发进展（2026-08-12）

- 测试数据集支持 `database` / `minio` 两种存储模式；MinIO 模式使用 50MB JSON 上限，数据库保存对象引用、版本引用和行数元数据。
- CRUD、版本快照/回滚、参数化用例、性能数据集、AI 样例和项目导出均通过统一 helper 读取 MinIO 数据；MinIO 故障会明确失败，不会静默变成空数据。
- 管理员可调用 `POST /api/v1/projects/{project_id}/datasets/storage/reconcile` 做项目级对象治理：默认 dry-run；仅在请求体传 `{ "purge": true }` 时删除未被数据库引用的对象，接口返回扫描、引用、孤儿、删除和错误统计。
- 存储管理页已增加项目选择、只读核对、孤儿对象明细、截断/错误提示和二次确认清理；清理按钮必须基于当前项目最近一次发现的孤儿对象，避免跨项目误删。
- 数据集管理页增加存储方式选择，已补充迁移、后端服务/API 和前端页面回归；完整非集成后端 `1944 passed`，264 个测试文件独立运行 `264 passed, 0 failed`，前端 `45 files / 185 tests passed`、type-check/build 通过。真实 MinIO 集群大数据量、对象生命周期和发布环境仍需验收。

- 大型测试数据集 MinIO 引用模式和数据准备 Hook。
- 项目级运行记录真实清理和保留策略。
- 邮件、企业微信、钉钉等性能通知渠道真实联调。
- 在真实 SMTP/Webhook 环境验证有限重试、429/5xx 退避、供应商限流和重复投递语义。
- 增加通知投递历史的保留/清理策略，并在真实渠道联调后固定错误码映射。
- 套件、计划、Android、性能和通知场景的真实后端 E2E。
- 完善前端关键流程覆盖率、发布 Runbook、备份恢复和生产部署证据。

## 状态约束

- 本地测试通过不代表真实设备、节点或外部服务验收通过。
- 未连接 Android 设备时，验收命令必须失败或明确提示，不能生成伪造通过证据。
- 每项真实环境验收必须记录环境、命令、时间、结果和附件；凭据、Token、日志敏感内容不得写入报告。
