# ATP 平台 Q3 实施计划

> 生成日期：2026-05-18
> 优先级：P0=紧急高价值，P1=高价值，P2=中价值
> 前置：Q2 P0/P1 全部收口（见 `implementation-plan-2026-Q2-detail.md`），含套件并发、看板缓存与索引、链路追踪、存储治理、终态运行记录清理、存储告警、用例/套件/计划批量操作（含 ZIP 导入导出）

---

## 总览

Q3 围绕 **效率工具化（AI / 国际化）** 与 **可观测性下沉（OTel/Jaeger）** 两个主题展开，并把 Q2 暂缓的几个 P2 项目（plan 级并发、storage max_size_gb 总量淘汰、BatchOperationBar 抽取）作为收口项一并完成。

### 优先级与依赖

```
P1 → 方向 E：AI 用例生成（OpenAPI/Postman → 用例 JSON）
P2 → 方向 F：前端国际化 i18n
P2 → 方向 G：完整链路追踪升级（OpenTelemetry + Jaeger）
P2 → 方向 H：Q2 暂缓收口（plan 并发 / 存储总量淘汰 / 通用批量组件抽取）
```

实施顺序按业务感知度排：E → H → F → G。

---

## 方向 E：AI 用例生成 [P1]

### 目标

业务测试人员上传 OpenAPI 3.x JSON/YAML 或 Postman Collection v2.1，AI 自动生成可执行的 ATP 接口用例草稿，节省 80% 手工编写时间。

### 现状

- 当前用例需逐条手工填写 method/url/headers/body/assertions
- 后端 `app/api/v1/cases.py` 的 `create_case` 已支持完整 config + steps 写入
- 项目尚未集成任何 LLM 调用

### 实施步骤

#### E.1 Schema 解析器

**新增**：`backend/app/services/ai_case_generation/openapi_parser.py`

- 解析 OpenAPI/Swagger 文档，输出标准化的 endpoint 列表
- 解析 Postman Collection v2.1 → 同样的 endpoint 结构
- 公共结构：`{method, url_template, parameters[], request_body_schema, response_examples[]}`

#### E.2 LLM 客户端封装

**新增**：`backend/app/services/ai_case_generation/llm_client.py`

- 通过 `settings.AI_PROVIDER`（claude/openai/dashscope）切换
- 支持 **API key 通过环境变量** 配置：`AI_API_KEY`、`AI_ENDPOINT`
- 默认模型：Claude Haiku 4.5（成本可控、速度足够）
- 必含提示词模板：
  - "根据下面的接口规范，生成 1 条覆盖正常路径的 ATP 测试用例 JSON…"
  - "生成 1 条验证缺失必填字段时返回 400 的负向用例…"

#### E.3 生成 API

**新增**：`backend/app/api/v1/ai_case_generation.py`

```
POST /api/v1/ai/cases/parse-schema   解析上传的 schema → 返回 endpoints
POST /api/v1/ai/cases/generate       根据选中的 endpoints + 生成策略 → 返回用例草稿数组
POST /api/v1/ai/cases/confirm        把草稿写入 TestCase 表
```

返回的草稿格式与现有 `TestCaseCreate` 一致，前端可直接复用 CaseFormDrawer 进行二次编辑后确认。

#### E.4 前端入口

**新增**：`frontend/src/views/case/AiGenerationView.vue`

- Tab1：上传 OpenAPI/Postman 文件或粘贴 URL
- Tab2：endpoint 多选 + 用例生成策略（正常路径 / 边界值 / 负向 / 全部）
- Tab3：草稿预览、可双击直接打开 CaseFormDrawer 编辑、批量确认入库

### 限制 / 不做

- 不做 Web UI 截图 → 用例生成（远期）
- 不做执行失败原因 AI 分析（远期）
- 暂不接入向量库 / RAG（用例上下文较小）

### 里程碑

- [x] E.1 OpenAPI / Postman 解析器（commit 4714fea）
- [x] E.2 LLM 客户端 + 提示词模板（commit 4714fea，统一支持 DeepSeek/OpenAI/Qwen/Ollama + Claude）
- [x] E.3 生成 API（parse-schema + generate，confirm 由前端直接调用 caseApi.create 替代）
- [x] E.4 前端：AILLMConfigList（admin）+ AIGenerateDrawer（CaseList 入口） — commit 68374a5
- [x] E.5 后端测试覆盖 40 用例（commit 4714fea）

---

## 方向 F：前端国际化 i18n [P2]

### 目标

支持中英文切换，便于团队接入海外项目；不影响现有页面布局。

### 实施步骤

#### F.1 vue-i18n 集成

- 新增依赖 `vue-i18n@9`
- `frontend/src/locales/zh-CN.ts` 与 `en-US.ts` 初始 key/value 字典
- `frontend/src/main.ts` 注册 i18n 插件
- URL 参数 `?lang=en` 切换 + 本地存储记忆

#### F.2 抽取硬编码（按页面优先级）

1. 登录页 + 导航栏 + 通用按钮（OK/Cancel/Save…）
2. Dashboard
3. 用例 / 套件 / 计划列表
4. 执行详情
5. 移动专项 + 系统设置

#### F.3 后端通知模板支持模板变量

- `services/notifier.py` 中的硬编码中文文案改为支持 `lang_hint` 参数（中/英）
- 通知 `NotificationConfig.config` 增加 `language` 字段（默认 zh）

### 里程碑

- [x] F.1 vue-i18n 集成 + 切换器
- [x] F.2 登录/导航/通用按钮翻译
- [~] F.3 业务页面逐步翻译（按需）
- [x] F.4 后端通知模板 i18n 化

### 当前迁移记录（2026-05-19）

已完成前端页面迁移：

- 基础与通用：登录页、导航栏、通用按钮、Dashboard、计划列表
- 用例与执行：`CaseList.vue`、`RunList.vue`、`RunDetail.vue`
- 套件：`SuiteList.vue`
- Android 专项：`SpecialTaskListView.vue`
- 系统设置：`EnvironmentList.vue`、`NotificationList.vue`、`GlobalVariableLibrary.vue`、`AILLMConfigList.vue`

本轮新增 / 扩展词典：

- `frontend/src/locales/zh-CN.ts`
- `frontend/src/locales/en-US.ts`

验证：

- `npm run type-check` 通过（`vue-tsc --noEmit`）

剩余迁移队列：

- 最终文案复核：`zh-CN.ts`、`en-US.ts`、已迁移页面与组件
- Android 专项报告：`ReportCenterView.vue`、`ReportDetailView.vue`
- 系统设置：`StorageManagementView.vue`、`BugTrackerList.vue`
- 组件级编辑器：`LowcodeStepEditor.vue`、`AndroidStepEditor.vue`、`ModuleTree.vue` 等公共组件中的可见文案

### 后续执行拆分

| 批次 | 范围 | 主要文件 | 验收标准 |
|------|------|----------|----------|
| F.3.1 | 用例详情与历史 | `CaseDetail.vue`、`CaseHistoryDrawer.vue` | 已完成：详情页、复制/评审/执行、版本对比与回滚提示均支持中英文；`npm run type-check` 通过 |
| F.3.2 | 用例编辑抽屉 | `AIGenerateDrawer.vue`、`WebCaseDrawer.vue`、`AndroidCaseDrawer.vue` | 已完成：AI 生成、Web 脚本/低代码、Android 表单主要可见文案走 locale；`npm run type-check` 通过 |
| F.3.3 | Android 专项报告 | `ReportCenterView.vue`、`ReportDetailView.vue` | 已完成：筛选、统计卡、趋势图图例、异常事件、报告文件、导出/下载提示支持中英文；`npm run type-check` 通过 |
| F.3.4 | 系统设置剩余页 | `StorageManagementView.vue`、`BugTrackerList.vue` | 已完成：存储策略/清理预览、缺陷跟踪表单、连接测试、确认弹窗支持中英文；`npm run type-check` 通过 |
| F.3.5 | 公共组件 | `LowcodeStepEditor.vue`、`AndroidStepEditor.vue`、`ModuleTree.vue`、`KvEditor.vue`、`CaseStepEditor.vue`、`BatchOperationBar.vue` | 已完成：步骤类型、按钮、占位符、模块弹窗等复用文案走 locale；`npm run type-check` 通过 |
| F.4 | 后端通知模板 | `services/notifier.py`、通知配置 schema/API/UI | 已完成：邮件、企业微信、钉钉通知可按配置语言发送；通知配置页可选择语言；通知相关后端测试通过 |
| F.5.1 | 设备 / APK / Mock | `DeviceList.vue`、`ApkList.vue`、`MockRuleList.vue` | 已完成：筛选、表格、弹窗、状态标签、导入导出、屏幕镜像与消息提示走 locale；目标文件扫描无中文命中；`npm run type-check` 通过 |
| F.5.2 | 项目 / 计划补齐 | `ProjectList.vue`、`PlanList.vue` | 已完成：项目卡片、AI 模型绑定、计划表单、Cron 编辑器、Webhook Secret、执行策略和消息提示走 locale；目标文件扫描无中文命中；`npm run type-check` 通过 |
| F.5.3 | 文案复核 | `zh-CN.ts`、`en-US.ts`、已迁移页面 | 已完成（2026-05-20）：`SuiteList.vue` 全表单/Modal/Drawer 与六个 options 数组改为响应式 computed；`CaseFormDrawer.vue` 4 种 case_type 配置全量迁移；新增 `suite.form/config_tips/case_table/.../msg` 与 `case_form.*` 命名空间共 ~220 个键。剩余中文仅限开发注释与后端错误字符串匹配（`RunDetail.vue` 中 `msg.includes('认证'/'超时'/'不存在')`）。`npm run type-check` 通过 |

每个批次完成后执行：

```bash
cd frontend
npm run type-check
```

最终收口检查：

```bash
rg "[一-龥]" frontend/src/views frontend/src/components
```

剩余结果应仅包含注释、中文业务示例或明确需要保留的中文样本文案。

---

## 方向 G：完整链路追踪升级 [P2]

### 目标

把 Q2 完成的 `trace_id` 关联升级为真正的分布式 tracing — span 级耗时、嵌套调用、跨进程上下文都能查询和可视化。

### 实施步骤

#### G.1 OpenTelemetry SDK 接入

- 新增依赖 `opentelemetry-api / sdk / instrumentation-fastapi / instrumentation-celery / instrumentation-sqlalchemy`
- `backend/app/core/tracing.py` 升级：根据 `OTEL_EXPORTER_OTLP_ENDPOINT` 自动启用导出
- 当未配置时回退到当前的纯 trace_id 模式（向后兼容）

#### G.2 业务 span 埋点

- Worker `dispatch_case` / 各 executor 入口加 `tracer.start_as_current_span("executor.api/web/android")`
- 步骤级 span：`step.request / step.assert / step.extract_vars`
- MinIO 操作 / Redis Pub/Sub span（可选，默认关闭）

#### G.3 Jaeger 容器编排

- `docker-compose.yml` 新增 `jaeger` 服务（all-in-one 镜像）
- Backend / Worker 默认连接 `http://jaeger:4317`
- 前端 RunDetail 的 Trace 面板增加"在 Jaeger 中打开"链接

### 里程碑

- [ ] G.1 OTel SDK 接入 + 配置开关
- [ ] G.2 业务 span 埋点
- [ ] G.3 Jaeger compose + 前端链接
- [ ] G.4 文档说明（如何抓取 trace、性能影响、采样率配置）

---

## 方向 H：Q2 暂缓收口 [P2]

把 Q2 已列出但暂缓的几个项目一并补齐，让进度图全绿。

### H.1 Plan 级并发执行

- `Plan.config` 增加 `execution_mode / max_workers / fail_strategy`（结构与 Suite 一致）
- `worker/tasks.run_test_plan` 增加 parallel 分支（仿 suite asyncio.gather 分批模式）
- 前端 PlanList 配置 Drawer 增加并发配置入口

### H.2 存储 max_size_gb 总量淘汰

- `services/storage_cleanup.preview_storage_cleanup` 增加按 `StoragePolicy.max_size_gb` 计算需淘汰的对象（按 last_modified 升序）
- 默认仍按 retention_days 淘汰；同时配置时取交集

### H.3 通用 BatchOperationBar 组件

- `frontend/src/components/common/BatchOperationBar.vue`：参数化选中列表 / 操作按钮 / 取消选择
- 改造 CaseList / SuiteList / PlanList / MockRuleListView 复用

### 里程碑

- [x] H.1 plan 并发执行 + 测试（commit a4b9d32：execution_mode/max_workers/fail_strategy；run_test_plan parallel 分支用独立 AsyncSession；8 个 worker 测试）
- [x] H.2 总量淘汰策略 + 测试（commit a4b9d32：StoragePolicy.max_size_gb + `_select_size_eviction`；与 retention_days 取并集；5 个新测试）
- [x] H.3 BatchOperationBar 抽取与接入（已抽取 `frontend/src/components/common/BatchOperationBar.vue` 并接入 CaseList / SuiteList / PlanList；MockRuleList 暂未启用批量操作，待后续按需接入）

---

## 风险与兜底

| 风险 | 缓解策略 |
|------|----------|
| LLM 接入成本 / 数据外泄 | 默认仅在管理员显式打开 AI 功能后调用，请求 schema 在调用前可勾选"脱敏" |
| i18n 翻译质量 | 先发布带占位英文 + 标注 `TODO: review`，邀请英文母语成员复审 |
| OTel 性能影响 | 默认采样率 10%，关键失败链路强制采样；本地开发关闭采集 |
| plan 级并发破坏 stat 聚合 | 同 Q2 suite 并发保留 sequential 默认；先做单 plan 测试集，灰度切换 |

---

## 实施顺序建议

```
Phase 1 (2-3 周)
  方向 E：AI 用例生成（业务感知最强，需要 LLM 选型 + 提示词调优）

Phase 2 (1 周)
  方向 H：Q2 暂缓收口（小步快推，进度图全绿）

Phase 3 (1-2 周)
  方向 F：前端 i18n（按页面优先级渐进）

Phase 4 (2-3 周)
  方向 G：OTel + Jaeger（基础设施级改动，需要联调和文档）
```

---

## 关键文件清单

| 文件 | 操作 | 方向 |
|------|------|------|
| `backend/app/services/ai_case_generation/` | 新建 | E |
| `backend/app/api/v1/ai_case_generation.py` | 新建 | E |
| `frontend/src/views/case/AiGenerationView.vue` | 新建 | E |
| `frontend/src/locales/{zh-CN,en-US}.ts` | 新建 | F |
| `frontend/src/main.ts` | 修改 | F |
| `backend/app/services/notifier.py` | 修改 | F |
| `backend/app/core/tracing.py` | 升级 | G |
| `backend/app/worker/tasks.py` | 修改（OTel span） | G |
| `docker-compose.yml` | 修改（jaeger 服务） | G |
| `backend/app/models/plan.py` + `worker/tasks.py` | 修改 | H.1 |
| `backend/app/services/storage_cleanup.py` | 修改 | H.2 |
| `frontend/src/components/common/BatchOperationBar.vue` | 新建 | H.3 |

---

## 验证方法

1. **方向 E**：上传一个 10 endpoint 的 OpenAPI → 一键生成 → 入库 → 触发执行；统计生成耗时 + 直接执行通过率
2. **方向 F**：切换 lang=en，验证登录页、导航栏、Dashboard、用例列表正常显示
3. **方向 G**：触发一次套件执行 → Jaeger UI 应展示完整 span 树（API → Celery → Worker → executor → step）
4. **方向 H.1**：20 套件的 plan，sequential vs parallel 执行时长对比
5. **方向 H.2**：上传 100GB 文件后跑 cleanup_expired_files，验证总量回落
6. **方向 H.3**：四个列表页选中后批量栏 UI 一致

---

## 当前进度记录

- 方向 E（AI 用例生成）：已完成 — 后端 commit 4714fea + 前端 commit 68374a5
- 方向 H（Q2 收口）：已完成 — H.1/H.2 commit a4b9d32，H.3 commit a060be4
- 方向 F（i18n）：已完成 — F.1~F.5 全部收口（2026-05-20）；视图与公共组件已无可见中文 UI 文案，剩余仅限开发注释与后端错误字符串匹配
- 方向 G（OTel/Jaeger）：未启动，将作为 Q3 收口最后一项推进
