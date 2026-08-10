# Q18 最新开发状态与前后实现对比

更新时间：2026-08-10

本文件是 `docs/implementation-plan-2026-Q18-capability-expansion.md` 的最新查看入口，配合 `docs/capability-baseline-2026-08-07.md` 使用。状态区分为：

- **已实现**：代码、调用入口和自动化回归已具备。
- **部分实现**：主链已具备，但仍缺少真实设备、外部服务或更完整的工程化验收。
- **外部阻塞**：需要当前 Windows 开发环境之外的资源，不能用本地模拟结果代替。

本次同步（2026-08-10）：本地代码和自动化回归继续保持通过；后端非集成测试更新为 `1721 passed`，前端 Vitest 为 `37 files / 146 tests passed`。当前开发重点从功能代码实现切换为 Linux/Kubernetes、真实设备、专用浏览器 Worker、Prometheus、外部通知和 Provider/Consumer 规格验收。

## 前后实现对比

| 能力域 | 之前 | 现在 | 状态与验证入口 |
|---|---|---|---|
| API 断言与 Schema 资产 | 只有基础状态码、字段、Schema 等断言，复杂表达式和 Schema 复用边界不清晰 | 增加 AST 白名单解释器、项目级 JSON Schema 资产 CRUD/版本，以及执行时项目隔离解析 | 已实现；`backend/app/services/safe_expressions.py`、`backend/app/api/v1/api_schema_assets.py` |
| API 场景编排 | 多步骤 API 缺少可视化依赖、失败策略和上下文边界 | 编辑器展示步骤关系并可追加步骤；Worker 支持 `depends_on`、失败停止/依赖跳过、步骤/场景上下文和登录态生命周期 | 已实现；`backend/app/services/api_scenario.py`、`CaseFormDrawer.vue` |
| 数据集参数组合 | 仅支持顺序、随机、固定次数 | 支持笛卡尔积、Pairwise、组合字段、最大迭代次数和嵌套脱敏；组合生成在物化前限流 | 已实现；`backend/app/services/dataset_execution.py` |
| OpenAPI/Postman 导入 | 解析后逐条创建，冲突和半成品风险较高 | 支持预览、同名/重复检测、跳过冲突和一次事务提交；异常自动回滚；AI 导入复用同一流程；项目级 Schema、Provider/Consumer 契约资产可保存、版本化、复用和比较 | 已实现；`/cases/import-preview`、`/cases/import`、`/system/api-contract-assets` |
| Web 浏览器与分辨率 | 浏览器和 viewport 可单独配置 | Chromium/Firefox/WebKit 与 viewport/device 参数可组合，矩阵子运行使用独立会话并发执行并汇总 | 已实现；`backend/app/services/web_matrix.py`、Web Worker |
| Web 页面资产/POM | 低代码步骤重复录入定位器，POM 不能直接执行 | 元素资产、备用定位器、页面对象 CRUD，低代码 `page_object` 展开执行并校验项目边界 | 已实现；`/system/web-assets`、Web Worker |
| Web 文件操作 | 文件步骤无统一上传/下载资产入口 | 项目级文件上传、MinIO 对象引用、上传到 `<input>`、下载等待和运行附件归档 | 已实现；`/projects/{id}/web-files` |
| Web 视觉回归 | 只有截图，没有基线差异 | PNG 基线、像素阈值、忽略区域、差异图和 `visual_assert` 步骤 | 已实现；`WebVisualBaseline`、`web_visuals.py` |
| Web 定位器失效修复 | 失败后只有诊断/备用定位器回退 | 失败资产可生成候选定位器、置信度和来源；用户确认后才写回、递增版本并可回归验证 | 已实现；`repair-preview`，默认不自动改写 |
| Android 设备工程化 | 有租约和标准安装/启动，但缺少矩阵与统一产物 | 设备信息、logcat、可选 MP4 录屏归档；系统动作、网络/权限/旋转/前后台；设备兼容矩阵隔离子运行并汇总 | 部分实现；真实 ADB 设备验收仍待完成 |
| iOS/Appium | 无 iOS 执行链 | 增加 `IosDevice`/`IosApp` 资产、IPA 项目隔离 API、iOS 设备租约、专用队列和 W3C Appium/XCUITest Worker；支持脚本/低代码步骤、截图、录屏和 syslog 产物 | 部分实现；需要 macOS、Xcode、Appium/XCUITest、签名应用和真实设备联调 |
| 性能自动阶梯 | 只能手工配置 stages | `auto_ramp` 根据起始并发、步长、最大并发自动生成有界 stages，并写入选项快照 | 已实现；`performance_ramp.py` |
| 性能目标服务指标 | 只有 Worker/平台自身采样边界 | 支持配置 Prometheus URL 或环境变量、最多 8 条查询、超时/响应大小限制，目标指标作为独立样本归档 | 部分实现；需要真实 Prometheus/目标服务验收 |
| JMeter | 可执行 JMX 并解析 JTL，缺少报告附件 | 可选生成 JMeter HTML 报告并压缩上传到 MinIO，同时保留统一 JTL 摘要 | 已实现；`performance_jmeter.py` |
| 性能分布式/容量/通知 | 多节点和容量分析链路不完整 | 节点分片、父子运行聚合、容量分析、阈值/基线/节点异常通知摘要已接入 | 部分实现；需要真实节点和外部通知渠道验收 |

## 当前仍需完成的任务

1. 在真实 Android 设备或模拟器上验收矩阵、租约并发、录屏、权限、网络、旋转和 logcat 产物。
2. 在 macOS Worker 上部署 Xcode、Appium 2/XCUITest、签名 IPA 和 iPhone/Simulator，完成已实现 iOS HTTP 协议执行链的真实最小闭环。
3. 准备真实 Prometheus 和目标服务，确认目标查询、时间线、权限、超时和告警结果。
4. 在 Docker Worker 中安装并验收 Firefox/WebKit/JMeter，完成三浏览器和 JMeter HTML 外部回归。
5. 外部/远程 OpenAPI `$ref` 已补齐发布策略：解析接口和 UI 支持 `warn`（默认，仅提示不联网）与 `reject`（发布安全模式，发现外部引用即拒绝）；真实 Provider/Consumer 规格联调仍待外部环境提供真实规格。其余本地 `$ref` 解析、契约资产 CRUD/版本化、Schema 资产复用、资产管理 UI、API 场景编排和现有关键页面 E2E 已实现/验收。
6. 本地全量后端、前端单元测试、Playwright E2E、类型检查、构建、迁移链、Bandit、pip-audit 和 npm audit 已完成；真实环境验收仍需按发布环境执行。

## 当前开发机环境探测

- Windows 上已检测到 ADB 37.0.0，但 `adb devices` 当前没有在线设备；Android 真实设备矩阵因此不能在本机宣称已验收。
- 已检测到 JMeter 5.6.3，可用于后续本地 JMX/JTL 烟测；Docker 命令不可用，因此 Docker Worker、分布式节点和容器内浏览器/JMeter 仍需部署环境。
- JMeter 5.6.3 已实际执行 `deploy/performance-acceptance/jmeter_smoke.jmx`：请求本地 `/login` 1 次、错误数 0，并生成 JTL 与 HTML 报告；该结果不替代 Docker Worker 外部验收。
- Playwright 1.61.1 及 Chromium、Firefox、WebKit 浏览器缓存可用，本轮通过 `frontend/tools/browser-matrix-smoke.mjs` 等待交互元素后，三者均访问本地 `/login` 返回 HTTP 200 且检测到 4 个输入框；这不等同于目标 Docker Worker 验收。
- 本机 `127.0.0.1:9090` 和 `localhost:9090` 没有 Prometheus ready 响应；iOS/Appium 仍必须转移到 macOS + Xcode + WDA + 签名 IPA + iPhone/Simulator。
- 已对已授权 Linux 主机做只读探测：ARM64、Docker 29.3.0 可用，主机已有健康的 PostgreSQL/Redis/MinIO 容器，但未发现 ATP 验收栈或 Prometheus 9090；为避免覆盖现有业务，未在该主机部署或重启任何服务。

## 2026-08-10 最新本地质量核验

- 后端非集成测试：`1721 passed`（使用 `--ignore=tests/integration`，符合仓库对集成环境变量的保护约定）。
- 前端 Vitest：`37 files / 146 tests passed`；`vue-tsc --noEmit` 和生产构建通过。
- Python 质量门禁：mypy `120 source files` 无错误；Ruff lint、格式检查、Bandit（无高/中风险）、pip-audit（无已知漏洞）和 `git diff --check` 通过；npm audit 报告 `0 vulnerabilities`。
- 录制/元素资产定向回归：`10 passed`；此前性能/Web 受影响模块定向回归 `27 passed`。
- 前端 E2E：`9 passed`（登录、Dashboard、用例、执行、Run 详情、套件和计划）；契约资产页面组件回归 `3 passed`，并完成真实浏览器抽查。
- 当前结论：本地代码实现和自动化验证已完成；Android/iOS、Prometheus、Firefox/WebKit/JMeter Worker、真实通知渠道、真实 API 联调和外部 Provider/Consumer 规格仍属于发布前验收，不将 mock E2E 或本地协议桩结果冒充真实环境结论。

## 代码入口速查

- API：`backend/app/worker/executors/api_executor.py`、`backend/app/services/execution_contract.py`、`backend/app/services/safe_expressions.py`、`backend/app/services/api_contracts.py`、`backend/app/api/v1/api_contract_assets.py`
- Web：`backend/app/worker/executors/web_lowcode_executor.py`、`backend/app/services/web_matrix.py`、`backend/app/services/web_visuals.py`、`backend/app/services/web_locator_repair.py`
- Android：`backend/app/worker/executors/android_lowcode_executor.py`、`backend/app/services/device_compatibility.py`
- 性能：`backend/app/services/performance_ramp.py`、`backend/app/services/performance_target_metrics.py`、`backend/app/services/performance_jmeter.py`
- 契约资产 UI：`frontend/src/views/system/ApiContractAssetsView.vue`、`frontend/src/views/system/ApiContractAssetsView.spec.ts`
- 计划与基线：`docs/implementation-plan-2026-Q18-capability-expansion.md`、`docs/capability-baseline-2026-08-07.md`、`docs/q18-implementation-log-2026-08-07.md`
