# ATP 项目任务跟踪

> 当前执行版计划与状态口径统一维护在 [`docs/development-plan-2026-08-25.md`](docs/development-plan-2026-08-25.md)；本文件保留任务勾选和历史交付记录。每个模块均须完成实现、测试、代码审查、修复、文档/记忆同步、提交推送后再进入下一项。

> 当前有效顺序（2026-08-25 2.4.0）：参考导航按“工作台、测试能力、测试资产、智能中枢、系统”五组落地；先维护 P0 工作台与任务中心，再按 P1 接口、P2 APP、P3 UI、P4 性能、P5 AI、P6 测试资产、P7 智能中枢、P8 系统和 P9 发布收口推进。P4 因缺少 Kubernetes、发布级 Prometheus 指标覆盖和独立 MinIO 保持阻塞；P1～P3、P5～P8 本地实现保持 `[E]`，不得把页面可打开或单节点 Compose 写成真实通过。详细模块边界、依赖和验收出口以开发计划 2.4.0 为准，下方 2.3.0 及历史记录不覆盖当前执行版。

## 2026-08-25 当前开发计划 2.4.0 跟踪摘要

- [x] 导航计划登记：五组分工、入口职责、旧 URL 兼容、项目上下文、阶段顺序和状态口径已同步到开发计划 2.4.0。
- [ ] P0 工作台与任务中心：复核深链、待办、轮询、重试、终止、批量操作、失败事件和越权边界。
- [ ] P1～P3 接口、APP、UI：按配置→预检→执行→过程→报告/证据→清理顺序复核，分别记录真实协议、Windows Worker 和浏览器矩阵证据。
- [ ] P4 性能测试工作台：等待 Kubernetes、发布级 Prometheus、独立 MinIO source/target；保持 `[-]`，不以 mock、单节点 Compose 或跳过项替代。
- [ ] P5～P8 AI、测试资产、智能中枢和系统：准备真实模型、临时项目、角色矩阵、需求/知识数据和目标部署，验证来源、审计、项目隔离、回滚和可清理性。
- [x] N5 AI 模型能力元数据解析：识别供应商 `capabilities`/`modalities` 等字段中的多模态与思考能力，能力无阳性证据时保持未知；模型发现/API 定向 `20 passed`、受影响 AI 定向 `69 passed`、后端非集成全量 `2340 passed`，真实模型参数接受情况仍待环境验收。
- [ ] N5 真实模型环境门禁：q19 AI LLM 配置数量为 `0`，外部模型端点不带凭据返回 HTTP `401`；真实模型列表、连接、参数接受、项目生成和清理暂不能验收，脱敏证据见 `docs/evidence/ai-model-environment-audit-2026-08-25.json`。
- [x] P7 Hermes 跨任务失败诊断本地闭环：case 复用原诊断链，suite/plan/android/performance 通过统一工作台入口读取执行摘要、Android 异常事件/错误事件和性能指标生成规则诊断；后端定向 `13 passed`、后端非集成全量 `2345 passed`，前端全量 `69 files / 293 tests passed`，新增服务 mypy、Ruff、格式、`vue-tsc` 和生产构建通过。真实模型、需求/知识数据和角色矩阵仍待验收。
- [x] P7 Hermes 项目级检索本地交付：新增项目 viewer 权限保护的 Hermes 查询接口，统一检索需求、知识和用例并返回脱敏摘要、来源引用和深链；Hermes 自由提问可调用检索，知识条目支持 `knowledge_id` 深链；新增 N7 临时数据验收脚本、运行手册和质量门禁。独立审查补强来源类型/项目路径/引用校验及需求、知识、用例详情读取；后端定向 `21 passed`、前端 Hermes/知识定向 `11 passed`。真实模型、角色账号和远端数据仍待验收。
- [x] P7/N6 验收缺陷修复与 q19 复验：空白临时项目无模块时脚本会显式创建模块；需求创建接口在异步提交后序列化过期 ORM 属性导致 `MissingGreenlet`/HTTP 500，已增加 `refresh` 和回归测试。q19 已按 `716d1b3` 重建到迁移 `20260825_0066`；N6 执行/缺陷关联/清理和 N7 需求/知识/用例检索/来源/清理均通过基础链路，脱敏证据见 `docs/evidence/n6-project-asset-acceptance-2026-08-25.json` 与 `docs/evidence/n7-intelligence-acceptance-2026-08-25.json`。普通 viewer 和 N7 真实 AI 草稿未验证，两个环境门禁保持 `[E]`/`partial`。
- [x] 计划检查点 2.4.7：已将 q19 N6/N7 基础验收结果、P8 本地治理入口、目标只读预检结果、N1 任务中心分页和下一执行顺序同步到开发计划、路线图、发布状态与 MEMORY；下一项固定为提供受控管理员/viewer 账号后执行角色矩阵，之后才进入受控真实 AI 与 P8 目标治理复核。
- [ ] 下一验收门：准备受控 viewer 账号并执行 N6/N7 `--require-role-matrix`；无账号时保持 `partial`，不得用管理员结果推断普通角色隔离。
- [x] P8 系统治理验收入口：新增 `scripts/n8-system-governance-acceptance.py` 和运行手册，覆盖远程工具箱诊断、配置聚合、配置版本/差异、审计 CSV、普通角色拒绝以及显式 `--allow-mutations --rollback`；接入 Make/CI/pre-commit，契约与质量回归 `34 passed`。目标部署和真实账号验收仍待完成。
- [x] P8 q19 目标只读预检：健康检查和 q19 运行栈通过；数据库只读检查确认启用管理员用户名为 `parado`，但受控登录仍返回 HTTP 401，随后停止继续尝试，未读取/记录密码字段、凭据或响应正文且未执行远端变更。脱敏证据见 `docs/evidence/n8-system-governance-environment-audit-2026-08-25.json`；完整治理验收仍待受控管理员与 viewer 凭据。
- [x] N1 任务中心分页：统一任务接口增加有界 `offset`，跨 Case/Suite/Plan/Android/Performance 合并排序后再切页；前端增加服务端分页并保留项目、状态、类型和页码深链，筛选时回到第一页。工作台定向 `15 passed`、后端非集成全量 `2380 passed`、前端全量 `69 files / 302 tests passed`，type-check/build/Ruff/diff-check 通过；真实角色和执行数据仍待环境复核。
- [x] N1 我的待办分页：工作台概览接口增加有界 `todo_offset`，跨评审、失败运行、逾期计划和设备异常按优先级/时间合并后切页；前端保留项目与 `todo_page` 深链，切换项目回到第一页并移除固定 100 条的本地截断。工作台定向 `16 passed`、后端非集成全量 `2381 passed`、前端全量 `69 files / 302 tests passed`，focused todos `2 passed`，type-check/build/Ruff/format/diff-check 通过；真实角色和待办数据仍待环境复核。
- [x] N5/N7 真实模型验收前置：`--require-ai` 现在要求管理员并校验保存的 AI 配置、模型发现、连接测试、临时项目绑定和可编辑草稿；`--require-vision`/`--require-thinking` 分别要求发现模型明确声明视觉/推理能力，单独传入能力参数会直接拒绝。脚本不在自定义业务 payload 中携带 API Key，也不写入报告；定向 `10 passed`、后端非集成全量 `2383 passed`、Ruff/格式/diff-check 通过；真实模型、参数接受和清理证据仍待外部门禁。
- [x] N6 缺陷状态刷新项目隔离：刷新执行记录关联缺陷状态前校验所属项目 viewer 权限，并拒绝跨项目已保存 tracker；新增无权限/跨项目回归，缺陷跟踪 API 定向 `11 passed`，独立审查和差异检查通过。真实项目角色、外部平台和可清理失败运行仍待 N6 环境复核。
- [x] N6 缺陷证据跨类型报告导航：case/Android/性能/suite/plan 缺陷证据均跳转到对应报告入口，suite/plan 深链按运行记录解析并恢复项目上下文；前端定向 `23 passed`、全量 `69 files / 297 tests passed`，`vue-tsc` 和生产构建通过，独立审查已修复项目上下文缺失。真实项目角色和报告环境仍待 N6 复核。
- [x] N6 计划报告套件明细导航：计划运行报告中的套件明细可携带 `project_id`/`suite_run_id` 跳转到套件执行记录并展开对应运行，无效运行 ID 禁止跳转；计划列表定向 `7 passed`、前端全量 `69 files / 298 tests passed`，`vue-tsc`、生产构建和独立审查通过。真实项目角色、可清理失败运行和报告环境仍待 N6 复核。
- [x] N6 数据集影响范围项目上下文：数据集影响范围的案例/套件/计划入口保留当前 `project_id`，案例详情可加载项目环境并返回项目筛选，避免跳转后丢失项目上下文；数据集定向 `9 passed`、前端全量 `69 files / 299 tests passed`，`vue-tsc`、生产构建和独立审查修复通过。真实项目角色、跨项目可见性和可清理数据仍待 N6 复核。
- [x] N6 用例评审打开详情项目上下文：评审工作台打开案例详情时携带记录自身 `project_id`，保留项目环境和返回筛选；评审工作台定向 `3 passed`、前端全量 `69 files / 300 tests passed`，`vue-tsc`、生产构建和独立审查通过。真实项目角色、跨项目可见性和可清理评审数据仍待 N6 复核。
- [x] N6 工作台任务详情上下文：case、suite、plan、Android、performance 任务详情统一保留 `project_id`；suite/plan/performance 额外携带 `run_id`，任务中心可直接定位具体运行记录；工作台 API 定向 `14 passed`，后端非集成全量 `2352 passed`，数据集影响范围静态契约旧路由断言修复后相关回归 `17 passed`，Ruff/差异检查通过。真实项目角色、跨项目可见性、可清理运行和报告环境仍待 N6 复核。
- [x] N6 项目资产与角色矩阵验收工具及 q19 基础链路：脚本覆盖用例评审、套件/计划、执行/报告、缺陷关联、普通 viewer 只读/写入拒绝和删除后 404 清理；脚本定向 `6 passed`、质量门禁一致性 `10 passed`。q19 `--execute` 的执行记录、缺陷关联和清理已通过，首次清理外键问题由 `716d1b3`/迁移 `20260825_0066` 修复；普通 viewer 未提供，角色矩阵仍待验收。
- [~] N8/N9 系统治理与发布收口：汇总脱敏证据、配置差异、回滚边界、操作手册和最终提交 SHA。
- [ ] 每个模块必须完成“实现/调整 → 测试 → 独立审查 → 修复 → 文档与记忆同步 → 提交推送”后才能移动游标。

详细拆分、依赖和状态口径见 [`docs/development-plan-2026-08-25.md`](docs/development-plan-2026-08-25.md) 的 2.4.0；2.3.0 以下内容仅作历史记录。

## 2026-08-25 当前开发计划 2.2.0 跟踪摘要

- [x] 导航基线：工作台、测试能力、测试资产、智能中枢、系统五组入口和旧 URL 兼容边界已登记。
- [ ] P0/N4 性能真实环境：等待 Kubernetes、Prometheus、独立 MinIO source/target；未具备前保持 `[-]`，不以 mock、单节点 Compose 或跳过项替代。
- [ ] P1/N5～P4/N8：按真实模型、项目角色/资产、知识数据和目标部署顺序复核；本地实现保持 `[E]`，不得直接改成真实通过。
- [~] P5/N9 发布收口：依赖所有未关闭门禁的负责人、原因、证据路径、复验命令和最终 SHA。
- [ ] 每个模块必须完成“实现/调整 → 测试 → 独立审查 → 修复 → 文档与记忆同步 → 提交推送”后才能移动执行游标；详细模板见开发计划 2.2.0。

## 2026-08-25 当前开发计划 2.1.0 跟踪摘要

- [x] N2 Karing 单设备：包身份、Windows Worker、低代码、录屏、稳定性/Monkey、性能/流畅度、事件/日志/报告和临时清理均已通过；脱敏证据以开发计划 N2.0.5～N2.0.7 为准。
- [ ] N4 真实性能环境：依赖真实 Kubernetes、Prometheus、独立 MinIO source/target；当前目标主机未提供这些条件，保持 `[-]`，不以 q19 Compose、mock 或跳过项替代。
- [ ] N5-N8 外部边界：真实模型、项目角色/资产、知识数据、目标部署、权限、脱敏、审计和回滚按顺序复核，当前为 `[E]`。
- [x] N5 本地密钥边界修复：Ollama 无 API Key 可用于用例、数据集、Mock、诊断和自愈；非 Ollama 空密钥仍拒绝，兼容请求不发送空 Authorization；定向 `88 passed`、后端非集成全量 `2315 passed`。
- [x] N5 AI 模型连接健康检查：配置页新增“测试连接”，复用已保存密钥并允许 keyless Ollama；请求固定短文本、限时限 token、规范化 Endpoint，错误脱敏且成功写审计；后端定向 `15 passed`、非集成全量 `2317 passed`，前端全量 `69 files / 287 tests passed`。
- [x] N5 模型能力提示与思考快捷配置：提供关闭（默认）、thinking、enable_thinking、reasoning_effort 选项，同步高级 JSON；拉取模型后提示思考/多模态能力状态；前端定向 `5 passed`、全量 `69 files / 289 tests passed`，类型检查和生产构建通过。
- [x] N5 AI 生成失败与原始响应安全边界：用例、数据集、Mock 和模型列表错误不回显供应商响应/网络异常；用例 `raw_response` 限长并脱敏 JSON 敏感字段、键值和 URL 凭据；AI 用例/治理定向 `21 passed`，数据集/Mock/LLM 相关回归 `78 passed`，后端非集成全量 `2322 passed`，Ruff 和差异检查通过。
- [x] N5/N6 AI 用例来源追踪摘要：生成结果记录配置/供应商/模型、接口数量、数据集版本、Mock 数量和生成时间，保存到 `_ai_source` 并在详情页展示；审计记录模型摘要且不含敏感输入；后端变更测试独立 `2 passed`、非集成全量 `2323 passed`、前端全量 `69 files / 289 tests passed`，类型检查和生产构建通过。
- [x] N6 失败运行转内部缺陷入口：Android 专项报告和性能压测详情支持一键创建缺陷、重复缺陷提示、关联缺陷展示和按执行记录跳转；通过/运行中状态不得创建；定向后端 `14 passed`、前端性能/缺陷页 `17 passed`、前端全量 `69 files / 292 tests passed`、后端非集成全量 `2326 passed`，真实项目权限仍待环境复核。
- [x] N9 发布证据索引与一致性校验子模块：新增脱敏索引、校验脚本、Make/CI/预提交入口；定向校验与发布契约 `22 passed`、后端非集成全量 `2333 passed`、Ruff/格式/差异检查通过。候选 SHA 必须匹配当前 HEAD，最终 N9 仍待真实门禁收口。
- [x] N9.2 发布文档同步一致性契约：发布索引校验开发计划、Task、MEMORY、路线图、发布状态和发布清单的关键标记；定向校验与发布契约 `23 passed`、后端非集成全量 `2334 passed`，缺少文件或标记会阻断发布校验。
- [x] N4 smoke 显式 Kubernetes 门禁：新增 `--require-kubernetes`，缺少 Deployment 时启动即拒绝；性能脚本、发布契约和质量一致性定向 `46 passed`，真实 N4 仍待 Kubernetes、发布级 Prometheus 和独立 MinIO。
- [x] N4 MinIO 灾备端点独立性门禁：拒绝同机文本/回环别名及解析到同一 IP 的 source/target；MinIO 灾备、性能 smoke、发布契约定向 `51 passed`，真实独立 MinIO source/target 仍待环境验收。
- [~] N9 发布收口整体：继续绑定最终提交 SHA，汇总测试、审查、环境证据、操作手册和剩余阻塞。
- [ ] 每个后续模块仍必须完成“实现/调整 → 测试 → 独立审查 → 修复 → 文档/记忆同步 → 提交推送”后才能移动游标。

详细拆分、解除条件和复验命令见 [`docs/development-plan-2026-08-25.md`](docs/development-plan-2026-08-25.md) 的 2.2.0～2.2.2 节；以下旧章节仅作历史记录。

## 2026-08-25 导航对齐开发计划 2.0

### 2026-08-25 当前计划同步与执行游标

- [x] 导航边界：按工作台、测试能力、测试资产、智能中枢、系统五组组织入口；设备、APK、Mock、数据集、Web/API 资产等页面保留兼容 URL，但从对应工作台或配置中心进入，不继续堆在系统管理下。
- [x] 已有本地交付：N0/N1/N3/N5-N8 的代码、定向回归、审查和文档基线已登记；真实账号、协议服务、模型、外部平台和目标部署仍按环境门禁独立复核。
- [x] 已完成模块：N2 Karing 单设备已完成包身份、Worker 前置、低代码、截图/录屏、稳定性/Monkey、性能/流畅度专项、事件/日志/报告详情、下载和临时数据清理。
- [ ] 后续模块：N4 真实性能环境验收；N5-N8 外部依赖、权限、脱敏、审计和回滚复核；N9 汇总最终证据并收口发布结论。
- [ ] 每个模块必须完成实现/调整、测试、独立代码审查、问题修复、文档与记忆同步、提交和推送，才允许移动执行游标。

本次同步只登记计划和当前状态，不把页面可打开、mock、Worker 心跳或跳过项写成业务验收通过。

- [x] 固化五组导航边界：工作台、测试能力、测试资产、智能中枢、系统；旧设备、APK、Mock、数据集和资产 URL 保持兼容，但不再作为系统管理下的业务入口。
- [x] 为 N0-N9 登记交付范围、最小验收出口、依赖和状态；`[E]` 只代表本地实现完成，不代表生产或真实设备通过。
- [ ] N4 真实 Kubernetes/Prometheus/独立 MinIO 门禁；缺少目标时保留阻塞原因和复验命令。
- [ ] N2 Karing 单设备闭环；包名/启动入口和 Worker 前置已通过，按低代码、录屏/回放、专项任务、事件/日志/报告和清理顺序执行。
- [ ] N5-N8 外部依赖复核与 N9 发布收口；每一项完成实现、测试、审查修复、文档同步和提交推送后再移动游标。

计划登记本身不伪造环境验收证据；随后完成的 N2 控件属性诊断已在下方单独记录，本地代码门禁与真实设备门禁保持分开。

### 2026-08-25 N2 Karing 真机包名与 Worker 前置验收

- [x] 目标设备 `172.16.102.91:5555` 的包管理确认 `com.nebula.karing` 已安装，入口解析为 `com.nebula.karing/.MainActivity`。
- [x] Windows Android Worker doctor、Backend 登录、PostgreSQL/Redis/MinIO readiness、Worker registry 和设备扫描通过；脱敏证据见 [`docs/evidence/android-karing-acceptance-2026-08-25.json`](docs/evidence/android-karing-acceptance-2026-08-25.json) 与 [`docs/evidence/windows-android-karing-worker-2026-08-25.json`](docs/evidence/windows-android-karing-worker-2026-08-25.json)。
- [ ] 创建或选择可清理的已审批 Android 低代码用例，执行无破坏的启动/等待/截图并确认步骤、设备产物和终态。
- [ ] 完成录屏/异常回放、专项任务、事件/日志/报告详情、下载和清理；当前低代码执行仍未运行，不能标记 N2 完成。
- [~] Karing 包身份和 Worker 前置门禁已关闭，N2 单设备业务闭环继续进行。

### 2026-08-25 N2 Karing 低代码与录屏回传验收

- [x] `run 27` 在 `172.16.102.91:5555` 上执行 Karing 启动、等待、截图 3/3 步骤通过，返回 3 张步骤截图和 2 个 Android 产物；临时项目已清理，证据见 [`docs/evidence/android-karing-lowcode-2026-08-25.json`](docs/evidence/android-karing-lowcode-2026-08-25.json)。
- [x] 代码审查发现并修复证据门禁过宽问题：新增 `-RequireAndroidRecording`，报告明确输出 `recording=True/False`，要求 `screen_recording` 产物存在；脚本契约回归 `12 passed`，PowerShell 解析通过。
- [x] 真实 `run 29` 开启录屏后通过，3/3 步骤、3 张截图、3 个产物且录屏产物存在；临时项目已清理，证据见 [`docs/evidence/android-karing-recording-gate-2026-08-25.json`](docs/evidence/android-karing-recording-gate-2026-08-25.json)。
- [ ] 异常回放、性能/稳定性/流畅度专项任务、事件/日志/报告详情、下载和对象清理仍待继续验证。
- [~] N2 已关闭低代码最小执行和录屏回传门禁，继续推进专项任务与报告闭环。

### 2026-08-25 N2 Android 控件属性获取诊断

- [x] API 进程和 Windows Android Worker 统一返回控件属性诊断状态：找到、未命中和不可用；诊断只包含稳定 code，不返回 ADB 原始错误。
- [x] Android 可视化录制在 UIAutomator/Worker/设备连接不可用时给出中英文提示，同时保留坐标步骤；正常未命中控件时继续静默坐标回退。
- [x] 定向回归 `22 passed`、前端相关回归 `23 passed`、后端非集成全量 `2305 passed`、前端全量 `69 files / 284 tests passed`；类型检查、生产构建、Ruff、格式检查、差异检查和独立代码审查通过。
- [E] 本地交付完成；真实 Karing 页面、UIAutomator 权限、Windows Worker 回传和真机控件属性仍待环境验收，不能用其他应用探针替代。

### 2026-08-25 N0/N6 测试套件导航归位

- [x] 将已有 `/suites` 页面加入“测试资产”侧栏，使用独立的“测试套件”中英文菜单文案和能力描述。
- [x] 修复 `/suites`、`/suites/:id` 深链错误选中“测试计划”的问题，面包屑保持“测试资产 → 测试套件”，旧 URL 不变。
- [x] 导航定向 `8 passed`，前端全量 `69 files / 285 tests passed`，类型检查、生产构建和差异检查通过；独立代码审查未发现问题。
- [E] 本地导航交付完成；真实账号、角色和项目数据复核仍按 N0/N6 维护。

### 2026-08-25 N0 工作台运行记录入口收敛

- [x] 工作台侧栏按参考导航收敛为首页、我的待办、项目中心和任务中心，移除重复的“执行记录”入口。
- [x] 保留 `/runs`、`/runs/:id` 旧地址和内部跳转；旧运行页面打开时统一选中任务中心，运行详情面包屑仍保留“工作台 → 执行记录”。
- [x] 导航定向 `9 passed`，前端全量 `69 files / 286 tests passed`，类型检查、生产构建和差异检查通过。
- [x] 独立审查发现并修复直接访问 `/runs` 未映射的问题，修复后未发现其他可操作问题。
- [E] 本地导航交付完成；真实账号、运行数据和任务权限复核仍按 N0/N6 维护。

### 2026-08-25 N4 真实性能环境只读复核

- [x] 只读核验 `172.31.27.133`：未发现 `kubectl/helm`，默认 `127.0.0.1:9090` Prometheus readiness 拒绝连接；现有 q19 为 Docker Compose 单性能 Worker/目标服务。
- [x] 未发现独立 MinIO 源/目标灾备端点；未执行远端安装、部署、重启或数据修改。
- [E] N4 本地代码入口和回归保持完成，但真实性能门禁仍阻塞；脱敏证据见 [`performance-environment-audit-2026-08-25.json`](docs/evidence/performance-environment-audit-2026-08-25.json)。

## 2026-08-25 参考导航分组执行游标（历史快照，当前以 2.0.0 为准）

计划细分和验收出口见 [`docs/development-plan-2026-08-25.md`](docs/development-plan-2026-08-25.md) 的“参考导航学习版执行台账”。当前按以下状态跟踪：

- `[E]` N0 导航壳与工作台：本地闭环已完成，继续随真实账号复核深链、权限和任务事件。
- `[E]` N1 接口测试：HTTP、会话复用、gRPC TLS Unary、OpenAPI/Postman 导入预览/落库、GraphQL、WebSocket、三种流式 gRPC 以及 HTML/JUnit/PDF 报告详情闭环已在 q19 受控环境通过；生产协议服务仍保持独立门禁。
- `[~]` N2 APP 自动化：Karing 真实包名、Windows Worker、低代码和录屏回传已通过；异常回放、专项任务、事件/日志/报告详情和最终清理仍待关闭。
- `[E]` N3 UI 自动化：本地/q19 录制、回放、Trace/HAR 和浏览器矩阵证据已有，继续用当前账号复核。
- `[E]` N4 性能测试：Worker/目标服务采样、本地与 q19 短压、Kubernetes 多节点/副本/Worker 资源预检、保留清理和跨端点 MinIO 复制/恢复 smoke 已完成；真实多节点、Prometheus/MinIO 生命周期和跨主机恢复证据仍待目标环境。
- `[E]` N5 AI 智能测试、N6 测试资产、N7 智能中枢、N8 系统：本地实现已完成，真实模型、项目数据、目标部署和外部平台边界仍需单独验收。
- `[~]` N9 发布收口：依赖 N2、N4 和真实外部服务；未完成项必须保留阻塞原因与复验命令。

当前执行游标为 **N2 Karing 专项任务/事件/报告闭环 → N4 真实性能环境（外部目标等待） → N5-N8 外部依赖复核 → N9 发布收口**；N2 已关闭包身份、Worker、低代码和录屏回传门禁，真机专项和报告门禁仍保持进行中。每个游标项都要完成实现、测试、代码审查、修复、文档/记忆同步和提交推送后再移动。

### 2026-08-25 1.1 Android 专项应用启动兼容

- [x] 统一性能、稳定性和流畅度执行器的应用启动逻辑：显式 Activity 使用 `am start -n`，未填写 Activity 使用 Launcher Intent 自动发现，不再假定入口一定是 `.MainActivity`。
- [x] 流畅度执行器尊重前置启动设置的 `auto_start=false`，避免前置操作完成后重复启动应用；专项任务表单空 Activity 不再保存 `.MainActivity`，历史显式配置保持兼容。
- [x] 代码审查与质量门禁：后端非集成 `2295 passed`；四个受影响测试文件独立 `3/25/19/15 passed`；前端 `67 files / 275 tests passed`；`vue-tsc`、生产构建、Ruff、`git diff --check` 均通过。
- [E] 真实 Karing APK/包名、Windows Android Worker/ADB、启动组件、专项媒体和报告仍待环境验收；不使用其他应用替代 Karing。

### 2026-08-25 1.2 Windows Android 包名与启动入口验收探针

- [x] `windows-android-acceptance.ps1` 增加 `-LaunchActivity`，指定包名后校验包已安装，并解析显式 Activity 或 `MAIN/LAUNCHER` 默认入口。
- [x] 报告新增脱敏应用元数据；探针只读取 Package Manager，不启动/修改应用，不保存包内容或日志正文。
- [x] 脚本契约 `2 passed`，脚本目录 `93 passed`，质量/发布文档回归 `15 passed`，PowerShell 语法检查通过；当前设备用 `com.android.settings` 完成自动/显式两条只读探针。
- [E] Karing APK/真实包名、Windows Android Worker 调度、低代码、录屏/异常回放、专项任务和报告仍待环境验收，系统设置包探针不替代 Karing 验收。

### 2026-08-25 1.3 Android 低代码控件属性录制与坐标回退

- [x] 可视化点击录制同时保存文本、resource-id、content-desc、className、bounds 和原始坐标；控件属性可用于阅读、标准步骤生成和稳定回放。
- [x] 回放按 resource-id → 文本 → content-desc 优先定位；UIAutomator dump 失败或找不到控件时回退到录制坐标，保留旧坐标步骤兼容性。
- [x] 后端 Android 低代码定向 `42 passed`、非集成全量 `2297 passed`，前端录制参数/标准步骤定向 `4 passed`、全量 `68 files / 277 tests passed`，`vue-tsc`、生产构建、Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- [E] 真实 Karing APK、Worker 上的 UIAutomator 权限、控件属性录制/回放、录屏/异常回放、专项任务和报告仍待真机验收。

### 2026-08-25 1.4 Android 低代码长按与输入控件定位

- [x] 长按步骤支持 resource-id、文本、content-desc 定位，按控件中心执行同点 swipe 长按；无控件属性时继续兼容坐标，目标不存在时明确失败。
- [x] 输入步骤分离输入内容和目标控件，支持 `targetText`、resource-id、content-desc；目标定位失败不再继续向当前焦点输入，Python 脚本也不会把输入值误当成控件文本。
- [x] 后端 Android 低代码定向 `45 passed`、非集成全量 `2300 passed`，前端标准步骤/脚本生成定向 `11 passed`、全量 `68 files / 279 tests passed`，类型检查、生产构建、Ruff、格式检查和差异检查通过；独立代码审查未发现可操作问题。
- [E] 真实 Karing APK、Windows Worker UIAutomator 权限及真机长按/输入行为仍待环境验收。

### 2026-08-25 1.5 Android 可视化滑动的分辨率适配

- [x] 可视化录制的坐标滑动保存 `screenWidth/screenHeight`；标准步骤摘要展示录制屏幕尺寸，旧点击/旧滑动步骤格式保持兼容。
- [x] Worker 读取当前设备生效屏幕尺寸，按宽高比例缩放并裁剪带元数据的坐标滑动；方向滑动按当前尺寸计算，读取失败时保留历史默认坐标。
- [x] 独立 Python 脚本生成器对方向滑动和带屏幕尺寸的坐标滑动使用运行时尺寸适配；补充后端 `47 passed`、非集成全量 `2302 passed`、前端定向 `16 passed`、全量 `68 files / 282 tests passed`，类型检查、生产构建、Ruff、格式检查和差异检查通过；独立代码审查未发现可操作问题。
- [E] 真实 Karing/Windows Worker 的不同分辨率、横竖屏、录屏和报告回放仍待真机验收。

### 2026-08-25 1.0 开发计划同步

- [x] 盘点 N4 已有本地能力：Worker/目标服务指标采样、Kubernetes 容量预检、保留清理、MinIO 生命周期审计和跨端点恢复 smoke 均已有代码与回归。
- [ ] N4 真实环境验收：依赖 Kubernetes、独立 MinIO 和 Prometheus 目标；缺少目标时保留 `[E]`，不以 q19 Compose、mock 或跳过项替代。
- [ ] N2 Karing 单设备闭环：等待真实 APK/`package_name`，解除条件和执行顺序见主计划 1.0 节。
- [ ] N5-N8 外部依赖复核与 N9 发布收口：按主计划顺序执行，凭据和测试数据均需可清理、可审计。

## 2026-08-25 当前开发计划登记（历史快照，当前以 2.0.0 为准）

- [E] **N1 接口测试**：GraphQL、WebSocket、Server/Client/Bidi Streaming 以及 HTML/JUnit/PDF 报告详情/导出已在 q19 受控目标完成真实创建、审批、执行、断言/提取和清理；生产协议服务仍单独跟踪。
- [~] **N2 APP 自动化**：Karing APK/真实包名、Worker、低代码和录屏回传已完成；按单设备异常回放、专项任务、事件/日志/报告和清理顺序继续执行。
- [~] **N4 性能测试**：继续推进真实多节点、资源采样、Prometheus/MinIO 生命周期和跨主机恢复；本地分片容量、趋势、基线和保留清理不等于生产通过。
- [E] **N0/N3/N5-N8**：本地实现和回归已完成，继续按真实账号、角色、项目、模型和目标部署复核。
- [~] **N9 发布收口**：依赖 N1、N2、N4 以及真实通知/外部缺陷平台证据；未满足条件时保留明确阻塞和复验命令。

每个模块均按“实现 → 测试 → 代码审查 → 修复 → 文档与记忆同步 → 提交推送”闭环，不把 mock、跳过项、Worker 心跳或页面截图记为真实通过。

### 2026-08-25 N1 受控协议目标交付

- [x] 扩展独立 `acceptance-target`：新增 GraphQL POST、WebSocket 握手/文本消息回显，并覆盖 Unary、Server Streaming、Client Streaming、Bidi Streaming gRPC 目标。
- [x] q19 真实网络闭环：GraphQL run `19`、WebSocket run `20`、gRPC Server Streaming run `23`、Client Streaming run `24`、Bidi Streaming run `25` 均通过；每条临时项目已清理，清理后同名项目匹配数为 `0`。
- [x] 本地验证：目标/部署契约和四类协议执行器回归 `90 passed`，后端非集成全量 `2288 passed`，Ruff、格式检查和 `git diff --check` 通过；独立代码审查未发现可操作问题。代码提交 `5b07a3e`，证据见 [`docs/evidence/api-protocol-targets-2026-08-25.json`](docs/evidence/api-protocol-targets-2026-08-25.json)。
- [E] 本项只关闭受控协议目标证据；完整报告导出/详情治理、生产协议服务和外部环境仍保持待验收。

### 2026-08-25 N1 完整报告闭环交付

- [x] 运行详情页新增 JUnit XML 导出入口，与既有 HTML/PDF 导出共用权限校验、Blob 下载和错误反馈；中英文文案与前端回归已补齐。
- [x] q19 真实网络闭环：临时项目 `42`、用例 `27`、运行 `26` 通过；详情接口 `200`，HTML `200/2561 bytes`、JUnit XML `200/220 bytes` 且 XML 可解析、PDF `200/167056 bytes`；项目删除 `204`，清理后匹配数 `0`。
- [x] 质量门禁：前端定向 `11 passed`、后端报告/导出 `24 passed`、前端全量 `67 files / 275 tests passed`，类型检查、生产构建、差异检查和独立代码审查通过；代码提交 `86f3bf7`，证据见 [`docs/evidence/report-closure-2026-08-25.json`](docs/evidence/report-closure-2026-08-25.json)。
- [E] 本项关闭 q19 受控报告详情/导出证据；生产协议服务、生产对象存储和外部发布环境仍保持独立门禁。

### 2026-08-25 N4 Kubernetes 性能容量预检

- [x] 扩展 `scripts/performance-environment-smoke.py`：可选校验 Kubernetes 可调度 Ready 节点数、性能 Worker Deployment 的 desired/available 副本数，以及指定容器的 CPU/内存 `resources.requests/limits`。
- [x] 节点不足、副本不足或资源配置缺失会让验收失败；默认不启用新门禁，兼容已有单 Deployment/Pod smoke。
- [x] 补充 2 个回归场景；性能环境脚本定向回归 `29 passed`，Ruff、格式检查和 `git diff --check` 通过，独立代码审查未发现可操作问题。
- [E] 本项只完成可复用的生产预检代码和本地证据；当前目标主机没有 Kubernetes 集群，因此真实多节点/副本、Prometheus/MinIO 生命周期和跨主机恢复仍未关闭。

### 2026-08-25 N4 跨端点 MinIO 恢复验收入口

- [x] 新增 `scripts/minio-dr-acceptance.py`：使用独立源端/目标端 MinIO 环境变量，创建唯一探针对象，校验源端回读、跨端点复制、目标端回读、恢复回源和 SHA-256 一致性。
- [x] 默认读取两端生命周期配置并记录规则数量；可重复传入 `--require-lifecycle-rule PREFIX=DAYS` 强制校验启用的精确前缀/保留天数；所有临时对象在 `finally` 中清理，凭据不会写入证据。
- [x] 增加 `make minio-dr-acceptance` 入口、性能验收包和 CI/pre-commit Ruff 清单；脚本回归 `3 passed`，质量门禁一致性和灾备文档回归 `17 passed`。
- [E] 本项完成跨主机恢复的可执行验收入口和本地回归；当前目标只有单机 Docker Compose，尚未取得独立 MinIO 目标，因此不关闭真实跨主机恢复或生产生命周期门禁。

### 2026-08-25 N1 协议用例空步骤防护

- [x] GraphQL、WebSocket、gRPC 在派发前拒绝缺失、空数组和 `null` 的 `config.steps`，终态为 `error`，错误原因可在执行记录中查看。
- [x] API 用例仍保留旧配置的默认主请求行为，未改变已有 API 导入和执行兼容性。
- [x] 定向派发/HTTP 家族回归 `94 passed`，后端非集成全量 `2279 passed`；前端类型检查、生产构建、Ruff 和 `git diff --check` 通过。
- [x] 独立代码审查未发现可操作问题；真实 GraphQL/WebSocket/流式 gRPC 和完整报告目标仍保持 `[E]` 待环境验收。

### 2026-08-25 N1 协议配置保存校验

- [x] 创建/更新 GraphQL、WebSocket、gRPC 时校验最小可执行配置：步骤、endpoint/url、WebSocket 消息、gRPC target/proto/service/method。
- [x] 校验失败返回 `422`，并且发生在创建快照前，不产生脏用例或无效快照；派发层仍保留运行期兜底。
- [x] 用例管理定向回归 `35 passed`，后端非集成全量 `2282 passed`，Ruff/diff-check 通过；独立代码审查未发现问题。

### 2026-08-25 N1 报告中心按用例类型统计

- [x] 报告概览 API 按当前用户可见项目聚合已完成运行，返回 API、GraphQL、WebSocket、gRPC、Web、Android 等类型的总运行、通过、失败、异常和通过率。
- [x] 报告中心增加用例类型分布卡片、通过率进度条、运行/失败摘要和无数据空态，并同步中英文文案与前端类型。
- [x] 报告定向回归 `5 passed`、前端报告页 `3 passed`，后端非集成全量 `2282 passed`；`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。
- [x] 独立代码审查未发现可操作问题；真实 GraphQL/WebSocket/流式 gRPC 和完整报告环境证据仍保持 `[E]` 待验收。
- [x] 修复报告对比选择边界：默认选择最近一组同用例运行，切换任一侧时自动对齐另一侧的同用例记录，前端在调用前校验同一项目用例约束。
- [x] 报告页回归 `4 passed`，前端全量 `66 files / 270 tests passed`，type-check、生产构建和差异检查通过；真实多协议和完整报告环境证据仍保持 `[E]` 待验收。

### 2026-08-25 N1 协议用例前端保存校验

- [x] 抽取 GraphQL、WebSocket、gRPC 保存前必填校验纯函数，统一检查空字符串/空格、消息数组和 target/proto/service/method，并复用既有中英文提示。
- [x] `CaseFormDrawer` 在发起创建/更新请求前执行校验；后端 `422` 仍是最终防线，未知或 API 用例不受协议校验影响。
- [x] 工具函数回归 `8 passed`；前端全量 `66 files / 272 tests passed`，`vue-tsc`、生产构建和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- [E] 本项只改善本地保存反馈，不关闭 GraphQL/WebSocket/流式 gRPC 真实目标和完整报告环境验收。

### 2026-08-25 P0-B.3.1 Android 专项 APK 选择体验

- [x] 专项任务只展示已解析包名的 APK；选择后自动绑定并锁定包名输入，清空 APK 时同步清空包名；未选择 APK 时仍可手工填写。
- [x] 中英文提示与后端包名不可覆盖规则一致；工具函数回归 `2 passed`，前端全量 `67 files / 274 tests passed`，`vue-tsc`、生产构建和 `git diff --check` 通过。
- [x] 独立代码审查未发现可操作问题；真实 Karing APK、设备执行、专项任务和完整报告仍保持环境验收边界。

### 2026-08-25 N0/N3 Windows smoke 当前账号边界

- [x] Windows smoke 默认只读取当前账号 `ATP_USERNAME/ATP_PASSWORD`，不再自动回退或混用 `FIRST_ADMIN_*`；新数据库初始化验证必须显式传入 `-UseBootstrapCredentials`。
- [x] 补充脚本契约和 Windows 操作手册，缺少当前账号时给出明确提示且不输出凭据；既有 HTTP 401 诊断仍保留。
- [E] 代码和脚本边界已完成，需用当前有效账号重新执行完整 Windows API/Web smoke 才能关闭真实环境证据。

## 2026-08-25 API gRPC TLS 真实目标闭环

- [x] q19 受控 gRPC TLS 目标完成临时项目、模块、用例创建、评审提交、审批、Unary 执行和终态查询。
- [x] TLS 使用目标公开 PEM 根证书和 `tls_server_name=grpc-target`，gRPC 状态 `OK`，响应断言和 JSONPath `$.text` 提取通过；根证书未进入执行请求快照。
- [x] 定向执行器回归 `69 passed`，Ruff、前端类型检查、生产构建和前端配置工具测试 `6 passed` 通过；证据见 [`docs/evidence/api-grpc-tls-2026-08-25.json`](docs/evidence/api-grpc-tls-2026-08-25.json)。
- [E] 本项只关闭受控 gRPC TLS Unary 证据；OpenAPI/Postman 导入、GraphQL/WebSocket/流式 gRPC 真实目标和完整报告仍需后续环境验收。

## 2026-08-25 API OpenAPI/Postman 导入解析加固

- [x] OpenAPI 参数、请求体和响应体保留显式 `0`、`false` 等合法假值，并支持 media `examples` 的首个值。
- [x] Postman 字符串 URL 的查询参数、空值查询参数和 urlencoded/formdata 请求体可解析；明确标记为 disabled 的查询项和请求头会跳过。
- [x] 定向解析与 API 端点回归 `38 passed`，Ruff 和 `git diff --check` 通过；q19 按 `75ed756` 重建 Backend/Worker 后，`/ai/cases/parse-schema` 的 OpenAPI/Postman 真实请求均返回 `200`，结果分别为 `1/1` 和 `1/3`（接口/参数）。脱敏证据见 [`docs/evidence/api-import-parser-2026-08-25.json`](docs/evidence/api-import-parser-2026-08-25.json)。
- [E] 本项关闭导入解析层证据；导入预览/落库/回读/清理闭环另见下节，GraphQL/WebSocket/流式 gRPC 和完整报告仍需后续验收。

## 2026-08-25 API 导入预览与落库真实闭环

- [x] q19 受控目标完成 OpenAPI 解析、临时项目/模块创建、导入预览（`valid=1/invalid=0`）、用例落库、状态码断言与步骤结果回读、项目删除清理。
- [x] 解析到的成功响应码 `201` 保留到导入用例的 API 断言和步骤预期；修复 `Module.project` 异步懒加载触发 `MissingGreenlet` 的 500，并补充回归测试。
- [x] 定向回归 `42 passed`，后端非集成全量 `2270 passed`，Ruff/diff-check 通过；q19 证据见 [`docs/evidence/api-import-persistence-2026-08-25.json`](docs/evidence/api-import-persistence-2026-08-25.json)，代码提交为 `a8f6e26`。
- [E] 本项只关闭 OpenAPI 导入的预览、落库、回读和清理；GraphQL/WebSocket/流式 gRPC、生产目标和完整报告仍需后续验收。

## 2026-08-25 API 测试工作台真实目标最小闭环

- [x] 使用当前有效账号在 q19 受控 HTTP 目标创建临时项目、模块和 API 用例，完成提交评审、审批、执行和运行终态查询。
- [x] HTTP `GET` 返回 `200`，状态码断言通过，JSONPath `$.service` 提取成功；临时项目、用例、运行及关联数据清理成功。
- [x] API 执行器相关回归 `77 passed`；脱敏证据见 [`docs/evidence/api-real-target-2026-08-25.json`](docs/evidence/api-real-target-2026-08-25.json)。
- [x] 显式选择 `session_lifecycle=reuse` 的两步登录/当前用户场景通过，后续步骤复用 Cookie，登录请求体密码在执行证据中脱敏；证据见 [`docs/evidence/api-session-reuse-2026-08-25.json`](docs/evidence/api-session-reuse-2026-08-25.json)。
- [E] 本项只关闭受控 HTTP 与项目级会话复用证据；OpenAPI/Postman 导入、GraphQL/WebSocket/gRPC 真实目标和完整报告仍需后续环境验收。

## 2026-08-25 参考导航对齐开发计划（当前版本）

主计划已更新至 [`docs/product-navigation-roadmap-2026-08-24.md`](docs/product-navigation-roadmap-2026-08-24.md) 的“0.5 当前开发计划与跟踪台账”。目标导航与参考方案保持一致：工作台（首页、我的待办、项目中心、任务中心）、测试能力（接口/APP/UI/性能/AI）、测试资产（用例/计划/缺陷/报告/评审）、智能中枢（Hermes/需求与用例/知识）和系统（远程工具箱/配置中心）。旧资产和治理页面不从系统管理重复铺开，而是从对应工作台或配置中心进入并保持 URL 兼容。

- [x] 记录五组导航、入口职责、模块边界和当前本地/真实环境状态。
- [x] 记录后续模块顺序：导航壳与工作台 → API → APP → UI → 性能 → AI/Hermes → 测试资产/智能中枢 → 系统 → 发布收口。
- [x] 记录每个模块的验收出口和统一交付门禁：实现/调整 → 测试 → 代码审查 → 修复 → 文档与记忆同步 → 提交推送。
- [~] 当前优先完成 Android 单设备执行闭环；真实通知供应商、外部缺陷平台和生产性能仍不能标记为通过。

### 2026-08-25 当前执行计划登记

- [~] **P0-0 运行基础与账号初始化**：修复管理员账号改名后，启动 bootstrap 只按用户名查找并按重复邮箱插入，导致 q19 Backend 进入重启循环的问题；补用户名/邮箱幂等回归，重建并验证 q19 健康、登录和基础读接口。
- [~] **P0-B.3 Android 单设备闭环**：前置 ADB、Worker、设备扫描、租约、截图和控件操作已通过；通用 APK 的低代码、录屏、设备产物和结果回传已通过，Karing 专项任务与完整报告回传仍待真实包验证。
- [x] **P0-A Windows API/Web 复核**：当前账号下完整 smoke 已通过认证读接口、依赖 readiness、浏览器矩阵、文件传输、报告导出和 Web 低代码；GraphQL/WebSocket/流式 gRPC 仍按 N1 其他协议门禁单独跟踪。证据见 [`windows-full-readiness-2026-08-25.json`](docs/evidence/windows-full-readiness-2026-08-25.json)。
- [ ] **P1-C/P1-D/P1-E/P1-F**：依次完成真实通知、外部缺陷平台、生产性能环境和发布收口，保留目标环境证据。

每项均执行“实现/调整 → 定向测试 → 代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送”；真实环境未具备时只能记录阻塞。

### 2026-08-25 P0-0 管理员初始化幂等修复（本地交付）

- [x] 修复管理员改名后保留默认邮箱时的启动崩溃：初始化同时按用户名/邮箱查询，已有账号不重复插入；并发唯一键冲突仅在复查到已有身份时忽略，不覆盖已有密码或角色。
- [x] 新增 `backend/tests/services/test_admin_bootstrap.py`，覆盖已有邮箱身份和缺失身份创建；定向 `2 passed`，后端非集成全量 `2262 passed`，Ruff、格式检查、`git diff --check` 通过。
- [x] q19 已用保留端口映射的 Compose 配置更新 Backend；迁移 `20260824_0065 (head)`、Backend `running/healthy`、当前账号登录、依赖 readiness、Web/Android Worker registry 和 2 台设备扫描通过，最近 2 分钟无启动错误。脱敏证据见 [`docs/evidence/q19-admin-bootstrap-2026-08-25.json`](docs/evidence/q19-admin-bootstrap-2026-08-25.json)。
- [~] P0-0 已关闭启动与认证阻塞，但 Android 真实 APK/package name、低代码和媒体执行仍待后续门禁；远端 Compose 现场配置未覆盖。

### 2026-08-25 P0-B.3 单设备真实执行与 MinIO 大对象上传修复

- [x] 使用在线设备 `172.16.102.214:5555` 和已安装包 `com.microsoft.emmx` 完成临时 Android 低代码冒烟；3/3 步骤通过，开启录屏后设备信息、logcat、3 个步骤截图和录屏均回传成功，临时项目/用例/运行已清理。
- [x] 真实 APK 上传约 262 MB 时定位 q19 MinIO 读超时复用 5 秒连接超时的问题；新增 `MINIO_READ_TIMEOUT_SECONDS=60`、MinIO 连接池 `maxsize=10/block=True`，并同步启动配置页面、示例和文档。
- [x] 定向后端 `19 passed`，前端启动配置 `6 passed`，后端非集成全量基线为 `2263 passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。
- [x] q19 重建到 `e1dc113` 后，262,615,229 字节 APK 上传、`com.microsoft.emmx`/版本元数据解析、项目对象绑定、列表回读和临时数据清理通过；证据见 [`android-apk-upload-2026-08-25.json`](docs/evidence/android-apk-upload-2026-08-25.json)。
- [x] 修复标准 `ResXMLTree` 包装与 `RES_STRING_POOL_TYPE` 解析缺口；APK 元数据/API 定向 `17 passed`，Ruff 和格式检查通过。
- [~] 当前包不是 Karing，不能替代 Karing 应用专项验收；APK 下载端点、Karing 低代码/专项动作和完整报告回传仍需后续真实包验证。

当前计划的唯一排序为：`P0-B.3 真实 Android 门禁 → P0-A Windows API/Web 复核 → P1-C/P1-D → P1-E → P1-F`。本节只维护勾选状态，详细范围、验收标准和禁止事项以主计划及 [`docs/release-status-2026-08-25.md`](docs/release-status-2026-08-25.md) 为准。

## 2026-08-25 参考导航版开发计划登记（历史快照，当前以 2.0.0 为准）

参考导航的五组入口作为当前产品结构：工作台（首页、我的待办、项目中心、任务中心）、测试能力（接口/APP/UI/性能/AI）、测试资产（用例/计划/缺陷/报告/评审）、智能中枢（Hermes/需求与用例/知识）和系统（远程工具箱/配置中心）。旧设备、APK、专项任务、Mock、数据集、Web/API 资产及治理页面保持 URL 兼容，从所属工作台或配置中心进入，不再全部堆在系统管理下。

当前模块顺序和出口如下：

- `[E]` 导航壳与工作台：侧栏分组、项目上下文、深链选中、待办/任务聚合和统一操作已完成本地回归；真实角色和任务数据待复核。
- `[E]` API 测试工作台：环境、认证复用、导入、协议执行、断言/提取/依赖和报告入口已完成本地实现；真实协议目标待验收。
- `[~]` APP 自动化工作台：Karing 真实在线设备、APK 包名、低代码和录屏回传已完成；继续验收异常回放、专项任务和事件/日志/报告回传，最终以清理证据收口。
- `[E]` UI 自动化工作台：录制、元素库、页面对象、视觉基线、Trace/HAR、网络/Console 日志和多浏览器本地/q19 链路已有证据；本轮 Windows 完整 smoke 已复核通过。
- `[E]` 性能测试工作台：本地趋势、基线、容量、Worker/目标服务采样、保留清理和跨端点恢复入口已完成；真实多节点、Prometheus/MinIO 生命周期和跨主机恢复待验收。
- `[E]` AI/Hermes、测试资产/智能中枢、远程工具箱/配置中心：本地实现、权限、审查和回归已完成；真实模型、项目数据、外部平台和目标部署待验收。
- `[~]` 发布收口：统一提交 SHA、证据索引、能力矩阵、操作手册和回滚边界，未关闭门禁必须保留负责人/证据/复验命令。

后续执行顺序固定为：N2 Karing 专项任务/事件/报告闭环 → N4 真实性能环境 → N5-N8 外部依赖复核 → N9 发布收口。每个模块均执行“实现/调整 → 定向与全量测试 → 代码审查 → 修复 → 文档/记忆同步 → Conventional Commit 推送”；`[E]` 不等于真实环境通过，`offline`、mock 和跳过项不得关闭验收门禁。

## 2026-08-25 Android 设备前置验收复核

- `[x]` `172.16.102.15:5555` 通过 ADB 命令、`get-state`、shell、设备属性、包管理和 logcat 检查；另一台 `172.16.102.214:5555` 也处于 `device`，当前共 2 台在线设备。
- `[x]` Windows Android Worker 正在运行，队列为 `android,mobile_special`；doctor 对 Python/Celery/Redis、PostgreSQL、Redis、MinIO 和 ADB 检查通过。
- `[E]` 两台在线设备的第三方包列表均未发现 Karing，不能用应用显示名替代真实 `package_name`，也没有执行启动、点击、Monkey 或其他应用操作。
- `[E]` 控制面 smoke 因 `.env` 中的 bootstrap 账号收到 HTTP 401，未能认证调用 `/devices/workers` 和 `/devices/scan`；未创建 Android 运行记录。证据见 [`android-device-control-preflight-2026-08-25.json`](docs/evidence/android-device-control-preflight-2026-08-25.json)。
- `[ ]` 解除条件：安装/提供 Karing APK 并取得真实 `package_name`，完成 Karing 低代码、专项任务、异常日志/录屏回放和报告下载验收；通用 APK 的资产上传门禁已由 [`android-apk-upload-2026-08-25.json`](docs/evidence/android-apk-upload-2026-08-25.json) 关闭。

## 2026-08-25 P0-B.3 后续开发计划（当前跟踪）

详细计划以路线图的“0.5 当前开发计划与跟踪台账”为准。本节同步当前执行顺序，避免把已经存在的页面或执行器误记成真实闭环：

- [~] P0-B.3.1 APK 资产与包名：选择传递、项目隔离、运行快照、真实 APK 上传、标准 Manifest 包名/版本识别、对象绑定和清理已通过；APK 下载端点和 Karing 包仍待验证。证据见 [`android-apk-upload-2026-08-25.json`](docs/evidence/android-apk-upload-2026-08-25.json)。
- [E] P0-B.3.2 Android 低代码最小执行：单设备租约、Worker 调度、步骤执行、截图、APK 前置安装和终态回传已完成本地实现与回归；真实 APK/真机最小步骤待验收。证据见 [`android-lowcode-execution-2026-08-25.json`](docs/evidence/android-lowcode-execution-2026-08-25.json)。
- [E] P0-B.3.3 录屏与异常回放：低代码/专项录屏失败状态、回放保存状态和报告告警已补齐并完成本地回归；真实设备采集、上传、异常保留和清理待验证。证据见 [`android-recording-observability-2026-08-25.json`](docs/evidence/android-recording-observability-2026-08-25.json)。
- [E] P0-B.3.4 Android 专项任务：已完成包名一致性校验、应用启动失败终态、Monkey 异常终态和流畅度动作失败终态的本地实现与回归；真实 APK/真机上的安装、启动、动作、超时、取消、崩溃和 logcat 仍待验收，不能用应用显示名替代包名。证据见 [`android-special-task-2026-08-25.json`](docs/evidence/android-special-task-2026-08-25.json)。
- [E] P0-B.3.5 事件、日志与报告：Worker 收尾阶段支持按配置保存最近 10000 行设备 logcat 与结束截图，写入 `MobileRunArtifact` 并在 `summary_json.android_artifacts` 返回状态；事件参数、结果、消息和 JSON 报告配置统一脱敏，运行详情展示产物状态、操作时间线和下载引用。真实 APK/真机/MinIO 媒体回传仍待验收。证据见 [`android-event-artifact-reporting-2026-08-25.json`](docs/evidence/android-event-artifact-reporting-2026-08-25.json)。
- [x] P0-A 完整 Windows API/Web 复核：当前账号登录、认证读接口、浏览器矩阵、文件传输、报告导出和 Web 低代码均通过；12 个 Playwright 用例通过，临时项目和产物已清理。脱敏证据见 [`docs/evidence/windows-full-readiness-2026-08-25.json`](docs/evidence/windows-full-readiness-2026-08-25.json)。
- [ ] P1-C/P1-D/P1-E/P1-F：按真实通知、外部缺陷平台、性能生产环境、发布收口顺序推进。

每个子模块都必须完成“实现/调整 → 定向测试 → 全量质量门禁 → 代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送”后才能进入下一项；真实环境未提供时保留 `[E]` 或 `[~]`，不把 mock、跳过项、Worker 心跳或 offline 设备写成通过。

### 2026-08-25 P0-B.3.1 APK 包名一致性保护

- [x] Manifest 能解析出包名时，以 Manifest 包名作为唯一可信值；手工填写的非空包名与 Manifest 不一致时在 MinIO 上传和数据库写入前返回 `400`。
- [x] 手工包名支持空白归一化；Manifest 无法解析包名时仍兼容手工填写，保持已有上传兼容性。
- [x] APK/API 与发布契约定向 `22 passed`，完整后端非集成 `2284 passed`，Ruff 和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- [E] 本项只关闭本地包名身份一致性风险，不代表真实 Karing APK、下载端点、专项任务和完整报告已验收。

### 2026-08-25 P0-B.3 Android 设备目标校验

- [x] Android 专项任务创建、更新和手工触发统一校验 `device_id` 对应设备仍存在；不存在或已下线时提前返回 `400`，不创建脏任务、运行记录或投递 Worker。
- [x] 新增创建、更新、触发三条入口的回归；专项任务路由定向 `32 passed`，后端非集成全量 `2287 passed`，Ruff 和 `git diff --check` 通过；独立代码审查未发现可操作问题。
- [E] 设备是全局资产，本项只校验目标存在性，不替代真实在线状态、租约、ADB 操作和 Karing 应用闭环验收。

### 2026-08-25 P0-B.3.5 事件、日志与报告回传本地交付

- [x] 新增 Android 专项 Worker 公共收尾采集：按任务配置保存设备结束时的 logcat（最多 10000 行、5 MB）和 PNG 截图（最多 10 MB），上传 MinIO 后写入 `MobileRunArtifact`；ADB、截图、上传失败只进入 `summary_json.android_artifacts` 和事件时间线的告警，不覆盖原始运行状态。
- [x] 新建/编辑专项任务增加“保存设备日志”和“保存结束截图”开关；报告详情增加设备产物状态卡片，报告文件表继续提供统一下载入口，已有性能专项异常回放/录屏产物保持兼容。
- [x] `MobileRunEventRecorder` 对参数、结果和消息递归遮盖 Authorization、Cookie、密码、Token、Secret、API Key 等常见敏感字段，并遮盖 URL 查询凭据；JSON 报告导出对运行摘要和配置快照复用同一脱敏逻辑。
- [x] 代码审查修复事件达到上限时摘要/产物未提交的边界，并补充事件脱敏、ADB 缺失/上传失败隔离、报告导出脱敏和产物入库回归；定向 84 项、后端非集成 `2260 passed`，前端 `66 files / 269 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。证据见 [`android-event-artifact-reporting-2026-08-25.json`](docs/evidence/android-event-artifact-reporting-2026-08-25.json)。
- [ ] 真实环境仍需用在线 `device`、真实 APK 和可用 MinIO 验证三类专项的结束日志/截图、性能录屏/异常回放、报告下载和对象清理；本地回归不关闭 Android 真机发布门禁。

## 2026-08-25 参考导航后续执行台账

本轮按照参考导航的五组结构继续推进：工作台、测试能力、测试资产、智能中枢、系统。导航入口和本地工作台已完成，不把入口存在误记为真实环境闭环；详细交付矩阵见 [`docs/product-navigation-roadmap-2026-08-24.md`](docs/product-navigation-roadmap-2026-08-24.md) 的“0.5 当前开发计划与跟踪台账”。

- [x] A1 工作台/任务中心：本地项目筛选、待办聚合、轮询、重试、终止、批量操作、失败事件和权限边界已实现；真实账号链路仍需复核。
- [E] A2 接口测试：本地环境变量、认证复用、OpenAPI/Postman 导入解析与预览/落库、HTTP/GraphQL/WebSocket/gRPC 工作台和执行结果入口已实现；q19 已形成 HTTP/会话复用/gRPC TLS/导入解析/导入落库证据，其他协议和完整报告仍待验收。
- [~] A3 APP 自动化：ADB 基础检查、Redis 配对、Worker registry、扫描回调、租约绑定控制、APK 资产选择/包名传递，以及专项任务失败终态本地闭环已通过；下一步验证真实 APK 上传包名识别、低代码真实运行、录屏、专项任务和结果回传。
- [x] A4 UI 自动化：录制、元素库、页面对象、视觉基线、Trace/HAR/Console/网络日志和多浏览器本地/q19 链路已有证据；目标环境仍需按发布版本复核。
- [~] A5 性能测试：P1-E.1～P1-E.4 本地 API、前端、容量和保留清理已完成；真实 Kubernetes 多节点、Prometheus/MinIO 生命周期和跨主机恢复未验收。
- [x] A6 AI/Hermes、A7 测试资产/智能中枢、A8 远程工具箱/配置中心：本地实现、权限、审查和回归已完成；真实模型、项目数据、外部缺陷平台和目标部署仍待验收。
- [ ] 每个台账项均须执行“实现/调整 → 定向测试 → 全量质量门禁 → 代码审查 → 修复 → 文档与记忆同步 → Conventional Commit 推送”；在当前 A3 未解除前，不开始把真实外部集成写成通过。

### 当前推荐开发顺序

1. 完成单设备 Android 真实 APK 上传包名识别与选择、低代码真实运行、录屏、专项任务和结果回传，每个阶段记录执行事件。
2. 保持受控队列和单 Worker，执行失败时保留事件、日志、媒体和报告证据。
3. 复核 Windows API/Web 完整 smoke，再依次验收真实通知供应商、外部缺陷平台和生产性能环境。
4. 汇总同一提交 SHA 的证据，更新能力矩阵、发布状态、用户手册和记忆文档后再做发布收口。

## 2026-08-25 P0-A Windows 本地 E2E 回归修复

- [x] 修复 Playwright 共享登录 fixture 对 Ant Design Vue 中文按钮自动空格的兼容，支持“登录”实际渲染为“登 录”以及英文 `Sign in`。
- [x] 补齐主布局侧栏徽标所需的 `/workbench/overview` mock，避免未拦截的真实 401 清理会话并把登录后的页面重定向回 `/login`。
- [x] 补齐运行详情加载内部缺陷关联所需的 `/defects` mock，避免运行详情回归受未拦截 401 干扰。
- [x] 代码审查确认改动仅限 E2E 测试隔离，不改变生产认证、路由或执行逻辑；登录定向 `3 passed`，运行详情定向 `1 passed`，全量 Playwright `12 passed`。
- [x] 前端 Vitest `66 files / 265 tests passed`，`vue-tsc --noEmit`、生产构建和 `git diff --check` 通过。
- [E] Windows 真实 API/Web smoke 仍需使用当前有效账号复跑；本轮 401 只说明账号未被接受，不能使用 `FIRST_ADMIN_*` 代替当前账号，也未将认证读接口、文件传输和报告导出记为通过。

## 2026-08-25 P0-A Windows 已认证浏览器冒烟复核

- [x] 复用当前有效登录会话完成统计看板、工作台概览、我的待办、用例管理、执行记录、测试套件、存储管理和 API 契约资产页面加载；均未回到登录页，q19 Backend 最近 5 分钟无 enum/Traceback/ERROR。
- [E] 证据见 [`docs/evidence/windows-browser-smoke-2026-08-25.json`](docs/evidence/windows-browser-smoke-2026-08-25.json)。本轮只覆盖已认证页面链路，文件传输、报告导出、浏览器矩阵和 Web 低代码不重复替代既有完整 readiness；P0-A 仍保持“已实现，待完整目标环境复验”。

## 2026-08-25 P0-B Android 单设备验收前置复核

- [x] 执行 `scripts/windows-android-acceptance.ps1`，确认 `adb.exe` 可用且 ADB 命令正常响应。
- [x] 验收脚本正确识别当前状态为 `online=0, unauthorized=0, offline=1, other=0`，输出重连/`adb reconnect` 提示，并生成脱敏本地报告 `.local-run/android-acceptance-current-20260825.json`。
- [x] 代码审查确认离线设备只触发必需检查失败，不继续执行设备命令、包管理、日志读取或创建 Android 运行任务；没有把本次失败写成设备执行通过。
- [E] P0-B 仍需将 ADB 恢复为 `device` 后继续配置配对、Worker 心跳、扫描、预约、截图、APK 包名、Android 低代码、专项任务和结果证据验收。

## 2026-08-25 P0-B Android 配对与扫描回调验收完成

- [x] 通过 ADB mDNS 发现在线目标，并对 `172.16.102.15:5555` 完成设备授权、命令执行、属性、包管理和 logcat 基础检查；本次基础验收通过。
- [x] 通过临时 SSH 隧道和配对配置，让 Windows Agent 与 q19 Backend 共用 Redis 实例、DB、认证、队列和注册前缀；配置校验、Worker doctor 和 `/devices/workers` registry 查询通过，在线 Worker 为 `android-win-HPS`。
- [x] 修复 `scan_adb_devices` 的 `ignore_result=True`，使 API 能按 `scan_id` 读取 Worker 的 `completed` 结果；新增 Celery 任务契约回归。
- [x] 重启受控 Worker、清理历史心跳链并重跑 smoke；Worker registry 在线，扫描返回 2 台设备，队列扫描后为 0。脱敏证据见 [`android-worker-scan-2026-08-25.json`](docs/evidence/android-worker-scan-2026-08-25.json)。
- [x] 完成租约绑定控制门禁：点击/滑动必须携带 `X-Device-Lease-Token`；Android 低代码抽屉自动申请、续租并在切换/关闭时释放租约。定向后端 `43 passed`、前端抽屉 `3 passed`、类型检查/Ruff 通过。
- [x] 真实设备链路通过：租约申请、29,099 bytes 截图、UI 属性响应、点击/滑动 `200`、无租约点击 `409`、释放 `204`；脱敏证据见 [`android-control-lease-2026-08-25.json`](docs/evidence/android-control-lease-2026-08-25.json)。
- [x] APP 自动化工作台选择 APK 后，运行请求会传递 `apk_id`；后端校验 APK 属于当前项目，并将 APK ID、包名写入运行记录和配置快照；定向后端 `53 passed`、前端工作台 `3 passed`、类型检查/Ruff/diff-check 通过。
- [x] APK 选择跨项目请求被拒绝，脱敏证据见 [`android-apk-selection-2026-08-25.json`](docs/evidence/android-apk-selection-2026-08-25.json)。
- [ ] 解除条件：继续真实 APK 上传包名识别、Android 低代码真实运行、录屏、专项任务和结果回传；未完成前不把 Android 单设备闭环标记为完成。
- [ ] 当前目标设备未确认存在用户指定的 Karing 包名；执行 Karing 专项任务前必须重新用 `pm list packages` 确认，不以应用显示名代替包名。

## 2026-08-25 Android 录屏证据展示补齐

- [x] 运行详情页从 `result_summary.android_artifacts.screen_recording` 读取 Android 录屏，同时保留 Web/接口既有的 `video_url` 优先路径。
- [x] Android 录屏不可用时展示 `screen_recording_error`，避免任务已经执行但页面没有任何可解释反馈。
- [x] HTML 报告在开启录像选项时嵌入 Android 录屏；PDF 既有不嵌入视频的行为保持不变。
- [x] WebSocket 收到运行完成事件后重新读取运行详情，确保执行页面无需手动刷新即可看到刚上传的 Android 录屏和告警。
- [x] 代码审查后补充回归：后端导出 `13 passed`，RunDetail `6 passed`，前端全量 `66 files / 268 tests passed`，type-check、生产构建、Ruff 和 diff-check 通过；提交 `279b254` 已完成本地提交。
- [x] q19 已从 `origin/main` 的 `257c479` 独立工作树重建并启动；迁移 `20260824_0065 (head)`、健康 `200`、Prometheus 4 个 target `up`、Celery 2 节点响应、后端最近 3 分钟错误匹配数为 0。证据见 [`q19-android-recording-deployment-2026-08-25.json`](docs/evidence/q19-android-recording-deployment-2026-08-25.json)。
- [E] 本轮只验证结果展示与报告链路，未使用真实 Android 设备生成录屏；当前 ADB 仍为 `offline`，P0-B 单设备执行证据继续保持未验收。

## 2026-08-25 P1-D 外部缺陷平台错误安全收口

- [x] 新增统一 `safe_external_error`，对供应商异常中的字段密钥、查询参数密钥和 URL 用户信息脱敏并限制返回长度。
- [x] 连接测试、创建缺陷、刷新缺陷状态三个入口不再把供应商原始异常直接返回；创建/状态刷新统一返回 502，连接测试保留 `ok=false` 结构。
- [x] 修复 `bug_trackers.py` 中查询结果变量被创建结果覆盖的 mypy 类型问题，避免外部缺陷入口继续携带基线类型错误。
- [x] 代码审查后回归：外部缺陷定向 `40 passed`，完整后端非集成 `2234 passed`，Ruff、格式、mypy 和 diff-check 通过；提交 `31df065` 已完成本地提交。
- [E] 未连接真实 Jira、禅道、GitHub Issues 或 GitLab Issues 项目；真实创建、去重、状态同步、权限和清理仍需临时项目与凭据。证据见 [`external-tracker-error-safety-2026-08-25.json`](docs/evidence/external-tracker-error-safety-2026-08-25.json)。

## 2026-08-25 P1-D q19 运行态部署

- [x] q19 已从 `origin/main` 的 `cec8eaf` 独立工作树重建，显式复用 `atp-q19-acceptance-20260824` Compose 项目名，未删除数据库、Redis 或 MinIO 卷。
- [x] 远端验证：迁移 `20260824_0065 (head)`、Backend 健康 `200`、Redis `PONG`、Prometheus `ready` 且 `4` 个 target 为 `up`；通用 Worker、性能 Worker、Beat、Web Recorder 共 `4` 个容器运行，最近 3 分钟 Backend/Worker 错误匹配数为 `0`。
- [E] q19 只证明最新代码在 Compose 验收环境可启动；未连接真实 Jira、禅道、GitHub Issues 或 GitLab Issues，也不替代 Kubernetes 多节点、生产外部平台和 Android 真机验收。证据见 [`q19-external-tracker-deployment-2026-08-25.json`](docs/evidence/q19-external-tracker-deployment-2026-08-25.json)。

## 2026-08-25 P1-C 通知验收脚本错误脱敏修复

- [x] 修复 `notification-channel-acceptance.py` 异常分支只截断问号后内容的问题，改为复用通知服务统一脱敏函数，避免 Token、密码和 URL 用户信息进入终端或 JSON 报告。
- [x] 代码审查发现并修复全量套件中的模块桩污染：新增测试独立加载真实通知服务模块，不依赖其他测试对 `sys.modules` 的修改。
- [x] 通知定向 `12 passed`，完整后端非集成 `2236 passed`，改动文件 Ruff/格式检查和 `git diff --check` 通过；提交 `9852387` 已完成本地提交。
- [E] 未触达真实 SMTP、企业微信或钉钉供应商；真实投递、供应商侧送达、限流和重复投递仍需临时目标与凭据。证据见 [`notification-acceptance-redaction-2026-08-25.json`](docs/evidence/notification-acceptance-redaction-2026-08-25.json)。
- [x] 追加修复 `notification-channel-smoke.py` 的 `access_token`、`sign` 和 URL 用户信息脱敏边界，提交 `8fd129b`；通知脚本定向 `12 passed`、完整后端非集成 `2236 passed`，证据见 [`notification-smoke-redaction-2026-08-25.json`](docs/evidence/notification-smoke-redaction-2026-08-25.json)。

## 2026-08-25 工作台任务状态枚举隔离修复

- [x] 根据 q19 工作台日志定位到跨域状态集合问题：普通 `TestRun` 查询被错误带入 Android `stopped` 和性能 `cancelled`，PostgreSQL 会在 `/workbench/overview` 返回 `invalid input value for enum runstatus`。
- [x] 按 case/suite/plan/android/performance 分别限制状态过滤值；空交集使用始终不匹配条件，避免不支持的状态退化为查询全部；重试能力继续使用各域既有策略并保留 case `skipped` 重试。
- [x] 代码审查确认未修改执行器、权限和数据库结构；工作台定向 `8 passed`，Ruff、差异检查和完整后端非集成回归 `2229 passed` 通过。
- [x] q19 已在独立工作树按 `36cacb9` 受控重建；迁移为 `20260824_0065`，Backend 健康 `200`，Prometheus 4 个 target 为 `up`，2 个 Celery 节点在线，重启后日志未再出现 enum 错误。脱敏证据见 [`q19-workbench-status-filter-2026-08-25.json`](docs/evidence/q19-workbench-status-filter-2026-08-25.json)。
- [E] 真实项目数据下的鉴权工作台请求仍需当前有效账号；本次只验证未认证边界 `401`，不把无凭据状态写成完整聚合通过。

## 2026-08-24 产品导航与能力扩展路线（持续跟踪）

开发计划和单模块交付规则已记录在 [`docs/product-navigation-roadmap-2026-08-24.md`](docs/product-navigation-roadmap-2026-08-24.md)，本节只维护阶段状态；导航已按参考方案固定为五组，N0 导航壳、N1 工作台与任务中心、N2.1/N2.2/N2.3/N2.4/N2.5、N3.1 API、N3.2 APP、N3.3 UI、N3.4 性能、N4.1 AI 智能测试工作台、N4.2 Hermes 助手、N4.3 需求与用例追踪、N4.4 知识中枢、N5.1 远程工具箱和 N5.2.1～N5.2.6 配置中心本地实现、审查和回归已完成，均待真实环境验收；N6.3/N6.4/N6.5/N6.6/N6.7/N6.8/N6.9/N6.10/N6.11/N6.12/N6.13 已补充远端依赖、完整 Windows API/Web readiness、q19 真实迁移、持久通用 Web Worker、独立录制 Worker、Chromium/Firefox/WebKit 证据链、跨 API 副本一致性、真实性能节点执行、通知本地链路、Android Backend/Agent 配置一致性门禁和全量质量门禁复核，Android、通知供应商和外部平台仍待独立验收。

- [x] 完成现状盘点：确认现有导航与图片目标存在结构差异，已有能力主要分散在测试设计、测试资产、执行中心、Android 专项和平台配置菜单。
- [x] 建立目标导航：工作台、测试能力、测试资产、智能中枢、系统。
- [x] 同步 `MEMORY.md`，记录本路线的范围、优先级和当前未实现边界。
- [E] N0 导航壳与信息架构：五层分组、路由注册、项目上下文基础、权限、占位入口、统一面包屑和旧 URL 兼容已完成本地实现与回归；动态徽标由 N1 工作台聚合承接。
- [E] N0 导航收口验证：新增 `frontend/src/layouts/navigation.ts` 统一路由分组、标题、面包屑和深层选中状态；导航定向 `6 passed`，前端全量 `66 files / 262 tests passed`，type-check 通过；不改变后端执行逻辑和权限边界。
- [E] N0 侧栏精简：测试能力仅展示 API/APP/UI/性能/AI，测试资产仅展示用例/计划/缺陷/报告/评审，系统仅展示远程工具箱/配置中心；旧资产页面映射到所属工作台，管理员治理页面由配置中心快捷区承接。新增配置中心治理入口回归，前端全量 `66 files / 263 tests passed`，type-check/build 通过。
- [E] N1 工作台与任务中心：聚合 API、统一任务结构、待办/任务中心页面、项目筛选、重试/终止/批量操作、轮询和动态徽标已完成本地实现与审查；待真实环境验收。
- [E] N2 测试资产闭环：N2.1 内部缺陷、N2.2 失败证据、N2.3 报告中心、N2.4 用例评审、N2.5 外部缺陷兼容均已完成本地实现、审查和回归；待真实环境验收。
- [E] N3.1 API 测试工作台：接口协议筛选、模块目录、导入/AI 生成、详情、环境选择执行和运行结果入口已完成；复用现有接口执行器与 API，待真实数据/权限/执行环境验收。
- [E] N3.2 APP 自动化工作台：设备池、Worker 状态、设备预约/心跳/释放、截图预览、Android 用例与专项任务执行、APK 选择、最近运行和兼容性概览已完成；待 Windows Worker/ADB、真实设备和报告链路验收。
- [E] N3.3 UI 自动化工作台：项目/模块工作区、Web 用例目录与详情、Playwright 录制创建、元素库/页面对象/视觉基线快捷入口、基线采集、运行观察和 Trace 状态已完成；q19 通用 Web 低代码执行 Worker 与独立 Playwright 录制 Worker 已完成持久部署，Chromium/Firefox/WebKit 录制、截图、停止、Trace/HAR/Console/网络日志和运行报告链路已验证，跨 API 副本可读取共享 Redis 停止快照。
- [E] N3.4 性能测试工作台：性能场景、环境/节点发起、实时运行队列、吞吐/延迟/错误率、资源采样时间线、门禁、基线、趋势和报告导出已完成；q19 已验证专用性能 Worker、四类执行器、Prometheus 采样和一次真实 k6 运行，逐节点分片容量校验已补齐，真实多节点调度和生产报告治理仍待环境验收。
- [x] P1-E.1 性能长期趋势：新增固定 7/30/90 天服务端趋势、空日期、分片父运行去重、摘要指标聚合和双前端入口；本地回归与审查已完成，真实多节点容量、节点资源限制和生产留存仍待环境验收。
- [E] N3 测试能力工作台：API、APP、UI 和性能统一配置/执行/观察入口已完成本地实现和审查；待真实 Worker、节点、协议服务、浏览器和性能环境验收。
- [E] N4 智能中枢：N4.1 AI 智能测试工作台、N4.2 Hermes 助手、N4.3 需求与用例追踪和 N4.4 知识中枢已完成本地实现、审查和回归，全部待真实环境验收。
- [E] N4.1 AI 智能测试工作台：统一项目模型门禁、AI 用例/数据集/Mock 生成入口、自动化覆盖缺口、失败热点、诊断入口和自愈反馈；待真实模型、权限和调用审计验收。
- [E] N4.2 Hermes 助手：按项目查询失败任务、调用既有运行诊断、生成可编辑测试计划草稿、汇总质量指标；结论保留任务/报告/统计来源，待真实项目数据、模型诊断和权限验收。
- [E] N4.3 需求与用例追踪：需求解析草稿、验收标准版本化、项目级需求 CRUD、需求负责人项目成员校验、需求—用例关联、验收覆盖率和影响候选分析已完成；待真实需求数据、项目角色和用例联动验收。
- [E] N4.4 知识中枢：新增带项目边界的知识条目、来源/状态筛选、统一搜索结果、来源引用、项目权限、全局发布可见性和敏感信息脱敏；聚合需求、缺陷和失败运行作为只读知识来源，待真实数据、权限和生产迁移验收。
- [E] N5.1 远程工具箱：基础设施、Android/ADB、Web Worker 和性能节点统一诊断，支持脱敏 JSON 导出与处理入口；待真实环境验收。
- [E] N5.2 配置中心：N5.2.1～N5.2.6（只读聚合、版本快照与审计、差异与影响提示、单资源回滚、前端统一工作台、质量收口）已完成本地实现、审查和回归；待真实环境验收。
- [~] N6 质量收口：回归、E2E、迁移、文档、外部环境证据和发布检查；N6.1/N6.2 已完成本地回归与文档收口，N6.3/N6.4 已完成远端依赖恢复和完整 Windows API/Web readiness，N6.5 已完成 q19 `0059 -> 0065` 真实迁移和项目删除回归，N6.6 已完成持久通用 Web Worker 的队列隔离、低代码执行和重启恢复，N6.7 已完成独立 Web 录制 Worker 的 q19 持久部署、Chromium 录制、截图、停止和重启恢复，N6.8 已完成 Chromium 证据链，N6.9 已完成 Firefox/WebKit 录制与跨 API 副本停止快照读取，N6.10 已完成 q19 性能节点、Prometheus 和真实 k6 短压证据，N6.11 已完成通知生产入口的本地 SMTP 链路验收，N6.12 已完成 Android Backend/Agent 配置一致性门禁；Android Worker/真机、真实通知供应商和外部平台证据仍待补齐。
- [x] N6.13 全量质量门禁复核：后端非集成测试 `2215 passed`，前端 type-check/生产构建、差异检查、工作区清洁和远端同步均通过；不替代 Android 真机、真实通知供应商和外部缺陷平台的独立验收。

当前推荐下一步：P1-F 的本地发布状态索引已建立，接下来恢复 Android Worker/真机单设备证据，再验收真实通知供应商、外部缺陷平台和生产性能环境；真实环境未通过前仍保持“部分实现/待环境验收”。统一索引见 [`docs/release-status-2026-08-25.md`](docs/release-status-2026-08-25.md)，每个子模块完成后先审查和修复，再同步文档并提交推送。

## 2026-08-25 P1-E.1 性能长期趋势本地交付

- [x] 新增项目级性能趋势 API，支持 1～365 天固定 UTC 日窗口、空日期补齐、项目权限和按性能场景筛选。
- [x] 趋势聚合按完成/开始/创建时间归档，分片父运行去重、子运行保留，统计运行状态和摘要平均指标；无效/非有限数值不污染结果。
- [x] `/system/performance` 与 `/performance-workbench` 增加近 7/30/90 天趋势切换、加载/空状态、双语文案和异步响应隔离。
- [x] 代码审查修复项目清空时趋势加载状态残留，并新增回归断言。
- [x] 验证：后端趋势/容量/API 定向 `79 passed`，完整非集成后端 `2220 passed`；前端趋势定向 `15 passed`、全量 `66 files / 265 tests passed`，type-check/build、Ruff、格式检查和 diff-check 通过。
- [x] P1-E.2 已补齐可选基线门禁：`require_baseline`、`fail_on_baseline_regression`、CLI 参数和 Webhook 透传；默认阈值门禁兼容，运行失败/取消状态优先；定向 `88 passed`，完整非集成后端 `2224 passed`。
- [x] P1-E.3 已将终态 PerformanceRun 根运行、分片报告和资源采样纳入运行记录保留清理；管理页展示压测执行数，兼容旧响应缺省值；清理/API 定向 `24 passed`，完整非集成后端 `2226 passed`，3 个受影响测试文件独立运行 `3 passed, 0 failed`，前端全量 `66 files / 265 tests passed`。
- [ ] 后续：真实 Kubernetes 多节点调度、节点资源限制、生产 MinIO 生命周期和跨主机恢复环境验收。

## 2026-08-25 P1-E.4 性能多节点分片容量校验

- [x] 先按节点数拆分总负载，再按每个节点的 `max_vus`、执行器和出口 allowlist 校验；总 VU 10 在两台上限 6 的节点上按 5/5 通过，上限 4 时返回 400 且不创建运行。
- [x] 代码审查、性能 API `72 passed`、性能服务/Worker `24 passed`、完整非集成后端 `2231 passed`、Ruff/diff-check 已通过，证据见 [`docs/evidence/performance-shard-capacity-2026-08-25.json`](docs/evidence/performance-shard-capacity-2026-08-25.json)。提交 `f9e7c54` 已推送。
- [x] q19 已重建到 `ca79937`；迁移 `20260824_0065 (head)`、Backend 健康 `200`、Prometheus 4 个 target、Celery 2 节点均通过，重启后 Backend 无 enum/Traceback/ERROR；证据见 [`docs/evidence/q19-performance-shard-deployment-2026-08-25.json`](docs/evidence/q19-performance-shard-deployment-2026-08-25.json)。
- [ ] 后续：真实 Kubernetes 多节点调度、节点资源限制、生产 MinIO 生命周期和跨主机恢复环境验收。

## 2026-08-25 P1-E.2 性能基线回归门禁本地交付

- [x] 性能运行门禁和 CI Webhook 支持 `require_baseline=true`，无可用成功基线时返回 `not_configured`。
- [x] 支持 `fail_on_baseline_regression=true`，对 RPS、P95、P99、错误率按业务方向判断回归；仅对成功运行覆盖门禁，不覆盖运行本身失败/取消状态。
- [x] `scripts/performance-gate.py` 新增 `--require-baseline`、`--fail-on-baseline-regression`，默认 URL 不带策略参数，保持旧 CI 调用兼容。
- [x] 代码审查修复 FastAPI 查询默认值与直接函数单测不一致的问题，并补齐无基线、回归、失败运行和 CLI URL 回归。
- [x] 验证：性能报告/API/Webhook/CLI 定向 `88 passed`，完整非集成后端 `2224 passed`，Ruff/格式检查通过。
- [ ] 后续：真实多节点/容量、节点资源限制、生产 MinIO 生命周期、跨主机恢复和外部性能环境验收。

## 2026-08-25 P1-E.3 性能报告与运行记录保留清理本地交付

- [x] 保留预览/执行新增 `performance_runs` 统计，仅清理终态 PerformanceRun 根运行；未完成运行不会被误删。
- [x] 根运行清理覆盖直接分片和 `performance_metric_samples` 的数据库级级联，执行前收集根/分片 MinIO 原始报告，提交成功后再删除对象。
- [x] 管理页与中英文文案增加压测执行数；前端对旧后端缺失字段按 0 处理，避免清理确认数量出现 `NaN`。
- [x] 代码审查补充性能根运行筛选、分片报告去重和旧响应兼容回归；定向 `24 passed`，完整非集成后端 `2226 passed`，3 个受影响测试文件独立运行 `3 passed, 0 failed`，前端全量 `66 files / 265 tests passed`，type-check/build/Ruff/diff-check 通过。
- [ ] 后续：真实 MinIO 生命周期、生产保留周期、跨主机恢复以及 Kubernetes 多节点验收。

## 2026-08-25 P1-F 本地发布收口

- [x] 新增 [`docs/release-status-2026-08-25.md`](docs/release-status-2026-08-25.md)，集中维护能力域、证据链接、真实环境边界、复验顺序和发布禁止事项。
- [x] 同步能力矩阵、Q18 最新状态、Q18 实施日志、`Task.md`、路线图、`MEMORY.md` 和 Release-Readiness Runbook，统一标注 P1-E.1/P1-E.2/P1-E.3 的本地完成状态。
- [x] 增加发布状态文档契约回归，确保 Android 无在线 Worker、通知 `local_link_only`、外部缺陷平台和生产性能门禁不会被文档误标为通过。
- [ ] 后续：恢复 ADB 为 `device` 后完成 Android 单设备验收；取得临时供应商/外部平台目标和生产性能环境后，补齐带日期证据，再进行最终发布收口。

## 2026-08-24 参考导航执行跟踪版

主计划见 [`docs/product-navigation-roadmap-2026-08-24.md`](docs/product-navigation-roadmap-2026-08-24.md) 的“0.4 参考导航下一阶段开发计划（当前跟踪版）”。后续按“工作台 → 测试能力 → 测试资产 → 智能中枢 → 系统 → 质量发布”跟踪，不因为菜单已显示就把真实能力标记为完成：

- [E] **工作台**：首页、我的待办、项目中心、任务中心已完成本地聚合和操作闭环；待真实项目角色、任务数据和执行器验收。
- [E] **测试能力**：API、APP、UI、性能、AI 工作台已完成统一入口；待 API/协议服务、Windows Android Worker/真机、浏览器/性能节点和真实模型验收。
- [E] **测试资产**：用例、计划、缺陷、报告、评审已完成本地关联和审计闭环；待真实运行证据、项目数据和外部缺陷平台验收。
- [E] **智能中枢**：Hermes、需求与用例、知识中枢已完成项目边界、来源和脱敏处理；待真实模型、需求/知识数据和调用审计验收。
- [E] **系统**：远程工具箱和配置中心已完成诊断、版本、差异、审计、回滚和权限门禁；待真实数据库、生产密钥和部署配置验收。
- [~] **质量发布**：Windows API/Web 可用性和 q19 Web/性能证据已形成；Android ADB 基础检查、Redis 配对、Worker registry 和扫描回调已通过，但单设备执行闭环仍待验收，真实通知供应商和外部缺陷平台尚未验收，真实性能多节点/容量和生产报告治理仍需环境验收。

当前开发入口固定为：**P0-B.3 Android 单设备闭环 → P0-A Windows 完整复核 → P1-C/P1-D 外部联调 → P1-E 性能增强 → P1-F 发布收口**。如果外部环境不可用，继续完成不依赖外部凭据的代码、测试和文档，但不得伪造环境通过。

## 2026-08-24 当前开发计划总表

详细计划和验收边界见 [`docs/product-navigation-roadmap-2026-08-24.md`](docs/product-navigation-roadmap-2026-08-24.md) 的“当前执行总表”。本表用于日常勾选，避免把本地代码完成误认为真实环境通过：

- [E] **P0-A Windows API/Web 可用性复核**：已改善 `windows-local-smoke.ps1` 在管理员登录返回 401/403/其他 HTTP 状态时的安全诊断，补充当前账号环境变量用法；Windows smoke 契约 `11 passed`、PowerShell 解析通过。仍需使用当前有效账号重跑登录、认证读接口、Playwright、浏览器矩阵、文件传输和报告导出，不在仓库记录凭据。
- [~] **P0-B Android Worker 单设备验收**：ADB 已通过在线目标的授权、命令、属性、包管理和 logcat 基础检查；但 Windows Worker 写入的 Redis 与 q19 Backend 使用的 Redis 不一致，`/devices/workers` 尚未看到在线 Worker。需先完成实例/DB/注册前缀配对，再依次验证扫描、预约、截图、控件属性、APK 包名、Android 低代码、专项任务和结果证据。
- [E] **P1-C 真实通知供应商验收**：SMTP/企业微信/钉钉临时目标的投递、重试、历史记录和脱敏；本地 SMTP sink 只能作为前置链路证据。
- [E] **P1-D 外部缺陷平台验收**：Jira/禅道/GitHub/GitLab 创建、重复识别、状态同步、权限和错误脱敏；临时数据使用后清理。
- [~] **P1-E 性能能力增强**：单节点 q19 k6 短压已有证据；长期趋势、基线门禁和运行记录/报告清理已完成本地实现，继续补多节点容量、资源限制、生产 MinIO 生命周期和跨主机恢复，再进行真实性能环境验收。
- [~] **P1-F 发布收口**：本地能力矩阵、Q18 状态、操作手册入口和发布状态索引已同步；Android 真机、真实通知供应商、外部缺陷平台和生产性能证据仍待补齐，GitHub 分支保护限制继续按发布清单记录。

执行顺序固定为：`P0-A → P0-B → P1-C/P1-D → P1-E → P1-F`。每项均执行“实现/调整 → 测试 → 代码审查 → 修复 → 文档与记忆同步 → 提交推送”。

### 2026-08-24 N6.4 Windows 完整 API/Web 验收与项目删除级联修复计划

目标：在已恢复远端 PostgreSQL/Redis/MinIO 的基础上，补齐 Windows 登录、认证读接口、Playwright、浏览器矩阵、文件传输和报告导出证据；同时修复验收夹具清理暴露的项目删除外键阻断，保证项目资源和环境变量按边界清理。

- [x] 执行 Windows 完整 smoke，覆盖管理员登录、认证读接口、Playwright `12 passed`、Chromium/Firefox/WebKit 矩阵、47 bytes 文件上传/清理和 HTML/JUnit 报告导出；脱敏证据归档到 `docs/evidence/windows-full-readiness-2026-08-24.json`，必需失败数为 0。
- [x] 审查发现删除项目会被 `environments.project_id` 外键阻断；补齐 APK、环境、模块、计划、套件的项目级 `CASCADE`，环境变量级联删除，计划环境引用改为 `SET NULL`，新增 Alembic `20260824_0065` 和迁移契约回归。
- [x] 通过项目路由、迁移和 Ruff 定向回归；清理远端 q19 临时验收项目及其环境，未保留测试夹具数据。
- [x] 将最新 `main` 部署到 q19，真实执行 `20260814_0059 -> 20260824_0065` 迁移；Backend、PostgreSQL、Redis、MinIO、性能 Worker 和 Beat 健康，Backend `/health` 返回 HTTP 200。
- [x] 通过项目删除 API 回归：临时项目返回 `204`，项目、环境和模块残留均为 `0`；启动临时默认队列 Web Worker 完成低代码下载执行 `run 3`，下载对象和清理均通过，验收后已移除临时 Worker。
- [x] 将通用 Web Worker 固化到 q19 持久部署并完成注册/执行证据；Android Worker/真机、真实性能节点、通知和外部缺陷平台继续独立验收。

### 2026-08-24 N6.5 q19 真实迁移与 Web Worker 临时验收计划

目标：把项目删除级联迁移部署到 q19 目标数据库，验证资源清理不再被外键阻断，并用一次受控的临时默认队列 Worker 补齐 Windows Web 低代码真实执行证据；临时 Worker 不作为持久部署完成标志。

- [x] 从最新 `main` 构建 q19 Backend、性能 Worker、Beat 和迁移镜像。
- [x] 在 q19 执行 Alembic `20260814_0059 -> 20260824_0065`，确认迁移完成后服务健康。
- [x] 创建并删除临时项目，确认 HTTP `204` 且项目、环境、模块没有残留。
- [x] 启动临时默认队列 Worker，完成 Web 低代码下载执行和对象清理；脱敏证据见 [`q19-migration-web-worker-readiness-2026-08-24.json`](docs/evidence/q19-migration-web-worker-readiness-2026-08-24.json) 与 [`windows-web-worker-readiness-2026-08-24.json`](docs/evidence/windows-web-worker-readiness-2026-08-24.json)。
- [x] 验收后移除临时 Web Worker，不改变 q19 既有性能 Worker/Beat 部署。
- [x] 后续模块已将通用 Web Worker 加入持久 Compose/部署编排，完成注册、`default,maintenance` 队列隔离、低代码下载和重启恢复验收；脱敏证据见 [`q19-persistent-web-worker-readiness-2026-08-24.json`](docs/evidence/q19-persistent-web-worker-readiness-2026-08-24.json)、[`windows-persistent-web-worker-readiness-2026-08-24.json`](docs/evidence/windows-persistent-web-worker-readiness-2026-08-24.json) 和 [`windows-persistent-web-worker-restart-readiness-2026-08-24.json`](docs/evidence/windows-persistent-web-worker-restart-readiness-2026-08-24.json)。Android 因 ADB 设备 offline 本轮未执行。

### 2026-08-24 N6.6 q19 持久通用 Web Worker 部署与恢复验收

目标：把此前只用于临时验收的默认队列 Worker 固化到 q19 Compose，和性能 Worker 做队列、资源及监控隔离，并验证低代码执行、Worker 重启恢复和对象清理。

- [x] 在 `docker-compose.performance-acceptance.yml` 新增独立 `worker` 服务，固定监听 `default,maintenance`；性能 Worker 保持 `performance.worker-a,performance`，不与通用 Worker 交叉消费。
- [x] 为通用 Worker 暴露 `9091` 指标并加入 q19 Prometheus target；Backend、通用 Worker、性能 Worker 和 Prometheus targets 均为 `up`。
- [x] 本地部署契约回归 `24 passed`，YAML 和 `git diff --check` 通过；代码审查未发现需要修复的问题。
- [x] q19 使用提交 `f1473d2` 重建并持久启动通用 Worker；Celery ping、队列隔离和服务健康通过。
- [x] Worker 重启后重新注册，Web 低代码 `run 5` 成功并回传 1 个下载对象，临时项目和 5 个证据对象清理通过；首次执行 `run 4` 同样通过。
- [x] 脱敏证据已归档；独立录制 Worker、Android、真实性能节点、通知和外部缺陷平台仍按后续模块验收。

### 2026-08-24 N6.7 q19 独立 Web 录制 Worker 持久部署与真实录制验收

- [x] 在 q19 Compose 新增独立 `web-recorder` 服务，Backend 固定使用 `WEB_RECORDER_MODE=worker`，API 与 Worker 使用同一 Redis 路由前缀；通用 Celery Worker、性能 Worker 和录制 Worker 边界保持分离。
- [x] 录制容器使用 Xvfb `:99`，启动时清理容器内残留 X99 锁并等待 socket 就绪后再启动 Worker；启用 Compose `init: true` 回收 Chromium 子进程，避免重启或多次录制累积僵尸进程。
- [x] 本地录制 API/传输/smoke/部署契约回归 `61 passed`，Ruff 和 `git diff --check` 通过；代码审查发现并修复 Xvfb 重启锁与僵尸进程两个问题。
- [x] q19 使用提交 `dfe86b1` 重建并持久启动录制 Worker；Backend、录制 Worker、通用 Worker、性能 Worker、Prometheus 和依赖服务运行，Backend `/health` 返回 200，Prometheus `atp-backend`、`atp-worker`、`atp-performance-worker` 和自身 targets 均为 `up`。
- [x] 临时 Web 项目真实录制、快照（2 步）、PNG 截图（17,117 bytes）、停止和项目删除通过；录制 Worker 重启后再次完成同一链路，`active_sessions=0` 且容器 `zombie_count=0`。脱敏证据见 [`q19-web-recorder-readiness-2026-08-24.json`](docs/evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recorder-restart-readiness-2026-08-24.json`](docs/evidence/q19-web-recorder-restart-readiness-2026-08-24.json) 和 [`q19-web-recorder-init-readiness-2026-08-24.json`](docs/evidence/q19-web-recorder-init-readiness-2026-08-24.json)。
- [x] Chromium Trace、HAR、Console/网络日志和运行报告已接入 MinIO，停止后 API 保留最终快照并可再次查询；首次部署和重启录制冒烟均通过。脱敏证据见 [`q19-web-recording-evidence-2026-08-24.json`](docs/evidence/q19-web-recording-evidence-2026-08-24.json) 和 [`q19-web-recording-evidence-restart-2026-08-24.json`](docs/evidence/q19-web-recording-evidence-restart-2026-08-24.json)。
- [ ] Firefox/WebKit、跨 API 副本和 Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待后续环境验收。

### 2026-08-24 N6.8 Web 录制证据链交付与 q19 验收

- [x] Playwright 录制会话新增 Trace、HAR、Console、页面异常、请求/失败请求/错误响应事件采集；HAR、步骤、URL、请求头和错误文本在持久化前脱敏，响应体、Cookie 和请求体不落盘。
- [x] 停止录制后将 Trace、HAR 和运行报告上传 MinIO，API 返回可访问的短期 URL；独立 Worker 模式在 Redis 中保留脱敏最终快照，支持停止后查询和重复停止，结束会话不再允许截图。
- [x] 前端录制弹窗显示三类证据入口和最近网络事件；冒烟脚本新增证据 URL 与停止后报告查询检查。
- [x] 代码审查修复 JSON 形式凭据和错误文本完整 URL 的脱敏边界；本地后端目标回归 `45 passed`，前端 Web Recorder `3 passed`、type-check、生产构建、Ruff 和 `git diff --check` 通过。
- [x] q19 使用提交 `9e93379` 重建并重启 `web-recorder`，首次及重启后录制均通过：Worker 注册、2 步快照、PNG 截图、停止、3 类证据、停止后报告查询；测试项目与 6 个录制对象已清理。脱敏证据见 [`q19-web-recording-evidence-2026-08-24.json`](docs/evidence/q19-web-recording-evidence-2026-08-24.json) 和 [`q19-web-recording-evidence-restart-2026-08-24.json`](docs/evidence/q19-web-recording-evidence-restart-2026-08-24.json)。
- [ ] Firefox/WebKit、跨 API 副本以及 Android、真实性能、通知和外部缺陷平台仍不属于本模块验收范围。

### 2026-08-24 N6.9 Firefox/WebKit 与跨 API 副本录制验收

- [x] 代码修复：Linux `WEB_RECORDER_MODE=worker` 下 WebKit 使用无头启动，避免 Xvfb 下 WebKit headed 启动挂起；Windows/local 模式与 Firefox 保持原有 headed 行为。回归新增 Linux Worker WebKit 启动断言。
- [x] 代码审查与回归：后端 Web Recording/传输/smoke/部署目标 `45 passed`，Ruff 和 `git diff --check` 通过；提交 `41ff87a` 已推送。
- [x] q19 使用 `41ff87a` 重建后，Firefox 录制、2 步快照、PNG 截图 `19076` bytes、停止、3 类证据 URL 和停止后查询通过；WebKit 同链路通过，截图 `21192` bytes，Linux Worker 走无头启动路径。证据见 [`q19-web-recording-firefox-2026-08-24.json`](docs/evidence/q19-web-recording-firefox-2026-08-24.json) 和 [`q19-web-recording-webkit-2026-08-24.json`](docs/evidence/q19-web-recording-webkit-2026-08-24.json)。
- [x] 启动临时第二 API 副本：副本 A 停止录制后，副本 B 通过共享 Redis 查询同一会话并返回 `status=stopped`；证据见 [`q19-web-recording-cross-api-2026-08-24.json`](docs/evidence/q19-web-recording-cross-api-2026-08-24.json)。临时项目、18 个录制对象和第二副本均已清理。
- [ ] Android Worker/真机、真实性能节点、通知和外部缺陷平台仍待独立环境验收。

### 2026-08-24 N6.10 q19 性能节点与真实短压验收

- [x] 性能预检通过：Backend `/health` 正常，k6、Locust、gRPC、JMeter 均 ready；专用节点 `worker-a` online，队列为 `performance.worker-a`，节点能力与四类执行器一致。
- [x] 真实低并发 k6 smoke 通过：临时项目执行 1 VU、5 次迭代，目标为 q19 内部 `http-target`，运行状态为 `success`，产生 1 条 `performance-worker` 资源采样。
- [x] Prometheus `/-/ready` 通过，`atp-backend`、`atp-worker`、`atp-performance-worker` 三个 target 均为 `up`；临时项目、测试、运行和脚本对象已清理。脱敏证据见 [`q19-performance-worker-smoke-2026-08-24.json`](docs/evidence/q19-performance-worker-smoke-2026-08-24.json)。
- [ ] Android Worker/真机、通知和外部缺陷平台仍待独立环境验收；当前 Android Worker 虽已注册心跳，但 ADB 设备处于 offline，未创建 Android 运行任务。

### 2026-08-24 N6.11 通知链路本地安全验收

- [x] 通过 `scripts/notification-smtp-link-check.py` 在 `127.0.0.1` 回环 SMTP sink 上调用生产通知入口，SMTP envelope、收件人规范化、MIME、显示名和六项性能摘要字段共 12 项检查通过。
- [x] 报告固定为 `local_link_only`，未触达真实邮箱、未记录凭据；脱敏证据见 [`notification-smtp-link-check-2026-08-24.json`](docs/evidence/notification-smtp-link-check-2026-08-24.json)。
- [ ] 真实 SMTP/企业微信/钉钉仍需管理员提供临时目标、凭据和供应商侧送达证据；该本地链路结果不能关闭外部通知门禁。

### 2026-08-24 N6.12 Android Backend/Agent 配置配对门禁

- [x] 新增 `scripts/validate-android-worker-config.py`，比较 Backend/Windows Agent 的 PostgreSQL、Redis、MinIO、应用密钥/加密密钥，并校验 `ADB_SCAN_MODE`、队列、`ANDROID_WORKER_QUEUE` 和 Redis 注册前缀；输出与 JSON 报告均不包含配置值。
- [x] `windows-android-worker.ps1 doctor` 新增 `-BackendEnvFile`，`startup.ps1` 支持透传；Make、CI、pre-commit 和 deployment readiness 已纳入脚本，两个示例配置的共享密钥占位符已统一。
- [x] 配置/Worker/PowerShell/质量门禁定向回归 `55 passed`，示例 Backend/Agent 配对通过；真实服务连通性和 Android 真机执行仍需单独验收。

### 2026-08-24 N5.2 配置中心开发计划（文档跟踪）

目标：把当前分散的运行配置收敛到一个“配置中心”入口，提供可追踪、可比较、可回退的配置治理能力；不重复实现各配置页面已有的编辑逻辑，不通过浏览器直接重启服务。

- [E] **N5.2.1 配置只读聚合与权限边界**：统一展示启动配置、环境、全局变量、AI 模型、存储策略、通知和性能节点；支持项目筛选、配置域筛选、当前状态和原页面深链接。摘要只返回脱敏字段，启动配置标为运行时只读；管理员/工程师可进入，具体编辑/查看权限沿用现有接口边界。
- [E] **N5.2.2 版本快照与变更审计**：新增配置版本模型和 Alembic 迁移；按单个配置资源保存加密原始快照、脱敏快照、指纹、创建人、原因和时间；写入统一审计日志，禁止把密码、Token、密钥、连接串或原始异常写入响应、日志和文档。
- [E] **N5.2.3 配置差异与影响提示**：支持当前配置与任意历史快照的字段级差异，敏感字段只显示“已变更/未变更”；根据配置域提示影响范围（例如环境变量影响项目执行、AI 配置影响生成、通知配置影响投递、性能节点影响调度），不把提示当成自动执行。
- [E] **N5.2.4 单资源可控回滚**：新增 `POST /api/v1/configuration-center/revisions/{revision_id}/rollback`，必须提交精确确认词 `ROLLBACK`；回滚前再次校验版本可见性、写权限、同一资源和项目范围、资源存在性及历史 HMAC 指纹。恢复在同一事务中执行，成功后生成新的“配置回滚”版本并写入不含敏感值的审计事件；唯一约束、篡改历史、权限或其他失败会回滚事务。启动配置仍只读，不在线重启服务，也不批量删除重建资源。
- [E] **N5.2.5 配置中心前端工作台**：新增 `/system/config` 统一入口，采用配置域导航、资源列表、版本时间线、差异面板和 `ROLLBACK` 回退确认弹层；保留现有环境/变量/AI/存储/通知/性能/启动配置入口，加载失败、无权限、无历史和敏感字段状态均有明确反馈，并兼容窄屏、键盘焦点和减少动态效果偏好。
- [E] **N5.2.6 代码审查、回归与文档收口**：补充跨项目历史版本拒绝、空历史、资源/变量行锁、提交前刷新失败事务回滚和配置版本迁移链/降级断言；完成后执行后端非集成回归、290 文件独立隔离扫描、前端 Vitest、type-check、生产构建、Ruff、mypy、Bandit、全量格式检查和 `git diff --check`。

N5.2 验收口径：管理员/工程师能从统一入口定位可见配置，查看脱敏当前值、历史版本和字段差异；普通角色不能越权读取或回滚；回滚只影响选中的单个资源且可在审计中追溯；任意失败不会泄露敏感值或造成半更新。真实数据库、生产密钥、三方 AI、通知、Worker 和性能节点联调仍只能单独记录为环境验收证据。

### 2026-08-24 N5.2.1 配置只读聚合与权限边界交付记录

- [E] 新增 `GET /api/v1/configuration-center/overview`，聚合启动档案、项目环境、全局变量、AI 模型、存储策略、通知配置和性能节点；返回配置域、资源摘要、更新时间、原页面深链接和可管理标记。
- [E] 启动档案只展示运行环境、Worker/ADB/性能/Web 录制模式等开关，不返回数据库、Redis、MinIO 地址或凭据，也不提供在线重启；AI/存储仅管理员可见，项目资源沿用项目 viewer/editor/owner 边界。
- [E] 任意节点 capabilities 仅保留字符串执行器名称，环境变量/全局变量/通知/API Key 的值、Endpoint、Webhook 和原始 JSON 均不进入聚合响应；新增根级测试桩字段保持历史测试隔离的 fill-missing-only 规则。
- [E] 审查修复：改用标准 `@router.get` 注册，补充新路由回归和历史测试收集阶段的 `get_project_role` 依赖桩；未发现需要改变权限或脱敏设计的问题。
- [E] 验证：配置中心定向 `4 passed`、路由定向 `1 passed`、后端非集成全量 `2181 passed`，Ruff、格式检查和 `git diff --check` 通过；真实数据库、项目角色、AI/通知/性能节点数据仍待环境验收。

### 2026-08-24 N5.2.2 配置版本快照与变更审计交付记录

- [E] 新增 `configuration_revisions` 模型与 Alembic `20260824_0064`；按配置域和资源保存项目范围、资源名称、创建人、原因、指纹、脱敏快照和 Fernet 加密原始快照，启动配置暂不生成资源版本。
- [E] 新增 `POST /api/v1/configuration-center/revisions` 与 `GET /api/v1/configuration-center/revisions`；支持环境、全局变量、AI、存储、通知和性能节点，沿用管理员/项目角色/工程师权限边界，列表只返回可见资源的脱敏版本记录。
- [E] 审计事件只记录配置域、资源 ID 和指纹，不记录原因、密钥、密码、Token、连接串、原始配置或异常；AI/存储版本对非管理员直接拒绝，项目版本按可见项目隔离，性能节点版本仅允许工程师/管理员查看。
- [E] 代码审查修复：普通环境变量不再被误判为密文；存储策略也统一经过脱敏处理；新增明文变量密文标记回归和敏感响应/审计边界回归。
- [E] 验证：配置版本/迁移定向 `7 passed`；后端非集成全量 `2185 passed`；Ruff、格式检查通过。真实数据库迁移、不同项目角色、加密密钥轮换和生产审计数据仍待环境验收；下一入口为 N5.2.3。

### 2026-08-24 N5.2.3 配置差异与影响提示交付记录

- [E] 新增 `GET /api/v1/configuration-center/revisions/{revision_id}/diff`，使用历史加密原文与当前资源计算字段级新增、删除和变更；返回历史/当前指纹、当前资源状态、变更计数和截断标志。
- [E] 普通字段只返回脱敏后的前后值；敏感字段（密钥、Endpoint、Webhook、URL、密码、Token、标记为 secret 的环境/全局变量以及性能节点出口/能力）只返回路径、变更类型和 `changed=true`，不返回前后值。
- [E] 按配置域提供影响提示：环境执行、变量引用方、AI 生成/诊断、对象保留、通知投递和性能调度；资源已删除时保留历史可查并明确无法计算当前差异，不伪造当前值。
- [E] 代码审查修复：性能节点无项目范围时的权限误拒绝；项目 viewer 查看差异时错误要求 editor；变量名含 URL/PASSWORD/TOKEN 但未勾选 `is_secret` 时的脱敏遗漏；新增历史指纹完整性校验。
- [E] 验证：差异/路由定向 `11 passed`；后端非集成全量 `2191 passed`；Ruff、mypy、格式检查和 `git diff --check` 通过。真实角色、密钥轮换和生产配置差异仍待环境验收；下一入口为 N5.2.4。

### 2026-08-24 N5.2.4 单资源可控回滚交付记录

- [E] 新增 `POST /api/v1/configuration-center/revisions/{revision_id}/rollback` 与 `ConfigurationRevisionRollbackIn/Out`；请求必须携带精确确认词 `ROLLBACK`，响应只返回脱敏的回滚后版本和源版本 ID。
- [E] 支持环境、全局变量、AI 模型、存储策略、通知配置和性能节点的单资源恢复；环境变量/全局变量/AI Key/通知敏感配置重新加密，启动配置明确不支持回滚。
- [E] 回滚前校验历史快照 HMAC、版本域与资源 ID、资源存在性、当前项目范围和写权限；项目资源沿用 editor/owner，AI/存储沿用 admin，性能节点沿用 engineer/admin，禁止 viewer 越权恢复。
- [E] 恢复和新版本快照在同一事务中完成，目标资源及环境变量行使用行锁避免并发覆盖；成功后写入 `configuration_revision_rollback` 审计事件，仅记录源/结果指纹、域和资源 ID；唯一约束、权限、历史篡改、刷新或其他异常失败均触发事务回滚。
- [E] 代码审查修复：将新版本刷新提前到提交前，确保刷新失败可回滚；补充篡改版本的事务回滚测试；未发现权限、项目隔离或敏感输出问题。
- [E] 验证：配置回滚/路由定向 `15 passed`；后端非集成全量 `2195 passed`；前端 `type-check`/生产构建、Ruff、改动文件格式检查和 `git diff --check` 通过。全量格式扫描剩余仓库原有 `backend/app/api/v1/workbench.py`，留待 N5.2.6 质量收口；真实数据库、角色、密钥轮换和生产配置仍待环境验收；下一入口为 N5.2.5。

### 2026-08-24 N5.2.5 配置中心前端工作台本地交付记录

- **统一入口**：`/system/config` 替换原导航占位页，仅对管理员/工程师显示和开放；按配置域展示启动档案、环境、全局变量、AI、存储、通知和性能节点，支持全部项目/指定项目筛选及原页面深链接，旧页面和旧 URL 保持不变。
- **变更账本**：资源详情提供当前状态、历史版本时间线、版本字段差异、影响提示、缺失资源和敏感字段脱敏状态；可保存当前快照，回退操作必须在确认弹层输入精确 `ROLLBACK`，沿用后端单资源权限和事务边界。
- **交互与安全**：补充加载失败/重试、无权限、无历史、空资源和敏感字段状态；页面采用窄屏堆叠布局、可见键盘焦点和 `prefers-reduced-motion` 适配，快速切换资源/版本时使用请求序列防止旧响应覆盖当前选择。
- **验证与审查**：新增配置工作台 4 组回归场景（共 `6 passed`，与导航路由一起运行），前端全量 `65 files / 258 tests passed`，`type-check`、生产构建和 `git diff --check` 通过；代码审查修复资源/版本异步请求竞态及普通角色仍可看到受限菜单的问题。真实角色、配置数据、生产密钥和三方依赖仍待环境验收，下一入口为 N5.2.6。

### 2026-08-24 N5.2.6 质量收口本地交付记录

- **回归补齐**：新增配置版本空历史、跨项目差异拒绝、资源与环境变量行锁、提交前刷新失败事务回滚，以及 `20260824_0064` 迁移链/外键/索引/降级契约测试；配置中心相关 API/迁移定向 `24 passed`。
- **全量验证**：后端非集成 `2201 passed`；独立文件隔离扫描 `290 passed / 0 failed`；Ruff check、全量 Ruff format-check（600 个文件）、mypy（151 个源文件）和 Bandit 均通过；此前前端全量 `65 files / 258 tests passed`、type-check、生产构建和 `git diff --check` 通过。
- **审查结论**：新增测试桩继续采用 fill-missing-only，锁断言覆盖资源行和环境变量行，刷新失败验证回滚入口；排除未发现业务或安全问题，补做原有 `backend/app/api/v1/workbench.py` 的纯格式收口。N5.2 已完成本地质量收口，真实数据库、项目角色、密钥轮换和三方依赖仍待环境验收，下一阶段为 N6。

### 2026-08-24 N6.1 配置中心浏览器回归交付记录

- **回归场景**：新增 `frontend/e2e/configuration-center.spec.ts`，使用脱敏的 Playwright 路由桩覆盖管理员进入 `/system/config`、查看项目配置资源、选择历史版本、查看字段差异、输入精确 `ROLLBACK` 并提交回退；同时覆盖普通测试角色访问配置中心时被路由权限拦截并回到工作台。
- **审查与修复**：首次定向执行发现测试选择器命中同名摘要文本的严格模式问题，已收紧为配置资源标题定位；重新执行定向用例通过，代码审查未发现产品逻辑、权限或敏感信息泄露问题。
- **验证证据**：配置中心 E2E 定向 `2 passed`，全量 Playwright `12 passed`；前端 Vitest `65 files / 258 tests passed`，`type-check`、生产构建和 `git diff --check` 通过。真实配置数据、数据库迁移、生产密钥和外部依赖仍待环境验收，下一入口为 N6.2 发布文档与环境证据收口。

### 2026-08-24 N6.2 发布文档、能力矩阵与操作手册交付记录

- **文档同步**：更新 `docs/capability-baseline-2026-08-07.md`、`docs/user-operation-manual.md`、`docs/q18-latest-status-2026-08-07.md` 和 `docs/q18-implementation-log-2026-08-07.md`；五组导航、远程工具箱、配置中心、权限/脱敏/回退边界和发布门禁入口已统一描述。
- **一致性审查**：核对 `Task.md`、本路线图、能力矩阵、用户手册、Q18 最新状态和实施日志中的模块状态及下一步；文档明确区分本地代码/自动化证据与真实环境验收，不把 mock、协议桩或本地浏览器回归当作生产通过。
- **验证与边界**：文档链接和状态审查通过，`git diff --check` 通过。真实数据库、生产密钥、Android/Windows Worker、性能节点、通知和外部缺陷平台仍需按环境生成带日期证据；当时下一入口为 N6.2 真实环境与发布 readiness 验收。

### 2026-08-24 N6.3 Windows 发布 readiness 与远端依赖恢复交付记录

- [x] 远端 Redis 异常端口状态已恢复：保留 Redis 挂载数据目录，清理异常容器状态并重启 Docker 网络层；Redis 6379、PostgreSQL 5432、MinIO 9000 从 Windows 可达，q19 验收后端 `/health` 返回 HTTP 200。
- [x] Windows 最小 smoke 通过：doctor、后端健康、前端登录页、PostgreSQL/Redis/MinIO、ADB、k6/Locust/gRPC 和性能队列检查均通过，脱敏证据见 [`docs/evidence/windows-release-readiness-2026-08-24.json`](docs/evidence/windows-release-readiness-2026-08-24.json)。
- [x] 仓库 readiness 默认检查通过；严格模式只因当前 Windows 缺少 Docker Compose 工具而失败，未把工具缺失伪装成部署通过。
- [ ] 本次显式跳过管理员登录、认证读接口、Playwright/浏览器矩阵、文件上传、报告导出和 Android 执行；完整发布验收及 Android Worker/真机、性能节点、通知和外部平台仍需后续独立证据。

### 本轮模块交付顺序

- [E] N1.1 我的待办：待评审、五类失败运行、逾期计划、设备异常聚合，项目范围和已有入口跳转；内部缺陷待 N2。
- [E] N1.2 任务中心：五类执行记录统一列表、筛选、刷新和精确总数。
- [x] N1.3 任务操作：服务端状态/权限校验，重试、Android/Performance 终止和批量操作。
- [E] N1.4 N1 验收：后端 `2131 passed`，前端 `52 files / 213 tests passed`，type-check/build/ruff/diff-check 通过；待真实环境验收后收口。

### 当前 N2 子模块顺序

- [E] N2.1 内部缺陷：项目级 CRUD、权限、分派、状态流转、优先级、严重程度和重复识别已完成本地实现、审查和回归；待真实项目角色验收。
- [E] N2.2 失败证据关联：失败运行、截图、日志、Trace、用例双向关联，创建时脱敏并保留来源已完成本地实现、审查和回归；待真实失败执行和对象存储证据验收。
- [E] N2.3 报告中心：项目/周期筛选、趋势、运行对比、用例执行覆盖率、缺陷健康度和质量评分，支持运行详情及用例/套件/计划入口；待真实环境验收。
- [E] N2.4 用例评审工作台：项目/状态/关键词筛选、待评审队列、批量评审、评论、详情、版本差异入口和评审记录已完成本地实现、审查和回归；待真实项目角色、审计和数据验收。
- [E] N2.5 外部缺陷兼容：保留现有 Jira/禅道/GitHub/GitLab 链路，支持内部缺陷手工映射、外部创建、状态同步和可选内部状态回写；待真实外部平台验收。

### 2026-08-24 N2.1/N2.2 本地交付记录

- [E] 新增 `defects` / `defect_run_links` 模型与 Alembic `20260824_0060`，接入模型注册、迁移和 API 路由。
- [E] 新增内部缺陷 CRUD、项目角色校验、指派、状态流转、重复指纹识别，以及从 case/suite/plan/Android/performance 失败记录创建缺陷。
- [E] 新增失败证据脱敏与大小/深度边界，保存截图、日志、Trace、Android 产物和性能结果引用；缺陷详情可反查运行，运行详情可反查内部缺陷。
- [E] 新增 `/bugs` 缺陷工作台、创建/编辑/筛选/证据抽屉和执行详情入口，补齐中英文文案及导航契约。
- [E] 回归证据：后端非集成 `2142 passed`；前端 `53 files / 214 tests passed`；`npm run type-check`、`npm run build`、迁移回归 `21 passed`、ruff 和 `git diff --check` 通过。真实数据库、项目角色、失败执行、MinIO/Trace 证据仍需环境验收。

### 2026-08-24 N2.3 测试报告中心本地交付记录

- [E] 新增 `/reports/overview` 与 `/reports/compare`，统一返回项目/周期运行趋势、通过率、平均时长、用例执行覆盖率、活动缺陷数、缺陷健康度和质量评分；运行对比限制同项目同用例的已完成记录。
- [E] `/reports` 报告中心支持项目/周期深链接、质量信号卡、趋势图、CSV 导出、最近运行记录、运行详情跳转、两次运行对比，并补充用例/套件/计划入口。
- [E] 质量评分口径已固定为“通过率 60% + 用例执行覆盖率 25% + 缺陷健康度 15%”；执行覆盖率不等同代码覆盖率，报告错误信息继续脱敏。
- [E] 回归证据：后端非集成 `2147 passed`；前端 `54 files / 217 tests passed`；type-check、生产 build、迁移 heads、ruff 和 `git diff --check` 通过。真实数据库、权限、套件/计划联动和运行数据仍需环境验收。

### 2026-08-24 N2.4 用例评审工作台本地交付记录

- [E] 新增 `/case-reviews` 队列、统计、项目可见范围、状态/关键词筛选和分页；新增批量通过/驳回、评论、处理/跳过结果和 editor 权限校验。
- [E] 评审提交、通过、驳回和批量评审写入审计事件；新增评审历史接口，兼容从版本快照读取历史；队列展示步骤数、快照数、最新版本和评审人。
- [E] `/case-reviews` 替换导航占位页，提供状态统计、批量操作、详情抽屉、评审时间线、版本历史/差异入口和原用例跳转，保留 `/cases` 兼容入口。
- [E] 代码审查修复批量跳过 ID 顺序和 Vue 表格记录类型推断问题；定向后端 `8 passed`、非集成全量 `2150 passed`，前端全量 `55 files / 219 tests passed`，type-check/build/迁移 head `20260824_0060`/ruff/diff-check 通过。真实项目角色、审计、版本差异和生产数据仍待环境验收。

### 2026-08-24 N2.5 外部缺陷兼容本地交付记录

- [E] 新增 `defect_external_links` 模型与 Alembic `20260824_0061`，按项目保存内部缺陷到 Jira、禅道、GitHub Issues、GitLab Issues 的外部 Issue 映射。
- [E] 复用现有四平台服务实现手工关联、按缺陷创建外部 Issue、重复查询、状态同步和可选内部状态回写；创建内容脱敏，外部 URL 做 HTTP/HTTPS 安全校验，失败信息不泄露平台凭据。
- [E] 缺陷详情增加外部关联卡片和操作弹窗；查看者可以查看映射但不能加载配置或看到变更按钮，旧列表/详情数据保持兼容。
- [E] 审查修复了同步状态覆盖详情表单、查看者 403 操作按钮和后端写接口权限绕过三个问题；四个外部缺陷写接口统一要求管理员/工程师。后端非集成 `2156 passed`，前端 `55 files / 221 tests passed`，缺陷详情定向 `3 passed`、外部权限定向回归包含在后端测试中，type-check/build/ruff/diff-check 和迁移 head `20260824_0061` 通过。真实平台凭据、网络和权限仍需环境验收。

### 2026-08-24 N3.1 API 测试工作台本地交付记录

- [E] 新增 `/api-workbench` 真实工作台入口，按项目和模块组织 API、GraphQL、WebSocket、gRPC 用例，支持协议筛选、关键词搜索、优先级/等级/最近运行状态、详情抽屉和运行历史。
- [E] 复用现有 `caseApi`、`environmentApi`、`runApi`、`CaseFormDrawer` 和 `AIGenerateDrawer`，提供新建、编辑、OpenAPI/Postman/cURL/样例导入、AI 生成、环境变量选择执行和运行详情跳转；未重复实现后端执行器，也未新增迁移。
- [E] AI 生成入口新增 `allowedCaseTypes` 约束，API 工作台只开放 API 协议类型；只读项目隐藏写操作并保留查看/结果访问，执行按钮要求项目编辑权限且用例必须可执行。
- [E] 代码审查修复刷新按钮重复请求问题；补充工作台挂载/协议过滤/执行跳转回归和路由回归。前端全量 `56 files / 223 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过。真实项目角色、环境变量、协议服务和运行结果仍需环境验收。

### 2026-08-24 N3.2 APP 自动化工作台本地交付记录

- [E] `/mobile-special/workbench` 已替换占位入口，按项目聚合设备池、Android Worker 状态、Android 用例、专项任务、APK 资产、最近运行和设备兼容性概览；保留设备、APK、专项任务和报告原有深链接。
- [E] 新增设备扫描、设备预约/心跳/释放和截图预览；预约期间锁定项目与设备焦点，专项任务执行前要求释放 UI 租约，避免与 Worker 自己获取的执行租约冲突。
- [E] Android 用例按 `case_type=android` 筛选并复用 `caseApi.run`；专项任务提供显式目标设备和可选 APK 包名覆盖，设备池焦点不会隐式改变任务默认目标；查看者保持只读，扫描/预约/执行受项目编辑权限保护。
- [E] 代码审查修复了 Android 用例客户端二次过滤、预览设备与执行设备解耦、租约期间禁止切换项目和刷新重复请求边界；补充工作台挂载、协议过滤/执行和路由回归。前端定向 `2 files / 4 tests passed`，全量 `57 files / 225 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过。
- [E] 本模块未新增后端模型、迁移或执行器；真实 Windows Android Worker/ADB、在线真机、截图回传、专项任务报告和 APK 包名数据仍需环境验收。

### 2026-08-24 N3.3 UI 自动化工作台本地交付记录

- [E] 新增 `/ui-workbench` 真实工作台入口，按项目和模块聚合 Web 用例、Playwright Worker 状态、元素库、页面对象、视觉基线和最近运行；保留 `/cases`、`/system/web-assets`、`/runs` 等既有深链接。
- [E] 工作台支持 Web 用例目录、关键词筛选、用例详情、低代码步骤预览、脚本生成状态、浏览器/视口/Trace 信息和运行详情跳转；新建/编辑复用 `WebCaseDrawer`，录制结果可直接带入新用例草稿。
- [E] 录制入口复用 `WebRecorderModal`，支持步骤录制和视觉基线截图采集；元素库、页面对象、视觉基线通过项目上下文快捷入口访问，资产页支持从路由查询切换目标标签。
- [E] 代码审查修复项目清空后的状态残留、项目切换异步响应覆盖、模块筛选空项目强制类型转换和资产页标签路由复用问题；补充录制草稿、项目清空、用例筛选/详情/运行回归。
- [E] 验证：UI 工作台/用例抽屉/导航定向 `3 files / 10 tests passed`，前端全量 `58 files / 230 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过。未新增后端模型、迁移或执行器；真实 Web Worker、浏览器录制、截图上传、Trace/网络日志和运行报告仍需环境验收。

### 2026-08-24 N3.4 性能测试工作台本地交付记录

- [E] 新增 `/performance-workbench` 真实工作台入口，按项目聚合性能场景、执行节点、环境、运行队列和性能执行器；保留 `/system/performance` 完整性能控制台兼容入口，并将测试能力导航切换到新工作台。
- [E] 工作台支持快速创建脚本型场景、选择环境和多执行节点发起运行、options 覆盖、活动运行 2.5 秒轮询、停止运行、运行进度和最近通过率；复杂可视化场景、压力阶段、PromQL、调度和容量分析继续复用完整性能中心。
- [E] 运行证据支持 RPS、P95、P99、错误率、阈值门禁、Worker/Prometheus/ATP 资源采样时间线、基线对比、设置基线和 JSON/CSV 报告导出；节点列表展示在线状态、队列和执行器能力。
- [E] 代码审查修复执行器服务异常时误放行启动、辅助接口失败阻断场景、资源来源标签映射、证据请求竞态，以及新旧性能入口项目上下文不一致问题；查看者保持只读，启动/创建/基线按项目编辑权限控制。
- [E] 验证：性能工作台定向 `4 passed`，性能中心/导航联动定向 `11 passed`，前端全量 `59 files / 235 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过。未新增后端模型、迁移或执行器；真实性能 Worker、节点容量、Prometheus、Locust/JMeter/gRPC 和生产报告仍需环境验收。

### 2026-08-24 N4.1 AI 智能测试工作台本地交付记录

- [E] 新增 `/ai-workbench` 真实工作台入口，替换 AI 能力占位页；按项目聚合 AI 模型绑定状态、模块、用例自动化覆盖缺口、测试数据集、Mock 规则、质量总览、失败热点和失败任务。
- [E] 生成通道复用现有用例 AI 生成、数据集 AI 生成和 Mock AI 生成入口；用例生成带入项目首个模块和 `ai_generate` 查询上下文，数据集/Mock 保留原页面的可编辑预览与确认流程，不重复实现 LLM 调用。
- [E] 诊断区跳转已有任务/运行详情，自愈区展示管理员可见的全平台反馈采纳率和高质量示例；模型密钥不在工作台展示，未绑定或禁用模型时前端阻止生成入口。
- [E] 代码审查修复项目清空加载状态、刷新并发旧响应覆盖、项目上下文数据隔离和管理员统计权限边界；新增自动化覆盖缺口、查看者只读及可选信号失败降级处理。
- [E] 验证：AI 工作台/导航定向 `2 files / 6 tests passed`，AI 工作台补充权限/模型门禁后单页 `5 passed`，前端全量 `60 files / 240 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过。未新增后端模型、迁移或执行器；真实三方模型、调用限额/审计和生产 AI 结果仍需环境验收。

### 2026-08-24 N4.2 Hermes 助手本地交付记录

- [E] 新增 `/hermes` 实际助手工作台，按项目加载模块、用例、任务、报告和失败热点；保留项目选择、刷新、空项目和部分数据失败降级，项目切换使用请求序号隔离旧响应。
- [E] 提供四类可追溯意图：查询失败任务、解释失败、汇总质量指标和生成测试计划；快捷提问与自然语言关键词均可触发，未知问题明确提示当前支持范围。
- [E] 失败解释复用既有 `runApi.generateFailureDiagnosis`，只对 Case 运行调用诊断链路；其他任务类型保留原始错误并跳转专属详情，诊断摘要、步骤建议和来源链接均展示在页面中。
- [E] 测试计划仅生成可编辑草稿，支持编辑名称、目标、覆盖点、添加/删除覆盖点，并跳转原有 `/plans` 页面确认保存；不会静默创建计划或改动测试资产。
- [E] 代码审查修复项目清空变更未更新 selected project、旧请求覆盖新项目证据和诊断失败无降级反馈边界；未新增后端模型、迁移或执行器，未在前端重复实现 LLM 调用。
- [E] 验证：Hermes 定向 `1 file / 5 tests passed`，前端全量 `61 files / 245 tests passed`，`npm run type-check`、`npm run build`、`git diff --check` 通过；真实项目数据、Case 诊断模型、任务类型权限和生产审计仍需环境验收。

### 2026-08-24 N4.3 需求与用例追踪本地交付记录

- [E] 新增 `test_requirements` 和 `requirement_case_links` 模型及 Alembic `20260824_0062`；需求按项目隔离，支持状态、优先级、来源、版本、负责人和 JSON 验收标准，关联关系支持覆盖/验证、标准 ID 和备注。
- [E] 新增 `/requirements` 项目范围 API：需求列表/详情/创建/编辑/删除、规则化文本解析草稿、需求负责人有效项目成员校验、需求—用例关联/解除、验收覆盖率和基于标题/描述/标签的影响候选分析；读取/写入分别要求 viewer/editor，跨项目用例和未知验收标准拒绝。
- [E] `/requirements` 替换导航占位页为需求追踪工作台：项目/状态/关键词筛选，需求清单、版本与覆盖率、验收标准状态、关联用例维护、未覆盖标准和影响雷达；文本解析结果先进入可编辑草稿，不静默生成或修改用例。
- [E] 代码审查修复需求列表无效条件表达式、创建时 ORM Python 默认值尚未回填的响应错误、负责人越权指派和前端项目/需求异步加载边界；菜单名称同步为“需求与用例追踪”。
- [E] 验证：后端需求/迁移/零状态回归 `10 passed`，前端需求追踪定向 `1 file / 3 tests passed`，前端全量 `62 files / 248 tests passed`，type-check、生产 build、Ruff 和 `git diff --check` 通过；真实需求数据、项目角色、用例联动和生产环境迁移仍待环境验收。

### 2026-08-24 N4.4 知识中枢本地交付记录

- [E] 新增 `knowledge_entries` 模型与 Alembic `20260824_0063`；知识条目支持全局/项目范围、来源类型、状态、版本、标签、来源引用和编辑权限，项目删除级联清理项目知识。
- [E] 新增 `/knowledge` 统一检索 API 和 `/knowledge` 知识中枢工作台；支持关键词、项目、来源、状态筛选，结果展示来源、项目范围、命中词、来源链接和可编辑状态。
- [E] 搜索聚合需求、内部缺陷和失败/错误运行作为只读证据，手工知识支持创建/编辑/删除；非管理员只能看到已发布全局知识和自己可见项目知识，写操作按管理员/项目 editor 控制。
- [E] 统一对标题、摘要、正文、来源引用和标签做敏感信息脱敏；内置来源跳转到对应需求、缺陷和运行详情，补齐需求/缺陷深链接的精确打开逻辑。
- [E] 代码审查修复全局知识在项目筛选时被误过滤、全局草稿对普通用户泄露、标签未脱敏，以及内置需求/缺陷结果只能打开默认列表项的问题。
- [E] 验证：知识/需求/迁移回归 `15 passed`，知识中枢/需求/缺陷定向前端 `3 files / 9 tests passed`，前端全量 `63 files / 251 tests passed`，`vue-tsc --noEmit`、生产 `vite build`、Ruff 通过；真实知识数据、项目角色、生产迁移和数据量性能仍待环境验收。

### 2026-08-24 N5.1 远程工具箱本地交付记录

- [E] 新增 `/api/v1/remote-toolbox/overview`，由管理员/工程师统一检查 PostgreSQL、Redis、MinIO、Android Worker/ADB、Web Worker/本地录制模式和性能节点，返回状态、检查时间、延迟、资源队列/能力和可操作原因码。
- [E] 新增 `/system/toolbox` 远程工具箱工作台，按“基础设施/执行节点”分组展示整体状态、资源明细、处理入口和中英文文案；支持导出已经脱敏的 JSON 诊断结果，不展示连接地址、密码、Token、密钥或原始异常。
- [E] 复用现有健康探针、Android/Web Worker 注册中心和性能节点查询，不新增模型、迁移或执行器；性能节点错误只返回安全原因码，Worker 注册信息只保留队列和能力元数据。
- [E] 代码审查修复前端资源元数据标签未走 i18n、导出文件名兼容当前 TypeScript 目标、导出回归缺少成功消息 mock，以及性能节点 capabilities 原样回显潜在敏感字段的问题；后端仅返回字符串执行器名称，并补充嵌套敏感字段脱敏测试。
- [E] 验证：后端全量非集成 `2177 passed`，前端全量 `64 files / 254 tests passed`，远程工具箱后端定向 `6 passed`、前端定向 `3 passed`，`vue-tsc --noEmit`、生产 `vite build`、Ruff、格式检查和 `git diff --check` 通过；真实数据库、Redis、MinIO、Windows Android Worker/ADB、Web Worker 和性能节点仍待环境验收。

## 2026-08-20 邮件通知链路本地自检

- [x] 新增 `scripts/notification-smtp-link-check.py`：在 `127.0.0.1` 上启动一次性最小 SMTP 接收端（Python 3.12+ 已移除 `smtpd`，改用标准库 socket 手写，不引入新依赖），经生产入口 `send_notification_channel` 真实完成一次 SMTP 会话后解析原始邮件。
- [x] 12 项检查全部通过：SMTP 信封、收件人规范化、MIME multipart、`To` 头显示名保留和正文六个性能字段；证据见 `docs/evidence/notification-smtp-link-check-2026-08-20.json`。
- [x] 实测确认上一轮修复生效：配置 `['qa@example.com', '  ', 'QA Team <ops@example.org>']` 的信封为 `['qa@example.com', 'ops@example.org']`，空白项被跳过、显示名被规约为裸地址，而 `To` 头保留显示名。
- [x] 负向验证：人为让正文缺少 RPS 字段后脚本返回非零并精确指出 `body field rps`，不会把回归报成通过。
- [x] 补充 7 项契约测试锁定脚本边界：状态只能是 `local_link_only`/`failed`、只绑定回环地址、不接受命令行凭据、不绕过 `send_notification_channel`、只使用 RFC 2606 保留域。
- [ ] 该自检不覆盖供应商送达、反垃圾/退信、DKIM/SPF、TLS 链路、限流和重复投递；SMTP、企业微信、钉钉的外部门禁保持开启，仍需 sandbox 凭据后分渠道执行并归档。

## 2026-08-19 通知投递目标校验一致性修复

- [x] 修复配置校验与实际投递规则不一致导致的通知丢失：`validate_notification_channel_config` 与 `_send_email` 统一改用新增的 `normalize_email_recipients`。此前 `['qa@example.com', '']` 和 `['qa@example.com', 'QA Team <ops@example.com>']` 能通过配置校验，却在投递时整批抛错，连合法收件人也收不到。
- [x] 收件人规则改为：允许 `Name <addr>` 显示名格式（`smtplib` 会自行取出地址，改动前本可正常送达），自动跳过空白条目，拒绝换行注入和缺少 `@`/本地部分/域名的地址。
- [x] Webhook 校验下沉到配置阶段：创建/更新即拒绝非 `http`/`https`、带用户名密码、`localhost` 和字面内网地址，避免保存成功却永久投递失败。
- [x] 修复阻塞事件循环：`_send_wechat`/`_send_dingtalk` 的公网 DNS 复核改为 `asyncio.to_thread`，与 `exports.py`、`web_recordings.py`、`dataset_preparation.py` 的既有约定一致。
- [x] 修复 MinIO 验收脚本只读探测把任意异常当作“write denied”的假通过：现在只接受明确的授权错误码，并在报告里输出真实的读写结果。
- [x] 修复通知验收脚本绕过生产入口和 `content_checks` 硬编码为 `true` 的问题：改为经 `send_notification_channel` 投递，`content_checks` 按“标签 + 取值”逐字段实测（已验证每个字段缺失时只有自己变 `false`）。
- [x] 新增回归：校验通过的配置必须可投递、被拒配置两层一致拒绝、字面内网 Webhook 在配置阶段被拒、DNS 复核在工作线程而非事件循环执行。
- [x] 验证：非集成后端 `2111 passed`，两个改动测试文件独立运行 `47 passed` / `7 passed`，通知与脚本契约定向回归 `138 passed`，Ruff check/format、mypy（137 文件）和 `git diff --check` 通过。
- [ ] SMTP、企业微信、钉钉真实送达仍需注入 sandbox 凭据后分渠道执行并归档；本地回归不替代供应商证据。

## 2026-08-17 非 Android/API 外部项收口推进

- [x] 在 `172.31.27.133` 的 `/opt/atp-q18-acceptance-20260817` 部署当前代码隔离 Compose 栈，改用 28080/28090/28092，旧 q17 栈未停止；Backend、Prometheus、专用 Worker、Beat、PostgreSQL、Redis、MinIO 和目标服务均健康，PromQL 同时看到 Backend/Worker target。
- [x] 完成真实 PostgreSQL→MinIO 日备份和临时库恢复：固定 Worker 使用 PostgreSQL 16.15 `pg_dump`，备份对象已上传，临时库恢复 53 张 public 表后删除；证据见 `docs/evidence/performance-linux-q18-acceptance-2026-08-17.json`。
- [x] Helm 专用 performance Worker 增加 `autoIdentity`：多副本时按 Pod hostname 生成独立节点 ID、名称和 `performance.<pod>` 队列；默认关闭以保持旧固定节点配置兼容。
- [x] 通知通道代码契约已通过 API/服务/验收脚本定向回归 `45 passed`，部署/Compose/通知契约回归 `28 passed`；重试、429/5xx 退避、脱敏和投递历史入口已具备。
- [x] 性能验收 Compose 栈增加 Prometheus（Backend、专用 performance Worker 两个 scrape target、7 天本地历史）和单副本 Beat；Helm 增加专用 performance Worker metrics Service 与 ServiceMonitor，避免 Kubernetes 只采集 Backend 而遗漏压测节点指标。
- [x] 自动 PostgreSQL 备份不再依赖 Worker 镜像中的 `mc` 或仓库根目录 `scripts/backup-postgres.sh`：Worker 内直接流式执行 `pg_dump`、gzip 并通过 Python MinIO SDK 上传；补充成功、失败和临时文件清理回归。
- [x] iOS IPA 上传会尽力解析 `Payload/*.app/Info.plist`，自动回填 Bundle ID 和版本号；手工字段仍优先，损坏/非标准归档不会阻断上传。
- [x] 增加 `scripts/macos-ios-worker.sh` 与 `config/startup-profiles/macos-ios-worker.env.example`：启动前检查 macOS/Xcode/Appium/XCUITest，并强制 Worker 只监听 `ios` 队列。
- [x] 本轮定向回归 `84 passed`，完整非集成后端回归 `2091 passed`；Ruff check/format 与 `git diff --check` 通过。
- [ ] Kubernetes 多节点、生产 Prometheus 历史、真实 MinIO 保留/跨主机恢复仍需目标集群和运维确认；远端 `172.31.27.133` 当前无 kubectl/helm，未将 Compose 结果冒充生产验收。
- [ ] SMTP/企业微信/钉钉真实投递仍需管理员提供临时测试目标；当前代码已有重试、429/5xx 退避、脱敏和投递历史，未伪造外部送达证据。
- [ ] iOS 真机/模拟器闭环仍需 macOS、Xcode、签名应用、WebDriverAgent 和设备；Windows/Linux 只完成代码契约与启动前检查。

## 2026-08-17 GitHub Actions 远端失败修复

- [x] 修复 CI 的 Ruff 格式检查失败：格式化 6 个被报告的后端源码/测试文件，并通过完整格式检查。
- [x] 修复 Linux 无 `DISPLAY` 导致的 Web 录制 API 回归失败：测试显式注入 `WEB_RECORDER_DISPLAY`，保留产品对真实可见显示环境的校验。
- [x] 修复 Security 的前端依赖漏洞：锁定 `nanoid` 到 `3.3.18`，本地 `npm audit --audit-level=high` 无漏洞。
- [x] 远端复核发现 k6 `2.2.0` 和 `master` 镜像仍内置受影响的 Go 版本，Worker 改为用固定 digest 的 Go `1.26.6` 构建并校验 k6 `v2.2.0` commit；JMeter 5.6.3 镜像构建同步替换存在固定版本的 Jackson、XStream、dnsjava、json-smart、HttpCore5、Batik，并移除当前执行器不使用的 Neo4j/Tika 可选包。
- [x] 修复远端新增的 Bandit XML 解析告警，统一改用 `defusedxml`；补齐 `test_mobile_special_events.py` 的模型 bootstrap，独立测试不再依赖历史收集顺序。
- [x] 本地完整非集成后端回归 `2084 passed`，独立文件扫描 `275 passed`，Web 录制定向回归 `22 passed`，Bandit/ruff/npm 审计通过；最新远端 CI/Security 全部通过，Worker 镜像构建与 Trivy 扫描通过。

## 2026-08-17 GitHub Actions 触发策略收口

- [x] 主 CI 与 Security 改为每周日北京时间 10:00（UTC 02:00）运行一次，并保留 `workflow_dispatch` 手动触发；不再由 push/PR 触发。
- [x] integration、E2E 和 Release readiness 保持手动触发；全部工作流 YAML 解析通过，触发契约回归已同步。
- [x] `.github/dependabot.yml` 继续按周检查依赖；它是独立的依赖更新服务，不会触发本项目 CI。

## 2026-08-16 Kubernetes 环境前置审计

- [x] 对 `172.31.27.133` 完成只读探测：当前可见 Docker 容器栈，但没有 `kubectl`、`helm`、`k3s`、`microk8s` 或 `minikube`；未执行安装、部署、重启或其他远端修改；证据见 `docs/evidence/kubernetes-readiness-audit-2026-08-16.json`。
- [ ] Kubernetes 性能验收仍需目标环境先提供集群/API 凭据和节点；在此之前不把 Docker Compose 结果计为 Kubernetes、多节点或生产 Prometheus 验收。

## 2026-08-15 Windows/远端依赖与性能环境复核

- [x] 20:37 实时复核通过：Windows 后端/前端、登录、项目读取、PostgreSQL/Redis/MinIO readiness、47 bytes 文件上传与清理均通过；本次明确跳过 Playwright、浏览器矩阵和报告导出，Android 仅保留无在线设备 warning；脱敏证据见 `docs/evidence/windows-smoke-live-2026-08-15-2037.json`。
- [x] 本轮质量门禁重新通过：后端非集成测试 `2082 passed`，前端 `50 files / 209 tests passed`，`type-check` 与生产构建通过。
- [x] 远端 PostgreSQL/Redis/MinIO 恢复监听后重新执行 Windows API/Web smoke：依赖 readiness、登录、项目读取、浏览器矩阵、47 bytes 文件上传和清理均通过；Android 仅保留无在线设备 warning；脱敏证据见 `docs/evidence/windows-smoke-current-2026-08-15.json`。

- [x] `scripts/windows-android-worker.ps1 doctor -EnvFile .env` 通过：Windows Python/Celery/Redis 依赖、ADB 可执行文件和远端 PostgreSQL/Redis/MinIO 端点均可用；Android 设备在线检查仅提示未发现设备。
- [x] Windows 到 `172.31.27.133` 的 PostgreSQL `5432`、Redis `6379`、MinIO `9000` TCP 检查通过；实时依赖 API 返回 PostgreSQL、Redis、MinIO 均为 `ok`。
- [x] `scripts/windows-local-smoke.ps1 -SkipPlaywright -SkipReports` 通过；后端健康检查、登录、当前用户、项目列表、Web Worker 状态、文件上传/清理和 Chromium 登录矩阵均通过，未发现失败请求。
- [x] 性能环境 readiness smoke 通过：ATP `/health`、k6/Locust/gRPC 执行器、专用节点队列、出口白名单、目标 TCP 和 Prometheus `/-/ready`/PromQL 查询均通过。
- [x] 真实低流量性能 smoke 通过：Locust run `1` 完成 `957` 次请求、错误率 `0`，并回传 `2` 条 `performance-worker` 资源采样；取消 smoke 的 run `2` 从运行态进入 `cancelled`。
- [x] Windows Android Agent 已按当前 `.env` 重新注册：`GET /api/v1/devices/workers` 返回 `android-win-HPS` online，队列为 `mobile_special`，能力为 `adb/android`。
- [x] 修复 Android Worker doctor 未提前加载 `ATP_ADB_HOME`/Android SDK 可选路径的问题；新增脚本契约回归，避免 PATH 未修改时误报 ADB 缺失。
- [ ] Android 单设备真实验收仍阻断：`adb devices -l` 没有授权在线设备，`scripts/windows-android-acceptance.ps1` 已按契约失败并生成 `.local-run/android-acceptance-20260815.json`；接入设备后需补执行低代码、截图、日志、Crash/ANR 和回放闭环。Windows 冒烟已新增 `-AndroidCaseId -RequireAndroidLowcode -RequireAndroidEvidence`，可在设备接入后复用已审核用例完成运行结果与证据检查。
- [x] Android Worker 低代码冒烟现在会先检查 Worker 注册和设备扫描；前置失败时不创建待执行 Run，避免无设备场景留下脏任务。
- [x] Android 无真机安全回归完成：Worker/性能/事件/回放/API/迁移和 Windows 验收契约定向回归 `258 passed`；验收脚本现在会区分未连接、未授权和离线设备，并在报告中输出安全的状态计数。
- [x] 最新完整非集成后端回归 `2082 passed`；发布 readiness 仓库检查通过，Android Worker Compose/Helm 配置契约已纳入门禁；本机缺少 Docker Compose/Helm 时仅记录环境检查为 `SKIP`。
- [x] 最新前端质量门禁 `50 files / 209 tests passed`，`npm run type-check` 与生产 `npm run build` 通过；ADB 仍无在线设备，真实 Android 数据面保持待验收。
- [x] 性能节点 `perf-node-local-01` 已切换到专用队列 `performance.worker-local` 并上线；真实取消、目标服务连通性和资源采样已完成本机闭环。
- [x] 新增 `config/deployment-profiles/android-worker-backend.env.example` 与部署说明：公网 Backend/Beat/普通 Linux Worker 使用 `ADB_SCAN_MODE=worker` 且排除 `android,mobile_special`，Windows Agent 继续使用独立 `android-agent` 档案；实际环境仍需验证队列隔离与设备回调。
- [x] 新增 Helm overlay `deploy/helm/atp/values-android-worker.example.yaml`：开启服务端 Worker 模式、保留 Android 专用队列给 Windows Agent，并默认引用外部 Secret；部署文档和 Helm 契约回归已同步。
- [x] 使用 Helm `v4.2.4` 完成 Chart lint 和 Android Worker overlay template 渲染，确认 `worker` 扫描模式、`mobile_special` 路由、Linux Worker 队列隔离及 `atp-runtime-secrets` 引用；真实集群 rollout 仍待目标环境。
- [x] 发布 readiness 现在校验 Compose/Helm Android Worker 模板的 `ADB_SCAN_MODE`、ADB 开关、`mobile_special` 路由和 Linux Worker 队列隔离；契约失败会在发布前直接阻断。
- [ ] 当前根 `.env` 仍为 Windows 全栈本地 Android 执行模式（`ADB_SCAN_MODE=local`）；切换公网后端+Windows Android Worker 时仍需使用服务端模板生成独立部署配置，并完成队列隔离与设备回调验收。

## 2026-08-15 Linux Docker 性能验收

- [x] Linux MCP 已恢复并连接 `172.31.27.133`；独立性能验收栈的 PostgreSQL、Redis、MinIO、Backend、专用 Worker、Prometheus 指标端口和 HTTP/gRPC 目标均健康。
- [x] Locust 真实 smoke 通过：run `1`、36 次迭代、错误率 `0`，节点 `worker-a` 使用队列 `performance.worker-a`，并通过目标 allowlist 与资源指标门禁；证据见 `docs/evidence/performance-linux-locust-smoke-2026-08-15.json`。
- [x] gRPC TLS 真实 smoke 通过：run `2`、5 次迭代、错误率 `0`，证书校验和 SNI `grpc-target` 通过；证据见 `docs/evidence/performance-linux-grpc-smoke-2026-08-15.json`。
- [x] Locust 取消验收通过：run `3` 在 2 秒取消请求后从运行态进入 `cancelled`；证据见 `docs/evidence/performance-linux-locust-cancel-2026-08-15.json`。
- [ ] 本轮为 Linux Docker Compose 隔离栈验收，尚未关闭 Kubernetes Deployment、真实多节点分片、外部目标和生产 Prometheus 门禁。

## 2026-08-15 Web Worker 控制面与备份恢复验收

- [x] 修复 Web 录制 API/Worker 使用 Redis `BLPOP` 时的读超时竞态：控制面 Redis 客户端的 `socket_timeout` 现在大于命令/心跳等待窗口，避免连接在等待回复前被 5 秒默认读超时关闭；定向回归 `18 passed`。
- [x] Windows Web Recording Worker 真实 smoke 通过：Worker 已注册且可用，Chromium 录制启动、记录 `2` 个步骤、截图返回 PNG（`13441` bytes），停止录制成功；脱敏证据见 `docs/evidence/web-recording-worker-local-2026-08-15.json`。
- [x] 远端 Linux/Xvfb 环境兼容性检查完成：旧 acceptance backend 镜像具备 Xvfb/Playwright，临时 Worker 可注册并已清理；但镜像缺少当前版本 `/web-recordings/workers` 路由，未将其计入真实录制验收；证据见 `docs/evidence/web-recording-linux-remote-2026-08-15.json`。
- [x] 当前仓库 backend 镜像已从 HEAD 构建并完成 Linux/Xvfb Chromium 录制 smoke；Worker 注册/容量预检、录制启动、状态查询、PNG 截图（`17117` bytes）和停止录制均通过。
- [x] 使用当前 Worker 源码挂载到现有多浏览器 Linux/Xvfb 运行时后，Firefox 截图 `19076` bytes、WebKit 截图 `21192` bytes 均通过；副本 A 启动会话、副本 B 查询/截图/停止的 Redis 路由也通过；临时容器与 Worker key 已清理；证据见 `docs/evidence/web-recording-linux-current-2026-08-15.json`。
- [x] `Dockerfile.worker` 已从 HEAD 完整构建成功（镜像 digest `sha256:4937375e68f2c10de982f19632f960eae402319bc539c34eabbd1eb43c69316a`）；同一镜像的 Chromium/Firefox/WebKit Linux/Xvfb 录制、容量切换重试、无 Worker 时 503 和跨副本 Redis 会话路由均通过，证据见 `docs/evidence/web-recording-linux-current-2026-08-15.json`。
- [x] 当前前端浏览器矩阵已生成 Chromium/Firefox/WebKit Trace、HAR、Console、失败请求和 HTTP 错误摘要；证据见 `docs/evidence/web-browser-trace-network-2026-08-15.json`。Linux acceptance 栈没有前端容器，因此该项是 Windows 当前前端的独立采集证据。
- [x] Linux Docker Compose 隔离验收栈完成 PostgreSQL 压缩备份/临时库恢复和 MinIO 临时对象镜像/恢复校验，临时数据库、对象和文件均已清理；证据见 `docs/evidence/backup-restore-linux-docker-2026-08-15.json`。
- [ ] 以上备份恢复仅覆盖隔离栈演练，MinIO 生命周期策略、生产保留周期、Kubernetes 多节点和外部通知仍需目标环境验收。

## 2026-08-15 MinIO 生命周期部署契约

- [x] 新增 `app.ops_minio_lifecycle` 显式运维命令：默认拒绝执行，仅在 `MINIO_LIFECYCLE_APPLY=true` 时运行；合并时保留非 `atp-managed-*` 规则，避免覆盖外部系统策略。
- [x] Helm 增加默认关闭的 `storageLifecycle` hook，Docker Compose 增加 `storage-lifecycle` profile；默认只清理未完成 multipart upload，过期规则必须绑定非空相对前缀。
- [x] 增加生命周期规则解析、边界校验、外部规则保留和部署契约回归；定向部署/服务测试 `23 passed`。
- [x] 对 `172.31.27.133` 的 `atp` bucket 完成只读 lifecycle 审计：当前无生命周期规则，版本控制/对象锁/复制未启用；证据见 `docs/evidence/minio-lifecycle-audit-2026-08-15.json`。
- [ ] 生产仍需由管理员确认 MinIO bucket 当前规则、对象引用关系和保留周期后，再在目标环境显式启用 hook/profile。

## 2026-08-15 外部通知验收前置检查

- [x] 对目标 `atp` 数据库完成只读通知配置审计：通知配置 `0` 条、启用配置 `0` 条、投递记录 `0` 条；证据见 `docs/evidence/notification-readiness-audit-2026-08-15.json`。
- [ ] SMTP、企业微信、钉钉的真实投递仍需由管理员提供不落库的测试凭据/目标，并完成回执、失败重试、限流和重复投递验收。

## 2026-08-14 Android 性能监控、卡顿检测与异常回放

- [x] Android 专项性能任务新增性能监控、卡顿/FPS、Crash/ANR 监控和异常回放开关，旧任务配置保持兼容。
- [x] Worker 采集 CPU、内存、电量、温度、FPS、慢帧次数，并将 Crash/ANR 的 logcat 与录屏证据写入 MinIO 和专项运行记录。
- [x] Android 报告详情新增设备最新指标卡片、FPS/卡顿/温度趋势选择和报告文件真实下载链接；新增 `replay` artifact 类型及 Alembic 迁移 `20260814_0058`。
- [x] 修复 Android/普通用例实时事件的 ID 串流风险：Redis channel 和 WebSocket 订阅按 `case` / `mobile` 类型隔离，Android 报告使用 `run_type=mobile`。
- [x] `ADB_SCAN_MODE=worker` 时，截图、屏幕流、点击、滑动和 UIAutomator 控件识别均通过 `ANDROID_WORKER_QUEUE` 派发到 Windows Android Worker；公网 API 不再直接调用本机 ADB。
- [x] 性能回放改为按 `replay_seconds`（5-1800 秒）滚动分段录制，设备端最多保留前一段和当前段，避免按整段性能任务时长录屏导致晚期异常没有回放或占满设备空间。
- [x] 修复带千分位 Android meminfo（如 `33,398 KB`）被截断为 `33 KB` 的解析错误；设备租约冲突也写入执行事件时间线；报告事件拉取上限统一为 5000 条。
- [x] 回归验证：后端非集成测试 `2073 passed`，本轮 Android/API/Worker 定向测试 `93 passed`，前端 `50 files / 209 tests passed`，type-check、生产 build、Ruff 与 `git diff --check` 通过。
- [ ] 真实 Crash/ANR 触发和录屏回放仍需在已连接 Android 真机上做一次专门验收；正常性能采样与 Worker 心跳验证已完成。

## 2026-08-14 通知 Webhook 错误信息脱敏收口

- [x] 修复企业微信 `?key=...` 和钉钉 `access_token/sign` 等 Webhook 查询参数可能进入异常文本的问题；服务端统一脱敏 URL 用户信息及敏感查询参数后，才写入日志、投递历史或返回 API 错误。
- [x] 同步通知渠道验收脚本的错误脱敏，避免脚本输出或 JSON 报告暴露 Webhook 凭据。
- [x] 新增企业微信 Webhook `key` 脱敏回归；通知服务与验收脚本定向测试 `23 passed`，Ruff check/format 和 `git diff --check` 通过。
- [ ] 真实 SMTP、企业微信和钉钉公网投递仍需在目标环境完成验收；本地回归不替代供应商后台投递记录。

## 2026-08-14 项目成员 owner 权限完整性

- [x] 修改项目成员角色时锁定 owner 记录并阻止把最后一个 owner 降级为 viewer/editor，避免项目失去可管理者；原有删除最后一个 owner 的保护保持不变。
- [x] 新增项目成员路由回归，覆盖最后 owner 降级拒绝；项目路由定向 `25 passed`，完整非集成后端 `2030 passed`，Ruff 格式和静态检查通过。
- [x] Windows 前端质量门禁：全量 `50 files / 207 tests passed`，type-check 和生产 build 通过。

## 2026-08-13 性能压测停止竞态与自动阶梯边界

- [x] 压测停止接口对父运行和分片运行使用事务行锁，避免停止请求与 Worker 完成更新交叉覆盖状态；节点删除与派发已有的节点行锁保持一致。
- [x] Worker 在执行器返回后再次检查取消标记，用户在最后阶段停止压测时不会被错误记为成功；自动阶梯的无穷大 `max_vus` 也会按非法配置拒绝，而不是触发 500。
- [x] 定向性能 API/Worker/自动阶梯回归 `87 passed`，完整非集成后端回归 `2029 passed`，Ruff 格式和静态检查通过。
- [ ] Linux MCP 当前仍返回 `Transport closed`；真实性能 Worker、Prometheus、TLS/目标服务和取消链路的外部验收继续等待目标环境恢复。

## 2026-08-13 性能压测时长边界防绕过

- [x] 拒绝 `NaN`、无穷大、负数和布尔值等非法性能时长，避免最大运行时长比较失效而绕过资源限制。
- [x] 同时校验顶层时长字段和分阶段时长；性能 API 定向回归 `69 passed`，完整非集成后端 `2027 passed`。
- [ ] Linux MCP 当前仍返回 `Transport closed`，真实性能 Worker、TLS 目标和 Prometheus 仍待外部验收。

## 2026-08-13 通知策略异常范围安全隔离

- [x] 后端校验通知策略的 `scope`、状态筛选和目标 ID 列表，拒绝 API/历史配置中的未知路由值。
- [x] 运行时遇到未知 `scope` 时改为 fail-closed，不再把限定通知意外扩大为全部执行；通知服务/API 定向回归 `35 passed`，完整非集成后端 `2026 passed`。

## 2026-08-13 API Cookie 属性安全恢复

- [x] 恢复项目 API 登录态时保留 Cookie 的 `secure`、`expires`、domain 和 path 属性，避免会话恢复时安全属性降级或过期时间丢失。
- [x] 扩展 Cookie 序列化回归，覆盖安全 Cookie、过期时间、空会话覆盖和旧密钥无效密文降级。

## 2026-08-13 API 登录态清理闭环

- [x] 修复项目级 API Cookie 会话在服务端退出登录/删除 Cookie 后不写回空集合的问题，避免后续用例继续复用旧登录态。
- [x] 增加 API 会话服务回归，验证空 Cookie 集合会覆盖旧 Redis 会话并保留加密与 TTL 约束。
- [x] 本轮 API 会话/HTTP 家族定向 `70 passed`，完整非集成后端 `2023 passed`。

## 2026-08-13 通用用例清空数据集后的配置隔离

- [x] 修复 API/GraphQL/WebSocket/gRPC/iOS 通用抽屉清空数据集后仍写回旧 `dataset_*` 参数化配置的问题；未绑定时只保存协议本身的配置。
- [x] 增加前端入口静态回归，防止后续重新引入无数据集时的参数化残留。

## 2026-08-13 启动依赖诊断原因展示

- [x] 启动配置页的 PostgreSQL、Redis、MinIO 检查结果新增具体原因文案：连接成功、连接超时、无法连接、存储桶不存在，便于 Windows 用户按结果排查地址/端口/服务状态。
- [x] 新增启动配置页回归断言；本轮前端全量 `50 files / 207 tests passed`，type-check、build 和 `git diff --check` 通过。
- [ ] 当前 `172.31.27.133` 仅 PostgreSQL `5432` 从 Windows 可达，Redis `6379`、MinIO `9000` 不可达；Linux MCP 只读检查仍返回 `Transport closed`，远端依赖验收保持待完成。

## 2026-08-13 数据集绑定异步请求隔离

- [x] 修复 Web/Android 共享数据集绑定组件在切换项目或清空数据集时，旧请求未返回导致数据集/版本 loading 状态卡住的问题。
- [x] 请求序列变化时立即清空旧选项并结束无效 loading；旧请求返回后不会覆盖当前项目或绑定状态。
- [x] 新增 2 个前端回归用例；本轮前端全量 `50 files / 207 tests passed`，type-check、build 和 `git diff --check` 通过。

## 2026-08-13 通用用例数据集版本固定

- [x] API/GraphQL/WebSocket/gRPC/iOS 通用用例抽屉增加数据集版本选择；创建、编辑、切换数据集和清空绑定都会同步维护 `dataset_version`。
- [x] 数据集版本不存在时不会继续展示失效选项，运行时未固定版本仍按后端语义使用最新版本；补充前端入口静态回归。
- [x] 本轮验证：后端非集成 `2022 passed`，前端 `49 files / 205 tests passed`，type-check 和 build 通过。

## 2026-08-13 Web/Android 专用用例数据集绑定

- [x] Web/Android 专用抽屉增加项目数据集、固定版本、严格 Schema、组合策略、最大迭代数和结果脱敏字段配置；创建与编辑都会保存 `dataset_id`、`dataset_version` 及对应运行配置。
- [x] 抽取共享数据集绑定组件，数据集切换后自动加载版本列表；清空绑定时同步移除旧的参数化配置，避免编辑保存残留。
- [x] Web/Android 回归覆盖新建与编辑数据集绑定；前端全量 `49 files / 205 tests passed`，type-check、build 通过。

## 2026-08-13 发布前部署校验严格模式

- [x] `validate-deployment-readiness.py` 增加 `--strict`：默认模式明确记录 Docker/Compose、Helm、`.env` 或 POSIX shell 缺失为 `SKIP`，严格模式将环境缺失转为失败。
- [x] Makefile 支持 `make validate-deployment-readiness ARGS=--strict`；该门禁只强化判定语义，不替代真实 Linux/Kubernetes、备份恢复或性能 Worker 验收。
- [ ] 本次继续尝试读取配置 Linux 主机仍遇到 MCP `Transport closed`；性能 Worker、Prometheus、TLS/目标服务和资源采样保持外部待验收，不以本地回归代替。

## 2026-08-13 Web/Android 专用入口收口

- [x] 通用 `CaseFormDrawer` 不再暴露 Web/Android 类型或显示后续实现占位提示；CaseList 统一使用专用 Web/Android 抽屉，避免用户进入不可配置的入口。
- [x] 增加前端静态回归，确认专用抽屉挂载且占位文案已移除；真实 Worker/Android 设备执行仍按外部验收边界处理。
- [x] 本轮验证：后端非集成 `2021 passed`，前端 `49 files / 203 tests passed`，type-check/build、Ruff 和 `git diff --check` 通过。

## 2026-08-13 Web/Android 低代码关键流程回归收口

- [x] 新增 Web/Android 专用用例抽屉创建与编辑回归，覆盖低代码步骤写入、Android 标准步骤生成和关键执行配置保存。
- [x] 修复 Web 用例编辑时浏览器配置被无条件重置为 Chromium 的问题，编辑 Firefox/WebKit 用例后保存不再静默改写浏览器。
- [x] 本轮前端定向 `4 passed`，全量 `49 files / 203 tests passed`，type-check 通过；真实 Worker/Android 设备仍需按计划单独验收。

## 2026-08-13 存储治理自定义前缀执行修复

- [x] 清理执行接口透传预览前缀，支持自定义 StoragePolicy 对象正确删除；默认调用仍兼容内置前缀。
- [x] maintenance 定时清理同步传入单条策略前缀；存储 API/服务/清理任务回归 `29 passed`，Ruff 通过。

## 2026-08-13 项目级运行记录清理范围修复

- [x] 清理页面主预览同时加载全局与项目覆盖预览，避免仅项目覆盖策略命中时按钮错误置灰。
- [x] 确认提示统一统计全局/项目级运行记录、对象估算和抽样状态；RunRetentionView 回归 `2 passed`，type-check/build 通过。

## 2026-08-13 性能节点删除并发保护收口

- [x] 删除节点与压测派发共用行级锁，避免节点检查与删除之间插入新的活动运行。
- [x] 性能 API 回归 `68 passed`，Ruff 通过；外部 Redis/MinIO、Linux/Kubernetes Worker 和真实通知渠道继续等待目标环境验收。

## 2026-08-13 启动配置依赖连接检查

- [x] 新增只读依赖检查接口，并行探测 PostgreSQL、Redis、MinIO，状态响应不泄露连接地址、账号、密码或异常详情。
- [x] 依赖探测路由限制为管理员，保留公开 `/health` 作为轻量存活探针，避免公开接口触发高成本外部连接。
- [x] 启动配置页增加当前连接检测按钮和三项状态/耗时展示；当前 172 环境已确认 PostgreSQL 可用，Redis/MinIO 不可达。
- [x] 后端定向 `4 passed`、StartupConfigView `6 passed`、Ruff/type-check 和真实接口检查通过。
- [x] 最新完整门禁：后端非集成 `2018 passed`，覆盖率 `82.03%`（门禁 82%）；`269` 个测试文件逐文件独立通过；前端 `47 files / 199 tests passed`，type-check/build、Ruff、format-check 和 mypy 通过。
- [x] Python 3.14.3 条件依赖环境复跑完整非集成后端 `2018 passed`；覆盖率门禁以 CI 使用的 Python 3.12.11 为准。
- [x] 发布前安全/配置门禁：Bandit、npm audit、pip-audit（锁定 requirements 模式）、pre-commit 和部署配置校验通过；Docker/Helm 工具缺失时按约定跳过真实工具检查。

## 2026-08-13 Windows 冒烟依赖分项检查

- [x] Windows 全量冒烟在登录后检查 `/api/v1/health/dependencies`，输出 PostgreSQL、Redis、MinIO 的分项状态、错误码和耗时。
- [x] Redis/MinIO 不可达时直接标记必需检查失败，避免后续文件传输、Worker 或报告检查产生级联误报。
- [ ] 当前远端 Redis/MinIO 仍不可达，恢复后需重新执行带脱敏报告的完整冒烟。

## 2026-08-13 Windows Mock E2E 选择器隔离修复

- [x] 修复计划页项目选择器同时命中已选值和下拉选项导致的 Playwright strict mode 失败，并分离页面目标文本与项目选项文本。
- [x] Chromium Mock E2E 全量 `10 passed`。

## 2026-08-13 Windows 当前启动档案冒烟复核

- [x] Windows 冒烟脚本新增 `-LiveRequestTimeoutSeconds`，解决远端 PostgreSQL 慢响应时固定 10 秒造成的认证误报；相关脚本契约回归 `10 passed`。
- [x] 重启项目并确认当前运行档案为根 `.env` / `172.31.27.133`；登录、认证读接口、项目列表和 Web Worker 状态接口通过。
- [ ] `172.31.27.133:6379` Redis、`:9000` MinIO 从 Windows 不可达；远端服务/防火墙恢复后再补完整冒烟证据。

## 2026-08-13 仪表盘 iOS 类型筛选补齐

- [x] 仪表盘类型筛选新增 iOS 选项，避免 iOS 执行数据无法按类型查看。
- [x] 增加 Dashboard 回归测试；前端全量回归 `46 files / 194 tests passed`，type-check/build 和 `git diff --check` 通过。

## 2026-08-13 性能节点删除生命周期保护

- [x] 删除性能节点前检查活动压测运行和启用中的定时任务，存在引用时明确返回 `409`，不再静默解除节点绑定。
- [x] 保留已完成运行记录；无活动运行且无启用定时任务时允许删除。
- [x] 性能 API 定向回归 `68 passed`；后端完整非集成回归 `2008 passed`、覆盖率 `82.12%`；前端回归 `46 files / 193 tests passed`，type-check/build 和 `git diff --check` 通过。

## 2026-08-13 通知渠道配置校验补强

- [x] 新建通知配置时校验邮件收件人和企业微信/钉钉 `webhook_url`，拒绝空配置或脱敏占位符。
- [x] 通知发送入口重复校验最小投递目标，避免历史空配置被记录为“发送成功”；仅修改名称/启用状态时保留兼容性。
- [x] 通知 API/服务定向回归 `32 passed`，并覆盖缺少投递目标时不调用发送器；NotificationList `5 passed`，全量前端 `46 files / 192 tests passed`，type-check/build 通过。
- [x] 通知测试发送完成或失败后自动刷新最近投递历史，页面可立即看到本次投递结果；NotificationList 回归保持 `5 passed`。

## 2026-08-13 运行记录清理预览刷新

- [x] 执行运行记录清理后同时刷新全局预览和项目级预览，避免项目级数量仍显示清理前的旧数据。
- [x] 新增 RunRetentionView 页面回归，验证清理成功后两类预览都重新请求；前端全量 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 运行记录清理对象安全顺序

- [x] 清理运行记录时先提交数据库删除，再删除关联 MinIO 对象；数据库提交失败会保留对象，避免运行记录仍存在但附件不可恢复。
- [x] MinIO 删除失败只形成可由存储治理发现的孤儿对象；新增提交顺序和失败保护回归，运行记录服务定向 `10 passed`。

## 2026-08-13 运行记录清理对象数语义补强

- [x] 预览接口返回 `estimated_objects_sampled`，当候选 TestRun/MobileRun 超过清理批大小时明确标记对象数仅基于首批记录估算。
- [x] 全局预览、按项目预览和执行确认提示展示抽样标识，避免把大数据量下的对象估算误认为精确数量。
- [x] 后端完整非集成回归 `2005 passed`、覆盖率门禁 `82.10%`；前端 `46 files / 192 tests passed`，type-check/build 通过。

## 2026-08-13 按项目清理预览补全

- [x] 按项目预览表格补齐 Plan、Suite、Test、Mobile 四类运行记录和项目级对象估算，展示范围与实际清理范围一致。
- [x] 项目级对象估算复用批量抽样边界，并在超过批大小时显示抽样标识；补充服务回归，避免只展示部分运行类型造成误判。

## 2026-08-13 按项目预览 API 契约收口

- [x] 启用按项目预览路由的 `response_model`，并将内部 `global_` 字段显式映射为前端使用的 `global` JSON 字段。
- [x] 新增 API 契约回归，覆盖全局对象估算、抽样标记和项目 TestRun 数量映射。

## 2026-08-13 通知配置响应脱敏补强

- [x] 修复通知配置新建和更新接口直接返回数据库对象的问题；响应现在与列表/详情接口统一经过脱敏，webhook、secret 等敏感字段只返回 `******`。
- [x] 补充新建/更新响应和底层加密值回归，通知 API 定向回归 `14 passed`；Ruff、格式检查和 `git diff --check` 通过。

## 2026-08-13 通知渠道真实环境验收入口

- [x] 新增 `scripts/notification-channel-smoke.py`，通过 `ATP_TOKEN` 或工程师账号环境变量调用现有测试发送接口，并核对投递历史中的新记录。
- [x] 验收脚本只输出配置 ID、渠道、状态、尝试次数和脱敏错误；不接受命令行密码/Token，也不把凭据写入报告。
- [x] 补充脚本契约测试 `3 passed` 和操作说明 `docs/notification-channel-acceptance.md`。
- [ ] 真实 SMTP、企业微信和钉钉公网联调仍需目标环境凭据、供应商后台投递记录和重复投递验收。

## 2026-08-13 通知服务测试隔离修复

- [x] 修复通知服务测试单独运行时依赖其他测试导入 `Project`/其他模型的问题；测试文件现在显式加载应用启动使用的完整 ORM 模型注册表。
- [x] `backend/tests/services` 独立扫描 `74 passed, 0 failed`；`backend/tests/worker` 独立扫描 `42 passed, 0 failed`。
- [x] API 及其余测试文件独立扫描通过；当前非集成后端全量 `2018 passed`，共 `269` 个测试文件逐文件通过。
- [x] 新增验收脚本已同步到 Makefile、CI 和 pre-commit 的 Ruff/格式检查清单，质量一致性回归恢复通过。

## 2026-08-13 通知错误信息脱敏

- [x] 统一重试、SMTP、企业微信、钉钉和测试发送 API 的异常脱敏，过滤 URL 用户信息、Token、Key、Secret、Password、签名和 Cookie 等敏感值。
- [x] 错误摘要同时清理 CR/LF/NUL，避免供应商异常文本形成日志注入；通知/API/服务定向 `36 passed`，完整非集成后端 `1992 passed`。

## 2026-08-13 通知历史清理审计

- [x] `cleanup_old_notification_deliveries` 删除记录时写入 `notification_delivery_cleanup` 系统审计事件，记录删除数量和保留天数，并与删除操作同事务提交。
- [ ] 生产环境仍需结合备份/归档要求确认审计日志保留周期和外部归档方式。

## 2026-08-13 通知投递记录写入容错

- [x] 将投递记录 `add/add_all`、提交和回滚统一纳入保护边界；记录持久化失败只记录日志，不反向打断测试发送或执行通知。
- [x] 补充新增记录失败与提交回滚回归，通知服务定向测试更新为 `16 passed`。

## 2026-08-13 历史投递记录读取脱敏

- [x] 投递历史查询 API 在读取出口再次执行错误摘要脱敏，兼容清理上线前已经保存的旧记录，避免旧敏感内容通过前端或接口重新暴露。
- [x] 增加历史记录 Token/换行内容回归，API/通知服务定向测试 `30 passed`。

## 2026-08-13 覆盖率门禁复核

- [x] 后端覆盖率门禁通过：`82.10%`，要求 `82%`；同次非集成回归 `2005 passed`。

## 2026-08-13 外部目标连接复核

- [ ] Linux 目标只读 MCP 系统概览最近一次仍返回 `Transport closed`，未取得外部主机、性能 Worker、Prometheus 或真实目标证据；连接恢复后继续执行 Linux/Kubernetes 验收。

## 2026-08-13 Web 录制 Worker 心跳容错

- [x] Web 录制 Worker 的初始注册和持续心跳同时兜底底层 Redis 客户端的普通异常；心跳失败会清理健康文件并继续重试，避免协程退出后留下过期健康状态。
- [x] 新增 Worker 心跳异常和启动残留标记回归；Web 录制/API/部署契约定向回归 `55 passed`，Ruff 检查和格式检查通过。

## 2026-08-13 Web Worker 外部验收入口

- [x] 新增 `scripts/web-recording-worker-smoke.py`：默认只检查 Worker 模式、注册数和可用容量，只有显式 `--run-recording` 才执行真实启动、状态查询、可选截图和停止。
- [x] 验收脚本只使用 `ATP_TOKEN` 或 `ATP_USERNAME`/`ATP_PASSWORD`，报告脱敏 URL、错误和输入；已加入 Makefile、CI 与 pre-commit 的脚本门禁。
- [x] 脚本契约与质量门禁一致性回归 `14 passed`；真实 Linux/Xvfb、Firefox/WebKit 和跨副本录制仍需目标环境执行。

## 2026-08-13 Linux/Kubernetes 性能栈完善

- [x] 修复手动、Webhook 和定时任务在多 API/Beat 副本同时派发压测时的性能节点容量竞态，节点选择与 `max_concurrency` 校验改为同一数据库行锁事务。
- [x] 补充节点容量锁、draining、队列路由和心跳超时回归；真实 Linux/Kubernetes、Prometheus、TLS、目标服务和资源采样继续单独验收。
- [x] 性能相关定向回归 `91 passed`，完整非集成后端 `1988 passed`，Ruff 和格式检查通过。
- [x] 手动触发和 Webhook 增加显式幂等键；同键同请求复用已有 Run，同键不同请求返回 `409`，并补充数据库唯一约束和前端触发键。
- [x] 性能环境验收脚本同步携带幂等键：支持 `--idempotency-key`/`ATP_PERFORMANCE_IDEMPOTENCY_KEY`，CI 可重试复用，本地默认生成新键，并区分 smoke/cancel 作用域。
- [x] 性能验收支持 `--require-metric-source`，要求指定 Worker 或目标 Prometheus 来源至少返回一条非空指标样本，避免空样本/错误样本被记为通过。
- [x] 性能验收支持 `--require-baseline` 与 `--fail-on-baseline-regression`，可把基线对比和回归方向纳入真实环境验收退出码。

## 2026-08-13 通知渠道可靠性收口

- [x] 通知发送统一经过有限重试链路；默认不重试，保持历史配置行为不变。
- [x] 仅对网络超时/连接失败、HTTP 5xx 和 429 重试，供应商拒绝、错误 Webhook 和其他配置错误不重复发送；重试次数上限 3 次，退避上限 30 秒。
- [x] 通知测试发送复用与执行通知相同的重试策略，通知配置页增加失败重试次数和首次退避等待配置。
- [x] 补充通知服务/API/前端回归；通知配置页面 `4 passed`；完整非集成后端 `1988 passed`。
- [ ] 邮件、企业微信、钉钉真实公网渠道联调和供应商限流策略仍需目标环境验收。

## 2026-08-13 通知投递结果可观测性

- [x] 新增 `notification_deliveries` 投递历史表，记录渠道、成功/失败状态、实际尝试次数、脱敏摘要和脱敏失败原因；通知配置删除后保留历史并解除配置引用。
- [x] 执行通知和测试发送均写入投递结果；新增工程师可读的项目范围查询接口和通知配置页“最近投递记录”表格。
- [x] 补充投递历史模型、迁移、服务/API/前端回归；完整迁移头更新为 `20260813_0057`。
- [ ] 真实外部渠道联调仍需确认供应商返回码、限流、重复投递和历史保留周期。

## 2026-08-13 通知投递历史保留策略

- [x] 新增 `NOTIFICATION_DELIVERY_CLEANUP_ENABLED` 和 `NOTIFICATION_DELIVERY_RETENTION_DAYS` 启动配置，默认开启、保留 30 天，天数限制为 1-3650。
- [x] Beat 每日调度维护队列任务 `cleanup_old_notification_deliveries`，按创建时间删除过期投递历史；关闭开关时不创建数据库会话。
- [x] 启动配置 UI、`.env.example`、启动配置文档和用户手册同步新增两个参数，并补充清理任务回归。
- [ ] 生产环境仍需根据合规/审计要求决定保留周期或数据库归档策略。

## 2026-08-13 审计日志保留策略

- [x] 新增 `AUDIT_LOG_CLEANUP_ENABLED`（默认关闭）和 `AUDIT_LOG_RETENTION_DAYS`（默认 365，范围 1-3650），未确认合规策略前不会自动删除审计记录。
- [x] 新增每日 maintenance 清理任务，并在删除成功时写入 `audit_log_cleanup` 审计事件；删除与事件写入同事务，异常整体回滚。
- [x] 启动配置 UI、`.env.example`、启动配置文档和用户手册已同步；配置边界、清理任务和队列路由回归通过。
- [ ] 生产环境仍需确认审计日志归档、保留周期和合规访问策略。

## 2026-08-13 审计日志时间范围查询

- [x] 管理员审计日志 API 增加 `created_from` / `created_to` ISO-8601 时间筛选，既有项目、用户、动作筛选和分页行为保持兼容。
- [x] 结束时间早于开始时间时返回 `422`，前端新增带时间范围选择器并支持重置；补充 API/前端回归。
- [x] 本轮门禁：后端非集成 `2017 passed`；前端 `47 files / 198 tests passed`，type-check/build 通过。

## 2026-08-13 审计日志 CSV 导出

- [x] 管理员可按当前项目、用户、动作和时间筛选导出审计日志 CSV；页面上限 5000 条，服务端上限 10000 条。
- [x] 导出复用权限和筛选条件，使用 UTF-8 BOM，并对可能被表格软件解释为公式的文本做保护；成功导出写入 `audit_log_export` 审计事件，记录操作者、筛选摘要、上限和条数。
- [x] 审计页面动作筛选补齐清理和导出事件，便于直接核对治理操作。
- [x] 补充 API、权限/边界和前端下载回归。
- [x] 本轮门禁：后端非集成 `2018 passed`；前端 `47 files / 199 tests passed`，type-check/build 通过。
- [ ] 生产环境仍需确认导出审批、审计留痕、归档和进一步脱敏策略。

## 2026-08-12 本轮开发收口

- [x] 完成 Mock 条件匹配与多规则确定性优先级；数据集准备动作增加公网 URL/DNS 安全校验，显式拒绝非数组配置。
- [x] 完成 MinIO 数据集元数据响应、存储表格行模型和项目导入导出存储模式支持；大数据集按 50MB 校验并在导入失败时清理已上传对象。
- [x] 最终验证：非集成后端 `1967 passed`；前端 `45 files / 188 tests passed`；type-check、build、Ruff、格式检查和 `git diff --check` 通过。

## 2026-08-12 Mock 条件响应增强

- [x] 保留原有字符串精确匹配，并新增受控 `$exists`、`$contains`、`$in` 条件操作符，支持 Query、Header 和 Body 三类请求数据。
- [x] 接口边界拒绝未知操作符、复合操作符、复杂 `$in` 值和超大条件集合；运行时对历史异常 JSON 安全按“不命中”处理，不执行用户代码或正则表达式。
- [x] 规则选择改为确定性优先级：HTTP 方法精确匹配优先，路径静态段更具体优先，条件字段更多优先，最后才按规则 ID 倒序；新增同路径条件冲突和模板路径冲突回归。
- [x] Mock 页面同步支持非字符串 JSON 条件，并在编辑表单提示操作符示例；补充创建校验、运行匹配和未知数据回归测试。
- [x] 数据集准备请求统一经过公网 URL/DNS 校验，拒绝本机、内网、链路本地和保留地址；非数组动作配置会明确失败，不再静默跳过。
- [x] MinIO 数据集只修改元数据时仍回读当前对象并返回完整 rows；存储核对表格将孤儿对象字符串转换为带 `object_name` 的行模型。
- [x] 定向 Mock 后端回归 `34 passed`，完整非集成后端 `1967 passed`，前端 Mock 页面 `5 passed`、全量前端 `45 files / 188 tests passed`，type-check/build、Ruff 与 `git diff --check` 通过；真实业务接口分流仍需结合项目规则验收。

## 2026-08-12 运行级数据准备 Hook

- [x] 新增受限 `dataset_prepare_actions` DSL：支持共享变量设置/删除、HTTP seed 请求、状态/响应断言和响应变量提取；不执行 Python/JavaScript。
- [x] 参数化 Worker 在创建子运行前只执行一次准备动作；提取变量注入所有子运行，行字段同名时优先使用行数据；准备失败时不创建子运行并记录父运行摘要。
- [x] 增加动作数量、HTTP 方法、超时和响应体大小限制，补充服务层与 Worker 回归测试及 CaseFormDrawer 配置入口。
- [x] 修复 MinIO 数据集上传/预览仍误用数据库 500 行限制的问题；MinIO 入口现在按 50MB 对象上限校验，并补充 501 行上传与预览回归。
- [x] 最新门禁：后端非集成 `1944 passed`，264 个测试文件独立运行 `264 passed, 0 failed`；前端 `45 files / 183 tests passed`，type-check/build、Ruff、格式、mypy 和 `git diff --check` 通过。
- [x] 同步 `docs/dataset-v2.md` 与用户操作手册；真实测试服务 seed、真实 MinIO 大数据量和对象生命周期仍需环境验收。

## 2026-08-12 MinIO 数据集对象生命周期治理

- [x] 新增 `POST /api/v1/projects/{project_id}/datasets/storage/reconcile` 管理员接口，默认只读核对项目范围内的 MinIO 对象与 PostgreSQL 当前/版本引用。
- [x] 仅显式传 `{ "purge": true }` 才清理孤儿对象；删除严格限制在项目 `datasets/{project_id}/` 前缀，逐项返回删除失败，并记录审计事件。
- [x] 更新/上传/回滚先写唯一当前对象，数据库提交成功后才删除旧对象；提交或版本快照失败时清理本次新对象并保留旧引用。
- [x] 补充对象清单、干运行、部分删除失败、项目外对象隔离、API 引用收集和事务失败补偿回归测试；服务/API 定向回归 `33 passed`。
- [x] 2026-08-13 使用隔离的真实 MinIO 完成 25,000 行/10.55MB 回读、dry-run/purge、提交失败补偿、50MB 限制、备份恢复和只读 IAM 验收；证据见 `docs/evidence/minio-dataset-acceptance-2026-08-13.json`。
- [ ] 发布 staging 仍需使用目标 IAM 与备份拓扑重跑同一脚本；定期治理调度按发布环境策略配置。

## 2026-08-12 存储容量告警入口

- [x] 存储管理页接入现有 `GET /api/v1/storage/alert`，展示容量正常/告警状态、当前占用 GB、阈值和触发时间。
- [x] 告警支持单独刷新；告警接口失败只提示，不阻断存储统计、清理策略和数据集对象治理。
- [x] 补充中英文文案和回归测试；存储页面 `8 passed`，前端全量 `45 files / 185 tests passed`，type-check/build 通过。

## 2026-08-12 执行记录清理预览一致性

- [x] 全局保留预览现在复用实际清理的项目范围：排除设置了保留天数覆盖的项目，避免与项目级预览重复计数。
- [x] Plan、Suite、TestRun、MobileSpecialRun 四类记录均支持项目范围过滤；前端提示和用户手册同步说明预览/执行一致性。
- [x] 新增排除项目范围的 SQL 回归，执行记录保留相关定向回归 `18 passed`。
- [x] 执行完成后前端展示各项目的实际删除明细；前端回归 `45 files / 183 tests passed`，type-check/build 通过。

## 2026-08-12 性能 Run 通知闭环

- [x] 性能 Worker 的提前终止分支统一复用通知路径：测试定义缺失、执行器未启用、节点不匹配/不可用/不支持执行器、节点容量不足和启动前取消都会先落库，再发送项目级通知。
- [x] 性能通知保留正常完成、阈值失败、基线回归、节点异常和资源采样异常摘要，并在正文展示 RPS、P95/P99、错误率、阈值状态和触发原因；发送失败只记录 Worker 日志，不回滚已经完成的 Run 状态。
- [x] 增加缺失测试与启动前取消的通知回归；性能 Worker/通知定向回归 `14 passed`，操作手册同步说明项目通道匹配规则。
- [x] 2026-08-13 增加真实 SMTP/企微/钉钉验收脚本，并修复空收件人/空 Webhook 被误报为成功、Webhook 投递时缺少公网 DNS 复核和邮件地址换行注入问题；API/Notifier 定向回归 `29 passed`。
- [ ] 当前环境未配置 SMTP、企微或钉钉供应商凭据；三个渠道的真实接收端证据需注入 sandbox 凭据后分别执行并归档。

## 2026-08-12 Q18 发布就绪清单补强

- [x] 将 `docs/q9-release-checklist.md` 升级为 Q18 扩展版，修正当前后端覆盖率门禁为 82%，并补充 MinIO 数据集治理、运行记录清理、性能通知、Windows Android、Linux/Kubernetes 性能、Web/iOS 外部验收要求。
- [x] 在 `docs/q9-release-evidence.md` 增加 Q18 本地门禁快照和外部证据待办，明确本地测试不能替代真实 MinIO、通知渠道、设备和目标环境验收。
- [x] 发布/灾备文档契约回归 `23 passed`；真实 staging、备份恢复和外部 Worker 证据仍保持阻塞标记。

## 2026-08-12 测试套件并行会话隔离

- [x] 修复并行套件复用同一个 SQLAlchemy `AsyncSession` 的风险；每个并行子用例现在创建独立数据库会话，避免并发事务冲突。
- [x] 顺序执行和测试桩路径保持兼容；套件配置与执行链定向回归 `43 passed`，Ruff 通过。

## 2026-08-12 API 登录态复用与套件边界

- [x] 创建/编辑并行套件时校验 API 用例的 `session_lifecycle`；开启项目登录态复用的 API 用例不能进入并行套件，避免 Cookie 读写顺序不确定。
- [x] SuiteList 保存失败时透传后端具体错误，串行套件仍保留按用例选择登录态复用的能力。
- [x] 后端套件校验 `20 passed`、SuiteList `6 passed`、type-check 和 Ruff 通过。

## 2026-08-12 下一阶段开发计划同步

详细计划统一记录在 [`docs/next-development-plan-2026-08-12.md`](docs/next-development-plan-2026-08-12.md)，当前执行顺序如下：

- [~] P1：Windows 真实 Android 设备验收；ADB 设备检查、Package Manager/logcat 可读性、可选 APK 包校验和脱敏 JSON 证据入口已完成；真实设备连接后再执行验收。
- [~] P1：Linux/Kubernetes 性能栈真实验收；已补充 Prometheus readiness/PromQL 验收入口和安全校验，真实专用 Worker、TLS/HTTP/gRPC/Locust/JMeter 目标、取消、allowlist、资源采样及生产 Prometheus 仍待目标环境执行。
- [~] P1：Web 专用 Worker 真实验收；已补充 Redis 心跳健康标记、Compose/Helm readiness/liveness 探针和浏览器矩阵 Trace/HAR/网络/Console 证据，Windows 三浏览器本机矩阵已通过（见 [`docs/evidence/web-browser-matrix-local-smoke-2026-08-12.json`](docs/evidence/web-browser-matrix-local-smoke-2026-08-12.json)），Linux/Xvfb、Firefox/WebKit Worker、跨副本路由和 E2E 仍待目标环境。
- [~] P1：macOS/iOS/Appium 最小真实闭环；已新增 Appium status/session smoke、受控步骤、截图/录屏/syslog 脱敏证据入口，真实 macOS Worker、Simulator/iPhone、IPA、XCUITest、设备租约和统一 ATP run 仍待目标环境。
- [~] P2：产品化收口；大型数据集 MinIO 引用模式、项目级运行记录清理和性能 Run 提前终止通知代码闭环已完成，真实 MinIO 治理、外部通知渠道、关键流程 E2E、覆盖率和发布 Runbook 仍待推进。

## 2026-08-12 大型测试数据集 MinIO 引用模式

- [x] `test_datasets` / `test_dataset_versions` 增加 `storage_mode`、`object_name` 和 `row_count`，Alembic `20260812_0055` 为历史数据库行数回填元数据。
- [x] 数据集 CRUD、上传、版本快照/回滚支持 `database` 与 `minio`；MinIO 当前对象和版本对象按项目/数据集隔离，写入失败明确返回错误。
- [x] 用例参数化、性能数据集、AI 上下文和项目导出统一读取 MinIO 引用；列表缓存会在数据集变更后失效。
- [x] 数据集管理页增加存储方式选择；后端数据集/存储/迁移回归 `45 passed`，前端 DatasetLibrary `8 passed`、type-check 通过。
- [~] 真实 MinIO 集群大数据量、对象生命周期治理和数据准备 Hook 的目标环境验收仍待完成；代码入口与回归测试已补齐。

## 2026-08-12 Windows Android SDK/ADB 路径发现

- [x] 统一 `windows-local.ps1`、`windows-android-worker.ps1` 和 `android-network-doctor.ps1` 的 ADB 路径发现：支持 `ATP_ADB_HOME`、`ANDROID_HOME`/`ANDROID_SDK_ROOT`、用户级 Android SDK 目录和 ATP 工具目录；只注入当前进程及子进程，不修改系统 PATH。
- [x] Android Worker 在加载选中启动档案后重新刷新工具路径，避免档案内的 SDK 路径直到下次打开 PowerShell 才生效；新增 12 项 Windows 合约回归，PowerShell 解析通过。
- [ ] 当前 Windows 主机仍无在线 Android 设备；设备扫描、真实 Android 用例和设备日志回传仍待连接真实设备后验收。

## 2026-08-12 性能目标指标 UI

- [x] 性能中心新建/编辑压测定义增加 Prometheus 目标指标配置区：支持直填 URL 或环境变量、查询超时和多条 PromQL，保存时合并到 `default_options.target_metrics`。
- [x] 压测执行详情增加指标来源切换，可分别查看 Worker 资源样本和 `target-service-prometheus` 目标服务样本；未知 Prometheus 指标名也能直接展示。
- [x] `PerformanceCenterView.spec.ts` 增加目标指标保存与不安全 URL 拒绝回归；前端全量 `44 files / 180 tests passed`，`vue-tsc --noEmit` 和生产构建通过。

## 2026-08-12 Windows 本地 Prometheus 目标指标闭环

- [x] 安装并校验官方 Prometheus Windows amd64 `v3.13.1`，放在 `%LOCALAPPDATA%\ATP\tools\prometheus`；不修改系统 PATH。
- [x] 新增 `config/prometheus/windows-local.yml` 和 `scripts/windows-prometheus.ps1`，支持 `doctor/up/down/restart/status/logs`，仅监听 `127.0.0.1:9090` 并抓取 ATP Backend `/metrics`。
- [x] 真实验证 Prometheus readiness=200、`atp-backend` target 为 `up`，k6 run `11` 成功并产生 6 条采样，其中 3 条为 `target-service-prometheus`，无采样错误；证据见 [`docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json`](docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json)。
- [ ] 真实外部目标、Linux/Kubernetes Prometheus、生产 SLO 连续历史和告警仍需独立环境验收；本机回环目标不替代生产结论。

## 2026-08-12 Windows k6 本地发现

- [x] 安装并验证 Windows `k6 v2.2.0`，安装目录为 `%LOCALAPPDATA%\ATP\tools\k6`。
- [x] 启动脚本自动发现 `ATP_K6_HOME` 或默认用户工具目录，并将路径仅注入当前启动进程及其子 Worker；不修改仓库配置和机器级 PATH。
- [x] `windows-local.ps1 doctor` 已显示 k6 可用；本机 `/health` 真实 k6 已完成，真实外部目标压测仍待目标环境准备后验收。

## 2026-08-12 Windows k6/Locust 平台真实执行

- [x] 主 Worker 节点 `perf-node-local-01` 已在线并声明 `k6,locust,grpc`；独立性能 Agent `performance-win-worker-a` 仍隔离在 `performance.worker-a`，声明 `jmeter,grpc`。
- [x] k6 测试定义 `7` / run `8` 在本机 ATP `/health` 目标真实执行成功：20 次迭代、错误率 0、3 条资源指标，证据见 `docs/evidence/performance-windows-local-k6-smoke-2026-08-12.json`。
- [x] 修复 Locust Windows Worker 使用裸命令导致的 `WinError 2`，改用当前 Worker Python 的 `sys.executable -m locust`；测试定义 `8` / run `10` 真实执行成功：168 次请求、错误率 0，证据见 `docs/evidence/performance-windows-local-locust-smoke-2026-08-12.json`。
- [ ] 真实外部目标、Linux/Kubernetes、Prometheus 和 Android 设备验收仍需独立环境，不以本机 `/health` 结果替代。

## 2026-08-12 Locust 依赖与服务恢复
- [x] 停止占用共享 Python venv 的本地服务和性能 Agent，安装 `locust 2.32.10` 及 Windows 依赖；临时目录中的 Locust 版本检查通过。
- [x] Windows doctor 现在对根 `.env` 报告 Locust 可用，仅保留 k6 和 Android 设备两个可选警告。
- [x] 172.31.27.133 的 PostgreSQL 握手仍超时；为保持本机服务可用，当前运行态使用已验收的 `remote-infra.env`（163.192.40.209），根目录 `.env` 未改写；性能 Agent 已按原档案恢复。
- [x] `windows-local.ps1 status` 增加脱敏运行元数据，显示实际运行档案、基础设施地址和队列；停止服务时自动清理，避免传入未运行的 `.env` 造成误判。

## 2026-08-12 外部基础设施文档去敏
- [x] 移除 `docs/external-infra-run.md` 中旧公网地址、管理员账号和明文密码，改为环境变量占位符。
- [x] 补充数据库、Redis、MinIO、初始管理员凭据的部署前检查和禁止提交说明。

## 2026-08-12 启动配置档案安全占位符
- [x] 远端、Android Agent 和性能 Agent 档案移除特定环境的 PostgreSQL/MinIO 用户名，改为 `<database-user>` / `<minio-user>` 占位符。
- [x] 启动配置必填检查覆盖主机和基础设施用户名；新增回归断言，避免复制档案后静默沿用旧环境连接信息。
- [x] `StartupConfigView.spec.ts`：`5 passed`；前端全量回归 `44 files / 178 tests passed`、类型检查通过；同步 `docs/startup-config.md` 与 `docs/windows-local-run.md` 的填写说明。

## 2026-08-12 Windows 全量本地冒烟与数据源核对
- [x] 使用根目录 `.env` 执行 `scripts/windows-local-smoke.ps1 -SkipBrowserMatrix`：Backend/Frontend 健康、管理员 HttpOnly 会话、当前用户/项目读接口、10 条 Playwright E2E、文件上传/清理、HTML/JUnit 报告全部通过。
- [x] 核对当前主线数据源：`local-all` 的根 `.env` 已指向 `172.31.27.133`；本次冒烟报告已记录为 [`docs/evidence/windows-local-smoke-2026-08-12.json`](docs/evidence/windows-local-smoke-2026-08-12.json)。
- [ ] 独立 `performance-agent.env` 仍指向 `163.192.40.209`，并使用 `jmeter,grpc`；如要让性能 Agent 加入当前 `172.31.27.133` 项目，必须先同步该档案的地址和凭据，再重启 Agent。
- [x] 当前 Windows 环境已补齐 k6、Locust；[ ] Android 在线设备仍缺少，本次仅作为可选 warning/skip，不将其标为完成。

## 2026-08-12 Windows JMeter 执行链路修复与验收
- [x] 修复 Windows `.bat` 执行器停止逻辑：通过 `taskkill /T /F` 递归回收 `cmd.exe -> Java` 子进程树，避免 JMeter 取消或超时后遗留 Java 进程锁定 `stderr.log`。
- [x] 新增 `backend/tests/services/test_performance_process.py`，覆盖 Windows 进程树回收和 Unix 优雅停止/强制停止两个分支。
- [x] 回归验证通过：JMeter/性能相关测试 `90 passed`，完整 Worker 测试 `427 passed`，非集成后端总回归 `1897 passed`，Ruff 与 `git diff --check` 通过。
- [x] Windows 专用 Worker 在 `performance.worker-a` 队列完成 JMeter 真实执行：run `6` 成功、1 次请求、错误率 `0`、资源采样 12 条且无采样错误；临时目录和 JMeter 进程树均已清理。证据见 [`docs/evidence/performance-windows-jmeter-smoke-2026-08-12.json`](docs/evidence/performance-windows-jmeter-smoke-2026-08-12.json)。
- [x] 取消路径真实验收通过：run `7` 进入 `running` 后发出 Redis 取消信号，最终为 `cancelled`，JMeter 进程树和临时目录均已清理。证据见 [`docs/evidence/performance-windows-jmeter-cancel-2026-08-12.json`](docs/evidence/performance-windows-jmeter-cancel-2026-08-12.json)。
- [ ] k6/Locust、真实外部目标、Prometheus/Kubernetes 与真实 Android 设备仍需独立环境验收。

## 2026-08-12 Windows 性能 Agent gRPC 执行验收
- [x] 通过平台 API 创建临时 gRPC 性能定义并绑定 `performance-win-worker-a`，任务经 `performance.worker-a` 专用队列进入 Worker。
- [x] 本机 gRPC 目标执行 5 次 Unary 请求，结果 `OK=5`、错误率 `0`、资源采样 1 条且无采样错误；证据见 [`docs/evidence/performance-windows-grpc-smoke-2026-08-12.json`](docs/evidence/performance-windows-grpc-smoke-2026-08-12.json)。
- [x] 修复 Windows 未安装 psutil 时系统指标回退到 Linux `/proc` 导致的 `FileNotFoundError`，改为 Windows 原生系统 API，并补充 8 条指标回归测试。
- [x] 取消链路验收通过：运行中的 gRPC 任务经 `/performance/runs/{id}/stop` 停止后最终状态为 `cancelled`；证据见 [`docs/evidence/performance-windows-grpc-cancel-2026-08-12.json`](docs/evidence/performance-windows-grpc-cancel-2026-08-12.json)。
- [ ] k6/Locust、真实外部目标、Prometheus/Kubernetes 和真实 Android 设备仍需独立环境验收。

## 2026-08-12 Windows 性能 Agent 运行验收
- [x] 从现有远程基础设施配置派生本机忽略配置 `config/startup-profiles/performance-agent.env`，未将数据库、Redis、MinIO 凭据写入版本库。
- [x] `scripts/windows-performance-worker.ps1 doctor` 通过：PostgreSQL、Redis、MinIO 可达；本机 `grpc` 与 `jmeter` 可用，未声明未安装的 k6/Locust。
- [x] 独立 Worker 已启动并 ready，消费专用队列 `performance.worker-a`，自动注册节点 `performance-win-worker-a`，数据库状态为 `online`，首次心跳成功。
- [ ] 真实压测任务、k6 指标、Prometheus/Kubernetes 监控和真实 Android 设备仍需在目标环境单独验收；**该次性能 Agent 验收使用** `remote-infra` 的 `163.192.40.209`，不代表当前根 `.env` 已切换到该主机。

> Q18 最新开发计划、前后实现对比和剩余任务：[`docs/q18-latest-status-2026-08-07.md`](docs/q18-latest-status-2026-08-07.md)。

## 2026-08-07 AI generation context fixes

## 2026-08-12 PostgreSQL 启动连接超时
- [x] 后端新增 PostgreSQL、Redis、MinIO 三类 `*_CONNECT_TIMEOUT_SECONDS`（默认 5 秒，范围 1-120），同步配置 asyncpg、psycopg2、Redis/Celery 和 MinIO 客户端，避免基础设施握手失败时无限等待。
- [x] 启动配置页面、`.env.example`、性能验收/Helm 配置、四套 Windows 启动档案和 Windows 本地运行文档同步暴露这些参数，并补充配置校验回归测试。
- [x] 本机核心回归 `4 passed`、Ruff、Python 编译、PowerShell 解析和配置档案覆盖检查通过；前端 Node 工具链已定位并修复 Vite ESM 配置问题，门禁已补跑。
- [x] 修复 `frontend/vite.config.ts` 在 ESM/runner 配置加载器下使用未定义 `__dirname` 的问题，新增静态回归；完整非集成后端回归 `1893 passed`，前端 `44 files / 178 tests passed`，默认 Vite 构建和 `vue-tsc` 通过。
- [x] Vite 配置修复后的 Playwright 浏览器回归 `10 passed`，覆盖登录、Dashboard、用例、执行详情、套件/计划和 Windows 下载夹具。
- [x] **历史迁移记录**：当时 `remote-infra` 配置指向 `163.192.40.209`，已完成 `alembic upgrade head`（`20260807_0053 -> 20260811_0054`），Backend/Worker/Beat/Frontend 已恢复运行，`/health`、`/openapi.json` 和未授权接口行为验证通过；该记录不代表当前根 `.env` 的数据源。

## 2026-08-12 Windows 性能 Agent 启动入口
- [x] 新增 `scripts/windows-performance-worker.ps1`，支持 `doctor/up/down/restart/status/logs`，仅消费 `PERFORMANCE_NODE_QUEUE` 专用队列，并通过 `PERFORMANCE_NODE_ID` 注册性能节点心跳。
- [x] 新增 `config/startup-profiles/performance-agent.env.example` 与 `startup.ps1 -Profile performance-agent`，可在 Windows 本机执行 JMeter/gRPC 等性能任务，同时复用远程 PostgreSQL/Redis/MinIO。
- [x] 启动配置页面新增四档启动方式下拉框：`local-all`、`remote-infra`、`android-agent`、`performance-agent`；选择后回填对应 `.env` 草稿，保存时只在浏览器持久化，复制/下载后仍由 `startup.cmd` 实际启动。
- [x] `doctor` 会阻止服务依赖、节点 ID/队列、远程端口和共享队列误配置；k6/Locust/JMeter/gRPC 缺失按可选执行器告警。PowerShell 解析和启动档案契约回归 `7 passed`。
- [x] 页面回归：StartupConfigView `5 passed`，`vue-tsc --noEmit` 和生产构建通过；构建验证后发现当前远端 PostgreSQL TCP 可达但连接超时，未切换数据源或修改远端配置。
- [x] Windows 主 Worker 的节点心跳、任务消费、k6/Locust 执行与指标回传已完成本机 `/health` 真实验收；Linux/Kubernetes、Prometheus 和真实外部目标仍不能由本机结果替代。

- [x] Limit Mock rules selected for one AI generation request to 20 and show a localized warning when the limit is exceeded.
- [x] Expand the Mock rule action column and enable horizontal scrolling so all row actions remain usable.
- [x] Persist the selected dataset version on AI-generated cases and load that immutable snapshot during parameterized execution.
- [x] Persist AI generation provenance in `_ai_source` (`dataset_id`, `dataset_version`, `mock_rule_ids`) and include the same context in generation audit events.

**最后更新**: 2026-08-12

## Worker 测试外部依赖隔离修复
- [x] 修复 `test_tasks_mobile_special_dispatch.py` 与 `test_tasks_performance.py` 的真实 Redis 取消控制客户端隔离问题；Worker 全量 `427 passed`，完整非集成后端 `1889 passed`，覆盖率 `82.13%`。
- [ ] 远端 SSH/MCP 会话恢复后，继续真实 k6、metrics、其余协议、取消、Kubernetes/Prometheus 和 Android 设备验收；不将旧工具镜像的失败报告作为通过证据。

## 2026-08-12 Linux 性能验收栈部署进度

- [x] Windows 性能验收 bundle 使用 POSIX ZIP 条目路径、manifest 和 SHA-256 sidecar 生成；本地 bundle 323 个文件，校验值 `7a2cd58fcb1762f38c91f2b1d6b98e02cabf4a783ba20f3ed98828370a29e853`。
- [x] 在 `172.31.27.133:/opt/atp-q17-acceptance` 建立隔离 Compose 栈；PostgreSQL、Redis、MinIO、Backend、验收目标和性能 Worker 已启动，Backend `/health` 与迁移通过。
- [x] 完成 API/节点 smoke：四类执行器 ready、`worker-a` online、队列和 egress allowlist 检查通过；证据为远端 `docs/evidence/performance-api-node-2026-08-12.json`。
- [x] 修复验收工具报告 `Path` 序列化和 state-changing 请求 CSRF header 缺失问题；本地 `backend/tests/scripts/test_performance_environment_smoke.py` 为 `17 passed`。
- [x] Windows 本地 k6/Locust smoke 与 metrics 证据已补齐；[ ] 远端 SSH/MCP 会话恢复后继续真实外部目标、取消、Kubernetes/Prometheus 和 Android 设备验收，不将失败的旧工具镜像报告作为通过证据。

## 2026-08-11 三方 AI 模型配置

- [x] 新增 `openai_compatible` 供应商协议，适配 Open WebUI、One-API、LiteLLM 等暴露 OpenAI `/v1` 接口的三方服务。
- [x] 模型发现使用兼容协议的 `GET {base_url}/models`，模型调用使用 `POST {base_url}/chat/completions`；Endpoint 必填，API Key 仍只加密保存。
- [x] AI 模型配置页新增“OpenAI 兼容（三方）”选项、Endpoint 提示和模型拉取入口，避免把三方服务误选为原生 Ollama。
- [x] 回归覆盖兼容供应商调用、模型发现、创建/更新 Endpoint 校验；真实三方服务联调仍需使用实际 Token 和目标服务验收。

## 2026-08-11 Windows Worker 启动前诊断

- [x] `scripts/windows-local.ps1 doctor` 校验 Web 录制模式只能是 `local`/`worker`，并检查 Python Playwright、Chromium 可执行文件、Worker 入口、Redis 队列前缀和正整数并发上限。
- [x] `scripts/windows-android-worker.ps1 doctor` 在 ADB 检查前校验 Celery 与 Redis Python 依赖；缺失依赖会直接给出安装提示，避免 Android Worker 启动后立即退出。
- [x] Windows 启动诊断回归：PowerShell 语法检查通过，`backend/tests/scripts/test_windows_local_contract.py` 为 `7 passed`，当前机器 `local-dev.cmd doctor` 通过（仅 Android 设备未连接这一可选警告）。
- [x] Android Agent 扫描回传：`ADB_SCAN_MODE=worker` 时返回 Celery 扫描任务 ID，设备页轮询任务状态后再展示扫描完成；本地 `local` 模式保持同步返回。
- [x] Android Worker 在线注册：Windows 启动脚本注入稳定 `ANDROID_WORKER_ID`，Worker 通过 Redis TTL 心跳注册，设备页可查看在线 Agent；未显式配置 ID 的普通 Worker 不会被误识别。
- [x] Windows Worker 模式隔离：`windows-local.ps1` 不再把带 `android-win-*` 或 `performance-win-*` 主机名的专用 Android/性能 Worker 误认成普通 Worker；`windows-local.ps1` 与 `windows-android-worker.ps1` 双向检测本地普通 Worker/专用 Android Worker 的队列重叠，并在停止现有服务前明确阻止冲突启动，避免任务被重复消费。相关 Windows 合约回归通过，PowerShell 解析通过。
- [x] Windows 全量冒烟接入 Android Worker：worker 模式或 `-RequireAndroid` 时校验在线 Agent，并发起设备扫描、轮询 task ID 回调；没有真实设备时只验证队列状态，不伪造设备数据。
- [x] Windows Web 低代码冒烟支持 `-SeedWebDownloadCase`：按需创建临时项目/模块/用例，自动提交审核并批准为 `active/approved` 后执行仓库下载夹具，终态后清理；超时保留资源并在脱敏报告中记录项目/运行 ID，避免误删运行中数据。
- [x] Windows 冒烟新增 `-EnvFile`，统一 doctor、登录和服务启停所使用的启动档案；使用当前 `remote-infra.env` 重跑 10 项 Playwright、三浏览器矩阵和 Web 下载对象闭环通过，证据见 `docs/evidence/windows-local-smoke-remote-infra-web-seed-2026-08-12.json`。

## 2026-08-11 项目工作台建设

- [x] 项目总览：汇总项目执行指标和测试资产数量。
- [x] 项目级配置中心：统一跳转环境、数据集、变量、Mock、套件、计划、Web 资产和 API 契约。
- [x] 项目生命周期：新增 active / archived 状态，以及归档/恢复接口和页面操作；归档后项目配置编辑进入只读保护。
- [x] 项目角色权限可视化与只读原因提示。
- [x] 项目模板与复制：支持 blank/API/Web/Android/full 模板初始化（模块、环境、示例数据）和基础项目复制；复制不包含成员、密钥、执行记录或外部资源。
- [x] 项目脱敏导入导出：支持 JSON 导出、导入预览、fail/rename 冲突策略、敏感变量和数据集字段脱敏，以及 AI 模型元数据匹配。
- [x] 归档后的测试资产新建/执行约束：统一拦截 editor/owner 写入断言并返回 409；查看、报告和导出保持可用，恢复后解除限制。
- [x] 归档前端按钮状态、审计事件和 owner/member 操作策略：归档项目禁用复制、项目编辑和成员变更，复制/导入/归档/恢复/成员变更均写项目审计事件。

详细设计与验证记录：[`docs/project-workspace-roadmap.md`](docs/project-workspace-roadmap.md)。

## 2026-08-11 数据集 AI 生成入口

- [x] 数据集管理页新增“AI 生成数据”入口：可填写名称、行数和生成要求，按当前项目绑定的 AI 模型生成合成 JSON 行。
- [x] AI 结果只回填数据集编辑器，不直接落库；用户确认后复用现有 Schema 校验、软/硬策略和版本快照保存流程。
- [x] 已有数据集可按已保存 Schema 生成覆盖草稿；未提供 Schema 时自动推断字段类型，限制 200 行并复用 256KB 数据集上限。
- [x] 后端新增 `/datasets/ai-generate`，覆盖项目权限、项目 AI 配置、模型错误和 JSON 对象数组解析；前后端回归已补齐。

详细设计与验证记录：[`docs/q18-implementation-log-2026-08-07.md`](docs/q18-implementation-log-2026-08-07.md)。

## 2026-08-11 Mock 规则 AI 生成入口

- [x] Mock 服务页新增独立“AI 生成 Mock”入口；保留原有“由 Mock 规则生成用例”入口，避免两个能力混淆。
- [x] 支持不选参考规则直接按要求生成，也支持使用当前选中的规则或单条规则作为上下文；单次最多生成 20 条。
- [x] AI 结果先进入可编辑 JSON 预览，不直接落库；确认后复用现有 Mock 规则创建接口逐条保存，并刷新规则列表。
- [x] 后端新增 `/mock-rules/ai-generate`，覆盖项目编辑权限、AI 配置、参考规则项目隔离、JSON 对象数组解析、响应体大小和模型异常处理。
- [x] 已补服务层、API 契约和 Mock 页面回归；未配置项目 AI 模型时会明确提示，AI 输出不会携带密钥、Cookie 或真实个人信息。

详细设计与验证记录：[`docs/q18-implementation-log-2026-08-07.md`](docs/q18-implementation-log-2026-08-07.md)。

## 2026-08-11 Worker 测试隔离收口

- [x] 根级 `backend/tests/conftest.py` 对 MinIO、Redis、数据库等公共测试替身采用 fill-missing-only 策略，不覆盖历史测试显式设置的行为。
- [x] 在测试模块收集前和每个测试启动前刷新缺失字段，解决模块级 `sys.modules` 替换导致的收集顺序依赖。
- [x] 完整 Worker 测试套件验证为 `415 passed`；全仓非集成回归为 `1867 passed`，256 个测试文件独立运行通过。
- [x] 旧记录中“Worker 套件 8 个失败”的内容仅保留为历史背景，当前不再作为未完成项。

**当前工作快照（2026-08-12）**: 本次已完成浏览器 HttpOnly Cookie 会话、WebSocket URL 脱敏、混合套件设备子任务队列隔离、项目资源权限收口、录制/报告 URL 安全校验、浏览器逐请求网络隔离、移动专项运行中取消、设备租约并发锁和异步 ADB 阻塞修复，并完成 Web 录制 Worker 服务化、Windows Worker 启动前诊断、Android Agent 扫描状态回传、Android Worker 在线注册、Windows Web 下载自包含冒烟入口、数据集页面 AI 生成草稿入口、性能中心 JMeter 配置入口、性能节点注册配置、Windows 节点队列/配置同步、性能验收 bundle 打包入口、Windows 本地 Prometheus 目标指标闭环、API gRPC 四种调用模式、多文件 Proto 文件读取入口和大型数据集 MinIO 引用模式。Web 录制现支持选择 Chromium/Firefox/WebKit；后端非集成测试为 `1929 passed`，前端已达 `45 files / 183 tests passed`，type-check/build 通过。当前验证结果、发布阻断项与分阶段计划见 [`docs/status-2026-08-11.md`](docs/status-2026-08-11.md)。
**最新验证（2026-08-12）**: 性能节点 UI 管理与 Worker 环境管理已隔离，Windows 会自动监听共享/专用性能队列，队列不一致会显示离线；完整非集成后端回归为 `1929 passed`，263 个测试文件逐文件独立运行 `263 passed, 0 failed`；前端为 `45 files / 183 tests passed`，type-check/build 通过。gRPC Proto 文件读取及多文件包边界回归为 `5 passed`；Windows Worker 隔离合约回归为 `5 passed`，当前 `local-all` 已恢复为 Backend/普通 Worker/Beat/Frontend 运行，专用 Android Worker 已停止，ADB 当前未连接设备；健康检查和 `/api/v1/devices/workers` 路由均可用。JMeter 本地 `/login` 烟测为 1 请求、0 错误，证据在 `.local-run/jmeter-smoke-20260811-233647/`；大型数据集 MinIO 真实对象验收、兼容供应商真实 Token/模型联调、真实设备、真实性能节点和外部服务仍待完成/验收。

**最新补充（2026-08-12）**: 性能节点卡片已展示后端 `last_error` 诊断信息，队列不一致时可直接定位 Worker 与节点配置差异；Web 录制已增加浏览器选择（Chromium/Firefox/WebKit），性能中心已增加 Prometheus 目标指标配置和来源切换，前端回归为 `44 files / 180 tests passed`，type-check/build 通过。其余真实性能节点心跳/消费、真实设备和外部服务仍待目标环境验收。

**API gRPC 补充（2026-08-12）**: API gRPC 执行器已按 Proto 方法声明支持 Unary、Server Streaming、Client Streaming 和 Bidi Streaming；编辑器提示 Client/Bidi 使用非空 JSON 数组，并支持主 Proto 与 import 文件分开选择，相关 gRPC/HTTP 回归 `68 passed`。当前完整非集成后端为 `1886 passed`、Python 3.12 覆盖率 `82.13%`；真实 Unary/Streaming 目标服务、TLS 和跨环境联调仍待验收。

**API gRPC 编辑器补充（2026-08-12）**: gRPC 用例编辑器新增主 `.proto` 与 import 文件读取入口，不上传协议源码；浏览器端拒绝非 `.proto`、空文件、单文件超过 1MB 或文件包超过 8MB/64 个文件，`grpcProtoFile` 回归 `5 passed`，前端全量 `44 files / 177 tests passed`，type-check/build 通过。

**Windows 冒烟补充（2026-08-12）**: 修复冒烟文件上传的 CSRF 403 和手工 Cookie 401，统一写请求头并使用 `CookieContainer` 复用 HttpOnly 会话；修复后真实冒烟通过 10 项 Playwright、三浏览器矩阵、管理员登录、文件上传和 MinIO 清理，报告为 `.local-run/windows-smoke-20260812-003248.json`。

**Windows Web seed 补充（2026-08-12）**: 自包含下载夹具随后通过临时项目 9/用例 5 的创建、审核、Worker 执行和下载对象校验，最终清理项目、1 个环境和 5 个运行产物；报告为 `.local-run/windows-smoke-20260812-003448.json`。

**项目工作台扩展验证（2026-08-11）**: 在上述基础上完成项目模板、复制、脱敏导入导出、冲突预览和归档测试资产写入/执行约束；项目相关回归 `72 passed`，完整非集成后端回归 `1827 passed`，前端 type-check/build 通过。导入不携带成员、密钥、执行记录和外部资源；归档项目仍可查看、报告和导出，恢复后解除写入/执行限制。
**平台分层（2026-08-10）**: Windows 是日常开发、Web/API/Android 联调和本地回归主线；Linux/Kubernetes 性能 Worker、真实设备池、macOS/iOS、专用浏览器 Worker、Prometheus 与外部通知属于目标环境开发/发布验收，不阻塞 Windows 日常开发。
**当前阶段**: Q1–Q12 路线图已全部完成；Q13 七个工作项中六个本地项全部完成；Q14 本地项已全部完成（Q14-01 Android/ADB 执行器族收口，Q14-02 API-router sweep，Q14-03 五个工作台页 mount tests，Q14-04 per-project retention real cleanup，Q14-05 gitleaks pre-commit，Q14-06 Q13 acceptance summary），并已发布 `docs/q14-acceptance-summary.md`。Q15 已完成 Q15-02（后端测试单文件可运行）、Q15-03（Windows CI job）、Q15-04（前端系统管理页面挂载测试）、Q15-05（worker/维护模块覆盖 + 门禁校准）、Q15-06（chartTheme 负载敏感）、Q15-07（Q14 acceptance summary），Q15-01 完成本地可做部分（服务端分支保护在当前 GitHub 套餐下不可得，已降级为本地钩子 + 文档约定并如实说明边界）。部署/灾备的仓库级配置也已收口：`make validate-deployment-readiness`、Helm 外部 Secret、ServiceMonitor、TLS 重定向和备份/恢复脚本契约已落地；校验器在 Windows 无 `sh`/`bash` 时会明确跳过 shell 语法检查，发布机可用 `--require-shell` 强制校验。真实集群部署、备份恢复和 smoke evidence 仍需外部环境。当前后端 TOTAL 为 **86.04%**（Python 3.12 / CI 口径；本地 Python 3.14 为 85.55%），门禁 **82**，`1467 passed`；前端 statements 为 **32.96%**（门禁 31.5，`128 passed`），`views/system` statements 为 **37.36%**。当前外部阻塞项为 Q15-00 / 原 Q14-00 / 原 Q13-00（Q12-05 生产 SLO 历史 + Android 真机演练采集）以及生产部署/灾备演练证据；对应模板已在 `docs/templates/` 固化，并提供 `make collect-q12-evidence` 自动查询 Prometheus、ATP API 和 ADB 后生成三份证据及附件，`make scaffold-q12-evidence` 仅作为草稿初始化，`make validate-q12-evidence` 做结构校验。覆盖工作累计发现并修复四个潜伏生产 500：grpc protobuf5、mobile-special create_task、ai_healing ProjectRole.engineer、global-variables create_variable（value_encrypted 重复关键字，变量库此前无法创建任何变量）。

**历史验证（2026-08-06）**: 当前工作区当时与 `origin/main` 同步至 `135906d`。以下 Q15 质量基线来自 2026-08-05 对验证提交 `87f0fc7` 的全量重跑；本次同步还包含 Q14 验收、部署/灾备仓库契约及相关回归测试，修改业务代码后需重新执行完整门禁。后端 `make test-backend-coverage` 在两个解释器下均通过门禁 82：Python 3.12（CI 口径）`1467 passed`、TOTAL `86.04%`；Python 3.14（本地 `backend/.venv`）`1467 passed`、TOTAL `85.55%`。**两者语句总数不同（13962 vs 13367，差 595 条、约 0.5 个百分点）**，抬门禁须以 3.12 为准并复验 3.14，口径说明见 `docs/coverage-baseline-2026-q13.md` 的 Interpreter note。`make test-backend-standalone` 为 `191 passed, 0 failed`（每个非 integration 测试文件单独可跑，防止测试间隐式耦合）。`make lint` / `make format-check`（381 文件）/ `make mypy`（76 源文件）全部通过；完整 pre-commit 链 8/8 通过（含 gitleaks）。`npm --prefix frontend run test:coverage` 为 `31 files / 128 tests passed`、statements `32.96%`、branches `27.81%`、functions `26.36%`、lines `34.04%`，`views/system` statements `37.36%`，门槛 31.5 / 26.5 / 24.5 / 32.5 通过。`npm run type-check` 与 `npm run build` 均通过。**门禁强制力如实说明**：`main` 无 required status checks（private 仓库 + 免费套餐，`branches/main/protection` 与 `rulesets` 均 403），CI 红绿只是通知，本地钩子可被 `--no-verify` 绕过，详见 `docs/ci-workflows.md`「门禁强制力现状」。Q12 自动采集器仍按既有留证通过定向回归（延迟取峰值、空窗口判为数据缺口、证据已存在时在采集前中止、`increase(...[1d])` 按实际统计日归档、整数计数不得被去零、凭据只认 `ATP_USERNAME`/`ATP_PASSWORD` 六条不变量）。历史验证：Docker Python 3.12 目标运行时、真实依赖 integration、前端 E2E、SLO 薄切、安全扫描与 GitHub runner 矩阵均按 Q10/Q11/Q13 文档留证。

**Q17 历史验证（2026-08-07）**：统一性能执行器、Locust worker 链路、gRPC Proto 动态编译及 Unary/Streaming 本地真实服务联调已完成；新增 `scripts/performance-environment-smoke.py`、外部环境验收 Runbook、Worker 镜像 grpc 依赖构建校验和专用 Worker metrics 健康探针。后端非集成回归 `1578 passed`，独立测试扫描 `210 passed, 0 failed`；前端 `36 files / 143 tests passed`，`npm run type-check` 和 `npm run build` 通过；后端覆盖率 `83.78%`（门禁 82）通过，Ruff、mypy（90 个源文件）、`git diff --check` 和部署 readiness 通过。Alembic head 为 `20260529_0044`。真实 Docker worker 镜像构建、Linux/Kubernetes Locust 压测和外部 gRPC 目标服务仍属于环境验收。

**下一步计划（2026-08-07）**:

- [x] Q17-02：gRPC Proto 动态编译、Unary/Streaming 并发、TLS/metadata 安全、取消、统一摘要和本地真实服务回归。
- [x] Q17-03：新增 `scripts/performance-environment-smoke.py`、外部验收 Runbook、Kubernetes/Docker Worker 镜像与容器 grpc 依赖检查、节点队列/allowlist 检查和专用 Worker metrics 健康探针；补充 ARM64 Docker Compose 隔离验收栈、`.env.performance-acceptance.example`、TLS gRPC/HTTP 目标和 Worker 挂载 CA 配置。
- [ ] Q17-04 环境验收：在 Linux/Kubernetes 专用 performance worker 构建并启动包含 grpcio/grpcio-tools 的镜像，使用真实 TLS 和外部 gRPC/Locust 目标服务完成 smoke、取消、节点 allowlist 与资源采样验证。
- [ ] 发布收口：依据环境验收证据更新 `docs/performance-executor-evaluation.md`、部署 runbook 和 release/PR 说明；若目标服务或证书未准备好，保留为明确的外部环境阻塞项。
- [x] Q17-04 验收工具可靠性补强：Compose 验收栈增加 Backend `/health` 健康依赖；`performance-environment-smoke.py` 等待专用 Worker 心跳变为 `online`，并新增离线→在线回归，避免启动竞态误报。
- [x] Windows 部署 readiness 修复：`validate-deployment-readiness.py` 兼容本地代码页下的非 UTF-8 shell 输出和空 stdout/stderr；实际命令现在可完成仓库检查，只对缺少的 Docker/Helm 显示 SKIP。部署文档回归 `13 passed`。
- [x] 2026-08-12 Linux 目标主机只读审计：已确认配置主机的 Docker/Compose、PostgreSQL、Redis、MinIO 可用，但现有 `/opt/testhub_platform` 为独立 Django 项目，不提供 ATP 健康接口；未发现 ATP Q17 性能隔离栈或 Prometheus，未对远端做部署、重启或修改。

## Q18 能力扩展入口（2026-08-07）

- [x] 开发计划：`docs/implementation-plan-2026-Q18-capability-expansion.md`。
- [x] 能力基线与前后对比：`docs/capability-baseline-2026-08-07.md`。
- [~] Q18-API：Cookie、multipart、XML/XPath、JSON Schema 资产、SSE、OpenAPI/Swagger/Postman 导入、受限前后置动作、统一结果契约、场景编排、受控数据集组合、事务导入、Provider/Consumer 契约资产 CRUD/版本化及 `/system/api-contract-assets` 管理/比较 UI 已完成；API/GraphQL 已支持 OAuth2 Client Credentials 与 Digest 认证，真实 Provider/Consumer、Token Endpoint 和认证流程联调仍待环境验收。
- [~] Q18-Windows：Windows 本地启动、远端 PostgreSQL/Redis/MinIO、PowerShell 进程托管、Playwright/ADB、本地回归入口、`local-dev.cmd doctor`、PowerShell Android 网络诊断和全量本地冒烟已具备；启动档案入口和底层 `-EnvFile` 现在都会把选中配置只注入新子进程，Android Agent `up/restart` 会先自动执行 doctor；冒烟实测通过真实健康/登录/认证读接口、Playwright 10 项、Chromium/Firefox/WebKit 页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务；`-WebCaseId` 可复用已有 Web 低代码用例，`-SeedWebDownloadCase` 可创建临时用例并自动审核、执行、校验真实 Worker/MinIO 下载对象后清理项目、环境和运行产物；性能中心已可注册/编辑/删除节点、配置执行器能力/容量/出口约束，可选择 JMeter 并上传 `.jmx`，本地 JMeter 烟测已通过；Android 真机验收和 Docker Worker 性能验收仍待完成。
- [~] Q18-Web：多浏览器配置、录制时 Chromium/Firefox/WebKit 选择、Trace、网络/Console 摘要、元素库/POM CRUD 与执行、绑定项目录制自动写入资产、文件操作、视觉回归、浏览器矩阵、定位器修复建议和逐请求网络隔离已完成；本地 Chromium/Firefox/WebKit 页面烟测已补齐，Redis 路由控制面、独立 Web 录制 Worker 入口、Windows 托管、Compose/Helm 部署契约已完成，真实 Firefox/WebKit Worker、Linux/Xvfb 与跨副本 E2E 仍待补。
- [x] Q18-Web 路由并发补强：录制 Worker 明确返回 `busy/not_ready` 时，API 会切换到其他有容量的候选 Worker；超时和未知错误不盲目重试，启动成功但快照响应异常时会主动停止远端会话清理资源，回归位于 `backend/tests/services/test_web_recording_transport.py`。
- [x] Q18-Web 录制失败收口：停止录制接口失败时，前端不再自动导入停止前的步骤或关闭弹窗；保留错误状态并补充 `WebRecorderModal` 组件回归。
- [x] Q18-Web 录制浏览器选择：录制弹窗支持选择 Chromium/Firefox/WebKit，API/Worker 参数、依赖提示和回归测试已同步；缺少浏览器时返回明确错误，不做隐式回退。
- [x] Q18-Web Worker 状态预检：新增 Worker 状态接口与脱敏容量摘要；录制弹窗会展示 `local` / `worker` 模式、注册数和可用容量，并在远程 Worker 无空闲容量时阻止启动，补充后端/前端回归。
- [x] Q18-Windows Web 录制冒烟：`windows-local-smoke.ps1` 登录后检查 Web 录制模式和 Worker 容量；Worker 模式没有注册节点或空闲容量时冒烟明确失败，local 模式验证 API 本地录制就绪。
- [~] Q18-Mobile：Android 设备租约、标准安装/卸载/清理/启动、录屏、设备日志、系统动作和兼容性矩阵已完成；矩阵子运行现在使用独立数据库会话和租约并行调度；iOS/Appium 的设备/IPA 资产、租约、专用队列、W3C Worker 和统一结果已完成本地实现；真实设备池并发抢占、macOS/XCUITest、iOS 外部系统事件仍待补。
- [~] Q18-Performance：自动阶梯、目标服务指标 UI/采样闭环、JMeter 非 GUI/JTL/HTML、多节点分片聚合、容量分析和性能 Run 全终止分支通知，以及性能节点注册/编辑/删除和执行器能力配置入口已完成代码实现；Windows 本地 Prometheus 与目标指标 k6 smoke 已通过，生产 Prometheus、节点镜像、外部通知渠道和真实性能验收仍待补。
- [~] Q18-验收：本地后端非集成 1929 项、263 个测试文件单独运行 `263 passed, 0 failed`、前端全量 45 文件/183 测试、Playwright E2E 10 项、迁移、mypy、Ruff、Bandit、pip-audit、npm audit、类型检查/构建和文档已通过；Windows Web seed 已完成真实 Worker/MinIO 下载对象闭环，JMeter 本地烟测、Windows 队列同步、Windows 本地 Prometheus 目标指标、gRPC 多文件 Proto 读取、Web 录制浏览器选择和大型数据集 MinIO 代码闭环已完成，真实 MinIO 大数据量、真实 Android 设备、真实性能节点心跳/消费、外部服务和真实 API 联调仍待完成/验收。

**Q18 下一阶段计划（2026-08-10）**：

- [~] Q18-Windows：启动前检查、性能执行器检测、Android PowerShell 网络诊断、全量本地冒烟、性能验收 bundle 打包和 Web 低代码真实下载 seed 闭环已完成；`scripts/windows-local-smoke.ps1` 已归档脱敏 JSON 证据，`scripts/package-performance-acceptance.ps1` 会生成带 SHA-256 和文件清单的无密钥 Linux 验收包，剩余 Android 真机扫描/执行验收与已有业务用例的持续复用验证。
- [ ] Q17-04：在 Linux/Kubernetes 隔离栈完成性能 Worker 镜像、Locust/gRPC/TLS 目标、取消、节点 allowlist、资源采样和 JMeter 外部验收。
- [~] Q18-API：使用真实 Provider/Consumer 规格完成契约比较联调，并在真实 OAuth2 Token Endpoint、Digest 服务上验证认证交互、超时和凭据轮换。
- [~] Q18-Web：在专用 Worker 上验收 Firefox/WebKit、Trace、网络/Console、文件操作和视觉回归，并补充关键 UI/E2E；Worker 控制面与部署入口已完成，Linux/Xvfb、跨副本和真实浏览器验收仍待补。
- [ ] Q18-Mobile：准备 Android 设备池和 macOS iOS/Appium 环境，完成租约并发、矩阵、录屏、系统动作及 iOS 最小闭环验收。
- [ ] Q18-Performance：在外部环境接入真实 Prometheus、外部通知渠道和多节点压测结果，归档带日期的性能基线与回归证据；Windows 本地 Prometheus 闭环已完成但不替代生产验收。
- [ ] 发布收口：将真实环境证据同步到 Q18 状态、性能 Runbook、部署文档和发布说明；在证据缺失前保持“部分实现/待验收”标记。

- [x] P0：整理提交 / PR 范围，按主题拆分当前大 diff：环境与依赖兼容、权限与缺陷联动、AI 诊断/治理、前端体验与文档进度。
- [x] P0：在 CI 或 Docker/目标 Python 3.12 环境复跑后端回归，确认 Python 3.14 条件 pin 不影响目标运行时。
- [x] P0：补跑前端质量命令：`npm run type-check`、`npm run build`，必要时补关键页面截图或构建日志。
- [x] P1：做最终 code review pass，重点检查新增权限边界、审计日志提交次数、AI 调用降级、依赖版本条件与 Makefile setup 兼容性。
- [x] P1：归档发布证据：测试命令、通过结果、已知 warnings、环境准备说明，并同步到 PR 描述 / release notes。
- [x] P2：进入 Q10 Phase 5 收口，ruff 最小 lint/format 门禁、pytest-cov 覆盖率基线、前端 Vitest 两批测试、Bandit SAST、依赖漏洞扫描清零、Gitleaks/Trivy/Dependabot security workflow 与目标 Docker Python 3.12 回归已落地；下一步按以下顺序推进：
  1. [x] 集成测试：`suite-run` / `plan-trigger` / `notification` / `bug-report` 已补齐并在真实 Postgres / Redis / MinIO 环境跑通。
  2. [x] E2E：suite / plan 前端关键路径已覆盖加载、触发执行、查看记录和 Windows 下载夹具，完整 Playwright E2E 为 `10 passed`。
  3. [x] SLO：已补 API 可用性、P95、run 成功率 3 条薄切指标与错误预算面板。
  4. [x] 收口：flaky 治理、`docs/q10-acceptance-summary.md`、README / Task.md / release evidence 最终同步已完成。
- [x] P2：Q11 全部完成；Android Worker ADB 控制路径、host-network 约束和安全诊断方式已形成实测/文档/静态契约证据，物理真机 shell 验收明确保留为外部环境项。
- [x] Q16-06：性能压测执行控制已补齐，包含 `cancelling` 状态、Redis 取消信号、k6 子进程安全终止、前端状态轮询与进度展示；后端 52 项定向回归通过，当前完整非集成回归 `1507 passed`，前端 `36 files / 142 tests passed`，type-check 与生产构建通过。
- [x] Q16-07：新增性能压测 JSON/CSV 报告导出、脱敏快照、阈值门禁摘要与前端门禁状态展示；相关后端 54 项、前端报告工具 2 项回归通过。
- [x] Q16-08 已完成：基线对比、定时执行和 CI 阈值门禁。

> 状态说明：
> - `[ ]` 待开始
> - `[~]` 进行中
> - `[x]` 已完成
> - `[-]` 已跳过/暂缓
>
> 文档同步说明：本文件已按当前仓库实现状态更新；`[~]` 表示基础能力已落地，但仍有明确缺口或尚缺联调/工程化收口。

---

## Phase 1 - 基础框架（MVP）

> 目标：跑通完整主流程，接口测试用例能够配置 → 执行 → 看报告

### 1.1 工程初始化

- [x] 创建 `docker-compose.yml`，包含 PostgreSQL / Redis / MinIO 服务
- [x] 创建 `.env.example`，定义所有必要环境变量
- [x] 初始化 FastAPI 后端项目结构（`backend/`）
- [x] 初始化 Vue 3 + TypeScript 前端项目结构（`frontend/`）
- [x] 配置前端开发代理，解决跨域问题
- [x] 配置 Nginx，托管前端静态资源并反代后端 API

### 1.2 数据库与 ORM

- [x] 配置 SQLAlchemy 2.x async 连接 PostgreSQL
- [x] 配置 Alembic 数据库迁移工具
- [x] 创建核心数据表：`User`、`Role`
- [x] 创建项目结构数据表：`Project`、`Module`、`TestCase`
- [x] 创建执行相关数据表：`TestRun`、`CaseResult`、`StepResult`
- [x] 创建环境相关数据表：`Environment`、`EnvVariable`
- [x] Alembic 迁移文件、迁移回归测试、Docker Compose migrate 服务与 Helm 迁移 Job 已补齐；首建流程统一为 Alembic 驱动，`create_all` 仅保留在显式本地排障开关中

### 1.3 用户认证

- [x] 实现用户注册/登录接口（`POST /api/v1/auth/login`）
- [x] 实现 JWT Token 签发与验证中间件
- [x] 实现 Token 刷新接口（`POST /api/v1/auth/refresh`）
- [x] 实现基于角色的权限控制（RBAC）依赖注入
- [x] 前端：实现登录页面（用户名/密码）
- [x] 前端：实现 HttpOnly Cookie 会话、自动携带凭据与 CSRF 请求头（Bearer 仍兼容外部 API 客户端）
- [x] 前端：实现未登录自动跳转登录页（路由守卫）

### 1.4 项目/模块/用例 CRUD

- [x] 实现项目管理接口（增删改查）
- [x] 实现模块管理接口（树形结构，支持嵌套）
- [x] 实现用例基础 CRUD 接口
- [x] 实现接口用例详情表（`ApiTestCase`）的存储与查询
- [x] 前端：项目列表页面
- [x] 前端：模块树形目录组件
- [x] 前端：用例列表页面（支持按模块过滤）
- [x] 前端：接口用例创建/编辑表单（URL、Method、Headers、Body、断言）
### 1.5 接口测试执行器（HTTP REST）

- [x] 搭建 Celery + Redis 任务队列基础框架
- [x] 实现 HTTP 接口测试执行器（基于 `httpx`）
  - [x] 发送请求（GET / POST / PUT / DELETE / PATCH）
  - [x] 支持 Headers、Query Params、JSON Body、Form Body
  - [x] 支持 Basic Auth / Bearer Token 认证
  - [x] 实现断言逻辑（状态码 / JSONPath / 响应头 / 响应时间）
  - [x] 实现变量提取（从响应 JSONPath 提取，存入上下文）
- [x] 实现执行任务触发接口（`POST /api/v1/cases/{id}/run`）
- [x] 实现执行结果写入数据库
- [x] 实现 WebSocket 推送执行状态到前端

### 1.6 执行报告（基础版）

- [x] 前端：执行记录列表页面
- [x] 前端：单次执行报告页面（总览 + 用例列表 + 步骤详情）
- [x] 前端：WebSocket 接收实时执行状态并更新 UI
- [x] 实现执行记录查询接口（`GET /api/v1/runs/{id}`）

### 1.7 环境管理

- [x] 实现环境 CRUD 接口（开发/测试/预发/生产）
- [x] 实现环境变量的存储与查询
- [x] 接口测试执行时注入环境变量（URL 前缀替换、变量占位符解析）
- [x] 前端：环境管理页面

---

## Phase 2 - Web UI 测试

> 目标：支持 Playwright + pytest 脚本的上传、执行与报告展示

### 2.1 脚本存储

- [x] 配置 MinIO 客户端（Python `minio` SDK）
- [x] 实现脚本文件上传到 MinIO（`POST /api/v1/cases/{id}/script`）
- [x] 实现脚本文件下载/预览接口
- [x] 前端：集成 Monaco Editor 在线代码编辑器
- [x] 前端：脚本上传与在线编辑页面

### 2.2 Playwright 执行器

- [x] 在 Worker Docker 镜像中安装 Playwright + Chromium
- [x] 实现 pytest 脚本执行器
  - [x] 从 MinIO 下载脚本到临时目录
  - [x] 调用 `pytest --json-report` 命令执行
  - [x] 解析 `pytest-json-report` 结果，映射到平台数据结构
  - [x] 收集失败截图，上传到 MinIO
  - [x] 清理临时目录
- [x] 实现执行配置：浏览器类型 / 无头模式 / 分辨率 / 超时
- [x] 修复脚本模式回归问题（pytest 超时参数、Monaco 双向绑定、浏览器选项约束、MinIO bucket 自动初始化）

### 2.3 Web 用例低代码模式

- [x] 设计步骤数据结构（操作类型 + 参数）
- [x] 实现低代码用例存储接口
- [x] 支持操作：跳转 URL / 点击 / 输入 / 断言文本 / 断言元素可见 / 等待 / 截图
- [x] 前端：步骤配置表单（可拖拽排序）
- [x] 实现低代码用例 → Playwright API 调用的执行器

### 2.4 报告增强（截图/录像）

- [x] 执行报告中展示每个步骤的截图
- [x] 支持失败步骤高亮
- [x] 支持 Playwright 录像（`.webm`）上传与播放

---

## Phase 3 - Android UI 测试

> 目标：支持 uiautomator2 + pytest 脚本执行，真机设备管理

### 3.1 设备管理

- [x] 实现 ADB 设备扫描服务（`adb devices` 定期轮询）
- [x] 实现设备 CRUD 接口（`GET /api/v1/devices`）
- [x] 实现设备状态监控（在线/离线，Celery Beat 定时扫描）
- [x] 前端：设备列表页面（显示设备名、系统版本、状态）

### 3.2 APK 管理

- [x] 实现 APK 文件上传到 MinIO
- [x] 实现 APK 版本管理接口（关联项目，支持多版本）
- [x] 前端：APK 管理页面（上传、列表、删除）

### 3.3 uiautomator2 执行器

- [x] Worker 容器侧已安装 `adb`，执行前新增设备可达性校验，并补齐 ADB over TCP 真机联调说明；通过 `app.services.adb_resilience` 抽象层（自动 disconnect/connect 重连 + 心跳监控 + 命令重试）消化宿主网络与设备抖动，4 个执行器（android / perf / stability / fluency）统一接入
- [x] 实现 Android pytest 脚本执行器
  - [x] 从 MinIO 下载脚本到临时目录
  - [x] 自动安装 APK 到目标设备
  - [x] 调用 `pytest --json-report` 执行
  - [x] 解析结果，收集截图上传 MinIO
  - [x] 清理临时目录
- [x] 实现执行配置：设备选择 / APK 版本 / 超时

### 3.4 设备屏幕镜像

- [x] 实现 MJPEG 截图流（后端定期调用 `uiautomator2.screenshot()` 推流）
- [x] 前端：嵌入屏幕镜像视频流组件

### 3.5 Android 低代码模式

- [x] 支持操作：点击坐标 / 点击元素（text/resourceId/xpath）/ 长按 / 滑动 / 输入 / 截图断言
- [x] 前端：步骤配置表单
- [x] 实现低代码步骤 → uiautomator2 API 调用的执行器

---

## Phase 4 - 高级功能

### 4.1 接口测试协议扩展

- [x] **GraphQL**：支持 Query / Mutation，变量配置，断言
- [x] **WebSocket**：建立连接 / 发送消息 / 接收断言 / 超时配置
- [x] **gRPC**：上传 `.proto` 文件，方法调用，响应断言

### 4.2 测试套件

- [x] 实现 `TestSuite` CRUD 接口
- [x] 支持跨类型用例组合（Web + 接口 + Android）
- [x] 支持套件内用例顺序配置
- [x] 支持套件级数据驱动（CSV / JSON 参数化）
- [x] 实现套件执行触发接口（`POST /api/v1/suites/{id}/run`）
- [x] 前端：套件管理页面

### 4.3 测试计划与调度

- [x] 实现 `TestPlan` CRUD 接口
- [x] 配置 Celery Beat，支持 Cron 表达式定时触发
- [x] 实现手动触发 / 定时触发 / Webhook 触发三种模式
- [x] 前端：测试计划配置页面已实现（创建/编辑/执行/记录查看），并已支持半可视化 Cron 配置、表达式校验与可读化提示

### 4.4 CI/CD 集成

- [x] 实现 Webhook 触发接口（`POST /api/v1/webhook/trigger`，API Key 认证）
- [x] 测试结果支持 JUnit XML 格式导出（供 Jenkins 解析）
- [x] 提供 GitLab CI `.gitlab-ci.yml` 模板示例
- [x] 编写 CI/CD 集成文档

### 4.5 通知集成

- [x] 实现邮件通知（SMTP，执行完成后发送报告摘要）
- [x] 实现企业微信机器人通知
- [x] 实现钉钉机器人通知
- [x] 前端：通知配置页面
- [x] 限制通知读接口为工程师权限，避免泄露 Webhook/Secret
- [x] 在企业微信/钉钉返回非 200 或非零 `errcode` 时抛错，避免误报发送成功
- [x] 删除项目时级联删除通知配置，避免外键阻塞项目删除

### 4.6 统计看板

- [x] 实现统计数据聚合接口（总览、通过率趋势、执行时长趋势、失败 Top 10、执行人 Top、触发方式分布、计划/套件趋势）
- [x] 前端：统计看板页面（折线图 / 柱状图，基于 ECharts + vue-echarts）
- [x] 支持按项目、时间范围、用例类型筛选

---

## Phase 5 - 完善与优化

### 5.1 接口 Mock Server

- [x] 实现 MockRule 数据模型与 Alembic 迁移（`mock_rules` 表）
- [x] 实现 Mock 规则 CRUD 接口（`/api/v1/mock-rules`）
- [x] 实现 Mock 服务入口（`ANY /mock/{project_id}/{path}`，数据库实时匹配）
- [x] 前端：Mock 规则管理页面（规则表格 + 创建/编辑 Modal）
- [x] 前端：显示 Mock 服务基地址，方便复制使用

### 5.2 用例版本历史

- [x] 实现用例修改历史记录（快照存储）
- [x] 实现用例版本回滚接口
- [x] 前端：版本历史查看与回滚页面

### 5.3 报告导出

- [x] 支持执行报告导出为 HTML（内嵌截图）
- [x] 支持执行报告导出为 PDF
- [x] 支持单用例 / 套件 / 计划执行结果导出为 JUnit XML

### 5.4 缺陷跟踪集成（可选）

- [x] Jira 集成：失败用例一键创建 Issue
- [x] 禅道集成：失败用例一键创建 Bug
- [x] 敏感配置脱敏返回与落库加密基础能力

### 5.5 安全与性能

- [x] 敏感配置加密存储（环境变量中的密码、Token）
- [x] API 接口限流
- [x] 数据库查询优化（索引审查）
- [x] 大报告分页加载优化
- [x] Worker 资源隔离（防止单任务耗尽资源）

### 5.6 运维支持

- [x] 日志统一收集（结构化日志输出）
- [x] 健康检查接口（`GET /health`）
- [x] 截图/报告文件定期清理任务（超过保留期限自动删除）
- [x] 一键部署脚本与初始化数据（管理员账号、默认环境）

### 5.7 统一用例管理体验

- [x] 设计统一用例管理模块，支持在单页内切换项目、查看模块树、管理用例与直接执行
- [x] 后端用例列表接口支持按 `project_id` 过滤，满足统一页面按项目聚合查询
- [x] 前端新增独立的“用例管理”导航入口，并兼容项目页/看板跳转
- [x] 统一用例管理页支持项目选择、模块筛选、用例 CRUD、历史回滚入口与执行环境选择
- [x] 修复统一入口下模块树与 Android 用例编辑的项目上下文依赖，完成本地与部署验证

### 5.8 已完成的收口工作

- [x] 测试计划体验收口：Cron 可视化配置、表达式校验、可读化提示
- [x] Android 真机容器联调说明与前置校验补齐
- [x] 套件 / 计划级 HTML / PDF 报告导出
- [x] 缺陷跟踪附件上传、重复缺陷检测、连接测试、字段映射、状态同步、GitHub Issues 集成与执行详情页联动展示
- [x] 统计看板缓存与筛选维度补齐（执行人、触发方式、计划/套件趋势、case_type 联动）
- [x] Mock 条件响应、批量导入导出、缓存加速、响应模板、请求样本录制与规则版本号管理
- [x] 计划级自动缺陷结果展示、套件级 case run 明细展示与 Run / Suite / Plan 三层体验收口
- [x] 为新增的 Mock、缺陷跟踪、统计缓存、Android 前置校验补关键回归测试

### 5.9 后续可选优化项

- [x] Android 真机在不同宿主机 / Docker 网络环境下的稳定性验证沉淀（`docs/android-device-debugging.md` 新增"宿主网络与 Docker 环境差异"专章 + `scripts/android-network-doctor.sh` 一键诊断脚本）
- [x] Android 真机执行链路抖动自愈（`backend/app/services/adb_resilience.py` 抽象层：自动 disconnect/connect 重连 + 异步心跳监控 + 命令级重试；android / perf / stability / fluency 4 个执行器统一接入；可经 `ADB_RECONNECT_*` / `ADB_HEARTBEAT_*` 配置开关一键关闭）
- [x] 部署、运维与性能优化的持续打磨（Q7 Phase 3 已完成 Celery 队列 routing + 文档、慢查询 Grafana 面板、K8s resources 模板、worker 多阶段镜像优化；实际镜像体积与执行器冒烟需在 Docker 环境复验）
- [x] 少量页面残余 `any` / 宽类型结构的工程化收口（P1.6 批 1-4 已完成；`frontend/src` 除 locale 文案 key `any_method` 外无显式 any）

### 5.10 Q3 前端国际化 i18n

> 目标：在不影响现有布局与交互的前提下，支持中英文切换，并逐步移除前端页面硬编码中文文案。

- [x] `vue-i18n` 基础设施、语言切换与本地存储记忆已接入
- [x] 登录页、导航栏、通用按钮、Dashboard、计划列表已迁移
- [x] 套件列表已迁移：`SuiteList.vue` 的列表、批量操作、执行记录列、执行策略标签与错误提示已接入 `t(...)`
- [x] 用例主列表已迁移：`CaseList.vue` 的筛选、统计卡、批量导入/导出/移动、执行环境弹窗、工作流操作与消息提示已接入 `t(...)`
- [x] 执行记录与执行详情已迁移：`RunList.vue` / `RunDetail.vue` 的导出、步骤统计、截图/请求/响应区、缺陷创建弹窗、缺陷状态刷新与分页文案已接入 `t(...)`
- [x] Android 专项任务页已迁移：`SpecialTaskListView.vue` 的任务筛选、表格列、任务表单、调度配置与执行/删除消息已接入 `t(...)`
- [x] 系统管理部分页面已迁移：环境管理、通知配置、全局变量库、AI 模型配置已接入中英文文案
- [x] 本轮迁移已通过 `npm run type-check`（`vue-tsc --noEmit`）
- [x] 设备管理、APK 管理、Mock 服务已迁移：`DeviceList.vue`、`ApkList.vue`、`MockRuleList.vue` 的筛选、表格、弹窗、状态标签与消息提示已接入中英文文案
- [x] 项目列表与计划表单已迁移：`ProjectList.vue`、`PlanList.vue` 的项目卡片、AI 模型绑定、计划表单、Cron 配置、执行策略与消息提示已接入中英文文案
- [x] 后端通知模板 i18n 化：`services/notifier.py` 支持语言参数，通知配置增加语言字段
- [x] 英文文案复核：对业务术语、错误提示和 AI 生成相关提示进行二次校对（轻量 review pass 已完成；2026-05-21）

#### 后续执行计划

建议按页面耦合度和风险分批推进，单批完成后均执行 `npm run type-check`：

1. [x] 用例详情与历史批次：`CaseDetail.vue`、`CaseHistoryDrawer.vue` 已迁移，详情页、复制/评审/执行弹窗、版本对比与回滚提示已接入中英文文案，并通过 `npm run type-check`。
2. [x] 用例编辑抽屉批次：`AIGenerateDrawer.vue`、`WebCaseDrawer.vue`、`AndroidCaseDrawer.vue` 已迁移，AI 生成流程、Web 脚本/低代码配置、Android 配置表单主要可见文案已接入 locale，并通过 `npm run type-check`。
3. [x] Android 专项报告批次：`ReportCenterView.vue`、`ReportDetailView.vue` 已迁移，报告筛选、统计卡、趋势图图例、异常事件、报告文件、导出/下载提示已接入中英文文案，并通过 `npm run type-check`。
4. [x] 系统设置剩余批次：`StorageManagementView.vue`、`BugTrackerList.vue` 已迁移，存储策略、清理预览、缺陷跟踪表单、连接测试和删除确认已接入中英文文案，并通过 `npm run type-check`。
5. [x] 公共组件批次：`LowcodeStepEditor.vue`、`AndroidStepEditor.vue`、`ModuleTree.vue`、`KvEditor.vue`、`CaseStepEditor.vue`、`BatchOperationBar.vue` 已迁移，复用按钮、占位符、步骤类型、模块弹窗文案已接入 locale，并通过 `npm run type-check`。
6. [x] 后端通知模板批次：通知配置已增加语言选项，`services/notifier.py` 可根据配置生成中英文通知标题与正文；邮件、企业微信、钉钉通知均可按配置语言发送，并通过通知相关后端测试。
7. [x] 设备 / APK / Mock 批次：`DeviceList.vue`、`ApkList.vue`、`MockRuleList.vue` 已迁移，筛选、表格列、创建/编辑弹窗、状态标签、导入导出、屏幕镜像与消息提示已接入 locale；目标文件扫描无中文命中，并通过 `npm run type-check`。
8. [x] 项目 / 计划补齐批次：`ProjectList.vue`、`PlanList.vue` 已迁移，项目卡片、AI 模型绑定、计划表单、Cron 编辑器、Webhook Secret、执行策略和消息提示已接入 locale；目标文件扫描无中文命中，并通过 `npm run type-check`。
9. [x] 文案复核批次：已完成 `SuiteList.vue` 与 `CaseFormDrawer.vue` 迁移，套件表单/弹窗/抽屉、用例表单 4 类 case_type 配置均已接入 locale；已执行 `rg "[一-龥]" frontend/src/views frontend/src/components` 收口扫描，剩余中文仅限开发注释与 `RunDetail.vue` 后端错误字符串匹配（`认证` / `超时` / `不存在`），无剩余可见中文 UI 文案。

---

## 里程碑汇总

| 里程碑 | 完成条件 | 状态 |
|--------|---------|------|
| **M1** Phase 1 完成 | HTTP 接口测试用例可完整执行并看到报告 | `[x]` |
| **M2** Phase 2 完成 | Playwright 脚本可上传执行，报告含截图 | `[x]` |
| **M3** Phase 3 完成 | 真机连接，uiautomator2 脚本可执行 | `[x]` |
| **M4** Phase 4 完成 | 支持调度、套件、CI/CD 集成、看板 | `[x]` |
| **M5** Phase 5 完成 | 全功能上线，安全加固 | `[x]` |

---

## Phase 4.6 统计看板 — 后续优化计划

> 以下为统计看板的迭代优化项，按优先级排列，可在 Phase 5 或后续迭代中逐步实施。

### P0 - 体验完善（建议优先）

- [x] 看板空状态引导：无数据时显示引导提示（"还没有执行记录，去创建用例吧"）
- [x] 图表 Loading 状态：数据加载中显示骨架屏或 Spin
- [x] 通过率趋势补零：无执行的日期也在 X 轴显示（值为 0），避免折线断裂
- [x] 失败 Top 10 点击跳转：点击柱状图某条目可跳转到对应用例详情页
- [x] 响应式布局：小屏/平板下卡片和图表自适应宽度

### P1 - 维度扩展

- [x] 按用例类型（API / Web / Android）分组统计饼图 — Q5 长尾 1 收口；`GET /statistics/case-type-distribution`（按 case_type 分组返回 total/passed/failed/error/pass_rate + 5min cache）+ `DashboardView` 新增 LazyChartCard 饼图（pie 含详细 tooltip）

### P2 - 性能优化

- [x] 高频查询加 Redis 缓存：statistics 已有 5 分钟缓存；dataset list 与 mobile statistics 已补 60 秒 TTL 自然失效缓存
- [x] `test_runs` 表添加复合索引：`(status, created_at)` 和 `(case_id, status, created_at)` — Q5 长尾 2 收口；alembic 0029 新增 `ix_test_runs_case_id_status_created_at`，与 0015 的 `(status, created_at)` 互补
- [x] 看板数据按需加载：首屏只加载总览和通过率趋势，其余图表通过 `LazyChartCard` + `IntersectionObserver` 滚动到可视区再请求
- [x] 大时间跨度（> 90 天）自动切换为按周聚合：前端 days > 90 时传 `aggregate=weekly`，后端 4 个 trend 端点用 PostgreSQL `date_trunc('week', ...)` 聚合

### P3 - 高级功能

- [x] 看板数据导出：支持图表导出 PNG 图片与统计数据 CSV
- [x] 自定义看板：用户可选择显示/隐藏图表卡片，自定义排序并持久化到 localStorage
- [x] 项目级看板 vs 全局看板切换：Dashboard 支持全局/单项目 segmented 切换，单项目模式显示项目下拉并记忆选择，全局模式不传 project_id
- [x] 通过率/时长异常告警：支持项目级告警规则/事件、定时检查、通知触发、抑制窗口、规则配置页和 Dashboard 项目级告警提示

---

## Phase 5.1 Mock Server — 后续优化计划

> 以下为 Mock Server 的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 规则快速复制：一键复制已有规则，修改路径/响应即可
- [x] 响应体语法高亮：monospace 等宽字体 + JSON 格式化按钮
- [x] Mock 请求日志：记录最近 N 次命中 Mock 服务的请求（method/path/timestamp），方便调试
- [x] 路径模板支持：支持 `/api/users/{id}` 形式的路径参数匹配

### P1 - 功能增强

- [x] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则（D.2 - `POST /mock-rules/{id}/promote-sample`）
- [x] Mock 规则版本管理：规则修改历史，支持回滚（D.2 - `MockRuleSnapshot` 表 + 列表/回滚 API）

### P2 - 高级功能

- [x] 独立端口模式：可选将 Mock 服务运行在独立端口，URL 不带 `/mock/` 前缀 — P1.3 Q5 收口；`backend/app/mock_main.py` 独立 FastAPI 子应用 + `docker-compose.yml` 中 `mock-standalone` service（profile=`mock-standalone`），裸路径 `/{project_id}/{path}`
- [x] 请求录制回放：记录真实 API 请求，一键生成 Mock 规则
- [x] Mock 规则版本管理：规则修改历史，支持回滚

---

## Phase 5.2 用例版本历史 — 后续优化计划

> 以下为用例版本历史的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 快照详情展开/折叠 config JSON 内容，便于查看完整配置差异
- [x] 版本对比：选择两个版本进行 diff 可视化（name/description/tags/config 逐字段对比）
- [x] 快照列表分页加载：快照数量过多时分页查询，避免一次加载全部
- [x] 快照操作人显示为用户名而非 user_id（JOIN users 表或前端缓存映射）

### P1 - 功能增强

- [x] 手动创建快照：支持用户主动保存当前版本（不依赖编辑触发），并添加版本备注
- [x] 快照保留策略：可配置最大快照数量（如保留最近 50 个），超出自动清理最旧快照
- [x] 批量回滚确认：回滚前弹出详细对比弹窗，显示当前值 vs 快照值（后端 diff API 已就绪 `GET /cases/{id}/snapshots/diff?from=&to=`，前端弹窗待跟进）
- [x] 快照搜索：支持按版本号、名称关键字搜索快照（list_snapshots 新增 `q` 参数）

### P2 - 高级功能

- [x] 快照导出/导入：支持将某个版本导出为 JSON 文件，或从 JSON 导入恢复
- [x] 用例克隆自快照：从历史版本直接创建新用例（而非回滚覆盖原用例）
- [x] 审计日志：记录每次回滚操作的触发人、时间、源版本号，供合规审查 — Q5 长尾 3 收口；`rollback_case` 写入 `audit_logs (action=case.rollback, resource_type=test_case, project_id, detail=回滚用例 X → 快照 vN (snapshot_id=...))`，可在系统-审计日志页按 `case.rollback` 筛选查看

---

## Phase 5.3 报告导出 — 后续优化计划

> 以下为报告导出的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 导出按钮 Loading 提示优化：PDF 生成较慢（~3s），增加进度提示文案
- [x] HTML 报告样式增强：添加打印友好的 @media print 样式
- [x] 报告中显示用例类型标签（API / Web / Android）
- [x] 报告时间显示时区：当前使用服务器本地时间，改为 UTC+8 或可配置时区

### P1 - 功能增强

- [x] 报告模板可选：支持简洁版（无请求/响应）和完整版两种模板（`?template=summary|full`）
- [x] 视频嵌入：HTML 报告中嵌入执行录像（仅 HTML 版本，PDF 不支持视频）— P1.1 Q5 收口，从 `run.result_summary.video_url` 自动渲染 `<video controls>`

### P2 - 高级功能

- [x] 批量导出：支持选中多个执行记录一次性导出为 ZIP 包（`POST /runs/export/zip`，最多 50 条）
- [x] 定时报告邮件：结合通知模块，定时生成并发送 HTML 报告邮件 — P1.2 Q5 收口；NotificationConfig.config 新增 `attach_html_report` 开关，开启时 plan/suite 完成自动生成 HTML 报告并以 multipart/alternative 嵌入邮件正文
- [x] 自定义报告封面：支持配置公司 Logo、项目名称、报告标题（`?cover_title&cover_logo_url`）
- [x] 报告 CDN 缓存：生成后存入 MinIO，重复下载直接返回缓存文件（key 含 `updated_at` 自动失效）

---

## Phase 5.4 缺陷跟踪集成 — 后续优化计划

> 以下为缺陷跟踪集成的迭代优化项，按优先级排列。

### P0 - 体验完善

- [x] 创建成功后在执行详情页显示已关联的缺陷链接（存储 bug_id + bug_url 到 TestRun.result_summary）
- [x] 缺陷创建前预览：弹窗中展示即将提交的标题和描述内容，确认后再提交
- [x] 错误信息截断提示：当 error_message 或 response_data 过长时显示截断提示
- [x] 创建失败时给出更友好的错误提示（区分认证失败 / 网络超时 / 项目不存在等）

### P1 - 功能增强

- [x] 禅道多产品支持：配置中支持多产品切换（`product_map` 映射 + `override_product_id` 参数）

### P2 - 高级功能

- [x] GitLab Issues 集成：扩展第三方平台支持（`TrackerType.gitlab` + 完整 CRUD/查询/duplicate）

---

## Phase 5.5 安全与性能 — 后续优化计划

> 以下为安全与性能的迭代优化项，按优先级排列。

### P0 - 安全加固

- [x] 敏感配置落库加密：当前仅脱敏返回，后续可在写入时 Fernet 加密、读取时解密
- [x] 限流规则可配置化：将限流阈值移入 config.py / 环境变量，无需改代码即可调整
- [x] CSRF Token 保护：对非 API 客户端（浏览器直接访问）添加 CSRF 防护

### P1 - 性能增强

- [x] 分页游标优化：`cases/runs.py` 已上线 Keyset (cursor) 分页，OFFSET 模式向后兼容；下轮推广到 suites/plans
- [x] 执行记录列表延迟加载 steps：列表查询不 eager-load steps，仅详情页加载（`PaginatedRunsOut.items` 已收敛为 `TestRunListItem`）
- [x] Redis 查询缓存：9 个 statistics 端点统一走 `@cached_json` 装饰器（TTL 5min），删除原函数体内冗余双层 cache 逻辑

### P2 - 运维支持

- [x] 慢查询监控：SQLAlchemy event listener，> `SLOW_QUERY_THRESHOLD_MS`（默认 1s）的 SQL 输出 WARNING（带 trace_id + SQL 截断），并写入当前 OTel span 的 `atp.slow_query` attribute
- [x] Celery 任务超时告警：`task_failure` 信号识别 `SoftTimeLimitExceeded` + `task_revoked` 识别硬超时 → WARNING 日志 + OTel span attribute `atp.task_timeout=soft|hard`
- [x] 定期清理过期 test_runs 数据：超过保留天数的执行记录自动归档/删除（Celery `cleanup_old_completed_runs` 每日定时 + 新增 admin 预览/手动触发 API `/api/v1/admin/runs/retention/{preview,run}`）

---

## Phase 5.6 运维支持 — 后续优化计划

> 以下为运维支持的迭代优化项，按优先级排列。

### P0 - 日志完善

- [x] 日志级别可通过环境变量 `LOG_LEVEL` 动态配置
- [x] 请求级别 trace_id 注入：每个 HTTP 请求生成唯一 ID 贯穿日志链路
- [x] 关键业务操作审计日志：用例创建/删除、用户登录/权限变更等写入独立审计表

### P1 - 清理策略增强

- [x] 按项目维度配置不同保留天数 — P1.4 Q5 MVP 收口；`Project.run_retention_days_override` 字段 + 迁移 + Schema + `resolve_project_retention` / `preview_old_runs_by_project` service + `GET /admin/runs/retention/per-project-preview` 端点（清理任务暂仍按全局调度，per-project 真实清理待下迭代）
- [x] 清理前生成清理报告（即将删除的文件数量/大小），支持管理员确认 — Q5 长尾 4 收口；后端 `preview_old_runs` 已返回 plan/suite/test/mobile 数量 + `estimated_objects`，前端新增 `system/RunRetentionView.vue` 展示全局+按项目预览，"执行清理"按钮带 Popconfirm 二次确认显示待删数量
- [x] 支持手动触发清理（管理后台按钮）— Q5 长尾 4 收口；调用既有 `POST /admin/runs/retention/run`，结果展示在"本次清理结果"卡片

### P2 - 部署与监控

- [x] Kubernetes Helm Chart 部署方案（`deploy/helm/atp/` 含 backend/worker/beat/flower 4 Deployment + Service/Ingress/HPA/ConfigMap/Secret + `docs/deploy-helm.md`；Q6 P1.7 补齐 `values.yaml` 字段注释与 `values.schema.json`）
- [x] Prometheus + Grafana 监控集成（compose profile=observability 启停；backend `/metrics` + celery-exporter；预置 `ATP Overview` 仪表盘；自定义业务指标 stats_cache / slow_queries / celery_timeouts / run_retention_deleted；Q6 P1.7 新增 `deploy/grafana/alerts/atp-alerts.yaml` 5 条告警模板）
- [x] 数据库自动备份脚本（pg_dump 定时备份到 MinIO；`scripts/backup-postgres.sh` + `tasks_db_backup.py` 日/周双调度 + 保留策略 `DB_BACKUP_RETAIN_DAILY=7` / `DB_BACKUP_RETAIN_WEEKLY=4`；Q6 P1.7 新增 `scripts/restore-postgres.sh` 与 `docs/disaster-recovery.md` 恢复演练文档）

---

## Android 专项测试中心

> 实现时间：2026-03-30 ~ 2026-03-31

### 数据模型层

- [x] `MobileSpecialTask` — 专项任务（名称、类型、设备范围、APK配置、调度配置）
- [x] `MobileSpecialRun` — 执行记录（状态、耗时、摘要JSON快照）
- [x] `MobileMetricSample` — 指标采样（CPU/内存/FPS/电池，时间序列）
- [x] `MobileIncident` — 异常事件（crash/ANR/Fatal日志/Watchdog）
- [x] `MobileRunArtifact` — 报告产物（CSV/JSON/截图/日志/Trace文件）
- [x] `GlobalVariable` — 全局变量库（项目级/全局，加密存储）
- [x] Alembic 迁移文件

### 执行器层

- [x] `android_perf_executor.py` — 性能测试：周期性采样 CPU/内存/电池，写入指标样本，生成CSV
- [x] `android_stability_executor.py` — 稳定性测试：Monkey随机探索 + logcat监控崩溃/ANR
- [x] `android_fluency_executor.py` — 流畅度测试：场景化FPS采样 + jank计算
- [x] `adb_client.py` — ADB命令构建器（meminfo/gfxinfo/cpuinfo/batterystats/logcat）
- [x] `parsers.py` — 指标数据解析（meminfo/cpuinfo/gfxinfo/batterystats/logcat）
- [x] `collectors.py` — 采样会话管理 + 设备就绪校验
- [x] `aggregator.py` — 指标聚合 + 任务类型特定摘要计算

### Celery 调度

- [x] `tasks_mobile_special.py` — `run_mobile_special_task` 任务路由
- [x] `check-mobile-special-schedules` — Cron表达式轮询定时触发
- [x] `cleanup-stale-mobile-special-runs` — 超时运行记录清理

### REST API

- [x] Tasks CRUD + `POST /tasks/{id}/run` 触发执行
- [x] Runs 查询 + `POST /runs/{id}/stop` 停止
- [x] `GET /runs/{id}/samples` 指标样本
- [x] `GET /runs/{id}/incidents` 异常事件
- [x] `GET /runs/{id}/artifacts` 产物列表
- [x] `GET /runs/{id}/export/csv` CSV导出
- [x] `GET /runs/{id}/export/json` JSON完整报告导出
- [x] `GET /statistics/overview` 总览统计
- [x] `GET /statistics/trend` 每日趋势
- [x] `GET /statistics/task-stats` 各任务统计
- [x] GlobalVariable CRUD + Fernet加密

### 前端页面

- [x] 专项任务列表页（SpecialTaskListView.vue）— 项目/类型筛选、创建/编辑抽屉、执行/编辑/删除
- [x] 报告中心（ReportCenterView.vue）— KPI卡片、14天趋势图、运行记录表、导出、停止
- [x] 报告详情（ReportDetailView.vue）— 任务信息、KPI卡片、指标趋势图（ECharts）、异常事件表、报告文件表
- [x] 全局变量库（GlobalVariableLibrary.vue）— 项目级/全局切换、加密值遮罩/显隐、新建/编辑/删除

### 测试

- [x] `test_mobile_special_migration.py` — 迁移文件测试（5个测试）
- [x] `test_mobile_special_schema.py` — Schema验证测试（19个测试）
- [x] `test_mobile_special_parsers.py` — 解析器单元测试（15个测试）
- [x] `test_mobile_special_collectors.py` — 采样器测试（5个测试）
- [x] `test_android_perf_executor.py` — 性能执行器测试（8个测试）
- [x] `test_android_stability_executor.py` — 稳定性执行器测试（6个测试）
- [x] `test_android_fluency_executor.py` — 流畅度执行器测试（6个测试）
- [x] `test_mobile_special_tasks_api.py` — 任务API测试
- [x] `test_global_variables_api.py` — 全局变量API测试
- [x] `test_mobile_special_stats_api.py` — 统计Schema测试（3个测试）

### 2026-04-01 回归修复收口

- [x] 修复启动模型加载链路遗漏 `mobile_special_*` / `global_variables` 表注册的问题
- [x] 修复专项任务启用调度时 `next_run_at` 未初始化，导致定时任务永不触发的问题
- [x] 修复 worker 执行前未将 `device_id` 解析为设备 serial 的问题，并保留手动运行覆盖参数
- [x] 修复统计接口在 SQLAlchemy 2.0 下 `case()` 调用方式不兼容导致报表中心加载失败的问题
- [x] 修复全局变量读取接口返回密文的问题，支持默认脱敏与按需显式查看明文
- [x] 修复稳定性执行器使用一次性 `logcat -d` 导致运行期间 crash/ANR 漏采集的问题
- [x] 修复报告中心按任务类型筛选无效的问题，并完成后端测试与前端构建验证

---

## Q10 — 质量与稳定性深化（质量门禁优先）

> 实施计划：`docs/implementation-plan-2026-Q10.md`（2026-05-30 编制）
> 当前状态：已启动；发布收口与 PR 范围整理完成，Q10 已落地 ruff/mypy/coverage/Vitest/Bandit/依赖扫描，且 pip/npm 依赖漏洞已清零。
> 定位：从「功能完整」推进到「质量可度量、回归可防护、工程可信赖」；不新增业务方向。
> 缺口画像：基础质量门禁、ruff format 基线、依赖漏洞清零、密钥/镜像扫描、Dependabot/security workflow、真实依赖集成、suite / plan 关键运行路径 E2E、SLO 薄切、flaky 治理与最终验收文档已完成。

### 启动顺序（2026-07-08 更新）

- [x] 0.1 发布收口：确认当前优化批次的提交范围、测试证据、文档同步和 PR 描述。
- [x] 0.2 环境矩阵验证：Python 3.14 本地全量回归通过；Docker `python:3.12-slim-bookworm` 目标运行时全量后端回归通过。
- [x] 0.3 前端构建验证：`npm run type-check` 与 `npm run build` 已通过，当前仅保留已知 circular chunk 警告。
- [x] 0.4 Q10 Phase 1 开工：新增 ruff 配置与 lint job，先以最小豁免建立可持续门禁。
- [x] 0.5 Q10 Phase 4 开工：新增 Bandit、pip-audit 与 npm audit 本地扫描命令，记录 SAST 与依赖漏洞基线。
- [x] 0.6 Q10 Phase 4 依赖升级收口：升级 FastAPI/Starlette、python-multipart、pytest/pytest-asyncio、Jinja2、cryptography、prometheus-fastapi-instrumentator、Vite/Vitest、Axios、ECharts、vue-i18n，并用 npm overrides 覆盖残留传递依赖漏洞；Q11-02 复扫时已将 `python-jose` 迁移到 `PyJWT[crypto]==2.13.0` 以移除 `ecdsa` 漏洞链。
- [x] 0.7 Q10 Phase 1 format 基线收口：执行 `ruff format backend/app backend/tests`，新增 `make format` / `make format-check`，并将 `ruff format --check` 接入 CI 与 pre-commit。
- [x] 0.8 Q10 Phase 5 收口：已新增并跑通 suite-run / plan-trigger / notification / bug-report 集成用例；补齐 `test_suites.config` 与 `bug_trackers.tracker_type` Alembic 迁移缺口后，真实 Postgres / Redis / MinIO 环境 integration suite 为 `10 passed`，二次重复运行仍为 `10 passed`；suite / plan 前端关键运行路径 E2E 已通过；SLO 薄切已新增 run outcome 指标、3 条 SLO 口径与 Grafana 错误预算面板；flaky 治理已新增 marker、一次有界重试和处理约定；Q10 验收总结与 README / 进度文档已同步。

### Phase 1 — 后端代码质量门禁 [P0]

- [x] ruff lint + format 配置（`pyproject.toml`）+ 存量基线豁免（per-file-ignores）：已启用 F821/F822/F823 最小 lint 门禁，并完成 format 全量基线
- [x] ruff format 一次性统一（独立 commit + `.git-blame-ignore-revs`）：格式化已落地，`.git-blame-ignore-revs` 已新增；待提交后只需补入格式化 commit SHA
- [x] mypy 渐进式覆盖 `core/` / `schemas/` / `services/`
- [x] `.pre-commit-config.yaml` 新建
- [x] CI 新增 lint job（ruff check + format --check）：`backend-lint` job 已同时运行 `ruff check` 与 `ruff format --check`

### Phase 2 — 测试覆盖率门禁 [P0]

- [x] pytest-cov 接入（`[tool.coverage]`）+ 跑出后端覆盖率基线并记录
- [x] CI 加 `--cov-fail-under=<基线-1%>` 门禁 + 覆盖率报告 artifact

### Phase 3 — 前端单元测试从 0 到 1 [P0]

- [x] vitest + @vue/test-utils + jsdom + @vitest/coverage-v8 接入
- [x] 首批：`stores/auth` / `api/http`(拦截器/401) / `utils/websocket` / 1-2 纯组件
- [x] 第二批：`stores/theme` / `utils/chartTheme`，覆盖主题持久化、DOM 属性、系统深色偏好、ECharts 主题注册幂等和主题切换
- [x] CI 前端 test 步骤（与 type-check/build 并列）

### Phase 4 — 自动化安全扫描 [P1]

- [x] bandit SAST + 基线豁免
- [x] pip-audit（后端）+ npm audit / osv-scanner（前端）依赖扫描：本地命令已落地；后端 6 个包 25 条记录、前端 16 条记录已完成升级收口，当前 `pip-audit` 与 `npm audit --audit-level=moderate` 均为 0 漏洞
- [x] trivy 镜像扫描（联动 release-readiness）：新增 security workflow，对 backend / worker / frontend 镜像按 HIGH/CRITICAL 阻断
- [x] gitleaks 密钥扫描（CI + pre-commit）：CI Gitleaks 扫描 + 本地 pre-commit 官方钩子（v8.24.3，复用 .gitleaks.toml；Q14-05 收口）
- [x] `.github/dependabot.yml` 四生态 + `.github/workflows/security.yml`（仅 high/critical 阻断）

### Phase 5 — 集成扩展 + SLO + 收口 [P2]

- [x] 5.1 集成测试补 suite-run / plan-trigger / notification / bug-report
  - [x] 5.1.1 新增 suite-run / plan-trigger 链路用例：创建项目/模块/API 用例、审批用例、创建套件、触发 suite run、创建计划、触发 plan run。
  - [x] 5.1.2 在真实 Postgres / Redis / MinIO 环境执行 integration suite，并记录命令与结果：临时端口 Postgres `55432` / Redis `6380` / MinIO `19000`，空库 `alembic upgrade head` 通过，`backend/tests/integration -m integration` 为 `10 passed`，二次重复运行仍为 `10 passed`。
  - [x] 5.1.3 补 notification 真实配置/发送降级路径集成验证：覆盖创建、敏感字段遮蔽、测试发送走解密配置、Webhook 失败转 HTTP 500。
  - [x] 5.1.4 补 bug-report 失败执行到缺陷创建/关联/去重的集成验证：覆盖 tracker 创建、连接测试解密配置、重复缺陷短路、创建缺陷写回 run summary、刷新状态、手动关联既有缺陷。
- [x] 5.2 E2E 补 suite / plan 关键路径
  - [x] 5.2.1 suite：加载套件、触发执行、查看执行记录抽屉。
  - [x] 5.2.2 plan：加载计划、手动触发、查看计划运行记录。
  - [x] 5.2.3 完整 Playwright E2E 回归：`9 passed`。
- [x] 5.3 flaky 治理（pytest-rerunfailures + 标记 + 文档）
  - [x] 5.3.1 明确 integration / e2e flaky 标记策略与重试边界：`docs/flaky-governance.md` 已新增。
  - [x] 5.3.2 将重试策略接入 CI 或记录为 release-readiness 手工步骤：integration workflow 已接入 `--reruns 1 --reruns-delay 2`，Playwright CI 保持 `CI=true` 时一次重试。
- [x] 5.4 SLO 薄切（API 可用性 / P95 / run 成功率 3 条 + 错误预算面板，复用既有 Grafana）
  - [x] 5.4.1 定义 3 条 SLO 与数据来源：`docs/slo-guide.md` 已覆盖 API 可用性、P95、run 成功率与错误预算口径。
  - [x] 5.4.2 更新 Grafana dashboard / alert 说明：`ATP Overview` 已新增 4 个 SLO 面板，`docs/observability-guide.md` 已同步。
- [x] 5.5 `docs/q10-acceptance-summary.md` + README / Task.md 收口
  - [x] 5.5.1 汇总质量门禁、安全扫描、覆盖率、集成/E2E、SLO 验收证据。
  - [x] 5.5.2 同步 README、Task.md、CONTEXT.md、MEMORY.md 与 release evidence。

---

## Q11 / Q12 — 生产就绪与持续质量优化

- [x] Q11 全部 15 项完成，验收证据见 `docs/q11-acceptance-summary.md`。
- [x] Q12-00 消除 41 条 `PytestCollectionWarning`：`backend/tests/conftest.py` 的 `pytest_pycollect_makeitem` 钩子统一跳过从 `app.*` 导入的 `Test*` 类（测试保留原始类名导入），pytest 将该警告升级为错误；完整后端回归 `840 passed`。
- [x] Q12-01 刷新覆盖率基线：后端 `53.46%` / 门禁 `52%`；前端 statements `3.66%`、branches `4.06%`、functions `2.26%`、lines `3.92%`，已建立 3%/3%/2%/3% 初始门禁及 CI artifact。
- [x] Q12-02 增补认证、用例执行、调度和报告关键前端流程测试：四个切片均完成，前端 `47 passed`，全源 coverage `4.44/4.88/3.01/4.66%`，门禁同步抬升。
- [x] Q12-03 收敛依赖弃用提示：vue-i18n 升级到 `11.4.6`（Composition 模式无 breaking），传递依赖 glob 经 npm override 固定到 `13.0.6`；clean install 零 `npm warn deprecated`。46 tests、type-check、build、E2E 9 passed。
- [x] Q12-04 前端 chunk 边界治理：改用 unplugin-vue-components 按需注册 Ant Design（替代全局 app.use），并将 chartTheme 移出入口依赖；/login 首屏 gzip 传输 773.9→510.1 kB（-34%），ant-design chunk 1502.45→1246.41 kB，构建零告警；46 tests、type-check、E2E 9 passed。后续已完成：components.d.ts 已开启并提交，112 处存量 a-* props 类型不匹配全部修复（见下条）。
- [x] Q12 类型加固：开启 unplugin-vue-components dts，修复全部 112 处存量 a-* props 类型错误（bodyCell record 断言 helper、v-model null 断言、badge/handler 签名收窄），vue-tsc 对模板组件 props 实现真实检查；46 tests、type-check 0 错、build、E2E 9 passed、后端 841 passed。
- [x] Q12-05（本地部分）冻结外部就绪证据口径：`docs/q12-external-readiness-evidence.md` 定义 SLO 7/14 天历史与 Android 真机演练的记录字段、通过标准与证据落点，契约测试 3 passed；采集执行待环境（长期抓取部署 + 真机）。
- [x] Q13 规划发布：`docs/optimization-roadmap-2026-q13.md`——7 个工作项：Q13-00 承接 Q12-05 采集与 Q12 验收、Q13-01 执行链路覆盖（tasks.py+9 executors，后端 53%→60%、gate 52→56）、Q13-02 服务/API 覆盖（bug_reporter/ai_healing/failure_diagnosis/exports/mobile_special）、Q13-03 前端工作台四视图行为切片（statements ≥8%）、Q13-04 Ant Design 路由级 chunk 证据与决策、Q13-05 AI 自愈 apply 闭环切片（feature-flag+审计）、Q13-06 依赖卫生。首个动作：Q13-01 执行器单元缝。
- [x] Q13-01 切片 1（执行链主体）：新增 `test_tasks_execution_chain.py` 34 项测试覆盖 run_test_case/run_test_suite/run_test_plan/_execute_plan_suite/check_cron_plans/check_dashboard_alerts 全部主干与异常分支；tasks.py 35%→86%，后端 TOTAL 53%→55.65%（878 passed）；单元缝约定沉淀到 `docs/coverage-baseline-2026-q13.md`。
- [x] Q13-01 切片 2（HTTP 家族执行器）+ 收官：`test_http_family_executors.py` 46 项测试只 fake 传输边界（httpx/websockets/grpc channel），api/graphql/websocket/grpc 执行器 3-8%→88-94%；**发现并修复生产级故障**：protobuf 5+ 移除 `message_factory.GetPrototype`，grpc 执行器此前每次执行必报错，改用 `GetMessageClass`。后端 TOTAL 60.03%（924 passed），CI 门禁 52%→56%。
- [x] Q13-02 切片 1（服务层）：`test_bug_reporter_unit.py` 38 项（Jira/禅道/GitHub/GitLab 四平台共用一个脚本化 httpx fake，payload 组装/鉴权/去重/JQL 转义/错误路径全走真实现）+ `test_failure_diagnosis.py` 15 项（规则分类矩阵、修复建议映射、LLM 成功/失败/限额/兜底三态）；bug_reporter 20%→95%、failure_diagnosis 12%→97%，TOTAL 63.35%（962 passed）。
- [x] Q13-02 切片 2（ai_healing run 级）：`test_ai_healing_run_level.py` 23 项——run_diagnosis_for_run 全状态（幂等/case 缺失/无配置/step 不足/缓存命中/日限额/解密失败/LLM 成败）、缓存键顺序无关性、文本与 vision 日限额、截图装载、run hook 阈值与入队兜底；ai_healing 46%→89%，TOTAL 64.50%（985 passed）。
- [x] Q13-02 切片 3（exports）：`test_exports_junit_reports.py` 18 项——run/suite/plan 三级 JUnit（含无 step 的 run 级 failure/error/skipped 合成、套件缺失 error 用例、真实 TestRun 耗时回查）、suite/plan 聚合 HTML 构建器、HTML 缓存命中/未命中、PDF 路由（Playwright 渲染边界 fake）、缓存读写存储异常吞；exports 36%→92%，TOTAL 65.97%（1003 passed）。
- [x] Q13-02 切片 4（mobile_special API）+ 收官：`test_mobile_special_routes.py` 16 项——任务 CRUD（访问检查/调度刷新/None 字段不覆盖）、触发（config 快照/设备回退/Celery 入队）、停止守卫、runs 联表查询、samples/incidents/artifacts、CSV/JSON 导出；**发现并修复生产级故障**：create_task 因 schema 的 created_by 与显式 kwarg 键冲突而每次调用必 500。mobile_special 45%→91%，TOTAL 66.98%（1019 passed），CI 门禁 56%→62%。
- [x] Q13-03 切片 1（CaseList）：抽 `utils/caseList`（level 筛选/待评审与 flaky 计数/工作流守卫状态机/flaky 提示参数/模块树扁平化），`caseList.spec.ts` 5 组断言；CaseList.vue 改用受测 helper（activeFilterTags 仅保留 i18n 标签映射、工作流守卫单点分发），type-check 0 错、E2E 仍绿；前端 statements 4.38%→4.65%（51 passed），门禁抬至 4.4/5.1/2.9/4.6。
- [x] Q13-03 切片 2（RunDetail）：抽 `utils/runDetail`（步骤状态统计/展开策略/参数化迭代摘要/run 级自愈与失败诊断载荷归一化/主错误摘要截断/状态色），`runDetail.spec.ts` 7 组断言；RunDetail.vue 改调 helper，type-check 0 错、run-detail E2E 仍绿；前端 statements 4.65%→5.10%（58 passed），门禁抬至 4.85/6.35/3.35/4.95。
- [x] Q13-03 切片 3（SuiteList）：扩充 `utils/suiteList`（模块后代映射 buildModuleDescendantMap、tree-select 空枝剪裁 buildModuleTreeOptions、用例不可执行原因分类 caseExecutionReasonKey、结构化用例筛选谓词 passesSuiteCaseStructuralFilter），`suiteList.spec.ts` +4 组断言；SuiteList.vue 删本地副本改调 util，type-check 0 错、suite-plan E2E 仍绿；前端 statements 5.10%→5.54%（62 passed），门禁抬至 5.3/7.15/3.45/5.35。
- [x] Q13-03 切片 4（DashboardView）：抽 utils/dashboardView（日期区间生成 generateDateRange、泛型趋势补零 fillTrendGaps 含 today 注入、布局归一化 normalizeDashboardLayout），dashboardView.spec.ts 6 组断言（含钉住『已存在但结构错误的已知 key 既不保留也不补回』的微妙契约）；DashboardView.vue 删本地副本改调 util，type-check 0 错、dashboard E2E 与生产构建仍绿；前端 statements 5.54%→5.95%（68 passed），门禁抬至 5.7/7.5/3.7/5.7。四工作台切片全部完成；≥8% 验收目标顺延到 form-drawer 追加切片。
- [x] Q13-03 追加切片（CaseFormDrawer）：抽 utils/caseFormConfig（配置步骤解析 getFirstStep、form body 回填 parseFormBody、GraphQL 变量 parseGraphqlVariables、WebSocket 消息归一 normalizeWsMessage、保存态请求体 resolveRequestBody），caseFormConfig.spec.ts 6 组断言；CaseFormDrawer.vue 删本地解析副本改调 util，type-check 0 错、E2E 与构建仍绿；前端 statements 5.95%→6.33%（branches 越过 8%，74 passed），门禁抬至 6.05/8.05/3.9/6.1。
- [x] Q13-03 切片（PlanList cron）：扩充 utils/planList（buildCronExpression 按 daily/weekly/custom 拼 cron、formatCronTime 补零 HH:MM），planList.spec.ts +3 组断言；PlanList.vue cron 预览/描述改调 util，type-check 0 错、suite-plan E2E 与构建仍绿；前端 statements 6.33%→6.40%（branches 8.4%，77 passed）。helper 抽取对 statements 边际收益已递减——到 8% 需组件挂载测试（@vue/test-utils），非继续抽 helper；已在 roadmap 记录评估与建议。
- [x] Q13-06 依赖卫生：审阅并固化 frontend allowScripts 白名单（core-js 赞助提示/fsevents 原生绑定/vue-demi Vue3 入口切换，三者均核实无害），npm ci 零 allow-scripts 与零弃用告警、audit 0 漏洞；新增 docs/dependency-hygiene.md 与契约测试 test_dependency_hygiene.py（3 passed）。顺带修复 Q13-03 slice4 重构后遗留的 test_dashboard_routes 静态契约（DEFAULT_DASHBOARD_LAYOUT 已移至 utils/dashboardView）。
- [x] Q13-04 Ant Design 路由级 chunk 证据与决策：实测 /login 首屏在单体 antd chunk 下拉取 374.7/510.1 kB gzip（73%）；移除 manualChunks 的 ant-design 归并、让按需组件随路由分裂后，/login 首屏 510→336 kB（-34%，-174 kB，远超 15% 门槛），代价 dist JS 总量 +~35 kB（共享运行时在少数路由 chunk 重复）。结论 GO 并采纳，chunkSizeWarningLimit 1500→600（echarts 563 成新上限）；全量 E2E 9 passed 于真实浏览器验证。证据与决策见 docs/frontend-bundle-decision.md，契约测试同步更新。
- [x] Q13-05 AI 自愈 apply 闭环（iter5 phase 2）：加 `AI_HEALING_APPLY_ENABLED`（默认关，apply 未启用返回 403；preview 只读门常开）+ 7 项行为测试（iter5 API 0%→72%）；修复端点 `ProjectRole.engineer` 潜在 500（第三个覆盖工作暴露的生产故障）+ 两处 sys.modules 测试隔离脆性。全库 1029 passed、TOTAL 67.76%。
- [x] Q13-03 收官（挂载测试切片）：`ApkList.spec.ts`（4 项）+ `DeviceList.spec.ts`（5 项）@vue/test-utils 挂载测试，ApkList 0→56%、DeviceList 0→62%；**前端 statements 6.40%→8.51%，达成 ≥8% 验收线**（挂载测试 +1pt/个 vs helper +0.07pt/个）。门禁 8.2/9.6/6.2/8.15，type-check/build/全量 E2E 绿。所有本地 Q13 项完成，仅剩 Q13-00 待环境。
- [x] Q13-01 补切片（web 家族执行器）：`test_web_executor.py`（8 项，fake subprocess.run 写 json-report + MinIO 边界，覆盖脚本缺失/超时/无测试/多步映射/截图上传/浏览器回退/healing hook）+ `test_web_lowcode_executor.py`（8 项，fake Page 记录动作分发 goto/click/fill/assert/press/wait/screenshot/unknown + 变量替换递归）。web_executor 13%→84%、web_lowcode 15%→51%，后端 TOTAL 67.76%→69.29%（1045 passed）；两文件加 minio 符号导入保护，免疫跨文件 stub 污染。
- [x] Q13-01 补切片（android 家族执行器）：扩充 `test_android_lowcode_executor.py`（+11 项，fake `_adb_cmd` 覆盖 click/long_click/swipe(方向+坐标)/input(转义+clear)/press_key(命名+原样)/start_app/stop_app/assert_text/assert_element/wait/screenshot/未知动作 + 变量递归替换）与 `test_android_executor.py`（+3 项，run_android_case 的脚本缺失/设备缺失/设备不可达三个前置守卫）。android_lowcode 15%→53%、android_executor 12%→23%，**后端 TOTAL 69.29%→70.23%，九个执行器全部有行为覆盖**（1059 passed）。
- [x] 后端覆盖延伸（environments API）：数据驱动挑最大 0% 模块——`test_environments_routes.py`（11 项，list/create/update/delete 环境 + 变量读取掩码 + 批量保存的删/插/密钥加密，含 404 与项目访问角色断言、重复 key 校验）。`api/v1/environments.py` 0%→100%，后端 TOTAL 70.23%→70.92%（1070 passed），CI 门禁 62%→66%。
- [x] 后端覆盖延伸（WebSocket 端点）：`test_ws_routes.py`（15 项，fake session/redis/WebSocket）——token 校验（缺失/非法/非 access 类型/用户缺失或禁用/有效）、run 订阅授权阶梯全五档（admin/触发者/用例创建者/项目成员/项目 owner + 各拒绝分支）、握手（未授权 1008/禁止 1008/accept）→pubsub 转发→收到 completed 主动关闭 + finally 清理。`api/v1/ws.py` 0%→89%，后端 TOTAL 70.92%→71.62%（1085 passed）。两个最大的 0% 模块（environments/ws）均已覆盖。
- [x] 后端覆盖延伸（mobile_special collectors）：`test_mobile_special_collectors_sampling.py`（10 项，fake run_adb_shell + parse_*）——SamplingSession 的 PID 解析（有/无输出）、四个采样器的 parser 路由与空输出→None、PeriodicSampler 的按 metric_types 产出/跳过 None/停止、device/package 校验器。`services/mobile_special/collectors.py` 0%→92%，后端 TOTAL 71.62%→72.26%（1095 passed）。
- [x] 后端覆盖延伸（mobile_special 调度分发）：`test_tasks_mobile_special_dispatch.py`（15 项，沿用 tasks.py 单元缝范式）——run_mobile_special_task 的 run/task 缺失、按 task_type 路由到 perf/stability/fluency executor、config 合并+设备解析、executor 异常→failed+completed 推送、设备 serial 解析；check_mobile_special_schedules 触发+cron 重排+坏 cron 禁用；cleanup 批量 update；3 个纯 helper 优先级。`worker/tasks_mobile_special.py` 26%→97%，后端 TOTAL 72.26%→72.87%（1110 passed）。至此 mobile-special 全链路（API/tasks/collectors/parsers）均有行为覆盖。
- [x] backend coverage extension (plans API, core business entity): test_plans_routes.py (16 tests) — suite-id validation (dup/missing/wrong-project) + env validation (404/wrong-project), create cron next_run_at + webhook secret gen, update next-run clear when not cron, manual run trigger env-var merge + empty/404 guards, and the webhook trigger secret-auth ladder (404 / non-webhook 400 / bad-secret 403 / empty-suites 400). api/v1/plans.py 55 -> 80%, backend TOTAL 73.76 -> 74.16% (1154 passed).
- [x] backend coverage extension (bug_trackers API, closes the bug-report subsystem with the earlier bug_reporter service): test_bug_trackers_routes.py (13 tests) — config encrypt-on-create + mask-on-read, the _merge_sensitive_config keep-existing-secret-when-masked/omitted invariant on update, CRUD 404s, and test-connection (inline config, saved-secret merge, type-mismatch graceful reject, backend-error swallow). api/v1/bug_trackers.py 55 -> 75%, backend TOTAL 73.41 -> 73.76% (1138 passed).
- [x] backend coverage extension (projects API, permission-system root): test_projects_routes.py (15 tests) — project CRUD (creator auto-owner + auto code), module-tree build/nest/sort + module CRUD access checks, member list mapping, member add (404 missing user / 409 duplicate), role update, and the remove-member last-owner-block security invariant. api/v1/projects.py 41 -> 79%, backend TOTAL 72.87 -> 73.41% (1125 passed).
- [ ] Q12-05 补充生产型 SLO 历史和物理 Android 设备执行证据。

当前路线图：`docs/optimization-roadmap-2026-q15.md`（2026-07-31 起草，**待评审**）。上一轮 Q14 七项中本地可执行项已全部完成，`docs/q14-completion-audit.md` 逐项记录完成证据；Q14-00 承接 Q12-05 采集（待环境），需要生产 SLO 7/14 天历史和 Android 真机演练后再发布 `docs/q12-acceptance-summary.md`。

---

## Q14 — 覆盖固化与工程遗留收口

> 实施计划：`docs/optimization-roadmap-2026-q14.md`（2026-07-11 编制）

- [ ] Q14-00 承接 Q12-05：生产 SLO 7/14 天历史 + Android 真机演练采集，随后发布 `docs/q12-acceptance-summary.md`（待外部环境；`make collect-q12-evidence` 已可自动采集 Prometheus/API/ADB 并生成证据，`make scaffold-q12-evidence` 仅作草稿初始化，`make validate-q12-evidence` 做结构校验）
- [x] Q14-01 Android/ADB 执行器覆盖：android 四执行器 82-93%、web/android_lowcode 97/98%、adb_service 97%；TOTAL 81%、CI 门禁 66→70（Makefile 同步 70）
- [x] Q14-02 API 路由覆盖扫尾：suites 100%、notifications 99%，并补齐 ai_healing_stats / devices / healing_prompt_examples 路由缝；TOTAL 82.20%、1310 passed
- [x] Q14-03 前端工作台挂载测试：CaseList / RunDetail / SuiteList / DashboardView / PlanList 均有组件级挂载测试；前端 statements 21.48%、102 passed，门禁提升到 20.5
- [x] Q14-04 按项目保留天数真实清理：override 项目按各自截止时间清理四种 run 类型，全局兜底排除 override 项目；预览补齐 test/mobile 按项目统计；run_retention 78→90%
- [x] Q14-05 Gitleaks pre-commit 本地钩子：官方钩子 v8.24.3 接入 `.pre-commit-config.yaml` 复用 `.gitleaks.toml`；Makefile 门禁漂移已在 Q14-01 一并修复（52→70）
- [x] Q14-06 Q13 验收总结：`docs/q13-acceptance-summary.md` 已发布（六个工作项 + 覆盖延伸 53→74-75% + 四个生产 bug + 前端 4.38→8.51%）

---

## Q15 — 门禁生效与测试可靠性（草案，待评审）

> 实施计划：`docs/optimization-roadmap-2026-q15.md`（2026-07-31 起草，尚未立项；以下条目在评审通过前不作为承诺范围）
>
> 实测输入（2026-07-31）：后端 TOTAL 82.73%（13962 语句 / 2045 未覆盖，1327 passed，门禁 70）；前端 statements 21.48% / branches 18.48% / functions 17.44% / lines 22%；183 个非 integration 测试文件逐个单独运行有 10 个失败（5.5%）。

- [ ] Q15-00 承接 Q14-00 / Q12-05：生产 SLO 7/14 天历史 + Android 真机演练采集，随后发布 `docs/q12-acceptance-summary.md`（待外部环境，已连续顺延三个季度；若环境短期不可得，应显式重新定界而非继续顺延）
- [~] Q15-01 让已声明的门禁真正拦得住（本地部分完成；服务端强制力不可得）：确认并记录 `main` 的分支保护状态、把 `ci.yml` 各 job 设为 required status checks（若当前套餐不支持，则退化为文档约定 + 本地钩子并如实说明）；`pre-commit install` 纳入 `make setup` 与 CLAUDE/AGENTS 验证章节；修掉 `.pre-commit-config.yaml` 中 mypy 钩子对环境 `PATH` python 的依赖；补 Makefile 与 `ci.yml` 覆盖率门禁的漂移回归
- [x] Q15-02 后端测试单文件可运行：183 个非 integration 文件逐个通过；8 个 `No module named 'app'` 走统一 `sys.path` 引导（扩展 `backend/tests/_paths.py` 或加 `tests/__init__.py`）、根 conftest 的 `app.api.deps` stub 补 `assert_project_access` / `require_project_access`、`test_conftest_stubs.py` 不再依赖环境中可导入的 `tests` 包；CI 增加逐文件扫描防回归
- [x] Q15-03 Windows CI job：`ci.yml` 增加 `windows-latest` 后端 pytest job（Python 3.12，单测已 stub 基础设施故无需 service container），纳入 Q15-01 的 required 集合；`docs/ci-workflows.md` 说明范围与刻意排除项（integration / E2E 仍仅 Linux）
- [x] Q15-04 前端系统管理页面挂载测试：新增 `DatasetLibrary` / `StorageManagementView` / `NotificationList` / `BugTrackerList` / `MockRuleList` / `mobile-special/ReportCenterView` 六组组件测试；前端 `31 files / 128 tests`，statements `32.96%`，`views/system` statements `37.36%`，达到 ≥35% / ≥28% 目标；Vitest 门禁提升为 statements/branches/functions/lines `31.5 / 26.5 / 24.5 / 32.5`；实际文件路径与原草案中的 `MockRulesView`、`views/system/ReportCenterView.vue` 差异已按仓库路由校准
- [x] Q15-05 后端 worker / 维护任务覆盖与门禁校准：`worker/tasks_performance.py`（当前 0%）、`worker/tasks_db_backup.py`、`services/ai_healing_stats.py`、`services/dashboard_alerts.py`、`services/mobile_special/aggregator.py` 补行为缝；后端 TOTAL ≥86%，CI 门禁 70→82 使其重新贴近实际
- [x] Q15-06 处理 `chartTheme.spec.ts` 的负载敏感：或给其动态 import 配相称的超时（或去掉动态 import），或按 `docs/flaky-governance.md` 立案登记原因/证据/退出条件；不接受「全局抬高 testTimeout」了事，需说明选择了哪条路径及理由

**Q15 进展（2026-08-06）**：Q15-02 / Q15-03 / Q15-04 / Q15-05 / Q15-06 / Q15-07 已完成，Q15-01 完成本地可做部分；仅剩待外部环境的 Q15-00。Q15-04 新增六组组件级挂载测试，覆盖初始化、错误提示、配置 CRUD、导入导出、清理执行、报告筛选/停止/下载、图表主题切换与卸载清理等行为；完整前端 `31 files / 128 tests passed`，statements `32.96%`，`views/system` statements `37.36%`，类型检查和生产构建通过。实际代码中 `MockRuleList.vue` 位于 `views/mock`，`ReportCenterView.vue` 位于 `views/mobile-special`，已按真实路由记录。分支保护经实测不可得 —— 仓库是个人账户下的 private 仓库，`branches/main/protection` 与 `rulesets` 两个 API 均返回 403（需 GitHub Pro 或转为 public），因此 required status checks 无法配置，Q15-01 与 Q15-03 中「纳入 required 集合」一条在当前套餐下无法满足，已按路线图预案降级为「文档约定 + 本地钩子」并在 `docs/ci-workflows.md`「门禁强制力现状」如实说明其边界（可被 `--no-verify` 绕过）。过程中另修两个既有缺陷：mypy 钩子与 `ci.yml` 的 lint job 都只装开发依赖，看不到 SQLAlchemy 真实签名（`d116359^` 的 run_retention.py 只报 8 个错而完整环境报 12 个，少掉的 4 条 `not_in()` arg-type 正是催生本季度的那批）；ruff 的受检脚本清单此前只在 Makefile 生效，CI 与钩子都没覆盖 `scripts/`。Q15-05 把五个指定模块（`tasks_performance` 0%、`aggregator` 9%、`ai_healing_stats` 26%、`tasks_db_backup` 44%、`dashboard_alerts` 56%）抬到 93–100%，并补了四个路由 —— 其中 `api/v1/auth.py` 与 `api/v1/scripts.py` 此前均为 0%（CLAUDE.md 举例引用的 `backend/tests/api/test_auth.py` 实际并不存在）。Q15-07 已发布 `docs/q14-acceptance-summary.md`，Q15-00 仍等待生产型 SLO 历史与物理 Android 设备证据。后端 `1467 passed`、TOTAL **86.04%（Python 3.12，CI 口径）/ 85.55%（Python 3.14，本地）**，门禁 70 → **82**；同一命令在两个解释器下语句总数不同（13962 vs 13367，差 0.5 个百分点），这正是路线图规划输入 82.73% 本地复现不出来的原因，抬门禁以 3.12 为准并复验 3.14，详见 `docs/coverage-baseline-2026-q13.md` 的 Interpreter note。单文件扫描 `191 passed, 0 failed`，完整 pre-commit 链 8/8 通过。

- [x] Q15-07 Q14 验收总结：按 Q13 格式发布 `docs/q14-acceptance-summary.md`（六个本地工作项、覆盖弧线后端 74%→82.73% 与前端 8.51%→21.48%、Q14-00 顺延、以及门禁未生效放过的两个缺陷：`run_retention` mypy 报错与仅在 Windows 触发的测试断裂）；2026-08-06 已发布

---

## Q16 — 性能压测中心可视化升级与环境联动

> 立项日期：2026-08-06。目标是把当前“k6 脚本执行与结果查看”薄切，升级为测试人员可以直接配置的 HTTP 压测工作台；仍以 k6 为第一阶段执行器，不扩展为 APM 平台。
> 方案基线：`docs/performance-testing-thin-slice.md`「Q16 升级计划」。

### Phase 1 — 可视化压测场景与环境注入（本次开发范围）

- [x] Q16-01 可视化创建 HTTP 场景：URL、Method、Headers、Params、Body、认证方式、状态码/响应内容检查。
- [x] Q16-02 内置 smoke/load/stress/spike/soak 五类压力模板，自动生成 k6 脚本并继续支持手写脚本上传。
- [x] Q16-03 运行时选择环境后，自动注入环境变量；环境变量在触发时加密固化到本次运行快照，由 worker 使用该快照解密加载，运行中修改环境不会影响已触发任务。
- [x] Q16-04 支持环境变量占位符 `{{VARIABLE_NAME}}`，在 URL、请求头、参数和请求体中统一解析。
- [x] Q16-05 增加可视化配置的前端单元测试、环境注入 API 回归测试和脚本生成器测试。

### Phase 2 — 运行控制与结果可用性

- [x] Q16-06 增加执行进度轮询、实时状态刷新和安全停止任务。
- [x] Q16-07 增加结果 JSON/CSV 导出、压测报告摘要和阈值门禁结果的可读化展示。
- [x] Q16-08 增加基线回归比较、定时执行和 CI 阈值门禁。

### Phase 3 — 专业压测能力

- [x] Q16-09 接入 CPU、内存、PostgreSQL、Redis、MinIO 等系统指标并与压测时间线关联。
- [x] Q16-10 支持分布式压测节点、节点资源限制和压测网络出口隔离。
- [x] Q16-11 数据集参数化和复杂用户行为编排：数据集版本固定、worker-only 注入、字段占位符和顺序多步骤 HTTP 行为已完成。
- [x] Q17-01 统一性能执行器契约并接入 Locust：能力矩阵、公共进程生命周期、Locust CSV 摘要适配和前端执行器选择已落地；真实 worker 镜像联调保留为环境验收项。
- [x] Q17-02 gRPC 性能执行器：完成 `.proto` 上传、动态 descriptor 编译、Unary/Server Streaming/Client Streaming/Bidi Streaming 并发调用、TLS/metadata 安全校验、取消、节点 allowlist、统一摘要及本地真实服务联调；待 Linux/Kubernetes 目标服务环境验收。

**Q16 验收口径**：新建可视化场景无需手写 k6 脚本或 options JSON；选择环境后目标地址与变量可直接用于执行；敏感环境变量不出现在普通用户可见的 options 快照；原有脚本上传、异步执行、指标趋势和结果对比功能保持兼容。

**2026-08-12 当前开发顺序调整**：Android 真机连接与真实设备验收暂缓，不生成伪造通过证据；优先完成不依赖真机的存储治理闭环。存储管理页新增项目选择、MinIO 数据集对象只读核对、孤儿对象明细、截断/错误提示和二次确认清理，调用现有管理员接口 `POST /api/v1/projects/{project_id}/datasets/storage/reconcile`。页面定向回归 `7 passed`，type-check 通过；真实 MinIO 集群权限、备份恢复和大数据量清理仍待环境验收。

**Q16 Phase 2 进展（2026-08-07）**：Q16-01 至 Q16-08 已完成。新增 `cancelling` 状态、Redis 取消标记、k6 子进程安全终止、前端活动 run 轮询与进度估算；新增安全 JSON/CSV 报告导出、脱敏快照、阈值门禁汇总/展示、持久化基线、按时区 Cron 调度、重叠保护和 CI API Key 门禁脚本。完整非集成后端回归 `1507 passed`，前端 `36 files / 142 tests passed`，Ruff、mypy、type-check 与生产构建通过；下一步进入 Q16-09。

**Q16 Phase 3 进展（2026-08-07）**：Q16-09 已完成。performance worker 在 k6 运行期间按配置采集 CPU、内存、PostgreSQL、Redis、MinIO 指标，样本通过 `performance_metric_samples` 与 `PerformanceRun` 关联；新增 Prometheus `atp_performance_resource` gauge、资源指标查询 API 和压测详情时间线，可按指标切换查看。采集异常按组件隔离，不阻断压测；完整非集成后端回归 `1514 passed`，前端 `36 files / 142 tests passed`，type-check、生产构建、Ruff 和 mypy 通过；下一步进入 Q16-10 分布式压测节点与资源隔离。

**Q16 Phase 3 进展（2026-08-07）**：Q16-10 已完成。新增 `PerformanceNode` 模型与 `20260529_0043_add_performance_nodes.py` 迁移，支持节点注册、心跳、在线状态、队列绑定以及节点级 VU/并发/目标出口约束；手动和定时 run 均可绑定节点队列，worker 启动前再次校验节点身份与容量；性能中心新增节点状态卡片、容量和心跳展示及运行/定时节点选择；Helm 增加 dedicated performance worker 节点参数和可选 Egress NetworkPolicy。Q16-10 定向回归 `72 passed`，前端 type-check 和 Helm schema 校验通过；下一步进入 Q16-11 Locust/gRPC、数据集参数化和复杂用户行为编排。

**Q16-11 进展（2026-08-07）**：已完成 k6 数据集参数化和多步骤用户行为编排。压测定义绑定数据集后，触发 run 固定当前版本，worker 通过 `ATP_DATASET_JSON` 注入数据行；可视化脚本支持字段占位符、按 VU 轮转数据和顺序 HTTP 步骤/think time。

**Q17-01/Q17-03 进展（2026-08-07）**：新增统一性能执行器能力矩阵和公共 subprocess 生命周期，k6 保持兼容；Locust 已接入 `.py` 上传、headless 执行、aggregate CSV 结果归一、threshold 解析、取消/超时、数据集/环境注入、节点能力校验和前端执行器选择。gRPC 已接入 `.proto` 上传、动态 descriptor、四种调用模式、并发/迭代、TLS/metadata 校验、取消和统一结果报告；新增外部环境 smoke 命令、JSON 证据报告、Kubernetes rollout/Pod/镜像依赖检查、真实运行/取消入口和 Worker 健康探针；补充 ARM64 Docker Compose 隔离验收栈、可复现 TLS gRPC/HTTP 目标和 Worker 公有 CA 挂载配置。本地真实 gRPC 服务回归已覆盖，后端非集成回归 `1578 passed`；Linux 主机已确认仅有 Docker/Compose，Q17-04 仍需在该隔离栈上完成真实 smoke、取消、allowlist 和资源采样证据。

**2026-08-06 修复补充**：同步完成启动配置安全校验与草稿脱敏、Ollama 无 Key 配置、AI 模型多模态能力切换、Web 录制事件去重/会话清理/Linux display 提示，以及压测环境快照确定性和敏感参数过滤。后端非集成测试 `1486 passed`，前端 `35 files / 139 tests passed`，type-check、生产构建和 Ruff 均通过。

**2026-08-07 审查修复与文档同步**：修复性能调度共享队列与专用节点队列消费关系，增加 Worker 启动后的持续心跳和异常后重排队；修复 Webhook 执行器透传、Locust/gRPC 进度估算，以及定时任务跳过活动 run 时 `next_run_at` 未提交问题。已同步 `docs/celery-queues.md`、`docs/deploy-helm.md`、`docs/performance-testing-thin-slice.md` 和外部验收 Runbook；本轮定向回归 `93 passed`，性能服务/任务回归 `46 passed`，Ruff、格式检查和 `git diff --check` 通过。完整 Worker 套件的 8 个失败为既有 MinIO/数据库测试桩隔离问题，仍需单独治理；Q17-04 Linux/Kubernetes 真实环境验收仍未完成。

**2026-08-07 AI 生成上下文增强**：AI 用例生成已支持按当前项目选择一个测试数据集和多个 Mock 规则；后端校验项目归属，向模型提供数据集字段/少量样例、Mock 方法/路径/状态码/响应体/录制样本，并在发送前脱敏密码、Token、Cookie、Authorization 等敏感字段。生成草稿使用数据集字段占位符，保存时自动绑定所选数据集；Mock 规则只作为生成上下文，不会被 AI 自动修改。已补充后端脱敏/权限/Prompt 回归测试、前端选择控件和治理文档。
- [x] 2026-08-11 覆盖率与解释器兼容性收口：新增 `ProjectList`、`UserManagementView`、`AccountSettingsView` 组件级回归，以及录制会话/路由/资产持久化和用户管理边界回归；前端全量 `40 files / 157 tests passed`，coverage statements/branches/functions/lines 为 `31.54% / 26.53% / 24.73% / 32.76%`，通过现有 `31.5 / 26.5 / 24.5 / 32.5` 门禁；`vue-tsc --noEmit`、生产构建通过。后端 Python 3.12/3.14 均为 `1827 passed`，coverage `82.50%`/`82.05%`，252 个测试文件单独运行全部通过。
- [x] 2026-08-11 Web/Android Python 脚本生成补齐：Web 低代码生成器支持上传、下载、视觉基线断言、元素资产和页面对象展开；Android 生成器支持旋转、权限、网络配置和前后台切换；缺少资产或未知动作生成显式 `pytest.fail`，避免脚本静默漏步骤。新增 4 组生成器回归，前端全量 `40 files / 161 tests passed`，coverage statements/branches/functions/lines `31.94% / 27.09% / 24.94% / 33.21%`，type-check 和生产构建通过。
## 2026-08-14 Android 专项实时执行过程

- [x] Android 专项 Worker 推送设备准备、前置操作、执行阶段、采样、Crash/ANR、日志和完成事件。
- [x] WebSocket 订阅权限覆盖 MobileSpecialRun 的触发人、管理员、项目成员和项目 owner。
- [x] 报告详情页增加实时进度、当前步骤、设备状态、采样数量、Worker 日志和异常事件。
- [x] WebSocket 断开时由详情页每 3 秒轮询运行状态、指标和异常列表，完成后自动切换为最终报告。
- [x] 执行任务后直接进入报告详情页；后端定向测试 83 passed，前端 type-check/build 通过。
## 2026-08-14 Android 执行事件记录、Monkey 操作回放

- [x] 新增 `mobile_run_events` 事件表，按运行保存阶段、操作、时间、参数、结果、耗时和执行序号；单次运行最多保存 5000 条，避免长时间 Monkey 日志无限增长。
- [x] Android 性能、稳定性、流畅度 Worker 接入持久化事件记录，覆盖设备检查、应用启动、采样、场景操作、Crash/ANR、Monkey 日志和完成结果。
- [x] Monkey 稳定性任务采集 verbose 输出，记录 Monkey 动作、原始日志、随机种子和命令参数。
- [x] 报告详情页增加操作时间线，可展开查看参数与结果；JSON 报告同步导出事件记录。
- [x] 增加稳定性运行回放接口和报告页入口，复用原运行配置与随机种子创建新的回放任务。
- [x] 新增事件记录、事件 API、回放 API、迁移和 Worker 回归测试；后端目标测试 75 个通过，前端 207 个测试、类型检查和生产构建通过。

## 2026-08-14 APK 包名复用

- [x] 上传 APK 时自动解析二进制 `AndroidManifest.xml`，保存包名、版本名和版本号；解析失败仍允许手工填写。
- [x] Android 用例和专项任务展示 APK 包名；专项任务选择 APK 后自动带出应用包名，手工输入可覆盖。
- [x] 后端校验 APK 与任务属于同一项目，避免跨项目引用；相关 API、解析器和前端构建测试通过。

## 2026-08-25 N2 Karing 单设备稳定性专项闭环（最新快照）

> 本节覆盖并更新早期“专项任务/事件报告待验收”的历史记录；历史条目保留原状，当前执行口径以本节和 `docs/development-plan-2026-08-25.md` 为准。

- [x] 修复 Monkey 输出采集与执行过程并发写入同一个 `AsyncSession` 导致的重叠提交；`MobileRunEventRecorder` 增加事件循环级写锁和串行 flush。
- [x] 修复调度层与稳定性/性能/流畅度执行器分别创建记录器导致的重复事件序号；调度层把同一个记录器传入执行器和产物收尾路径。
- [x] q19 受控依赖 + Windows Android Worker 真实执行 Karing：设备 `153 / 172.16.102.91:5555`、包名 `com.nebula.karing`，稳定性运行 `6` 与回放 `7` 均 `completed`，随机种子 `20260825` 保持一致。
- [x] 回放运行 `7` 保存 78 条事件，序号 1～78 无重复；包含 Monkey 日志/动作、Crash、完成、设备 logcat 和 screenshot；JSON 报告与产物 URL 均返回 200。
- [x] 临时项目 `50` 清理：删除 204、删除后查询 404、匹配项目 0；证据见 [`docs/evidence/android-karing-special-task-2026-08-25.json`](docs/evidence/android-karing-special-task-2026-08-25.json)。
- [x] 代码审查与问题修复后，定向回归 82 项，后端非集成全量 2306 项，Ruff、格式检查和 `git diff --check` 通过。
- [ ] N2 总体验收仍未完成：下一步验证同一 Worker/设备上的性能专项 CPU/内存/电池/网络样本与报告，再验证流畅度专项 FPS/jank 阶段采样。
