# ATP 当前开发计划与导航对齐跟踪（2026-08-25）

> 本文是参考导航对应的当前执行版计划，负责记录“接下来做什么、完成到什么程度、如何验收”。历史方案和详细实施记录见 [`product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md)；任务勾选同步到 [`Task.md`](../Task.md)，长期记忆同步到 [`MEMORY.md`](../MEMORY.md)。

## 1.1 Android 专项应用启动兼容交付（2026-08-25）

本模块作为 N2 Karing 真机门禁前的本地补强，解决 Android 专项执行器把入口固定为 `.MainActivity` 导致真实 APK 无法启动的问题。性能、稳定性和流畅度执行器现在共用 Android 启动辅助：明确填写 Activity 时使用 `am start -n`，留空时使用 Launcher Intent 自动发现入口；流畅度执行器同时尊重前置操作设置的 `auto_start=false`，避免同一任务重复启动应用。专项任务表单留空启动 Activity 时不再写入 `.MainActivity` 默认值，旧任务中已有的显式 Activity 仍保持兼容。

- **代码范围**：`backend/app/services/mobile_special/preflight.py`、Android 性能/稳定性/流畅度执行器，以及专项任务中英文启动 Activity 提示和默认值。
- **回归范围**：显式 Activity、Launcher 自动发现、启动失败、前置启动后不重复启动均有回归；受影响后端全量 `2295 passed`，四个改动测试文件独立运行 `3/25/19/15 passed`，前端全量 `67 files / 275 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。
- **状态**：`[E]` 本地实现、代码审查和回归完成；真实 Karing APK、Windows Android Worker/ADB、真实启动组件、专项任务媒体和报告仍待环境验收，不使用其他应用替代。
- **下一入口**：先取得 Karing APK 或真实 `package_name`，在在线 Android Worker 上按 APK → 低代码 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 清理执行；N4 Kubernetes/Prometheus/独立 MinIO 仍作为独立外部环境门禁等待目标。

## 1.2 Windows Android 包名与启动入口验收探针（2026-08-25）

为推进 N2 真机门禁，`scripts/windows-android-acceptance.ps1` 现在支持可选 `-LaunchActivity`：指定 `-AppPackage` 后，脚本先确认包已安装，再通过 `cmd package resolve-activity --brief` 校验显式 Activity，未指定时校验 `MAIN/LAUNCHER` 入口。该检查只解析 Package Manager，不启动或修改应用；脱敏报告新增 `app.package`、请求组件和解析组件，仍不保存包内容或日志正文。

- **回归范围**：脚本契约 `2 passed`，脚本目录 `93 passed`，质量/发布文档回归 `15 passed`，PowerShell 语法检查通过。
- **设备验证**：当前在线设备使用 `com.android.settings` 做自动 Launcher 和显式 `.Settings` 两条只读探针，均通过；这不代表 Karing 已安装或关闭 Karing 真机门禁。
- **状态**：`[E]` 本地脚本、文档、回归和设备探针完成；真实 Karing APK/包名、Worker 调度、低代码、录屏/异常回放、专项任务和报告仍待验收。
- **下一入口**：用户提供或上传 Karing APK 后，以 Manifest 包名、设备 `pm path` 和 Activity 解析三重证据确认目标，再执行单设备 Android 闭环。

## 1.3 Android 低代码控件属性录制与坐标回退（2026-08-25）

本模块补齐 Android 可视化录制的“可读定位 + 可执行兜底”链路。点击截图时保留 UIAutomator 返回的文本、resource-id、content-desc、className 和 bounds，同时保存原始屏幕坐标；回放优先按 resource-id、文本、无障碍描述定位，控件属性找不到或 UIAutomator 不可用时回退录制坐标。这样既不会把录制结果退化成只有坐标，也避免页面轻微变化后步骤完全无法执行。

- **代码范围**：`frontend/src/utils/androidRecording.ts`、`frontend/src/components/common/AndroidStepEditor.vue`、`backend/app/worker/executors/android_lowcode_executor.py`。
- **回归范围**：后端 Android 低代码执行器定向 `42 passed`，非集成全量 `2297 passed`；前端录制参数与标准步骤定向 `4 passed`，前端全量 `68 files / 277 tests passed`；`vue-tsc`、生产构建、后端 Ruff、格式检查和 `git diff --check` 均通过。
- **代码审查**：独立检查确认选择器优先级为 resource-id → 文本 → content-desc，坐标仅作为最后回退；未发现可操作问题。
- **状态**：`[E]` 本地实现、回归和审查完成；真实 Karing 仍需在 Windows Android Worker 上验证 UIAutomator 权限、录制控件属性、低代码执行和媒体/报告链路，不能用 `com.android.settings` 探针替代。
- **下一入口**：取得 Karing APK/真实包名后，执行单设备 APK → 控件属性录制 → 低代码回放 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 清理闭环。

## 1.0 当前计划登记（2026-08-25）

本节是当前最新执行口径，优先于本文后面的历史交付记录。N4 的本地代码链路已经覆盖 Worker/目标服务采样、Kubernetes 容量预检、保留清理、跨端点 MinIO 恢复和生命周期门禁；下一步不重复开发已有采样器，而是按真实目标逐项验收，并同步推进被外部条件阻塞的 N2 与发布收口。

### 下一阶段顺序

1. **N4 性能生产环境验收**：先用真实 Kubernetes 目标执行多节点、Worker 副本和资源门禁；再用独立 MinIO 目标执行复制、回源、生命周期和清理；最后用真实 Prometheus 验证 Worker 与目标服务指标来源、查询失败记录和报告时间线。没有对应目标时保持“待环境验收”，不得用 q19 Compose 或 mock 替代。
2. **N2 Karing Android 单设备闭环**：用户提供/上传 Karing APK 后，以 `pm list packages` 和 Manifest 双重确认 `package_name`，再执行 APK 下载、低代码点击/滑动、录屏/异常回放、专项任务、事件/日志/报告和清理；在真实包确认前不使用其他应用替代。
3. **N5-N8 外部依赖复核**：按真实三方模型、通知供应商、外部缺陷平台、项目/角色数据和目标部署顺序验收；凭据只通过环境变量或临时部署注入，测试数据完成后清理。
4. **N9 发布收口**：绑定最终提交 SHA，整理能力矩阵、测试输出、代码审查记录、环境证据、操作手册、回滚边界和未关闭门禁，形成可复核的发布结论。

### 下一项模块登记：N4 真实性能环境门禁

| 项目 | 内容 |
| --- | --- |
| 范围 | Kubernetes 多节点/副本/Worker 资源预检、Worker/目标服务指标采样、MinIO 生命周期与跨端点恢复、运行指标/报告和临时对象清理 |
| 已有入口 | `scripts/performance-environment-smoke.py`、`scripts/minio-dr-acceptance.py`、`make minio-dr-acceptance`、`--require-metric-source` |
| 依赖 | 可控 Kubernetes 集群、独立 MinIO 源/目标端点、Prometheus 地址及最小权限凭据 |
| 最小验收出口 | 多节点短压成功；容量不足/资源缺失明确失败；至少得到 `performance-worker` 和 `target-service-prometheus` 非空样本；MinIO 复制/回源 SHA-256 一致；生命周期规则命中；临时对象清理为零；证据不含凭据 |
| 当前状态 | `[E]` 本地实现与回归完成，真实环境缺失，暂不关闭 N4 发布门禁 |
| 复验命令 | `make performance-environment-smoke`；`make minio-dr-acceptance`；按目标配置追加 `--min-ready-nodes`、`--min-worker-replicas`、`--require-worker-resources` 和 `--require-metric-source` |

### 统一交付门禁

下一项模块仍必须按“实现/调整 → 定向回归 → 受影响全量质量门禁 → 独立代码审查 → 修复 → 同步 `Task.md`、路线图、发布状态和 `MEMORY.md` → Conventional Commit 提交并推送”执行。外部目标缺失时，只记录可复用入口和阻塞证据，不把跳过项标为通过。

## 0.9 当前开发计划登记（2026-08-25）

本节是当前执行口径，优先级高于本文后面的历史交付记录。产品导航按参考方案保持五组：工作台、测试能力、测试资产、智能中枢、系统；设备、APK、专项任务、Mock、数据集、Web/API 资产和平台治理页面保留兼容 URL，但从所属工作台或配置中心进入，不再全部堆在系统管理下。

### 当前阶段台账

| 阶段 | 导航模块 | 当前目标 | 状态 | 进入下一阶段的条件 |
| --- | --- | --- | --- | --- |
| N0 | 工作台 | 稳定首页、待办、项目中心、任务中心的项目上下文、深链、权限和任务事件 | `[E]` | 真实账号复核刷新、窄屏、角色和任务状态 |
| N1 | 接口测试 | 受控 GraphQL、WebSocket、流式 gRPC 和 HTML/JUnit/PDF 完整报告闭环已完成 | `[E]` | 协议创建/执行/断言/提取/报告/清理均有脱敏证据 |
| N2 | APP 自动化 | 等待 Karing 真实 APK/包名，完成单设备执行、录屏、专项任务和结果回传 | `[-]` | 设备包管理确认包名，且低代码、专项、媒体、报告和清理通过 |
| N3 | UI 自动化 | 维护 Playwright 录制、回放、元素/页面对象、Trace/HAR 和浏览器矩阵 | `[E]` | Chromium、Firefox、WebKit 的失败证据可追踪 |
| N4 | 性能测试 | Worker/目标服务采样、Kubernetes 多节点/副本/Worker 资源预检、保留清理和跨端点 MinIO 复制/恢复 smoke 已完成 | `[E]` | 多节点容量、取消、采样、报告、生命周期和恢复演练有真实环境证据 |
| N5-N8 | AI、测试资产、智能中枢、系统 | 以真实项目、模型、角色和目标部署复核本地能力 | `[E]` | 来源、权限、脱敏、审计和回滚均可复核 |
| N9 | 发布收口 | 汇总代码 SHA、测试、证据、操作手册和剩余阻塞 | `[~]` | 所有未关闭门禁都有负责人、原因和复验命令 |

### 当前执行顺序

1. **N4 性能真实环境**：本地代码入口已齐；下一步只做真实 Kubernetes、Prometheus、MinIO 目标验收，验证多节点调度、资源采样、生命周期、保留清理和跨主机恢复。
2. **N2 Android Karing 单设备门禁（阻塞但不阻塞 N4）**：用户提供或上传 Karing APK 后，以 `pm list packages` 和 Manifest 解析结果确认真实 `package_name`，再按 APK → 低代码 → 录屏/异常回放 → 专项任务 → 事件/日志/报告 → 下载/清理执行。
3. **N5-N8 外部依赖复核**：在 N4 不具备生产目标时，继续验证真实模型、通知、外部缺陷平台、项目数据、权限、审计和配置回滚。
4. **N5-N8 外部依赖复核**：依次验证真实 AI 模型、通知供应商、外部缺陷平台、项目数据、权限、审计和配置回滚。
5. **N9 发布收口**：生成最终能力矩阵和证据索引；未通过项保持“待环境验收”，不得用 mock、跳过项或页面可打开替代。

### 统一模块交付门禁

每完成一个模块，必须依次完成：实现/调整 → 定向回归 → 受影响全量质量门禁 → 独立代码审查 → 修复审查问题 → 同步 `Task.md`、路线图、发布状态和 `MEMORY.md` → Conventional Commit 提交并推送。只有完成这一闭环，才允许把模块状态从 `[~]` 改为 `[x]` 或 `[E]`。

### 0.9.2 N1 受控协议目标交付

- **实现范围**：`acceptance-target` 增加 GraphQL POST、WebSocket 握手/文本回显；目标测试覆盖 gRPC Unary、Server Streaming、Client Streaming 和 Bidi Streaming。
- **真实证据**：q19 GraphQL run `19`、WebSocket run `20`、gRPC Server Streaming run `23`、Client Streaming run `24`、Bidi Streaming run `25` 全部通过，临时项目清理后同名项目匹配数为 `0`。脱敏证据见 [`evidence/api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)。
- **质量门禁**：目标/部署契约和协议执行器回归 `90 passed`，后端非集成全量 `2288 passed`，Ruff、格式检查、`git diff --check` 和独立代码审查通过；代码提交 `5b07a3e` 已推送。
- **边界**：本项不关闭完整报告导出/详情治理、生产协议服务或外部环境门禁，下一入口为 N1 完整报告闭环。

### 0.9.3 N1 完整报告闭环交付

- **实现范围**：运行详情页新增 JUnit XML 导出，HTML/PDF/JUnit 三种报告格式均可从详情页下载；既有步骤、截图、录像、设备矩阵和错误证据继续由详情/HTML 报告承载。
- **真实证据**：q19 临时项目 `42`、用例 `27`、运行 `26` 通过；详情 `200`，HTML `200/2561 bytes`、JUnit XML `200/220 bytes` 且可解析、PDF `200/167056 bytes`；删除临时项目后匹配数 `0`。脱敏证据见 [`evidence/report-closure-2026-08-25.json`](evidence/report-closure-2026-08-25.json)。
- **质量门禁**：前端定向 `11 passed`、后端报告/导出 `24 passed`、前端全量 `67 files / 275 tests passed`，类型检查、生产构建、`git diff --check` 和独立代码审查通过；代码提交 `86f3bf7` 已完成。
- **边界**：本项关闭 q19 受控报告详情/导出证据；生产协议服务、生产对象存储和外部发布环境仍保持待验收，下一入口为 N4 性能真实环境。

### 0.9.4 N4 Kubernetes 性能容量预检

- **实现范围**：扩展 `scripts/performance-environment-smoke.py` 的 Kubernetes 检查，可选验证可调度 Ready 节点数、性能 Worker Deployment 的 desired/available 副本数，以及指定 Worker 容器的 CPU/内存 `resources.requests/limits`。
- **使用方式**：在真实集群验收时追加 `--min-ready-nodes`、`--min-worker-replicas` 和 `--require-worker-resources`；默认不启用，既有 Deployment/Pod smoke 行为保持兼容。
- **质量门禁**：脚本回归 `29 passed`，Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- **边界**：当前 Linux 目标只有 Docker Compose、没有 Kubernetes 集群，本项只关闭预检实现和本地回归，不关闭真实多节点、生产 Prometheus/MinIO 生命周期或跨主机恢复。

### 0.9.5 N4 跨端点 MinIO 恢复验收入口

- **实现范围**：新增 `scripts/minio-dr-acceptance.py`，从 `ATP_MINIO_DR_SOURCE_*` 与 `ATP_MINIO_DR_TARGET_*` 读取两端连接信息，验证源端探针回读、目标端复制/回读、恢复回源和 SHA-256 一致性，并在结束时清理唯一前缀下的临时对象。
- **生命周期门禁**：默认审计两端规则数量；通过重复参数 `--require-lifecycle-rule PREFIX=DAYS` 时，要求两端均存在 `Enabled`、前缀和过期天数完全匹配的规则。报告只包含端点、桶、规则要求和摘要，不包含账号、密钥或对象内容。
- **质量门禁**：脚本回归 `3 passed`；质量门禁一致性和灾备文档回归 `17 passed`，Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- **边界**：当前 `172.31.27.133` 没有独立 MinIO 灾备端点，因此本项只关闭验收入口和本地回归；真实跨主机恢复、生产生命周期和长期保留仍待目标环境。

## 1. 目标导航

产品导航按五组组织，侧栏只承担高频入口；设备、APK、专项任务、Mock、数据集、Web/API 资产和治理页面保留兼容 URL，但从所属工作台或配置中心进入。

| 导航分组 | 入口 | 主要职责 |
| --- | --- | --- |
| 工作台 | 首页、我的待办、项目中心、任务中心 | 统一项目上下文、待办聚合、任务队列和操作反馈 |
| 测试能力 | 接口测试、APP 自动化、UI 自动化、性能测试、AI 智能测试 | 完成配置、执行、过程观察、报告和证据闭环 |
| 测试资产 | 测试用例、测试计划、缺陷管理、测试报告、用例评审 | 管理可复用资产，串联运行、失败证据、缺陷和评审 |
| 智能中枢 | Hermes 助手、需求与用例生成、知识中枢 | 提供可追溯查询、草稿生成、需求追踪和知识检索 |
| 系统 | 远程工具箱、配置中心 | 依赖诊断、配置版本/差异、审计和精确回滚 |

## 2. 状态口径

- `[x]` 已完成：代码、测试、审查、修复和文档均已完成，并且本地质量门禁通过。
- `[E]` 已实现待环境验收：本地实现和回归已完成，但还缺真实设备、协议服务、模型、外部平台或目标部署证据。
- `[~]` 进行中：仍有代码、联调或验收工作，不能作为发布通过。
- `[ ]` 未开始：尚未进入实施。
- `[-]` 阻塞/暂缓：需要外部条件或用户提供信息；必须写明解除条件。

`[E]` 不等同于生产通过；mock、协议桩、跳过项、Worker 心跳和页面可打开都不能替代真实业务证据。

## 3. 当前模块台账

| 顺序 | 模块 | 已完成 | 当前剩余工作 | 最小验收出口 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 0 | 导航壳与信息架构 | 五组侧栏、深层路由选中、旧 URL 映射、面包屑和权限入口 | 用当前账号补刷新、窄屏、角色和项目上下文复核 | 五组入口可达；刷新/深链不丢上下文；权限隐藏一致 | `[E]` |
| 1 | 工作台与任务中心 | 项目筛选、待办聚合、轮询、重试、终止、批量操作和失败事件 | 用真实项目数据复核五类任务及越权操作 | 任务状态、失败原因、操作事件可追踪 | `[E]` |
| 2 | API 测试工作台 | 环境变量、认证复用、OpenAPI/Postman、HTTP/GraphQL/WebSocket/gRPC、断言/提取/依赖 | q19 已通过 HTTP、会话复用、gRPC TLS Unary、GraphQL、WebSocket、三种流式 gRPC、HTML/JUnit/PDF 报告以及 OpenAPI/Postman 导入预览/落库/回读/清理；协议用例已在保存和派发两层拒绝无效/空步骤 | 请求、断言、变量传递、报告和权限边界完整 | `[E]` |
| 3 | APP 自动化工作台 | Windows Android Worker 配对、扫描、租约、截图/控件、APK 上传与包名解析、通用 APK 低代码录屏和设备产物 | Karing APK/真实包名、专项任务、APK 下载、完整报告和异常回放验收 | 单设备真实 APK 执行；事件、日志、媒体、报告和清理可追踪 | `[~]` |
| 4 | UI 自动化工作台 | Playwright 录制、元素库、页面对象、视觉基线、Trace/HAR、网络/Console 日志、多浏览器 | 用最新 Windows 运行档案复核录制和回放失败证据 | Chromium/Firefox/WebKit 可录制、执行和定位失败 | `[E]` |
| 5 | 性能测试工作台 | 本地压测模型、采样、趋势、基线、报告、保留清理和 q19 短压 | 真实多节点、容量限制、Prometheus/MinIO 生命周期、跨主机恢复 | 真实节点完成短压、取消、采样、报告和恢复演练 | `[~]` |
| 6 | AI 智能测试与 Hermes | 三方模型配置、模型拉取、多模态/思考参数、用例/数据/Mock 草稿生成、调用审计 | 配置可用真实模型，验证来源、限额、失败诊断和敏感值脱敏 | 生成结果可编辑、有来源；无权限/无模型时明确失败 | `[E]` |
| 7 | 测试资产与智能中枢 | 用例—计划—运行—报告—缺陷—评审关联，需求追踪和知识检索本地闭环 | 用真实项目数据复核权限和外部缺陷映射 | 失败运行可追到证据/缺陷/评审，知识结果可追溯 | `[E]` |
| 8 | 远程工具箱与配置中心 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断、配置版本/差异、审计、单资源回滚 | 在目标部署复核密钥、角色和回滚 | 输出脱敏；越权拒绝；回滚精确且可审计 | `[E]` |
| 9 | 发布质量收口 | 发布状态、能力矩阵、证据索引、操作手册和回滚边界 | 绑定最终提交 SHA，关闭或明确所有环境门禁 | 文档、证据、代码 SHA 和未完成项一致 | `[~]` |

## 4. 本轮开发顺序

### 4.1 P0：先关闭当前可验证链路

1. **API 真实协议目标** `[~]`：q19 受控目标已完成临时 API 用例创建、评审审批、HTTP 请求、状态码断言、JSONPath 提取、显式会话复用、gRPC TLS Unary、GraphQL、WebSocket、三种流式 gRPC、OpenAPI/Postman 解析、导入预览/落库/回读/清理、终态查询和清理。证据见 [`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json) 和 [`api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)。完整报告仍保持环境验收项。
2. **Android 单设备闭环**：取得 Karing APK 或真实 `package_name`，按“APK 下载 → 低代码 → 录屏 → 性能/稳定性/流畅度专项 → 事件/日志/报告 → 下载与清理”顺序执行；没有真实包时保持阻塞，不使用其他应用冒充 Karing。
3. **Windows API/Web 复核**：在 Android 阶段不阻塞的同时，用当前有效账号复跑认证、依赖、文件传输、Web 低代码、报告导出和浏览器矩阵，保留脱敏 JSON 证据。

### 4.2 P1：再补真实外部能力

4. **通知供应商**：使用临时 SMTP/企业微信/钉钉目标验证投递、重试、限流、回执和错误脱敏，结束后清理凭据和测试数据。
5. **外部缺陷平台**：使用临时 Jira/禅道/GitHub/GitLab 项目验证创建、去重、状态同步、权限和清理；没有凭据时只维护本地适配器。
6. **性能生产环境**：验证多节点调度、容量拒绝、资源采样、Prometheus/MinIO 生命周期、长期趋势和跨主机恢复；没有 Kubernetes/Prometheus 目标时不关闭门禁。
7. **发布收口**：把同一提交 SHA、测试结果、代码审查记录、环境证据、操作手册和回滚边界汇总到发布状态文档。

## 5. 每个模块的强制交付流程

每个模块都必须按以下顺序执行，不能只修改页面就标记完成：

1. 在本文和 `Task.md` 登记范围、依赖、风险和最小验收出口。
2. 实现或调整代码，补充对应的回归测试；敏感配置只通过环境变量或临时部署注入。
3. 运行定向测试，再运行受影响的全量质量门禁。
4. 独立检查未提交 diff，进行代码审查；发现问题先修复，再重跑门禁。
5. 更新 `Task.md`、`MEMORY.md`、路线图、发布状态和必要的操作手册/证据索引。
6. 使用 Conventional Commit 提交并推送；推送后记录提交 SHA 和验证结果。

## 6. 当前风险与解除条件

| 风险 | 影响 | 解除条件 |
| --- | --- | --- |
| Karing APK/包名未在当前设备确认 | APP 专项任务、应用级动作和完整报告不能验收 | 提供或上传 Karing APK，并以 `pm list packages`/解析结果确认包名 |
| 生产协议服务和发布环境未形成真实证据 | API 工作台只能维持“受控目标已验收、生产环境待验收” | 提供生产协议服务、对象存储和发布窗口，复跑协议/报告/清理证据 |
| 通知、外部缺陷平台无目标凭据 | 不能声称真实投递或外部同步通过 | 提供临时目标和最小权限凭据，且不写入仓库 |
| 生产性能环境未提供 | 多节点、跨主机恢复和生产监控保持待验收 | 提供可控 Kubernetes/Prometheus/MinIO 目标及回滚窗口 |

## 7. 更新记录

- 2026-08-25：登记 1.0 当前执行计划：N4 本地性能采样、Kubernetes 容量预检、MinIO 跨端点恢复和生命周期门禁代码已齐，下一步转为真实目标验收；N2 Karing、N5-N8 外部依赖和 N9 发布收口按依赖顺序跟踪。
- 2026-08-25：API 工作台在 q19 受控 HTTP 目标完成真实创建/审批/执行/状态码断言/JSONPath 提取/清理，定向执行器回归 `77 passed`；证据见 [`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)。
- 2026-08-25：API 工作台显式 `session_lifecycle=reuse` 的两步登录/当前用户场景通过，登录请求体密码在执行证据中脱敏，临时项目清理成功；证据见 [`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)。
- 2026-08-25：补齐 API gRPC TLS 自签名/私有 CA 支持：用例可配置公有 PEM 根证书和 SNI 服务名，执行器拒绝私钥且不把证书写入步骤请求快照；q19 Unary 真实目标通过，临时项目清理成功。证据见 [`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)，代码提交为 `96c7db0`。
- 2026-08-25：加固 OpenAPI/Postman 导入解析：保留 `0/false/空字符串` 示例，解析 Postman 字符串 URL 查询参数，跳过禁用请求头/查询项并支持 urlencoded/formdata 示例；q19 按 `75ed756` 的 `/ai/cases/parse-schema` 真实接口返回 OpenAPI 1 个接口/1 个参数、Postman 1 个接口/3 个参数。证据见 [`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)；导入预览/落库、后续协议和完整报告仍待验收。
- 2026-08-25：完成 API 导入预览/落库闭环并修复异步 SQLAlchemy 懒加载导致的 500：导入读取模块时预加载所属项目，q19 真实完成 OpenAPI 解析（响应码 `201`）→预览 `1/0`→落库 `201`→回读状态断言/步骤结果→项目删除 `204`。定向回归 `42 passed`、后端非集成全量 `2270 passed`，证据见 [`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)，代码提交为 `a8f6e26`；后续只剩其他协议和完整报告验收。
- 2026-08-25：修复 GraphQL/WebSocket/gRPC 空步骤误报通过：派发层在协议执行前拒绝缺失、空数组和 `null` 的 `config.steps`，运行终态为 `error` 并写入可解释原因；API 的旧配置默认主请求兼容不变。派发/HTTP 家族定向 `94 passed`，后端非集成全量 `2279 passed`，前端类型检查、生产构建、Ruff 和差异检查通过；代码审查未发现问题。真实 GraphQL/WebSocket/流式 gRPC 和完整报告目标仍待环境验收。
- 2026-08-25：补齐协议用例保存时校验：创建/更新 GraphQL、WebSocket、gRPC 配置时检查步骤、endpoint/url、消息、target/proto/service/method，失败返回 `422` 且不创建快照/脏用例；与派发层规则保持一致。用例管理定向 `35 passed`，后端非集成全量 `2282 passed`，Ruff、差异检查和代码审查通过。真实协议目标和完整报告仍待环境验收。
- 2026-08-25：补齐报告中心按用例类型统计：后端按当前用户可见项目聚合 API、GraphQL、WebSocket、gRPC、Web、Android 等已完成运行，返回总运行/通过/失败/异常/通过率；前端报告中心增加类型分布、通过率进度条和空态，补齐中英文文案。报告定向回归 `5 passed`、前端报告页 `3 passed`、后端非集成全量 `2282 passed`，`vue-tsc`、生产构建、Ruff 和差异检查通过，代码审查未发现问题。真实多协议目标和完整报告环境证据仍待验收。
- 2026-08-25：修复 Windows smoke 凭据边界：默认只读取当前账号 `ATP_USERNAME/ATP_PASSWORD`，不再自动回退或混用 `FIRST_ADMIN_*`；仅通过显式 `-UseBootstrapCredentials` 才验证全新数据库的初始化账号。补充脚本契约回归和操作手册，避免管理员改密后误报/反复 401；Windows 真实 API/Web smoke 仍需使用当前有效账号复验。
- 2026-08-25：修复报告中心跨用例对比误导：默认从最近记录中选择同一用例的基线/当前运行，切换任一选择器时自动对齐另一侧的同用例记录，并在请求前复核同用例约束；代码审查发现并修复了初版禁用选项造成的选择死锁。报告页回归 `4 passed`，前端全量 `66 files / 270 tests passed`，type-check、生产构建和差异检查通过。
- 2026-08-25：补齐协议用例前端保存校验：抽取 GraphQL、WebSocket、gRPC 的必填项校验纯函数，空字符串/空格和空消息数组在创建/更新请求前直接提示，后端 `422` 继续作为最终防线。工具函数回归 `8 passed`，前端全量 `66 files / 272 tests passed`，`vue-tsc`、生产构建和差异检查通过，代码审查未发现可操作问题；真实协议目标和完整报告仍待环境验收。
- 2026-08-25：补齐 APK 包名身份一致性保护：Manifest 可解析包名时以其为准，手工包名不一致在 MinIO 上传/数据库写入前返回 `400`，匹配值和无 Manifest 场景保持兼容并归一化空白。APK/API 与发布契约定向 `22 passed`，后端非集成全量 `2284 passed`，Ruff、差异检查和代码审查通过；真实 Karing APK、下载端点、专项任务和完整报告仍待环境验收。
- 2026-08-25：补齐 Android 专项任务设备目标校验：创建、更新和手工触发在进入 Worker 前确认 `device_id` 存在，不存在/已下线返回 `400`，避免任务或运行记录进入等待后才失败。专项任务路由 `32 passed`，后端非集成全量 `2287 passed`，Ruff、差异检查和代码审查通过；真实设备在线状态、租约、ADB 操作和 Karing 仍待环境验收。
- 2026-08-25：补齐 Android 专项 APK 选择体验：选择器仅展示已解析包名的资产，选中后自动绑定并锁定包名，清空 APK 同步清除包名，未选择 APK 仍可手工填写；工具函数回归 `2 passed`，前端全量 `67 files / 274 tests passed`，`vue-tsc`、生产构建和差异检查通过，代码审查未发现可操作问题。真实 Karing APK、设备执行、专项任务和完整报告仍待环境验收。
- 2026-08-25：重新完成 Windows API/Web 完整 smoke：当前账号登录、PostgreSQL/Redis/MinIO readiness、Web Worker、Playwright `12 passed`、浏览器矩阵、文件上传/清理、Web 低代码下载、HTML/JUnit 报告和临时项目清理全部通过；脱敏证据为 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)，来源提交 `35ad777`。Android 检查按可选参数跳过，N2 Karing 真实门禁仍未关闭；下一步转向 N1 其他协议/完整报告真实证据。

## 8. 参考导航学习版执行台账（2026-08-25）

这份台账把参考导航中的菜单分组转换成可持续追踪的开发阶段。导航入口可达只代表信息架构完成；只有满足“代码/配置、回归测试、代码审查修复、文档同步和对应环境证据”的模块，才可以关闭本地交付。真实设备、外部服务、第三方模型和生产基础设施缺失时，保留 `[E]` 或 `[-]`，不使用页面截图、mock、跳过项或 Worker 心跳替代验收。

| 编号 | 导航分组 | 阶段目标 | 最小验收出口 | 当前状态 |
| --- | --- | --- | --- | --- |
| N0 | 导航壳与工作台 | 首页、待办、项目中心、任务中心统一项目上下文，深链和权限入口稳定 | 折叠/刷新/窄屏/深链可用；待办、任务状态和失败事件可追踪 | `[E]` 本地完成，真实账号复核随 Windows smoke 维护 |
| N1 | 接口测试 | HTTP、环境变量、会话复用、OpenAPI/Postman 导入、gRPC TLS Unary、GraphQL、WebSocket、流式 gRPC 和完整报告形成闭环 | 请求、断言、提取、依赖、导入预览/落库/回读、报告和清理有证据 | `[E]` q19 受控协议与报告闭环已通过；生产环境独立跟踪 |
| N2 | APP 自动化 | Windows Agent/ADB、APK 包名、低代码、录屏、专项任务、事件/日志/报告回传 | Karing 真实 APK 在单设备上完成执行、失败定位、媒体查看和清理 | `[~]` 通用 APK 链路已通过；Karing 包与专项报告仍阻塞 |
| N3 | UI 自动化 | Playwright 录制、元素/页面对象、视觉基线、Trace/HAR、日志和多浏览器 | Chromium/Firefox/WebKit 均可录制、回放并查看失败证据 | `[E]` 本地/q19 证据已有，继续随 Windows 复核 |
| N4 | 性能测试 | 压测模型、节点分片、采样、趋势、基线、报告和保留清理 | 多节点容量校验、采样、基线门禁、报告和恢复演练可复核 | `[~]` 本地和 q19 短压完成；生产多节点/监控/恢复待验收 |
| N5 | AI 智能测试 | 模型拉取、多模态/思考参数、草稿生成、诊断和调用审计 | 结果带来源、可编辑、可限额；失败和敏感值处理可解释 | `[E]` 本地完成，真实模型和项目数据待验收 |
| N6 | 测试资产 | 用例、计划、缺陷、报告、评审串联运行和证据 | 运行可追到步骤证据、缺陷、评审和项目权限 | `[E]` 本地完成，真实项目和外部缺陷平台待验收 |
| N7 | 智能中枢 | Hermes、需求与用例生成、知识检索形成可追溯入口 | 查询/生成结果可编辑并带来源，不静默写入业务数据 | `[E]` 本地完成，真实模型、需求和知识数据待验收 |
| N8 | 系统 | 远程工具箱、配置中心、审计和单资源回滚集中管理 | PostgreSQL/Redis/MinIO/Worker/ADB 诊断脱敏，回滚精确且可审计 | `[E]` 本地完成，目标部署和密钥边界待复核 |
| N9 | 发布收口 | 汇总能力矩阵、代码 SHA、测试、环境证据、操作手册和回滚边界 | 所有未关闭门禁有负责人、阻塞原因和复验命令 | `[~]` 依赖 N2、N4 及真实外部服务收口 |

### 当前执行游标

1. **N4 性能真实环境**：N1 q19 受控协议与报告闭环已通过；N4 本地采样、容量预检、保留清理和跨端点恢复入口已齐，下一步验证真实多节点、Prometheus/MinIO 生命周期和跨主机恢复。
2. **N2 APP 自动化**：Karing 的真实 `package_name` 尚未确认，暂保持阻塞；拿到 APK 或设备包名后再完成 APK 选择、低代码、录屏/异常回放、专项任务和事件/日志/报告回传。
3. **N0/N3 Windows 复核**：已完成当前账号认证、依赖、文件传输、Web 低代码、浏览器矩阵和报告导出的完整 smoke；脱敏证据见 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)。
4. **N4～N9 外部收口**：依次验证性能真实环境、通知、外部缺陷平台与发布索引，保持凭据只存在于受控环境。

每个游标项完成后，必须按“实现/调整 → 定向测试 → 全量质量门禁 → 独立代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送”推进，完成后才移动到下一项。
