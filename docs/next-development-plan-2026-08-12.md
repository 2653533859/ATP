# ATP 下一阶段开发计划（2026-08-12）

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
| 5 | P2 | 产品化收口 | 进行中：大型数据集 MinIO、项目级运行记录清理、性能 Run 通知和存储治理 UI 已完成；真实治理、外部通知渠道、E2E、覆盖率和发布 Runbook 待推进 |

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
- 套件、计划、Android、性能和通知场景的真实后端 E2E。
- 完善前端关键流程覆盖率、发布 Runbook、备份恢复和生产部署证据。

## 状态约束

- 本地测试通过不代表真实设备、节点或外部服务验收通过。
- 未连接 Android 设备时，验收命令必须失败或明确提示，不能生成伪造通过证据。
- 每项真实环境验收必须记录环境、命令、时间、结果和附件；凭据、Token、日志敏感内容不得写入报告。
