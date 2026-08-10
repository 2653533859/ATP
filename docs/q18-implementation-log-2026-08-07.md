# Q18 实施记录

最新前后实现对比和剩余任务统一见 [`docs/q18-latest-status-2026-08-07.md`](./q18-latest-status-2026-08-07.md)。

## 2026-08-10 文档同步

- 本地后端非集成回归已复核为 `1721 passed`；前端 Vitest 已复核为 `37 files / 146 tests passed`，前端类型检查与生产构建通过。
- 本次同步不把本地 mock、协议桩或浏览器缓存烟测当作真实发布验收；Android/iOS、Linux/Kubernetes 性能节点、Firefox/WebKit Worker、Prometheus、外部通知和 Provider/Consumer 规格仍保留为外部任务。
- 下一阶段按以下顺序推进：先完成 Q17-04 性能隔离栈验收，再并行推进真实设备、Web 专用 Worker、API 契约联调和性能观测/通知验收，最后统一归档发布证据。

## 本轮补齐内容

- API：受限表达式断言、统一执行结果契约、数据集笛卡尔积/Pairwise 组合、输入脱敏、导入预览/冲突/事务回滚。
- Web：项目文件上传下载、视觉基线与差异、POM 执行、浏览器矩阵独立会话并发、定位器候选建议与用户确认写回。
- Android：设备兼容矩阵、设备/日志产物、可选录屏、旋转/权限/网络/前后台系统动作。
- 性能：自动阶梯、目标 Prometheus 指标采样边界、JMeter HTML 报告附件。

这些能力均已增加定向回归测试；真实 Android、macOS/iOS、Prometheus、Firefox/WebKit/JMeter Worker 仍按最新对比文档列为外部验收项。

更新时间：2026-08-07

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
- `mypy` 检查 `120` 个源文件无错误；Ruff lint、格式检查、Bandit（无高/中风险）、pip-audit（无已知漏洞）、npm audit（0 vulnerabilities）、`vue-tsc --noEmit`、前端生产构建和 `git diff --check` 全部通过。
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
