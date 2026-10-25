# ATP 学习 AutoDroid：接口与 App 自动化开发任务计划

> 制定日期：2026-10-25。**开发目标是 ATP**；`~/MyProject/AutoDroid` 仅作为对照项目。A0 已完成源码核对；A1/A2/M1 代码与定向验证完成，真实环境验收待补。完成情况以 `Task.md` 和专项证据为准。

> A0 基线见 [`autodroid-atp-capability-baseline-2026-10-25.md`](autodroid-atp-capability-baseline-2026-10-25.md)；A1/A2/M1 证据分别见 [`evidence/autodroid-atp-api-impact-preview-a1-2026-10-25.md`](evidence/autodroid-atp-api-impact-preview-a1-2026-10-25.md)、[`evidence/autodroid-atp-api-suggestion-reliability-a2-2026-10-25.md`](evidence/autodroid-atp-api-suggestion-reliability-a2-2026-10-25.md)、[`evidence/autodroid-atp-android-recording-bridge-m1-2026-10-25.md`](evidence/autodroid-atp-android-recording-bridge-m1-2026-10-25.md)。

## 1. 对比结论与边界

ATP 已有 HTTP/GraphQL/WebSocket/gRPC 执行、OpenAPI/Swagger 契约比较与同步、API 场景字段点选和断点调试、混合 DAG、Android 投屏与低代码执行、iOS Appium/WDA 执行及设备租约。这些能力见 [`current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md)、[`development-task-plan-v2.7.0.md`](development-task-plan-v2.7.0.md) 和 [`ios-device-automation-plan.md`](ios-device-automation-plan.md)。计划聚焦从“已有执行能力”走向“测试人员可持续创建、维护和复用自动化资产”。

| 学习主题 | AutoDroid 代码/文档依据 | ATP 当前代码依据 | 拟在 ATP 补齐或核实的点 |
| --- | --- | --- | --- |
| 接口资产维护 | `backend/api_testing/{specs,schemas,service}.py`；`docs/API_TESTING.md` 的接口版本、引用影响面与冲突同步 | `backend/app/services/{spec_sync,api_contracts}.py`；`backend/app/api/v1/cases/importing.py` | 已有规格差异与导入预览；核实“规格版本 → 用例/场景步骤 → 局部覆盖”是否可追溯，并补用户可见的影响预览 |
| 调试与校验闭环 | `backend/api_testing/{service,ai_service}.py` 的隔离调试、真实响应校验、建议过滤；`frontend/src/views/api-testing/ScenarioEditor.vue` | `frontend/src/views/workbench/components/{ApiRequestConsole,ApiScenarioOrchestrator}.vue`；`backend/app/services/ai_case/suggestion.py` | ATP 已有响应字段点选和 AI 建议；重点验证建议与本次响应一致、重复应用、过期响应和不重发请求的行为 |
| 可视化 App 录制 | `frontend/src/components/{DeviceStage,StepBuilder}.vue`、`backend/drivers/cross_platform_runner.py`、`docs/EXECUTION_SPEC.md` | `frontend/src/views/device/components/DeviceMirrorModal.vue`、`frontend/src/views/case/AndroidCaseDrawer.vue`、`backend/app/worker/executors/android_lowcode_executor.py` | ATP 已可投屏、触控和执行；核实触控/元素审查能否直接形成可编辑标准步骤，再补录制闭环 |
| 预检与真机运营 | `backend/cross_platform_execution.py` 的 `precheck_case_execution`、`backend/drivers/cross_platform_runner.py`、`backend/device_execution_lease.py` | `backend/app/services/{device_leases,ios_device_leases}.py`、Android/iOS 执行器 | ATP 已有租约与参数校验；补选定设备上的结构化运行前诊断，并完成真实设备验收 |
| 探索转回归 | `backend/inspection/`、`backend/compatibility_replay.py`、`docs/INSPECTION_REPLAY_ASSETS.md` | `backend/app/worker/executors/android_stability_executor.py`、`backend/app/services/device_compatibility.py` | 先验证 ATP 稳定性专项的产物能否选取、冻结并重放路径；仅在有业务场景时做模型化巡检试点 |

对照路径以 AutoDroid 仓库根目录为基准。**不直接移植**其单进程 SQLite 执行、进程内调试状态或数据库模型；ATP 应继续使用现有权限、Celery/Worker、PostgreSQL/SQLite 双模式、MinIO 与审计边界。AutoDroid 的明文报告策略也不覆盖 ATP 现有脱敏要求。

## 2. 任务顺序

| 任务 | 优先级 | 依赖 | 交付物与验收标准 |
| --- | --- | --- | --- |
| A0. 固定两边能力基线 | P0 | 无 | 用同一组“导入接口 → 调试/断言 → 场景运行”和“选设备 → 录制 → 执行 → 报告”样例，记录两边可见入口、源码、测试、当前障碍和真实环境要求。确认实际缺口后冻结 A1–M3 的最小范围；不把“未搜到代码”当成缺失证明。 |
| A1. 接口规格到场景的影响预览 | P0 | A0 | 在 ATP 现有 `spec_sync`/导入预览上，展示新增、修改、移除端点所影响的用例和场景步骤；标出局部覆盖与版本冲突，支持跳转定位。预览只读，用户显式确认后才沿既有写入路径更新；旧运行快照不变。若 A0 证明已有同等能力，则只补验收和文档。 |
| A2. 接口调试与建议可靠性 | P0 | A0 | 用本次真实响应生成/应用断言和提取建议；校验字段存在、建议在该响应上成立、已存在规则不重复、响应/环境/草稿变化后建议失效。应用后可只重新校验，不发送第二次业务写请求。AI 关闭时手工路径完整；模型只接收 ATP 允许的脱敏上下文。 |
| M1. Android 录制流程衔接 | P0 | A0 | 复用已有 `AndroidStepEditor` 的截图点选、滑动录制和坐标回退，将设备镜像、App 工作台与用例草稿的操作衔接起来，完成“录制 → 编辑 → 保存 → 回放”可见流程。录制失败不写入半成品正式用例；不重写现有录制模型或低代码执行器。 |
| M2. 设备级执行前预检 | P0 | M1 | 对选定设备检查在线/租约、应用映射、平台支持、定位器、变量及 Android 执行环境；返回步骤 ID、错误码、可修复提示。执行入口在获得租约后仍重新校验，防止录制/保存后设备状态变化。预检本身不操作业务 App。 |
| M3. Android 真机闭环验收 | P0 | M1、M2 | 用一台真实 Android 设备完成录制、编辑、预检、执行、取消、断线与报告回看；分别记录成功和故障路径的运行 ID、设备、版本及证据。现有租约/矩阵/低代码回归通过后再宣布完成。 |
| M4. iOS 可视化录制可行性与试点 | P1 | A0、M2、macOS/WDA 环境 | 先验收 ATP 现有 iOS 执行链。若环境可用，再参考 AutoDroid 的只读 MJPEG + 静态截图/层级选点，形成少量标准步骤并回放；WDA 不可用时明确停在环境阻塞，不以 mock 替代真机通过。 |
| M5. 探索路径资产试点 | P2 | M3、明确业务应用 | 选一个 Android 应用，用 ATP 现有稳定性产物和兼容性能力试验“可审阅路径 → 冻结版本 → 当前安装版本回放”。给出覆盖与误判数据，再决定是否引入 AutoDroid 的页面身份/页面族调度；不在首期复制完整巡检引擎。 |

### 优先实施切片

1. **A0 → A1/A2**：先把接口资产从规格到场景的变更链路做成可查看、可确认的闭环；复用 ATP 已有契约比较和响应字段点选。
2. **M1 → M2 → M3**：围绕 Android 真机完成一条从录制到报告的可重复业务流程，作为 App 自动化首期完成标准。
3. **M4/M5**：在真机环境与业务样例就绪后推进。ATP 已有的混合 DAG、多协议支持、Trace、设备池无需再次立项。

## 3. 每项任务的技术与验收约束

- **变更边界**：保留现有 API、用例、场景和报告兼容性；优先新增可选字段或复用已有模型。涉及数据库结构时按 Alembic 指南迁移，兼顾服务器与 Windows 本地模式。
- **权限与数据**：调试/录制只允许有项目权限的用户操作；真实请求和 App 操作需明确提示会产生业务数据。响应、凭据、截图和模型上下文沿用 ATP 现有脱敏及资产访问控制。
- **测试**：A1/A2 做导入冲突、版本并发、建议失效/重复应用和无二次请求的回归；M1/M2 做坐标映射、定位器回退、设备竞争和取消回归。先跑相关后端测试、前端 type-check/组件测试，真机任务再补环境证据。
- **完成定义**：源码、用户入口、回归测试和真实设备证据分别记状态。代码通过单测但缺真机时标记“代码完成、环境待验收”，同步 `Task.md`，避免把计划或 mock 结果写成已交付。
