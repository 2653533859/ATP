# AutoDroid → ATP 接口与 App 自动化能力基线（A0）

> 2026-10-25 源码与定向测试核对。开发目标为 ATP；AutoDroid 是对照项目。以下“待补”指本次核对的使用链路差距，不表示仓库中完全没有相关代码。尚未进行真实业务服务或真机操作。

## 同一组验收样例

| 样例 | 操作与观察点 | 当前验证方式 |
| --- | --- | --- |
| API-1 规格变更 | 导入含 `POST /orders` 的规格，建立“创建订单 → 查询订单”两步场景；将新版规格增加必填参数，并只在场景第二步做局部覆盖。观察受影响用例/步骤、版本冲突和人工确认入口。 | 源码/API 契约与定向测试；未向真实业务服务发请求。 |
| API-2 调试校验 | 用 `POST /orders` 的一次真实响应生成字段提取和断言，修改环境或请求后再尝试应用旧建议；确认可重新校验且不会重复发送写请求。 | 源码和现有 AI 建议测试；真实请求/过期建议流程待 A2 验收。 |
| APP-1 录制回放 | 选定 Android 设备，在可视画面点选、输入并滑动，保存为可编辑步骤；预检后执行并查看截图、结果和失败定位。 | 前端录制工具/后端执行器源码及定向测试；真机待 M3。 |
| APP-2 故障恢复 | 执行前设备被占用，或执行中断开设备；观察错误码、运行终态、租约释放和报告。 | 租约/执行代码与已有测试；真机断线待 M3。 |

## 源码对照与任务收窄

| 链路 | AutoDroid 已有入口 | ATP 已有入口与本次判断 | 后续任务 |
| --- | --- | --- | --- |
| 规格到场景 | `backend/api/api_testing.py` 的 `/interfaces/{id}/usages`、`sync-apply`；`frontend/src/views/api-testing/InterfaceEditor.vue` 显示引用和冲突 | `backend/app/services/spec_sync.py` 返回接口新增/修改/移除及用例补丁；`backend/app/api/v1/api_contracts.py` 已暴露比较和 `sync-cases`，`cases/importing.py` 有事务导入预览。当前 `sync_spec_with_cases` 以用例为主要对象，未在该结果中列出 API 场景步骤和局部覆盖。 | A1：扩展只读影响预览与定位；复用现有比较/导入，不重写契约引擎。 |
| 响应到校验 | `backend/api_testing/service.py` 有隔离调试和不重发请求的断言复核；`ai_service.py` 对建议做来源与实际响应校验 | `ApiScenarioOrchestrator.vue` 已有字段点选、断言、取值和单步调试；`ai_case/suggestion.py` 已有启发式/LLM 建议。`CaseFormDrawer.vue` 可从粘贴样例、缓存响应，甚至请求体构造建议；尚未见服务端绑定本次响应版本并判定建议仍有效的闭环。 | A2：绑定响应来源、验证建议、去重和重新校验。 |
| Android 录制 | `DeviceStage.vue` + `StepBuilder.vue` 连续录制与编辑，统一交给跨端 runner | `AndroidStepEditor.vue` 已有截图点选、滑动录制、元素属性加坐标回退；`androidRecording.ts` 和 `android_lowcode_executor.py` 支持录制坐标与重放。`DeviceMirrorModal.vue` 提供独立的 Scrcpy 控制画面，未见其操作直接写入步骤编辑器。 | M1：衔接现有录制器、镜像与工作台；保留已有录制模型和执行器。 |
| 设备预检 | `cross_platform_execution.py::precheck_case_execution`，用例和场景 API 均有按设备预检 | ATP 有字段/参数校验、设备租约和 Worker 执行检查；`cases/runs.py::trigger_run` 创建运行后投递任务，未见针对所选 Android 设备的用例步骤预检结果入口。 | M2：新增或复用运行前诊断，并在执行入口复核。 |
| iOS 与探索 | `docs/EXECUTION_SPEC.md` 的 iOS 静态录制；`backend/inspection/` 的路径冻结与回放 | ATP 已有 iOS Appium/WDA 执行、Android 稳定性专项和兼容性服务；真实 iOS 环境验收仍待完成。 | M4/M5 是环境/业务驱动试点，排在 Android 闭环之后。 |

## 本次验证与限制

- ATP 后端定向回归：`test_spec_sync.py`、`test_api_contracts.py`、`test_ai_case_suggestion.py`、`test_device_mirror.py`，共 **30 passed**。
- ATP 前端定向回归：`androidRecording.spec.ts`、`ApiWorkbenchView.spec.ts`，共 **2 个文件、15 passed**。
- AutoDroid 对照测试未运行成功：本机该仓库 Python 环境未安装 `pydantic` 与 `sqlmodel`；用例与预检能力依据源码和已有文档核对，不能声称已在本次复测通过。
- 本机未向业务系统发送 API 请求，也未连接 Android/iOS 真机。A1/A2 与 M1/M2 的代码验收可在隔离环境开展；M3/M4 的真机结果需另留带日期证据。

**A0 结论**：A1/A2 与 M1/M2 继续推进，但范围收窄到上述缺口。ATP 的多协议、DAG、Trace、Android 录制基础和 iOS 执行基础不重新建设。
