# ATP 发布收口状态（2026-08-25）

> 这是当前发布候选的状态索引。它只汇总已经存在的代码/自动化证据和真实环境证据，不把本地 mock、协议桩或“代码已实现”写成生产通过。

> 当前开发顺序与模块状态以 [`development-plan-2026-08-25.md`](development-plan-2026-08-25.md) 为准；本文件只维护发布证据、环境边界和收口结论。

> 当前计划跟踪版本为 2.4.0：参考导航按工作台、测试能力、测试资产、智能中枢、系统五组跟踪，按 P0 工作台、P1 接口、P2 APP、P3 UI、P4 性能、P5 AI、P6 测试资产、P7 智能中枢、P8 系统和 P9 发布收口推进。P4-P8 未完成真实环境复核前，发布结论继续保持“存在未关闭门禁”，不因本地实现完成而变更；Windows 与 Android Worker 的本地边界不影响 Web/API 使用。

> 2026-08-25 计划检查点 2.4.15：2.4.0 只更新导航分组、阶段编号、执行顺序和验收口径；在此基础上，N1 任务中心/待办分页、P1 API 工作台运行记录和用例详情竞态保护、P0 终止确认、失败诊断入口和失败证据展示、N5/N7 真实模型验收前置、N6 viewer 隔离矩阵工具均已完成本地闭环；P8 本地治理验收入口已具备，q19 目标只读预检健康通过但管理员认证仍返回 401，未读取密码或执行远端变更。当前剩余为普通 viewer/管理员受控账号、真实 AI 草稿和 P8 目标治理复核。P4 缺少 Kubernetes、发布级 Prometheus 和独立 MinIO 保持 `[-]`，发布结论仍为存在未关闭门禁；脱敏预检见 `docs/evidence/n8-system-governance-environment-audit-2026-08-25.json`。

> 2026-08-25 N1 任务中心分页本地交付：统一任务接口支持有界 `offset`，跨五类任务域合并排序后切页；前端支持服务端分页和项目/状态/类型/页码深链。工作台定向 `15 passed`、后端非集成 `2380 passed`、前端全量 `69 files / 302 tests passed`，type-check/build/Ruff/diff-check 通过。该项仍不替代真实角色、任务数据和执行器环境验收。

> 2026-08-25 N1 我的待办分页本地交付：工作台概览接口支持有界 `todo_offset`，跨评审、失败运行、逾期计划和设备异常合并排序后切页；前端支持项目与 `todo_page` 深链，切换项目回到第一页。工作台定向 `16 passed`、后端非集成全量 `2381 passed`、前端全量 `69 files / 302 tests passed`，focused todos `2 passed`，type-check/build/Ruff/format/diff-check 通过。该项仍不替代真实角色、待办数据和执行器环境验收。

> 2026-08-25 N5/N7 真实模型验收前置本地交付：N7 验收脚本的 `--require-ai` 现在要求管理员、已保存配置、模型发现、连接测试、临时项目绑定和可编辑草稿；`--require-vision`/`--require-thinking` 要求发现模型明确声明对应能力，独立能力参数会拒绝。脚本定向 `10 passed`、后端非集成全量 `2383 passed`、Ruff/格式/diff-check 通过；不在自定义业务 payload 中携带 API Key，也不记录 Token 或供应商响应，真实模型/参数接受和项目生成仍待受控环境验收。

> 2026-08-25 N6 viewer 隔离矩阵工具本地交付：提供普通 viewer 账号时，N6 脚本会创建独立隔离项目，验证主项目用例/评审/套件/计划/运行/缺陷读取，以及跨项目读取和用例/模块写入拒绝；成员、主项目和隔离项目分别清理。定向 API/脚本回归 `93 passed`、后端非集成全量 `2385 passed`、Ruff/格式/diff-check 通过；真实 viewer/admin 账号和项目数据仍待环境验收，不改变发布阻塞结论。

> 2026-08-25 N6 viewer 令牌接入本地交付：角色矩阵脚本优先使用短期 `ATP_VIEWER_TOKEN`，未提供时兼容账号密码；认证值只从环境变量读取，不写入报告。脚本/API 定向回归 `93 passed`、后端非集成全量 `2385 passed`，真实 viewer/admin 账号和项目数据仍待环境验收，不改变发布阻塞结论。

> 2026-08-25 P0 任务中心终止确认本地交付：单任务和批量终止均要求二次确认，执行回调再次验证动作资格，避免过期确认绕过前端状态保护；前端全量 `69 files / 303 tests passed`，`vue-tsc`、生产 build 和 diff-check 通过。真实角色权限和执行器终止效果仍待环境复核，不改变发布阻塞结论。

> 2026-08-25 P0 任务中心失败诊断入口本地交付：失败/异常/取消/停止任务可从任务中心直接打开诊断弹窗，case 复用既有用例诊断链，suite/plan/android/performance 复用工作台诊断接口；定向 `4 passed`、前端全量 `69 files / 304 tests passed`，`vue-tsc`、生产 build 和 diff-check 通过。真实角色、失败运行和执行器证据仍待环境复核，不改变发布阻塞结论。

> 2026-08-25 P0 任务中心失败证据展示本地交付：诊断弹窗新增失败步骤/截图计数、结构化错误样本和安全截图入口，截图链接限制为 HTTP(S) 并带 `noopener noreferrer`；定向 `4 passed`、前端全量 `69 files / 304 tests passed`，`vue-tsc`、生产 build 和 diff-check 通过。真实角色、失败运行和执行器证据仍待环境复核，不改变发布阻塞结论。

> 2026-08-25 P1 API 工作台运行记录竞态保护本地交付：用例请求序列同时保护最近运行记录的成功、失败和空结果分支，旧模块响应不会覆盖最新模块结果；定向 `3 passed`、前端全量 `69 files / 305 tests passed`，`vue-tsc`、生产 build 和 diff-check 通过。真实角色和执行数据仍待环境复核，不改变发布阻塞结论。

> 2026-08-25 P1 API 工作台用例详情竞态保护本地交付：详情/编辑请求增加序列保护，关闭编辑、新建和保存完成会失效旧请求，迟到响应不会覆盖当前用例或重新打开表单；定向 `5 passed`、前端全量 `69 files / 307 tests passed`，`vue-tsc`、生产 build 和 diff-check 通过。真实角色和执行数据仍待环境复核，不改变发布阻塞结论。

> 2026-08-25 P7 Hermes 项目级检索本地交付已完成：`POST /hermes/query` 返回需求、知识和用例的脱敏来源与项目深链，Hermes 自由提问和知识条目深链已接通；N7 验收脚本现在校验三类 marker 来源、项目路径、source_ref 及需求/知识/用例详情读取。后端定向 `21 passed`、前端 Hermes/知识定向 `11 passed`，真实模型、角色账号和远端数据仍待受控验收，不改变 N7 及发布阻塞结论。

> 2026-08-25 P7/N6 真实验收发现并修复两个本地缺陷：blank 项目模块缺失导致脚本无法继续，需求创建在 async commit 后读取过期 ORM 属性导致 q19 返回 HTTP 500/MissingGreenlet；脚本现在创建临时模块，接口在响应前 refresh。q19 已按 `716d1b3` 重建并复验基础数据链路，最新脱敏证据见 [`evidence/n6-project-asset-acceptance-2026-08-25.json`](evidence/n6-project-asset-acceptance-2026-08-25.json) 与 [`evidence/n7-intelligence-acceptance-2026-08-25.json`](evidence/n7-intelligence-acceptance-2026-08-25.json)。

> 2026-08-25 N6 清理级联问题已修复并复验：首次真实执行在删除临时项目时因 `plan_runs.plan_id` 外键缺少级联返回 HTTP 500；提交 `716d1b3` 新增迁移 `20260825_0066`，q19 重建后 N6 执行/缺陷关联/项目清理均通过。N6 仍因普通 viewer 账号缺失保持未关闭。

> 2026-08-25 N7 真实数据基础链路已复验：需求/知识/用例创建、详情读取、Hermes 三类来源引用和清理均通过；N7 报告为 `partial`，因为没有普通 viewer 凭据且未启用受控真实 AI 草稿。真实模型和角色矩阵仍是发布阻塞。

> 2026-08-25 计划同步标记：2.3.0 只更新导航职责、执行顺序、验收出口和状态口径，不伪造真实环境证据。N4 缺少 Kubernetes、发布级 Prometheus 和独立 MinIO 保持 `[-]`；N2～N3、N5～N8 的本地实现保持 `[E]`，N9 保持 `[~]`。

> 2026-08-25 N7 Hermes 跨任务失败诊断已完成本地交付：新增工作台诊断接口并复用项目 viewer 权限边界，case 走原诊断链，suite/plan/android/performance 使用各域执行摘要和事件/指标生成规则线索；后端定向 `13 passed`、非集成全量 `2345 passed`，前端全量 `69 files / 293 tests passed`，`vue-tsc` 和生产构建通过。真实模型、需求/知识数据和角色矩阵仍待 N7 验收，不改变 N4-N8 未关闭门禁及当前发布阻塞结论。

> 2026-08-25 N6 缺陷状态刷新项目隔离已完成本地交付：刷新 case 执行记录关联缺陷状态前校验所属项目 viewer 权限，已保存 tracker 必须属于同一项目，跨项目配置在外部调用前拒绝；缺陷跟踪 API 定向 `11 passed`，真实项目角色矩阵、外部缺陷平台和可清理失败运行仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 缺陷证据跨类型报告导航已完成本地交付：case/Android/性能/suite/plan 缺陷证据均跳转到对应报告入口，suite/plan 深链解析 `run_id` 并恢复项目上下文；前端定向 `23 passed`、全量 `69 files / 297 tests passed`，`vue-tsc` 和生产构建通过。真实项目角色、可清理失败运行和报告环境仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 计划报告套件明细导航已完成本地交付：计划运行报告中的套件明细可携带 `project_id`/`suite_run_id` 跳转并展开对应套件运行；计划列表定向 `7 passed`、前端全量 `69 files / 298 tests passed`，`vue-tsc` 和生产构建通过。真实项目角色、可清理失败运行和报告环境仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 数据集影响范围项目上下文已完成本地交付：测试数据集影响范围的案例/套件/计划入口保留 `project_id`，案例详情可加载项目环境并返回项目筛选，避免跳转后丢失项目上下文；数据集定向 `9 passed`、前端全量 `69 files / 299 tests passed`，`vue-tsc` 和生产构建通过。真实项目角色、跨项目可见性和可清理数据仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 用例评审打开详情项目上下文已完成本地交付：评审工作台打开案例详情时携带记录自身 `project_id`，保留项目环境和返回筛选；定向 `3 passed`、前端全量 `69 files / 300 tests passed`，`vue-tsc` 和生产构建通过。真实项目角色、跨项目可见性和可清理评审数据仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 工作台任务详情上下文已完成本地交付：case、suite、plan、Android、performance 任务详情统一保留 `project_id`，suite/plan/performance 额外携带 `run_id`，任务中心可直接定位具体执行记录；工作台 API 定向 `14 passed`、后端非集成全量 `2352 passed`，数据集静态契约旧路由断言修复后相关回归 `17 passed`。真实项目角色、跨项目可见性、可清理运行和报告环境仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N6 项目资产与角色矩阵验收工具已完成本地交付：新增 `scripts/n6-project-asset-acceptance.py` 及运行手册，支持临时项目资产链、可选执行/报告、缺陷关联、viewer 隔离和清理后 404；凭据只从环境变量读取，副作用/执行需显式授权，错误响应不回显。脚本定向 `6 passed`、质量门禁一致性 `10 passed`，真实角色、执行报告和清理证据仍待 N6 验收，不改变当前发布阻塞结论。

> 2026-08-25 N5 AI 模型能力元数据解析已完成本地交付：模型发现支持第三方能力/模态字段，能力提示无阳性证据时保持未知；模型发现/API 定向 `20 passed`、受影响 AI 定向 `69 passed`、后端非集成全量 `2340 passed`，真实模型和项目级生成仍待受控环境验收，不改变当前发布阻塞结论。

> 2026-08-25 N5 真实模型环境只读复核确认阻塞：q19 acceptance 没有 AI LLM 配置，外部模型入口不带凭据返回 HTTP `401`；脱敏证据为 [`evidence/ai-model-environment-audit-2026-08-25.json`](evidence/ai-model-environment-audit-2026-08-25.json)，不改变发布结论，也不代表真实模型能力通过。

> 2026-08-25 N4 smoke 防误验收已完成本地交付：发布级性能检查必须显式传入 `--require-kubernetes` 和 Deployment；缺少参数会失败，Docker Compose 本地检查保持兼容。目标主机 q19 的 Prometheus readiness/targets 只作为单节点观察，不能替代 Kubernetes 多节点、发布级 Prometheus 和独立 MinIO 灾备证据。

> 2026-08-25 N4 MinIO 灾备端点独立性门禁已完成本地交付：跨端点脚本拒绝同机文本、回环别名和同 IP 解析结果；定向回归 `51 passed`。真实独立 MinIO source/target 和生命周期/恢复证据仍未关闭发布门禁。

> 历史计划登记（2.1.0）：导航已按工作台、测试能力、测试资产、智能中枢、系统五组统一，N0-N9 的范围与验收出口见开发计划 2.1.0。N2 Karing 单设备包身份、Worker 前置、低代码、录屏、稳定性/Monkey、性能/流畅度专项、事件/报告和清理已通过；N4 仍缺真实 Kubernetes/独立灾备 MinIO/生产 Prometheus，未关闭门禁继续按“待环境验收”处理。当前顺序以本文件上方 2.2.0 计划跟踪为准。

> 2026-08-25 N5/N6 AI 用例来源追踪摘要已完成本地交付：生成与审计记录配置/供应商/模型摘要和上下文计数，保存的 `_ai_source` 在详情页可查看；不记录 Endpoint、提示词、API Key 或原始响应。后端非集成全量 `2323 passed`、前端全量 `69 files / 289 tests passed`，真实模型、项目权限和测试资产全链路仍待环境验收，不改变“不具备无条件发布资格”的结论。

> 2026-08-25 N6 失败运行转内部缺陷入口已完成本地交付：Android 专项报告和性能压测详情支持失败/异常/取消/停止运行一键创建内部缺陷，当前详情展示关联项并可按执行记录跳转；后端重复指纹继续追加脱敏证据。后端非集成全量 `2326 passed`、前端全量 `69 files / 292 tests passed`，真实项目角色和失败运行仍待环境验收，不改变“不具备无条件发布资格”的结论。

> 2026-08-25 N9 发布门禁证据索引子模块已完成本地交付：滚动索引不保存候选 SHA，门禁校验命令在发布时接收并核对实际 HEAD；每个未关闭门禁必须具备脱敏证据路径、阻塞原因、依赖、负责人和复验命令，缺字段或仓库外路径都应阻断发布。定向校验与发布契约 `22 passed`、后端非集成全量 `2333 passed`，不改变真实 N4-N8 门禁未完成的发布结论。

> 2026-08-25 N9.2 发布文档同步一致性契约已完成本地交付：发布索引校验六份计划/任务/记忆/路线图/发布文档的路径和关键标记，缺少文件或标记时阻断发布校验；定向校验与发布契约 `23 passed`、后端非集成全量 `2334 passed`，不改变真实 N4-N8 门禁未完成的发布结论。

> 2026-08-25 N5 本地 AI 密钥边界已完成：Ollama 空 API Key 可用于用例/数据集/Mock 生成、失败诊断和自愈，非 Ollama 空密钥仍拒绝，兼容请求不发送空 Authorization；相关 AI 定向 `88 passed`、后端非集成全量 `2315 passed`。真实模型列表、健康检查、多模态/思考参数和项目级生成仍待环境验收，不改变发布结论。

> 2026-08-25 N5 AI 模型连接健康检查已完成本地交付：新增管理员接口和配置页入口，复用已保存密钥并允许新建 keyless Ollama；请求固定短文本、15 秒超时、4 token 上限，Endpoint 规范化，错误和审计摘要脱敏。后端非集成全量 `2317 passed`、前端全量 `69 files / 287 tests passed`，真实模型连接、多模态/思考参数和项目生成仍待环境验收，不改变“不具备无条件发布资格”的结论。

> 2026-08-25 N5 模型能力提示与思考快捷配置已完成本地交付：AI 配置页默认关闭思考，可选择三种思考参数形式和 `reasoning_effort` 档位，能力提示不等同于供应商承诺；前端全量 `69 files / 289 tests passed`，类型检查、生产构建和差异检查通过。真实模型参数接受情况仍待环境验收，不改变发布结论。

> 2026-08-25 N5 AI 生成安全边界已完成本地交付：用例、测试数据集、Mock 和模型列表的网络错误不回显供应商响应正文或异常字符串；用例 `raw_response` 限制为 12,000 字符并对 JSON 敏感字段、键值文本和 URL 凭据脱敏。AI 用例/治理定向 `21 passed`、数据集/Mock/LLM 相关回归 `78 passed`、后端非集成全量 `2322 passed`，真实供应商错误格式和模型返回内容仍待环境验收，不改变“不具备无条件发布资格”的结论。

> 2026-08-25 N2 Karing 性能与流畅度专项已完成真实单设备复核：性能运行 `10` 完成 CPU/内存/电量/温度/FPS/卡顿采样，流畅度运行 `13` 完成滑动/点击两个阶段并采集 FPS/jank；事件序列无重复，两个 JSON 报告导出均 HTTP 200，临时项目 `51` 删除 204 且删除后查询 404。Android 14 兼容修复已补入性能内存 VmRSS 兜底和 gfxinfo UI HISTOGRAM 解析/GPU 直方图排除；相关定向回归 `60 passed`，脱敏证据见 [`android-karing-performance-fluency-2026-08-25.json`](evidence/android-karing-performance-fluency-2026-08-25.json)。N2 单设备门禁已关闭，但不代表多设备矩阵或 N4 真实性能环境通过。

> 2026-08-25 N2 Karing 真机前置阶段已通过：设备 `172.16.102.91:5555` 安装并解析 `com.nebula.karing/.MainActivity`，Windows Android Worker、依赖 readiness、Worker registry 和设备扫描通过；后续低代码与录屏结果见最新 N2 记录。发布结论保持“不具备无条件发布资格”。脱敏证据见 [`android-karing-acceptance-2026-08-25.json`](evidence/android-karing-acceptance-2026-08-25.json) 与 [`windows-android-karing-worker-2026-08-25.json`](evidence/windows-android-karing-worker-2026-08-25.json)。

> 2026-08-25 N2 Karing 低代码与录屏已通过真实单设备复核：`run 27` 通过启动/等待/截图 3/3，`run 29` 在 `-RequireAndroidRecording` 门禁下返回 3/3 步骤、3 张截图、3 个产物且 `recording=True`；两个临时项目均已清理。稳定性/Monkey、性能、流畅度、专项事件/日志/报告和最终临时对象清理也已在后续证据中关闭；不代表多设备矩阵或 N4 真实性能环境通过。证据见 [`android-karing-lowcode-2026-08-25.json`](evidence/android-karing-lowcode-2026-08-25.json) 与 [`android-karing-recording-gate-2026-08-25.json`](evidence/android-karing-recording-gate-2026-08-25.json)。

> N2 控件属性获取诊断已完成本地交付：API 进程和 Windows Android Worker 返回 `found`/`not_found`/`unavailable` 及脱敏诊断码；录制界面在不可用时提示并保留坐标回退。后端定向 `22 passed`、前端相关定向 `23 passed`、后端非集成全量 `2305 passed`、前端全量 `69 files / 284 tests passed`，类型检查、生产构建、Ruff、格式检查和差异检查通过。真实 Karing 页面、UIAutomator 权限和真机 Worker 回传仍未关闭发布门禁。

> N0/N6 测试套件导航归位已完成本地交付：`/suites` 已加入测试资产侧栏，深链、面包屑、菜单标题和能力描述元数据一致；导航定向 `8 passed`、前端全量 `69 files / 285 tests passed`，类型检查、生产构建和差异检查通过。真实账号、角色和项目权限复核仍待环境验收，不改变当前发布结论。

> N0 工作台运行记录入口收敛已完成本地交付：侧栏不再展示重复的“执行记录”，`/runs` 与 `/runs/:id` 旧地址继续可访问并选中任务中心；导航定向 `9 passed`、前端全量 `69 files / 286 tests passed`，类型检查、生产构建和差异检查通过。运行权限和真实账号复核仍待环境验收，不改变当前发布结论。

> N4 真实性能环境只读复核：`172.31.27.133` 未提供 Kubernetes CLI/集群、默认 `127.0.0.1:9090` readiness 或独立 MinIO 源/目标；q19 `127.0.0.1:29090` readiness 和四个 Compose targets 只能作为受控单节点观察，不关闭真实性能发布门禁。脱敏证据见 [`performance-environment-audit-2026-08-25.json`](evidence/performance-environment-audit-2026-08-25.json)。

> N1 受控协议与报告证据已补齐：GraphQL、WebSocket、gRPC Server/Client/Bidi Streaming 以及 HTML/JUnit/PDF 报告详情和清理均通过 q19 真实网络；详见 [`api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json) 与 [`report-closure-2026-08-25.json`](evidence/report-closure-2026-08-25.json)。生产协议服务和发布环境仍未关闭。

> API 受控目标、显式会话复用、gRPC TLS Unary、GraphQL/WebSocket/流式 gRPC、OpenAPI/Postman 解析和导入落库证据：[`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)、[`api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)。这些证据不代表生产协议服务、完整报告或发布环境验收通过。

> N1 协议执行边界已补齐：GraphQL、WebSocket、gRPC 的缺失/空 `config.steps` 会 fail-fast 为 `error`，避免产生零步骤的虚假通过；该项有本地回归，不替代真实协议目标验收。

> N1 保存边界已补齐：协议用例创建/更新会在写入快照前校验最小可执行配置，失败返回 `422`；该项有本地回归，不替代真实 GraphQL/WebSocket/流式 gRPC 和完整报告验收。

> N1 报告中心已补齐按用例类型统计的本地能力：API 按项目可见范围聚合完成运行，前端展示类型、通过率和失败/异常摘要；该项有回归和构建证据，不替代真实多协议和完整报告环境验收。

> N1 协议用例前端保存校验已补齐：GraphQL、WebSocket、gRPC 的空必填项在提交前直接提示，空格和空消息不会进入创建/更新请求；纯函数回归 `8 passed`，前端全量 `66 files / 272 tests passed`，类型检查和生产构建通过。该项不关闭真实多协议或完整报告发布门禁。

> Android APK 包名身份保护已补齐：Manifest 有包名时拒绝不一致的手工包名，避免资产选择和安装目标被错误覆盖；异常发生在 MinIO 上传和数据库写入前。定向 `22 passed`、后端非集成全量 `2284 passed`，真实 Karing APK、下载端点和专项报告仍待设备环境验收。

> Android 专项任务设备目标保护已补齐：创建、更新和手工触发会先确认 `device_id` 存在，不会把无效设备写成待执行任务；定向 `32 passed`、后端非集成全量 `2287 passed`。该项不代表设备在线、租约、ADB、Karing 或媒体报告验收通过。

> Android 专项 APK 选择体验已补齐：选择器只展示已解析包名的 APK，选中后自动绑定并锁定包名，清空 APK 会同步清空包名；未选 APK 仍可手工填写。工具函数回归 `2 passed`，前端全量 `67 files / 274 tests passed`，类型检查和生产构建通过。该项不代表真实 Karing APK、设备执行、专项任务或完整报告验收通过。

> Android 低代码控件属性录制与坐标回退已补齐：可视化点击步骤同时保存文本、resource-id、content-desc、className、bounds 和原始坐标；回放优先使用控件属性，UIAutomator 不可用或控件找不到时回退录制坐标。后端定向 `42 passed`、非集成全量 `2297 passed`，前端定向 `4 passed`、全量 `68 files / 277 tests passed`，`vue-tsc`、生产构建、Ruff、格式检查、差异检查和独立代码审查通过。该项只关闭本地录制/回放代码门禁，真实 Karing APK、Windows Worker UIAutomator 权限、媒体、专项任务和报告仍待验收。

> Android 低代码长按与输入控件定位已补齐：长按支持 resource-id/文本/content-desc 并按控件中心执行真实长按，输入步骤分离输入内容与目标控件并在定位失败时明确失败；Python 脚本不再把输入值误当成控件文本。后端定向 `45 passed`、非集成全量 `2300 passed`，前端定向 `11 passed`、全量 `68 files / 279 tests passed`，类型检查、生产构建、Ruff、格式检查、差异检查和独立代码审查通过。该项只关闭本地代码门禁，真实 Karing/Worker 真机行为仍待验收。

> Android 可视化滑动分辨率适配已补齐：录制步骤保存屏幕宽高，Worker 按当前 `wm size` 缩放并裁剪坐标，方向滑动和独立 Python 脚本使用运行时尺寸，尺寸读取失败时保留旧行为。后端定向 `47 passed`、非集成全量 `2302 passed`，前端定向 `16 passed`、全量 `68 files / 282 tests passed`，类型检查、生产构建、Ruff、格式检查、差异检查和独立代码审查通过。该项只关闭本地代码门禁，真实 Karing/Worker 的不同分辨率、横竖屏、录屏和报告回放仍待验收。

## 发布结论

当前结论：**暂不具备无条件发布资格**。

## 2026-08-25 当前执行计划与新增阻塞

当前执行顺序为：保持 N4 真实性能环境阻塞边界，先复核 N6/N7 普通 viewer 角色矩阵，再复核 N5 真实模型和 N8 目标部署治理，最后进入 N9 发布收口；N2 Karing 单设备专项任务/事件/报告闭环、Windows API/Web 和 N1 受控 API/报告闭环已复核完成。

### 2026-08-25 Windows Android 包名与启动入口验收探针

- `scripts/windows-android-acceptance.ps1` 新增 `-LaunchActivity`；指定 `-AppPackage` 后确认安装状态，并用 `cmd package resolve-activity --brief` 校验显式 Activity 或 `MAIN/LAUNCHER` 默认入口。
- 报告仅记录包名、请求组件、解析组件和检查状态，不启动或修改应用，不保存 APK 内容和日志正文。
- 脚本契约 `2 passed`、脚本目录 `93 passed`、质量/发布文档回归 `15 passed`，PowerShell 语法检查通过；当前在线设备用 `com.android.settings` 的自动/显式 Activity 只读探针均通过。
- 该证据只关闭本地验收探针，不关闭 Karing：当前设备仍未发现 Karing，真实 APK/Manifest 包名、Worker 调度、低代码、媒体、专项任务和报告仍待验收。

### 2026-08-25 Android 专项应用启动兼容

- Android 性能、稳定性和流畅度执行器已统一应用启动策略：填写 Activity 时执行显式组件启动，未填写时通过 Launcher Intent 自动发现，不再固定拼接 `.MainActivity`；流畅度任务会跳过已由前置操作完成的重复启动。
- 专项任务表单的启动 Activity 为空时不再写入默认 `.MainActivity`，已有显式 Activity 配置保持兼容；启动失败仍会记录失败结果，不会把后续步骤误报为成功。
- 后端非集成 `2295 passed`，四个改动测试文件独立运行 `3/25/19/15 passed`，前端全量 `67 files / 275 tests passed`，`vue-tsc`、生产构建、Ruff、差异检查和独立代码审查通过。
- 该项只关闭本地启动兼容代码门禁；真实 Karing APK/包名、Windows Android Worker/ADB、启动组件、录屏/异常回放、专项任务和报告仍待环境验收。

### 2026-08-25 1.0 计划同步

- N4 本地实现不再列为待开发项：性能指标采样、目标服务 Prometheus 指标、Kubernetes 容量预检、保留清理和 MinIO 跨端点恢复入口均已有回归和代码审查记录。
- N4 发布门禁仍未关闭：必须取得真实 Kubernetes、独立 MinIO 源/目标和 Prometheus；使用 `docs/development-plan-2026-08-25.md` 1.0 节的最小出口和复验命令。
- N2、N5-N8 和 N9 的阻塞条件、凭据边界与清理要求保持不变，不能用替代应用、mock 或跳过项宣称通过。

### 2026-08-25 N4 Kubernetes 性能容量预检

- 性能验收脚本新增可选 `--min-ready-nodes`、`--min-worker-replicas` 和 `--require-worker-resources`，分别校验可调度 Ready 节点、性能 Worker desired/available 副本和 Worker CPU/内存 requests/limits。
- 定向回归 `29 passed`，Ruff、格式检查、`git diff --check` 和独立代码审查通过；默认参数不改变已有 Docker/Kubernetes smoke。
- 当前目标主机没有 Kubernetes 集群，故只记录实现与回归完成；真实多节点、生产 Prometheus/MinIO 生命周期和跨主机恢复仍为发布阻塞。

### 2026-08-25 N4 跨端点 MinIO 恢复验收入口

- 新增 `scripts/minio-dr-acceptance.py` 和 `make minio-dr-acceptance`，使用独立 source/target MinIO 环境变量验证对象复制、目标回读、恢复回源、SHA-256 和临时对象清理。
- 默认审计两端生命周期规则；`--require-lifecycle-rule PREFIX=DAYS` 可把精确的启用规则纳入门禁。凭据只从进程环境读取，不进入报告；同一主机会被拒绝，避免把同桶/不同桶误报为跨主机恢复。
- 脚本回归 `3 passed`，质量门禁一致性和灾备文档回归 `17 passed`，Ruff、格式检查、`git diff --check` 和独立代码审查通过。
- 当前目标没有独立 MinIO 灾备端点，因此本项不关闭真实跨主机恢复和生产生命周期门禁。

### 2026-08-25 N1 受控协议目标交付

- q19 受控目标完成 GraphQL、WebSocket、gRPC Server/Client/Bidi Streaming 的创建、审批、执行、断言/提取和清理；运行编号分别为 `19/20/23/24/25`，均为 `passed`。
- 本地目标/执行器回归 `90 passed`，后端非集成全量 `2288 passed`，Ruff、格式和差异检查通过；提交 `5b07a3e` 已推送。
- 发布边界：本项不代表生产协议服务或完整报告导出/详情治理通过，下一入口为完整报告闭环。

### 2026-08-25 N1 完整报告闭环交付

- q19 临时项目 `42`、用例 `27`、运行 `26` 通过；详情接口 `200`，HTML `200/2561 bytes`、JUnit XML `200/220 bytes` 且 XML 可解析、PDF `200/167056 bytes`；项目删除 `204`，清理后匹配数 `0`。
- 运行详情页新增 JUnit XML 导出入口；前端定向 `11 passed`、后端报告/导出 `24 passed`、前端全量 `67 files / 275 tests passed`，类型检查、生产构建、差异检查和独立代码审查通过；代码提交 `86f3bf7` 已推送。
- 脱敏证据见 [`report-closure-2026-08-25.json`](evidence/report-closure-2026-08-25.json)。发布边界：生产协议服务、生产对象存储和外部发布环境仍待验收。

- 本轮 Windows smoke 已使用当前账号重新通过认证；健康检查、前端登录页、PostgreSQL/Redis/MinIO readiness、Web Worker、Playwright `12 passed`、浏览器矩阵、文件传输、Web 低代码和报告导出均通过。未在文档或证据中记录账号、密码或 Token。
- Windows smoke 继续只读取当前账号 `ATP_USERNAME/ATP_PASSWORD`，不自动回退或混用 `FIRST_ADMIN_*`；全新数据库初始化验证仍必须显式使用 `-UseBootstrapCredentials`。

### 2026-08-25 N1 报告中心按用例类型统计

- 报告概览 API 在项目权限过滤后按 `TestCase.case_type` 聚合完成运行，输出总运行、通过、失败、异常和通过率。
- 报告中心新增用例类型分布卡片、通过率进度条、运行/失败摘要和无数据空态；中英文文案和 API 类型同步。
- 报告定向 `5 passed`、前端报告页 `3 passed`，后端非集成全量 `2282 passed`；`vue-tsc`、生产构建、Ruff 和差异检查通过，独立代码审查无可操作问题。
- 发布边界不变：真实 GraphQL/WebSocket/流式 gRPC、完整报告目标和 Android Karing 仍需外部环境证据。

- 报告中心对比选择已补同用例边界：混合最近运行记录时自动选择同用例组合，切换任一侧会自动对齐另一侧，避免前端发起必然被后端拒绝的请求；该项有前端回归，不替代真实报告数据验收。

### 2026-08-25 API gRPC TLS 受控目标验收

- 已补齐 API gRPC TLS 的自签名/私有 CA 配置：用例表单支持公有 PEM 根证书和 SNI 服务名，执行器限制证书大小、拒绝私钥，并且只在步骤快照记录“已配置”状态，不保存证书内容。
- q19 已按 `96c7db0` 重建 Backend/Worker；临时项目完成 gRPC Unary TLS 用例创建、评审、审批、执行、`grpc_status=OK`、响应断言、JSONPath 提取和清理，运行 `17` 通过。
- 本地回归：gRPC Worker `69 passed`，Ruff、前端类型检查、生产构建和配置工具测试 `6 passed`；脱敏证据见 [`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)。
- 发布边界：这只关闭 q19 受控 gRPC TLS Unary 证据；OpenAPI/Postman 导入、GraphQL/WebSocket/流式 gRPC、生产目标和完整报告仍待验收。

### 2026-08-25 API OpenAPI/Postman 导入解析验收

- q19 已按 `75ed756` 重建 Backend/Worker；当前账号调用 `/api/v1/ai/cases/parse-schema` 的 OpenAPI 与 Postman 样例均返回 `200`，分别解析出 `1/1` 和 `1/3`（接口/参数）。
- 本地解析与端点回归 `38 passed`，Ruff 和差异检查通过；证据见 [`api-import-parser-2026-08-25.json`](evidence/api-import-parser-2026-08-25.json)。
- 发布边界：本项只关闭解析层；导入预览/落库闭环见下节，GraphQL/WebSocket/流式 gRPC、生产目标和完整报告仍待验收。

### 2026-08-25 API 导入预览与落库验收

- q19 已按 `a8f6e26` 重建 Backend/Worker；受控流程完成 OpenAPI 解析（成功响应码 `201`）、临时项目/模块创建、导入预览 `valid=1/invalid=0`、用例落库 `201`、回读断言/步骤预期和项目删除清理 `204`。
- 验收中发现并修复 `Module.project` 异步懒加载导致的 `MissingGreenlet` 500：导入预览读取模块时预加载所属项目；定向回归 `42 passed`，后端非集成全量 `2270 passed`，Ruff/diff-check 通过。
- 脱敏证据见 [`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)。发布边界：仅关闭 OpenAPI 导入预览/落库/回读/清理；其他协议和完整报告仍待验收。

### 当前剩余阻塞

- q19 Backend 的管理员 bootstrap 启动缺陷已按 `65eef50` 修复并完成真实复验：初始化按用户名/邮箱幂等识别，不覆盖已有账号密码或角色；当前账号登录、依赖 readiness、Worker registry 和设备扫描均已通过。
- 历史 Android 前置证据仍有效，但已由最新复核补充：Windows ADB 当前有 3 台 `device`，Worker doctor、PostgreSQL、Redis、MinIO 和 logcat 检查通过；目标设备 `172.16.102.91:5555` 已发现 Karing。
- 最新复核已关闭 Karing 包名、启动入口、Worker 注册/扫描、低代码最小执行和录屏回传；剩余阻塞转为异常回放、专项任务、事件/日志/报告和对象清理，不能用其他应用、Worker 心跳或跳过项替代。

本节计划与 [`docs/product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md) 的 0.7 节、[`Task.md`](../Task.md) 和 [`MEMORY.md`](../MEMORY.md) 同步维护。

### 2026-08-25 P0-0 管理员初始化幂等修复（本地证据）

- 已修复 `backend/app/main.py::_init_admin` 按用户名/邮箱幂等识别和并发唯一键复查逻辑，避免管理员改名后 q19 Backend 因默认邮箱重复进入重启循环。
- 新增管理员初始化回归；定向 `2 passed`，后端非集成全量 `2262 passed`，Ruff、格式检查和 `git diff --check` 通过。
- q19 已按 `65eef50` 更新 Backend，迁移 `20260824_0065 (head)`，Backend `running/healthy`，当前账号登录、依赖 readiness、Web/Android Worker registry 和 2 台设备扫描通过，最近 2 分钟无启动错误；脱敏证据见 [`q19-admin-bootstrap-2026-08-25.json`](evidence/q19-admin-bootstrap-2026-08-25.json)。
- P0-0 的启动与认证阻塞已关闭，但 Android 真实 APK/package name、低代码、录屏、专项任务和报告媒体仍未验收；远端 Compose 的端口映射等现场改动已保留，不能用仓库文件覆盖。

### 2026-08-25 P0-B.3 单设备运行与 APK 上传问题

- 已在真实在线设备 `172.16.102.214:5555` 上用已安装包 `com.microsoft.emmx` 完成临时低代码、步骤截图、设备信息、logcat 和录屏回传；3/3 步骤通过，临时业务数据已清理。该证据只覆盖平台执行链路，不代表 Karing 包存在。
- 真实上传约 262 MB APK 时发现 q19 MinIO multipart 分片使用 5 秒读超时并返回 HTTP 500；已在本地修复为独立 `MINIO_READ_TIMEOUT_SECONDS` 和并发连接池，前端配置/示例/文档已同步。
- q19 已按 `e1dc113` 重建并健康运行；262,615,229 字节 APK 上传、标准 `ResXMLTree` Manifest 解析出 `com.microsoft.emmx`/版本信息、项目对象绑定、列表回读和临时记录/对象/项目清理均通过。证据见 [`android-apk-upload-2026-08-25.json`](evidence/android-apk-upload-2026-08-25.json)。
- 本项仍不关闭 Android 总门禁：当前设备包列表没有 Karing，Karing 专项动作、APK 下载端点、异常回放和完整报告下载仍需真实 Karing APK/设备复验。

本地代码、回归和 Windows/q19 API/Web/性能链路已经形成可复核证据；以下外部门禁仍未关闭，因此发布只能按“部分实现/待环境验收”处理：

- Android Worker/真机：ADB、Agent/Backend Redis 配对、Worker registry、扫描回调、租约绑定控制和 APK 资产选择/包名传递已通过；专项任务包名一致性、应用启动/Monkey/动作失败终态已完成本地回归，但真实 APK 上传、低代码、录屏、专项任务和结果回传仍不能验收。
- 性能生产环境：真实 Kubernetes 多节点、容量限制、生产 Prometheus、MinIO 生命周期和跨主机恢复未验收。
- 通知供应商：当前只有回环 SMTP 的 `local_link_only` 证据，没有真实 SMTP/企业微信/钉钉送达回执。
- 外部缺陷平台：没有可使用的临时 Jira/禅道/GitHub/GitLab 项目和凭据，创建、同步和脱敏链路未做真实验收。

### 2026-08-25 P0-A Windows API/Web 完整 smoke

- 使用当前有效账号运行完整 `scripts/windows-local-smoke.ps1 -SeedWebDownloadCase -RequireWebLowcode -RequireWebDownload`：Backend/Frontend HTTP 200、HttpOnly Cookie 登录、PostgreSQL/Redis/MinIO readiness、Web Worker、Playwright `12 passed`、浏览器矩阵无失败请求/错误响应、文件上传/清理、Web 低代码下载和 HTML/JUnit 报告导出均通过。
- 临时 Web run `18` 通过，HTML/JUnit 报告分别为 `18,718/320` bytes；临时项目 `35` 与 5 个产物已清理。脱敏证据已更新为 [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)，来源提交 `35ad777`。
- P0-A Windows API/Web 复核本轮关闭；该证据不替代 Karing Android、GraphQL/WebSocket/流式 gRPC 完整真实目标、真实通知、外部缺陷平台或生产性能验收。

## 当前开发计划

当前按参考导航的五组结构推进：工作台、测试能力、测试资产、智能中枢、系统。旧设备/APK/专项任务、Mock、数据集和治理页面保留兼容 URL，但从所属工作台或配置中心进入；“入口可见”不作为业务闭环通过条件。

当前优先关闭 Android P0-B.3 单设备执行闭环，拆分为：真实 APK 上传/包名识别与选择、低代码最小执行、录屏与异常回放、专项任务、事件/日志/报告回传。每一项都必须同时具备代码、回归测试、代码审查修复和脱敏证据；没有 APK、包名或在线 `device` 时，只记录阻塞，不创建脏运行。

P0-B.3.5 事件、日志与报告回传已完成本地实现，并已用通用 APK 完成低代码录屏、设备信息、logcat、截图和结果回传验证；Karing 包身份、Worker 前置、低代码和录屏回传现已通过，下一步是异常回放、专项任务、事件/日志/报告详情与最终对象清理。未完成前不移动 N2 游标。

Android 闭环完成后，按 P0-A → P1-C → P1-D → P1-E → P1-F 继续复核 Windows API/Web、真实通知供应商、外部缺陷平台、性能生产环境和发布收口。详细依赖、出口和状态见 [`product-navigation-roadmap-2026-08-24.md`](product-navigation-roadmap-2026-08-24.md) 的“0.5 当前开发计划与跟踪台账”，执行勾选见 [`Task.md`](../Task.md)。

### 2026-08-25 Android 设备前置验收复核

- 两台 ADB 设备均为 `device`，选定 `172.16.102.15:5555` 完成命令、属性、包管理和 logcat 检查；Windows Android Worker 正在消费 `android,mobile_special`，PostgreSQL/Redis/MinIO doctor 通过。
- 当前在线设备第三方包列表没有 Karing，且 `.env` bootstrap 账号登录返回 HTTP 401；因此未调用认证 Worker registry/扫描接口，也未创建 Android 运行记录。
- 脱敏证据见 [`android-device-control-preflight-2026-08-25.json`](evidence/android-device-control-preflight-2026-08-25.json)。这项证据只关闭设备前置检查，不关闭 Android 真实执行门禁。

## 2026-08-25 Android 低代码最小执行本地交付

- 单设备执行现在按设备 serial 查询注册设备、申请/释放租约；租约冲突会在执行步骤前结束为 error。设备矩阵保持每个子运行独立租约。
- Worker 按 `apk_id` 查询项目 APK 资产并校验模块项目归属，执行前复用 Android preflight 下载/安装 APK；步骤结果、截图和完成事件继续回传。
- Android 相关回归 `145 passed`，后端非集成全量 `2245 passed`，Ruff 和 `git diff --check` 通过；脱敏证据见 [`android-lowcode-execution-2026-08-25.json`](evidence/android-lowcode-execution-2026-08-25.json)。
- 发布边界：本地代码链路已完成，但当前没有真实 APK 文件，尚未完成在线设备低代码执行、录屏、专项任务和完整事件/日志/报告回传，因此 Android 真机门禁仍未关闭。

## 2026-08-25 P0-B.3.3 录屏与异常回放可观测性本地交付

- 低代码录屏启动失败现在写入 `result_summary.android_artifacts.screen_recording_error`；专项异常回放写入 `summary_json.incident_replay`，包含是否请求、是否保存和失败原因。
- 报告详情页展示异常回放不可用告警；如果后续录屏轮换成功并保存回放，会清除过时的启动失败告警，避免与可播放视频同时出现矛盾提示。
- Android 执行器定向 `64 passed`，后端非集成全量 `2248 passed`，前端 Vitest `66 files / 269 tests passed`，类型检查、生产构建、Ruff 和差异检查通过；脱敏证据见 [`android-recording-observability-2026-08-25.json`](evidence/android-recording-observability-2026-08-25.json)。
- 发布边界：没有真实 APK 和在线设备录屏/Crash/ANR 证据，MinIO 视频上传、设备权限和专项回放仍待真实环境验收；本地回归不关闭 Android 真机门禁。

## 2026-08-25 P0-B.3.4 Android 专项任务本地交付

- 任务新建、编辑和手工触发现在统一校验项目内 APK 的已确认 `package_name`；缺少包名或手工包名与 APK 不一致时返回 `400`，默认任务 APK 也会被解析并写入运行快照。
- 性能、稳定性和流畅度执行器在应用启动失败、Monkey 启动/异常退出或流畅度动作失败时写入 `summary_json.error_message` 并终态为 `failed`；完成事件会携带失败状态和错误摘要，正常取消仍为 `stopped`。
- 定向回归 `86 passed`，4 个受影响文件独立运行 `28/25/19/14 passed`，后端非集成全量 `2255 passed`；前端 Vitest `66 files / 269 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过。脱敏证据见 [`android-special-task-2026-08-25.json`](evidence/android-special-task-2026-08-25.json)。
- 发布边界：未获得真实 APK 和在线 `device` 执行证据前，不关闭真实安装/启动、专项动作、超时取消、Crash/ANR logcat、录屏、MinIO 或报告回传门禁；Karing 仍需先通过包管理确认真实包名。

## 2026-08-25 P0-B.3.5 事件、日志与报告回传本地交付

- Worker 收尾阶段按任务配置采集结束时的设备 logcat 和 PNG 截图，分别限制在 5 MB/10 MB；上传成功登记 `MobileRunArtifact`，摘要记录 `requested/saved/file_name/file_size/error`，采集、上传或 ADB 失败不会覆盖专项原始状态。
- 专项任务配置页已增加设备日志/结束截图开关；报告详情页展示产物状态，报告文件表通过受保护的 artifact URL 下载；已有性能 CSV、异常日志、录屏和异常回放不改变原有路径。
- 事件记录器与 JSON 报告导出统一脱敏常见 Authorization、Cookie、密码、Token、Secret、API Key 以及 URL 查询凭据；事件达到上限时仍会提交产物行和摘要。
- 定向 84 项、后端非集成 `2260 passed`，前端 Vitest `66 files / 269 tests passed`，`vue-tsc`、生产构建、Ruff 和 `git diff --check` 通过；脱敏证据见 [`android-event-artifact-reporting-2026-08-25.json`](evidence/android-event-artifact-reporting-2026-08-25.json)。
- 发布边界：真实 APK、在线 `device`、MinIO 上传/下载/清理、三类专项端到端日志/截图和性能录屏/异常回放仍待真实环境验收，本地证据不关闭 Android 真机门禁。

## 2026-08-25 P0-A 本地 E2E 回归复核

- 本地 Playwright 共享 fixture 已修复中文登录按钮自动空格，以及主布局 `/workbench/overview`、运行详情 `/defects` 未隔离导致的真实 401；登录定向 `3 passed`、运行详情定向 `1 passed`、全量 Playwright `12 passed`。
- 前端 Vitest `66 files / 265 tests passed`，`vue-tsc --noEmit`、生产构建和 `git diff --check` 通过。
- 这不改变发布结论：Windows 完整 smoke 仍需使用当前有效账号重跑；认证读接口、文件传输和报告导出在账号未通过前保持未验收，不记录任何密码或 Token。

## 2026-08-25 P0-B Android 单设备验收前置复核（历史记录）

- 早期执行 `scripts/windows-android-acceptance.ps1` 时，设备统计为 `online=0, unauthorized=0, offline=1, other=0`，必需检查失败；该结果只代表当时的设备状态。
- 脱敏本地报告：`.local-run/android-acceptance-current-20260825.json`。脚本在离线状态下不会继续执行设备命令、包管理、日志读取或创建 Android 运行任务。
- 后续设备已恢复在线，当前阻塞已转为 Worker 注册 Redis 通道配对，见下方最新记录；历史 `offline` 不能被重新解释为当前通过。

## 2026-08-25 P0-B Android ADB 在线但 Worker 注册未配对

- ADB 通过 mDNS 发现在线目标；目标 `172.16.102.15:5555` 的授权、shell、属性、包管理和 logcat 基础检查通过。
- Windows Android Worker 的 Redis DB 2 中存在心跳注册，但 q19 Backend 通过 SSH 隧道使用 q19 Compose 内部 Redis，因此 `/devices/workers` 返回没有在线 Android Worker。
- 发布边界：这不是 ADB 失败，而是 Agent/Backend 注册通道配置不一致。完成同实例、DB、注册前缀配对并重新验证 Worker registry、扫描和结果回传之前，Android 发布门禁仍保持未关闭。
- 当前重新发现的设备未确认存在 Karing 包名；任何 Karing 专项任务必须先通过设备包管理确认真实包名。

## 2026-08-25 P0-B Android Redis 配对与 Worker 注册复核（扫描回调修复前快照）

- Windows Agent 与 q19 Backend 已通过受控临时 SSH 隧道共用同一 Redis 实例、DB、认证、队列和注册前缀；配置配对校验、Worker doctor 和 `/devices/workers` 查询通过，在线 Worker 为 `android-win-HPS`。
- ADB 基础检查仍通过；本条记录保留的是修复前扫描 smoke 未在 10 秒窗口内收到完成回调的历史状态，后续已定位并修复 `scan_adb_devices` 丢弃 Celery 结果的问题，当前结论以紧随其后的 P0-B.2 验收记录为准。
- 本机复验命令为 `adb devices -l`；只有明确显示目标为 `device` 才能继续 Android 单设备链路，`offline` 或 `unauthorized` 仍保持阻塞。
- 为避免 Beat 继续生成维护任务，q19 Beat 当前保持受控停用；恢复前必须确认队列已清理、只保留预期任务，并重新取得扫描回调证据。
- 发布边界：Worker registry 在线和基础控制通过仍不等于 Android 单设备闭环通过；APK 包名、低代码真实运行、录屏、专项任务、事件和报告回传仍保持未验收。当前设备是否安装 Karing 仍须以 `pm list packages` 为准。

## 2026-08-25 P0-B.2 Android 扫描回调修复与验收（控制门禁前基线）

- 修复 `scan_adb_devices` 声明 `ignore_result=True` 的问题。任务此前已经在 Windows Worker 成功执行，但 API 读取不到 Celery 结果，导致 `scan_id` 长时间保持 `queued`；现已保留任务结果并新增契约回归。
- 重新启动单个受控 Worker 后，配置配对、ADB、Worker registry 和扫描回调均通过；扫描返回 2 台在线设备，扫描后 `mobile_special` 队列长度为 `0`。
- 定向测试 `24 passed`，三份受影响测试文件独立运行 `4/17/3 passed`，完整后端非集成 `2237 passed`，Ruff 和 `git diff --check` 通过。脱敏证据见 [`android-worker-scan-2026-08-25.json`](evidence/android-worker-scan-2026-08-25.json)。
- 发布边界：本项只关闭 Worker 配对和扫描回调门禁；租约、控件属性、截图/录屏、APK 包名、Android 低代码、专项任务、事件和报告回传仍待 P0-B.3。

## 2026-08-25 P0-B.3 Android 租约绑定控制验收

- 修复设备点击/滑动接口缺少租约校验的问题；现在必须通过 `X-Device-Lease-Token` 携带当前有效设备租约，缺少或过期令牌返回 `409`。
- Android 低代码抽屉会在选择设备后自动申请租约并定时续租，切换设备、切换脚本模式、保存关闭或卸载时释放；截图读取保持兼容，控件属性读取继续用于生成定位器。
- 定向后端 `43 passed`，前端 Android 抽屉 `3 passed`，类型检查、Ruff 和差异检查通过；脱敏真实证据见 [`android-control-lease-2026-08-25.json`](evidence/android-control-lease-2026-08-25.json)。
- Windows Worker/q19 依赖上的真实链路：设备 ID `1`、扫描 2 台；租约申请成功，截图 `29,099` bytes，UI 属性响应，点击/滑动 `200`，无租约点击 `409`，释放 `204`。
- 发布边界：APK 包名、Android 低代码真实运行、设备录屏、专项任务、事件/日志/报告回传仍保持未验收。

## 2026-08-25 P0-B.3 APK 资产选择与包名传递验收

- APP 自动化工作台选择 APK 后现在传递 `apk_id`；后端校验 APK 属于当前项目，并将 APK ID、包名写入手工触发运行的记录和配置快照，Worker 可据此取得安装资产。
- 任务默认 APK 的 ID 会继续进入运行快照；跨项目 APK 选择返回 `400` 且不写入运行记录。
- 定向后端 `53 passed`，前端 APP 工作台 `3 passed`，类型检查、Ruff 和差异检查通过；脱敏证据见 [`android-apk-selection-2026-08-25.json`](evidence/android-apk-selection-2026-08-25.json)。
- 发布边界：当前没有真实 APK 文件可上传，连接设备的包管理结果也未发现 Karing 包名；真实 APK 上传/包名识别、低代码、录屏、专项任务和事件/报告回传仍待验收。

## 2026-08-25 工作台任务状态枚举隔离修复

- q19 日志暴露工作台将 Android `stopped`、性能 `cancelled` 混入普通 `TestRun`/套件/计划状态查询，可能导致 PostgreSQL `runstatus` enum 错误。
- 已按任务域限制状态过滤，空交集显式无匹配，重试状态按域恢复；工作台定向 `8 passed`，完整后端非集成 `2229 passed`，Ruff/diff-check 通过。
- q19 已按 `36cacb9` 受控重建，迁移 `20260824_0065`、Backend `200`、Prometheus 4 targets `up`、Celery 2 节点在线，重启后未出现新的 enum 错误；脱敏证据见 [`q19-workbench-status-filter-2026-08-25.json`](evidence/q19-workbench-status-filter-2026-08-25.json)。鉴权工作台请求仍因缺少当前有效账号未执行，发布结论不因此提前关闭。

## 2026-08-25 Android 录屏证据展示补齐

- Android Worker 产生的 `result_summary.android_artifacts.screen_recording` 现在可在运行详情页直接播放；`screen_recording_error` 会以告警形式展示。
- HTML 报告会在开启录像选项时嵌入 Android 录屏；通用 `video_url` 仍优先，PDF 不嵌入视频的既有行为不变。
- 运行详情在收到 WebSocket 完成事件后自动刷新，避免执行页面必须手动刷新才能看到录屏。
- 本地证据：提交 `279b254`，后端导出 `13 passed`、RunDetail `6 passed`、前端全量 `66 files / 268 tests passed`，类型检查和构建通过；详见 [`android-recording-evidence-2026-08-25.json`](evidence/android-recording-evidence-2026-08-25.json)。
- q19 已从 `origin/main` 的 `257c479` 独立工作树重建并启动；迁移 `20260824_0065 (head)`、健康 `200`、Prometheus 4 个 target `up`、Celery 2 节点响应、后端最近 3 分钟错误匹配数为 0；详见 [`q19-android-recording-deployment-2026-08-25.json`](evidence/q19-android-recording-deployment-2026-08-25.json)。
- 发布边界：当前没有真实 Android 录屏采集证据，且 Worker 注册通道尚未配对；这项改动不关闭 Android 真机发布门禁。

## 2026-08-25 P1-D 外部缺陷平台错误安全收口

- 连接测试、创建缺陷和刷新状态入口已统一脱敏供应商异常，覆盖 Token、密码、Webhook 查询参数和 URL 用户信息；创建/状态刷新返回 502，连接测试返回 `ok=false`。
- 缺陷跟踪入口的 mypy 变量复用问题已修复，成功创建、重复检测、状态同步和附件上传路径保持不变。
- 本地证据：提交 `31df065`，外部缺陷定向 `40 passed`、完整后端非集成 `2234 passed`，Ruff、格式、mypy 和 diff-check 通过；详见 [`external-tracker-error-safety-2026-08-25.json`](evidence/external-tracker-error-safety-2026-08-25.json)。
- 发布边界：没有真实外部缺陷平台项目与凭据，本模块不关闭 Jira/禅道/GitHub/GitLab 的环境验收门禁。

## 2026-08-25 P1-D q19 运行态部署

- q19 已重建到 `cec8eaf`，复用 `atp-q19-acceptance-20260824` Compose 项目名，迁移为 `20260824_0065 (head)`。
- 运行验证通过：Backend `200`、Redis `PONG`、Prometheus ready 且 `4` 个 target 为 `up`；通用 Worker、性能 Worker、Beat、Web Recorder 正常运行，最近 3 分钟 Backend/Worker 错误匹配数为 `0`。
- 发布边界：q19 Compose 不是 Kubernetes 多节点或生产外部平台证据；真实 Jira/禅道/GitHub/GitLab、Android 真机和生产性能验收仍待独立完成。详见 [`q19-external-tracker-deployment-2026-08-25.json`](evidence/q19-external-tracker-deployment-2026-08-25.json)。

## 2026-08-25 P1-C 通知验收脚本错误脱敏修复

- 通知供应商验收脚本已改为复用统一异常脱敏逻辑，Token、密码和 URL 用户信息不会进入终端或 JSON 报告；全量测试下的历史模块桩污染也已隔离。
- 本地证据：提交 `9852387`，通知定向 `12 passed`、完整后端非集成 `2236 passed`，改动文件 Ruff、格式和 diff-check 通过；详见 [`notification-acceptance-redaction-2026-08-25.json`](evidence/notification-acceptance-redaction-2026-08-25.json)。
- 发布边界：未连接真实 SMTP、企业微信或钉钉供应商，本模块不关闭真实投递、供应商侧送达、限流和重复投递门禁。
- 追加提交 `8fd129b` 补齐通知 Smoke 对 `access_token`、`sign` 和 URL 用户信息的错误脱敏；定向 `12 passed`、后端非集成 `2236 passed`，详见 [`notification-smoke-redaction-2026-08-25.json`](evidence/notification-smoke-redaction-2026-08-25.json)。

## 2026-08-25 Windows 已认证浏览器冒烟复核

- 复用当前已登录的 Windows 浏览器会话，实际加载统计看板、工作台概览、我的待办、用例管理、执行记录、测试套件、存储管理和 API 契约资产；页面均保持在业务页，未回到登录页，用户菜单显示为 `admin`。
- q19 Backend 最近 5 分钟日志未发现 `Traceback`、`ERROR` 或 `invalid input value for enum`；这轮验证确认前端到远端后端的已认证页面链路可用。
- 脱敏证据见 [`windows-browser-smoke-2026-08-25.json`](evidence/windows-browser-smoke-2026-08-25.json)。本轮复用了已有会话，未记录密码/Token；文件传输、报告导出、浏览器矩阵和 Web 低代码仍沿用既有完整 readiness 证据，不因本轮页面冒烟重复通过。

## 2026-08-25 P1-E.4 性能多节点分片容量校验

- 多节点压测现在先按节点数拆分总负载，再用每个节点的 `max_vus`、执行器能力和出口 allowlist 校验分片；总负载 10、两台节点上限 6 时生成 5/5 分片，上限 4 时返回 400 且不写入运行记录。
- 代码审查未发现问题；性能 API `72 passed`、性能服务/Worker `24 passed`、完整后端非集成 `2231 passed`，Ruff 和 `git diff --check` 通过。脱敏证据见 [`performance-shard-capacity-2026-08-25.json`](evidence/performance-shard-capacity-2026-08-25.json)。
- 这只完成本地分片校验，不代表真实 Kubernetes 多节点调度、生产 Prometheus/MinIO 生命周期或跨主机恢复已通过。
- q19 已按 `ca79937` 重建并启动，迁移 `20260824_0065 (head)`、Backend `200`、Prometheus 4 targets `up`、Celery 2 节点 `pong`；重启后 Backend 无 enum/Traceback/ERROR。脱敏证据见 [`q19-performance-shard-deployment-2026-08-25.json`](evidence/q19-performance-shard-deployment-2026-08-25.json)。

## 2026-08-25 N2 Karing 稳定性专项真实闭环（最新）

- Windows Android Worker 已与当前 q19 受控 Backend 使用同一 Redis、数据库、MinIO 和注册前缀；`android-win-HPS` 在线，设备 `153 / 172.16.102.91:5555` 为 `online`，目标包名为 `com.nebula.karing`。
- 稳定性运行 `6` 与回放运行 `7` 均为 `completed`，随机种子 `20260825` 保持一致；回放保存 78 条事件，序号 1～78 无重复，记录 Monkey 动作/日志、Crash、设备 logcat 和截图。
- 运行详情 JSON 导出和 2 个产物 URL 均返回 200；临时项目 `50` 已删除并确认不存在。脱敏证据见 [`evidence/android-karing-special-task-2026-08-25.json`](evidence/android-karing-special-task-2026-08-25.json)。
- 真实运行先暴露并发提交缺陷，代码审查再发现多记录器序号重复；已完成写锁串行化和共享记录器修复。定向回归 `82 passed`，后端非集成全量 `2306 passed`，Ruff、格式、差异检查通过。
- **发布边界**：这只关闭 N2 的稳定性/Monkey、事件时间线、Crash、设备日志/截图、报告导出和清理证据；性能专项、流畅度专项以及 N2 总体验收仍未关闭，不能以本项替代。

## 2026-08-25 N2 Karing 性能/流畅度专项真实闭环（最新）

- 同一 Windows Android Worker、设备 `153 / 172.16.102.91:5555` 和包名 `com.nebula.karing` 上，性能运行 `10` 为 `completed`，采集 CPU、VmRSS 内存、电量、温度、FPS 和卡顿各 3 条；流畅度运行 `13` 为 `completed`，执行滑动/点击两个阶段并采集 2 个 FPS 样本。
- 两个运行的事件序列均无重复，JSON 报告导出均 HTTP 200；临时项目 `51` 删除返回 204，删除后查询 404。脱敏证据见 [`evidence/android-karing-performance-fluency-2026-08-25.json`](evidence/android-karing-performance-fluency-2026-08-25.json)。
- 真实 Android 14 复验发现并修复 `dumpsys meminfo` 标题-only 的 VmRSS 兜底，以及 `gfxinfo` `Total frames`/等号 `HISTOGRAM` 解析和 GPU 直方图排除；定向回归 `60 passed`，Ruff 通过，修复后重启 Worker 并完成复验。
- **发布边界**：N2 Karing 单设备闭环已关闭；多设备兼容性矩阵、真实 Kubernetes/Prometheus/独立 MinIO 性能环境和其他外部发布门禁仍未关闭。

## 能力与证据索引

| 能力域 | 当前结论 | 主要证据 | 未关闭边界 |
|---|---|---|---|
| Windows API/Web | 当前账号下完整 smoke 已重新通过；N1 受控协议与报告闭环已补齐，生产协议和外部环境仍按各自门禁独立跟踪 | [`windows-full-readiness-2026-08-25.json`](evidence/windows-full-readiness-2026-08-25.json)、[`windows-browser-smoke-2026-08-25.json`](evidence/windows-browser-smoke-2026-08-25.json)、[`api-real-target-2026-08-25.json`](evidence/api-real-target-2026-08-25.json)、[`api-session-reuse-2026-08-25.json`](evidence/api-session-reuse-2026-08-25.json)、[`api-grpc-tls-2026-08-25.json`](evidence/api-grpc-tls-2026-08-25.json)、[`api-import-persistence-2026-08-25.json`](evidence/api-import-persistence-2026-08-25.json)、[`api-protocol-targets-2026-08-25.json`](evidence/api-protocol-targets-2026-08-25.json)、[`report-closure-2026-08-25.json`](evidence/report-closure-2026-08-25.json) | 生产协议服务、生产对象存储和发布环境仍需验收 |
| Web Worker/录制 | q19 持久 Worker、Chromium/Firefox/WebKit 录制和跨 API 停止快照已验证 | [`q19-web-recorder-readiness-2026-08-24.json`](evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recording-cross-api-2026-08-24.json`](evidence/q19-web-recording-cross-api-2026-08-24.json) | Linux/Xvfb、跨副本和目标部署拓扑仍需独立复验 |
| Android | Karing 包名、配置配对、Worker registry、扫描、租约、低代码、录屏、稳定性/Monkey、性能/流畅度和事件/报告回传已验证 | [`android-karing-acceptance-2026-08-25.json`](evidence/android-karing-acceptance-2026-08-25.json)、[`android-karing-special-task-2026-08-25.json`](evidence/android-karing-special-task-2026-08-25.json)、[`android-karing-performance-fluency-2026-08-25.json`](evidence/android-karing-performance-fluency-2026-08-25.json) | 多设备矩阵、真实兼容性覆盖和 N4 生产性能环境仍待验收 |
| 性能 | P1-E.1～P1-E.4 本地闭环完成，q19 已按最新提交重建 | [`q19-performance-worker-smoke-2026-08-24.json`](evidence/q19-performance-worker-smoke-2026-08-24.json)、[`performance-shard-capacity-2026-08-25.json`](evidence/performance-shard-capacity-2026-08-25.json)、[`q19-performance-shard-deployment-2026-08-25.json`](evidence/q19-performance-shard-deployment-2026-08-25.json) | 真实 Kubernetes 多节点、生产 Prometheus、MinIO 生命周期和跨主机恢复 |
| 通知 | 本地 SMTP 链路已验证 | [`notification-smtp-link-check-2026-08-24.json`](evidence/notification-smtp-link-check-2026-08-24.json) | 真实供应商送达、重试、限流和重复投递 |
| 外部缺陷平台 | 本地适配器和脱敏逻辑已实现 | [`docs/capability-baseline-2026-08-07.md`](capability-baseline-2026-08-07.md) | 临时项目、权限、创建/去重/状态同步和清理 |

## 当前本地质量证据

- P1-E.3 性能运行记录清理：后端定向 `24 passed`，完整非集成后端 `2226 passed`，3 个受影响测试文件独立运行 `3 passed, 0 failed`。
- 前端全量 Vitest：`66 files / 265 tests passed`；`vue-tsc --noEmit` 和生产构建通过。
- 本次模块的 Ruff、格式检查和 `git diff --check` 通过。
- 这些结果证明当前代码变更的本地质量，不替代下表中的外部环境门禁。

## 发布前复验顺序

1. 在 Windows 上使用当前有效账号重跑完整 API/Web smoke，并记录同一提交 SHA。
2. 已完成 Windows Agent 与 q19 Backend 的 Redis 实例、DB 和注册前缀配对，并确认 `/devices/workers` 在线；下一步在同一设备执行性能/流畅度专项，任何 `offline`、`unauthorized`、无 Worker 或无设备结果都保持阻塞。
3. 在目标 Linux/Kubernetes 环境执行 `scripts/performance-environment-smoke.py`，补齐真实节点、目标服务、Prometheus、取消和资源采样证据。
4. 注入不落库的临时通知供应商凭据，按渠道取得供应商侧送达回执后清理目标和凭据。
5. 使用临时外部缺陷项目验证创建、重复识别、状态同步、权限、错误脱敏和清理。
6. 汇总新的带日期证据后，再更新本文件、能力矩阵、Q18 状态和发布说明；在此之前保持“部分实现/待环境验收”。

## 禁止事项

- 不把 `offline` 设备、无凭据跳过、回环 SMTP、localhost 目标或 Docker Compose 契约测试写成生产通过。
- 不在仓库、证据 JSON、日志或截图中保存密码、Token、Webhook、MinIO 密钥或外部平台凭据。
- 不用 GitHub Actions 绿灯替代真实设备、真实供应商和真实目标服务证据；当前 Actions 触发策略以 [`docs/ci-workflows.md`](ci-workflows.md) 为准。
