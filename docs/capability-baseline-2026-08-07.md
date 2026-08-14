# ATP 能力基线与目标对比

> 2026-08-13 系统治理补强：管理员审计日志已支持时间范围查询和受限 CSV 证据导出，导出会写入 `audit_log_export` 审计事件；生产审批、归档和进一步脱敏仍待确认。

> 2026-08-12 后续路线同步：当前能力矩阵中标记为“部分支持/待环境验收”的项目，统一按 [`docs/next-development-plan-2026-08-12.md`](next-development-plan-2026-08-12.md) 排序推进。优先完成 Windows 真实 Android 设备验收，再推进 Linux/Kubernetes 性能、Web 专用 Worker、iOS/Appium 和产品化收口。

> 2026-08-12 本轮补强：Linux/Kubernetes 性能验收脚本现在可检查 Prometheus `/-/ready` 和 PromQL 查询；该入口通过本地回归，但不代表目标集群已完成验收。

> 2026-08-12 Web Worker 补强：独立录制 Worker 现在通过 Redis 心跳健康标记接入 Compose/Helm readiness/liveness；真实浏览器矩阵和跨副本 E2E 仍待环境验收。

> 2026-08-12 浏览器证据补强：矩阵 smoke 可按需输出 Trace/HAR、Console、失败请求和 HTTP 错误摘要，并对 URL 脱敏；该能力不替代真实 Worker 环境验收。

> 2026-08-12 Windows 本机矩阵真实通过：Chromium、Firefox、WebKit 均返回 HTTP 200 且登录页输入框挂载，汇总证据已归档；Linux/Xvfb Worker 和跨副本 E2E 仍待验收。

> 2026-08-12 iOS/Appium 补强：新增 status/session smoke、受控步骤和脱敏附件证据入口；真实 macOS/XCUITest/WDA/设备执行仍待验收。

> 最新实现状态和前后对比请先查看 [`docs/q18-latest-status-2026-08-07.md`](./q18-latest-status-2026-08-07.md)。

> 基线日期：2026-08-07
> 对应开发计划：[Q18 测试平台能力扩展开发计划](./implementation-plan-2026-Q18-capability-expansion.md)
> 用途：记录“当前实现 → 目标实现 → 验收方式”，后续开发只需要更新本文件的状态和证据列。

## 状态定义

- ✅ 已支持：已有代码、入口和执行链路，能够按现有边界使用。
- 🟡 部分支持：有基础能力，但缺少关键子能力、工程化能力或真实环境验收。
- ❌ 未支持：当前未发现可用实现，或只有规划文档。
- 🔵 待环境验收：代码已具备，但必须使用真实设备、节点或外部服务确认。

## 1. API 测试

| 能力 | 当前状态 | 当前实现 | 目标状态 | 后续验收 |
|---|---|---|---|---|
| HTTP/HTTPS、REST | ✅ | `httpx` API 执行器 | 保持并补齐高级请求能力 | HTTP 家族执行器回归 |
| GraphQL | ✅ | Query/Mutation、变量、错误断言 | 增加 Schema/订阅能力评估 | GraphQL 执行器回归 |
| WebSocket | ✅ | 连接、发送、接收、断开、消息断言 | 统一变量和结果契约 | HTTP 家族执行器回归 |
| SSE | 🔵 | API 执行器 `response_type=sse`，支持事件上限、类型/数据断言；真实服务待验收 | 连接、事件、超时、断言、关闭 | `backend/tests/worker/test_http_family_executors.py` + SSE 真实服务 |
| gRPC | 🔵 | API 用例和性能模块均支持 Proto 动态解析；API 按方法声明执行 Unary、Server Streaming、Client Streaming、Bidi Streaming，支持主 Proto 与 import 文件包，统一响应、提取和断言结果 | API 与性能统一流式语义 | `backend/tests/worker/test_http_family_executors.py`；真实 Unary/Streaming 服务联调 |
| Dubbo 等 RPC | ❌ | 未发现执行器 | 评估协议适配器和依赖隔离 | Dubbo 样例服务验收 |
| Headers/Params/Body | ✅ | Headers、Query、JSON、Form、Raw | 增加文件和 XML | 请求体矩阵回归 |
| Cookie | 🔵 | CaseFormDrawer Cookie 编辑器 + 项目 API 会话复用；真实登录服务待验收 | 静态 Cookie、变量 Cookie、会话策略 | `backend/tests/worker/test_http_family_executors.py` |
| Auth | 🔵 | Bearer、Basic、API Key；API/GraphQL 支持 OAuth2 Client Credentials（Basic/Post、scope/audience、单场景 token 缓存）和 Digest | 真实 Token Endpoint、Digest challenge、超时与凭据轮换联调 | `backend/app/services/api_auth.py`、`test_api_auth.py`、`test_http_family_executors.py` |
| JSON/XML/表单/文件 | 🔵 | JSON、表单、Raw、XML、multipart；文件走 `api-files/` 对象引用 | 完整内容类型与文件字段 | `test_api_request_files_routes.py` + multipart/XML 回归 |
| 状态码/字段/表达式断言 | ✅ | 状态码、Header、Body、耗时、JSON Schema、XPath、受限 AST 表达式及基础操作符 | Schema、XPath、安全表达式 | `test_http_family_executors.py`、`test_safe_expressions.py` |
| JSONPath 提取 | ✅ | JSONPath 提取到上下文变量 | 与 XML/XPath 统一 | 提取链路回归 |
| XPath 提取 | 🔵 | API 执行器安全 XML 解析和 XPath 提取/断言 | XML 提取和断言 | `test_http_family_executors.py` |
| 接口依赖和上下文变量 | ✅ | 环境、全局、数据集、前步提取、API 会话 | 增加作用域和生命周期可视化 | 登录-Token-业务请求场景 |
| 前置/后置脚本 | 🟡 | API 受限动作 DSL：变量设置/删除、响应提取和断言；不执行任意代码 | 扩展统一表达式与场景作用域 | API Hook 回归 |
| 数据驱动 | 🟡 | 数据集按行生成子运行并支持版本；API/GraphQL/WebSocket/gRPC/iOS 通用抽屉及 Web/Android 专用抽屉均可选择数据集并固定版本，支持有界组合策略、MinIO 引用模式和 API 用例运行级数据准备 Hook；数据集页面可按项目 AI 配置生成合成数据草稿 | 真实 seed/MinIO 集群验收、受控组合策略和输入摘要脱敏 | 数据集参数化回归、`test_dataset_preparation.py`、`test_ai_dataset_generator.py`、前端用例抽屉回归 |
| 参数组合 | ✅ | 支持顺序/随机/固定次数、笛卡尔积、Pairwise、组合字段、迭代上限和嵌套脱敏摘要 | 受控组合策略和输入摘要 | `test_dataset_execution.py`、`test_dataset_parameterized.py` |
| 集合/场景编排 | ✅ | 套件、计划、多步骤用例；API 编辑器展示 `depends_on`，支持失败策略、上下文作用域和登录态生命周期 | API 场景依赖、失败策略和作用域可视化 | `test_api_scenario.py`、`test_http_family_executors.py`；Suite/Plan E2E |
| OpenAPI/Swagger/Postman | 🟡 | 支持解析、预览、冲突检测、跳过/替换策略、单事务导入和异常回滚；项目级 JSON Schema 与 Provider/Consumer 契约资产已可保存/复用；项目内 `$ref` 可展开，外部/远程 `$ref` 支持默认 `warn` 和发布安全 `reject`，均不联网拉取 | 预览、冲突、回滚、可执行用例导入、Schema/契约资产和真实规格联调 | `test_case_import_routes.py`、`test_api_schema_assets.py`、`test_api_contract_assets.py`、`test_ai_case_parsers.py` |
| Mock 服务 | ✅ | 路径、方法、匹配条件、模板、录制、版本；支持按要求或参考规则 AI 生成草稿并确认保存 | 增加 Schema 和契约联动 | Mock 规则回归、Mock AI 生成回归 |
| 契约/兼容性测试 | 🟡 | OpenAPI/Swagger/JSON Schema 比较、必填字段/类型/状态码变化报告；项目级 Provider/Consumer 资产 CRUD、版本递增、角色筛选和资产比较页面已接入；外部引用已具备 `warn/reject` 发布策略 | 真实 Provider/Consumer 规范样本和关键 UI/E2E | `test_api_contract_assets.py`、`ApiContractAssetsView.spec.ts`；真实规格联调 |

### AI 模型配置补充

| 能力 | 当前状态 | 当前实现 | 后续验收 |
|---|---|---|---|
| 三方 OpenAI 兼容模型 | 🟡 | `openai_compatible` 协议、Endpoint 必填、`/models` 模型发现和 `/chat/completions` 调用；适配 Open WebUI/One-API/LiteLLM | 真实 Token、模型列表、多模态输入和思考参数联调 |

## 2. Web UI 测试

| 能力 | 当前状态 | 当前实现 | 目标状态 | 后续验收 |
|---|---|---|---|---|
| Playwright | ✅ | pytest-playwright + Playwright 低代码执行器 | 保持统一配置 | Web 执行器回归 |
| 浏览器录制/低代码 | ✅ | 录制弹窗可选择 Chromium/Firefox/WebKit，点击/输入/选择/按键转步骤；Web/Android 低代码可生成可编辑 Python 脚本，Web 文件操作/视觉断言/POM 会展开或明确失败 | 真实专用 Worker 上的浏览器矩阵和资产引用深度联动 | 录制 E2E |
| 页面元素定位 | ✅ | CSS、Playwright locator、文本等基础定位 | 元素库、备用定位器、版本记录 | 元素库组件测试 |
| 元素库 | 🔵 | `WebElementAsset` 模型、项目级 CRUD 页面/API、备用定位器、版本和失效记录；绑定项目的 Web 录制会自动创建资产并回填 `element_asset_id`，低代码 Worker 按顺序回退；录制会话已支持 Redis 路由与独立 Worker 进程 | 与 POM/执行报告联动 | `test_web_recordings.py`、`test_web_assets_routes.py`、`test_web_lowcode_executor.py`、`test_web_recording_transport.py`；真实 Linux/Xvfb 与跨副本录制 E2E 待补 |
| 页面对象模型 POM | 🔵 | `WebPageObject` 模型、元素引用/公共操作 JSON 编辑、项目级 CRUD 页面/API；低代码 Worker 已展开并执行引用 | 低代码步骤可直接引用页面对象并执行公共操作 | `test_web_assets_routes.py`、`test_web_lowcode_executor.py`；真实浏览器验收 |
| 多浏览器 | 🔵 | 录制、低代码、脚本均接受 Chromium/Firefox/WebKit；本机三浏览器烟测均可访问 `/login` 并等待输入元素挂载，真实 Worker 矩阵仍待验收 | Chromium/Firefox/WebKit | `frontend/tools/browser-matrix-smoke.mjs`、`docs/evidence/web-browser-matrix-local-smoke-2026-08-07.json`；Docker Worker 验收 |
| 多分辨率 | ✅ | viewport 宽高配置 | 浏览器×分辨率矩阵 | 矩阵结果回归 |
| 并行执行 | ✅ | 套件/计划支持并行 | 浏览器矩阵和资源限额 | 并行 E2E |
| 截图/录像 | ✅ | 截图和 WebM 上传 MinIO | 保持并关联 Trace | 报告附件回归 |
| Playwright Trace | 🔵 | 低代码执行器采集 `traces/runs/{run_id}/trace.zip` 并写入 `trace_url` | Trace 采集、下载、展示 | Web 真实浏览器回归 |
| 失败步骤定位 | ✅ | 步骤状态、错误、截图、AI 诊断 | 联合 Trace/网络/Console | 失败证据完整性测试 |
| 网络请求/浏览器日志 | 🔵 | 低代码执行器记录 request/response/Console 摘要到 `result_summary` | 网络时间线、失败请求和 Console | Web 日志采集 E2E |
| 文件上传/下载 | ✅ | 项目级文件上传、MinIO 对象引用、`input` 上传、Playwright 下载等待和运行附件归档 | 上传、下载等待、文件校验 | `test_web_files_routes.py`、`test_web_lowcode_executor.py` |
| 视觉回归 | ✅ | PNG 基线、像素阈值、忽略区域、差异图和 `visual_assert` 步骤 | 基线、忽略区域、阈值、报告 | `test_web_visuals.py`、`test_web_visuals_routes.py` |
| 定位器失效诊断/修复 | ✅ | 失败资产生成有界候选定位器、置信度和来源；用户确认后递增版本写回 | 用户确认后应用并回归验证 | `test_web_assets_routes.py`、前端修复预览流程 |

## 3. 移动端测试

| 能力 | 当前状态 | 当前实现 | 目标状态 | 后续验收 |
|---|---|---|---|---|
| Android 真机/模拟器 | ✅ | ADB、uiautomator、设备扫描 | 保持并完善设备调度 | Android 真机演练 |
| iOS 真机/模拟器 | 🟡 | `IosDevice`/`IosApp` 资产、项目隔离 IPA API、iOS 设备租约和统一 iOS 用例入口已实现；真实 macOS/iPhone/Simulator 仍待接入 | macOS Worker + iOS 统一执行链 | `tests/worker/test_ios_executor.py`、iOS 资产 API；iPhone/Simulator 验收 |
| Appium | 🟡 | Worker 通过 W3C WebDriver HTTP 协议连接 Appium，支持 XCUITest capabilities、低代码 click/input/assert/wait/screenshot/tap/swipe、录屏和 syslog 产物；专用 `ios` 队列及租约回收已接入 | Appium 2 + XCUITest | Appium 协议回归；真实 macOS Worker 最小闭环 |
| 设备管理 | 🔵 | 扫描、CRUD、在线状态；`device_leases` 租约表、获取/心跳/释放 API、移动 Worker 自动占用释放和过期回收 | 真实 ADB 设备并发调度与故障恢复 | `tests/api/test_devices_routes.py`、`tests/worker/test_tasks_mobile_special_dispatch.py`；真实设备并发抢占回归 |
| App 安装/卸载/版本 | 🟡 | APK 资产选择；专项任务支持执行前安装/卸载/清理/启动和执行后卸载 | 真实 ADB 设备生命周期验收 | Android 前置动作回归 |
| 截图/录屏/设备日志 | 🟡 | Android 截图、可选 MP4 录屏、logcat、设备信息和系统日志上传；受大小/时长限制 | 标准录屏、logcat、设备信息附件 | `test_android_lowcode_executor.py`；真实设备附件回归 |
| 弱网/权限/旋转/来电 | 🟡 | 已支持网络配置、授予/撤销权限、旋转、后台/前台；来电等外部事件仍待设备环境 | 网络、权限、旋转、系统事件注入 | Android 专项回归和真实设备验收 |
| 多设备并行 | 🔵 | 设备兼容矩阵创建隔离子运行；每个子运行使用独立数据库会话和独立设备租约，并通过 `asyncio.gather` 并行调度后聚合结果 | 设备池自动分配、并发抢占、故障恢复和矩阵聚合 | `test_android_lowcode_executor.py`；真实设备并发回归 |
| 兼容性测试 | 🟡 | 支持设备序列号、型号、系统版本、SDK 和分辨率匹配校验及矩阵汇总 | 兼容性矩阵和失败聚合 | `test_device_compatibility.py`；真实设备矩阵验收 |

## 4. 性能测试

| 能力 | 当前状态 | 当前实现 | 目标状态 | 后续验收 |
|---|---|---|---|---|
| 并发用户/请求速率 | ✅ | k6、Locust、gRPC options | 保持统一选项契约 | 三执行器回归 |
| 阶梯/峰值/稳定性 | ✅ | stages、smoke/load/stress/spike/soak 模板 | 增加容量模式 | 压力模型回归 |
| 容量测试 | 🔵 | `auto_ramp` 自动生成有界阶梯；容量分析返回最大稳定负载、错误率/P95 瓶颈和逐次观察 | 自动阶梯调度、资源瓶颈关联和真实样例服务 | `test_performance_ramp.py`、`test_performance_capacity.py`；真实节点验收 |
| 场景编排/参数化 | ✅ | k6 多步骤行为和数据集注入 | 扩展多场景和变量组合 | 多场景回归 |
| 分布式执行 | 🟡 | 节点注册、心跳、队列、容量限制、单次运行多节点分片和父子聚合 | 多节点真实压测与资源样本验证 | 性能分片/API 回归 |
| TPS/RPS/响应时间/错误率 | ✅ | RPS、P95、P99、错误率和耗时 | 统一所有执行器摘要 | 结果契约回归 |
| CPU/内存/数据库监控 | 🟡 | Worker、PostgreSQL、Redis、MinIO 探针；可选 Prometheus 目标服务指标采样独立归档 | 目标服务指标关联 | `test_performance_target_metrics.py`；真实 Prometheus 验收 |
| 性能基线 | ✅ | 基线运行和核心指标对比 | 增加趋势和历史窗口 | 基线回归 |
| 回归/阈值门禁/告警 | 🟡 | 阈值门禁、基线回归、容量瓶颈和节点/资源异常已汇总并复用项目通知渠道 | 真实通知渠道联调、抑制和重试观测 | 告警渠道验收 |
| k6/Locust | ✅ | 已接入并有统一执行器接口 | 保持兼容 | k6/Locust 环境验收 |
| JMeter | 🔵 | Worker 镜像安装 JMeter 5.6.3，支持 JMX 非 GUI 执行、JTL 统一摘要和可选 HTML 报告 ZIP 附件；本机无凭据 JMX 已完成 1 请求/0 错误烟测 | JTL/HTML 附件与真实任务 | `test_performance_jmeter.py`、`deploy/performance-acceptance/jmeter_smoke.jmx`、`docs/evidence/performance-jmeter-local-smoke-2026-08-07.json`；真实 Worker 验收 |

## 5. 后续如何使用本表

每完成一个能力，按以下顺序更新：

1. 将“当前状态”从 `❌`/`🟡` 更新为 `✅` 或 `🔵`。
2. 在“当前实现”中补充实际 API、执行器、前端页面或迁移文件。
3. 在“后续验收”中补充测试文件、命令、截图、真实设备或外部服务证据。
4. 只有代码、入口、自动化测试和必要环境验收都完成后，才改为 `✅`。
5. 在 `Task.md` 和 Q18 开发计划中同步勾选对应条目。
