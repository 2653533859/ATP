# Hermes 助手开发文档

> 版本：H9.5 加固 / 2026-09-23
> 状态：H1～H9.5 本地开发及目标同节点双 Backend 一致性验收已完成；真实模型、角色、多节点故障域与发布门禁待独立验收
> 关联计划：[`development-plan-2026-09-08.md`](development-plan-2026-09-08.md) H9

## 1. 产品定位

Hermes 是 ATP 的项目级测试智能助手，负责把需求、知识、用例、运行任务和质量指标整理成可追溯的下一步建议。

Hermes 的默认原则：

- 以当前项目为边界，所有查询先经过项目 viewer 权限校验。
- 先读取项目证据，再生成结论；每条结论都应能回到来源。
- AI 结果只作为回答或可编辑草稿，不静默修改用例、需求、知识和测试计划。
- 模型不可用时必须保留规则检索能力，不能因为 AI 服务故障导致页面不可用。

## 2. 当前能力

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| 失败任务查看 | 已完成 | 从任务中心加载当前项目失败/错误任务 |
| 失败诊断 | 已完成 | Case 复用既有诊断链路；Android、Suite、Plan、Performance 使用统一工作台诊断 |
| 质量指标解读 | 已完成 | 汇总通过率、运行次数、覆盖率、开放缺陷和失败热点 |
| 测试计划草稿 | 已完成 | 生成可编辑草稿，不自动保存 |
| 项目证据检索 | 已完成 | 检索 Knowledge、Requirement、Case 三类来源 |
| 证据约束 LLM 问答 | H1 已完成 | 有启用项目 AI 配置且命中来源时返回 `llm_grounded` |
| 多轮对话 | H2 已完成 | 项目绑定会话 ID、来源/日期/预算控制与服务端脱敏裁剪已完成；项目/用户隔离 Session 持久化最近 40 条脱敏消息 |
| 工具调用 | H3 已完成 | 五个项目级受控只读工具具备参数白名单、权限、超时、脱敏证据和审计；会话保留快捷工具调用记录 |
| 结构化草稿与人工确认 | H4 已完成 | 展示结构化 diff、来源和影响范围；显式确认后可创建禁用的手工 draft，也可将草稿交给现有计划保存页 |
| 评测治理 | H5 + H9.2～H9.3 已完成本地切片 | `hermes-core-v2` 十题固定集、工具选择/引用相关性/答案完整度/拒答正确率、回答与规划延迟、usage/成本和人工反馈；真实模型阈值仍待环境验收 |
| 自然语言只读编排 | H6 已完成本地切片 | 根据自然语言自动选择最多 2 个固定只读工具；目标编号不明确时先追问，未知问题回退原有项目证据检索 |
| 多轮参数补全 | H7 已完成本地切片 | 将缺失目标的只读意图以受控状态保存到当前会话；同一用户、项目和 `conversation_id` 的下一轮只能补齐该固定工具，不能扩大为任意工具或写操作 |
| 挂起意图取消与恢复 | H8 已完成本地切片 | 同一受控会话可用精确取消词清除只读 pending 状态，不执行工具；之后可继续提出新的项目问题 |
| 模型辅助只读规划 | H9.1 已完成本地切片 | 规则未命中的普通问题可由项目模型生成候选计划；服务端重新校验固定白名单、严格参数 Schema 和两步上限，非法结果回退原链路 |
| 模型规划成本治理 | H9.2 已完成本地切片 | 聚合规划尝试/调用、延迟、Token、回退原因和分币种估算成本；无 usage 或价格时显示稳定不可用原因，不把零值当真实成本 |
| 可复现质量评测 | H9.3 已完成本地切片 | 十道固定题按声明入口运行，服务端确定性评分并持久化每题最新结果；治理面板展示四项准确率、样本数和覆盖率 |
| 失败任务回归建议 | H9.4 已完成本地切片 | 从失败 Case/Suite/Plan 推导活动套件，展示可编辑理由与 diff；确认后仅预填禁用计划或创建禁用手工 draft |
| 多副本状态一致性 | H9.5 已完成本地及目标双进程验收 | 持久会话使用数据库乐观版本；陈旧消息、挂起意图、取消、草稿和治理指标写入回滚并返回 `409`，治理窗口稳定排序；同节点双 Backend 并发无丢失更新 |

## 3. H1 技术链路

```text
Hermes 页面
    │
    │ POST /api/v1/hermes/query
    ▼
项目 viewer 权限校验
    │
    ▼
读取当前项目的 Knowledge / Requirement / Case
    │
    ▼
脱敏、限长、词法排序，生成来源 [S1]...[Sn]
    │
    ├─ 无 AI 配置 / 无来源 / 超限 / 调用异常 → 规则检索答案
    │
    └─ 启用 AI 配置 → 统一 LLM 客户端 → grounded answer
                                      │
                                      ▼
                               共享 LLM 脱敏器再次处理后返回前端
```

核心实现：

- API：`backend/app/api/v1/hermes.py`
- 检索与提示词：`backend/app/services/hermes.py`
- 数据契约：`backend/app/schemas/hermes.py`
- 前端页面：`frontend/src/views/intelligence/HermesAssistantView.vue`
- 前端接口类型：`frontend/src/api/hermes.ts`（`index.ts` 保留兼容导出）

### H2 多轮上下文链路

```text
选择项目 / 开始新会话
        │ 生成 conversation_id
        ▼
前端保留当前会话消息（内存）
        │ 仅发送最近历史、来源类型、更新时间范围和预算
        ▼
后端校验 → 脱敏 → 保留最近上下文 → SQL 先筛选再限量
        │
        └─ LLM prompt 标记历史为不具备指令权限的数据
```

H2 会话按当前用户与项目持久化在数据库中，最多保留最近 40 条脱敏消息；刷新项目页会恢复该用户在当前项目的最近会话，切换项目或点击“新会话”会清空当前 Session ID，下一次查询创建新的会话。首次保存 H4 草稿且尚无会话时，前端先调用 `POST /hermes/sessions` 创建空会话，再进入草稿确认流程。后端响应返回历史使用量、裁剪量和字符数，便于解释当前回答上下文。

### H3 只读工具链路

```text
已认证客户端
        │ GET /hermes/tools
        ▼
固定 allow-list（viewer / read_only）
        │ POST /hermes/tools/execute
        ▼
项目 viewer 校验 → 参数白名单 → 最长 5 秒执行
        │                         │
        │                         └─ timeout / error 只返回通用状态
        ▼
脱敏数据 + 稳定来源路径 + hermes_read_tool 审计
```

H3 当前提供 `failed_tasks`、`run_detail`、`quality_trend`、`requirement_case_links` 和 `knowledge_detail` 五个工具。工具不会触发重试、终止、创建、修改、删除或外部网络操作；工具结果带有可复现的项目路径和 `HERMES-*` 来源编号。H6 已增加受控的自然语言自动选择/编排入口，但不接受用户自定义工具名、参数或写操作。

### H4 结构化草稿链路

```text
当前项目证据（模块 / 用例 / 失败任务 / 报告 / 指标）
        │
        ▼
Hermes 生成内存草稿：名称、目标、测试点、模块、用例、回归任务
        │
        ├─ 用户逐项编辑，界面显示基线 / 当前 diff、来源和影响数量
        │
        └─ 用户显式确认
              │ 路由状态交给现有测试计划页
              ▼
       预填名称 / 目标 / 测试点，用户选择套件并点击保存
```

H4 不在确认前创建业务计划。用户可以选择“确认后保存草稿”：Hermes 先把有界草稿保存到当前用户/项目会话，二次确认后由后端创建禁用的手工测试计划草稿，不自动执行；也可以选择“确认并打开计划页”，通过一次受校验的路由状态预填现有计划页，具体套件映射和最终保存仍由用户完成。当前测试计划接口以测试套件为保存单位，因此 Hermes 展示的模块、用例和失败任务范围会带入影响摘要。

### H5 / H9.2 / H9.3 评测与治理链路

```text
固定 hermes-core-v2 评测集（10 题，只读）
        │
        ├─ 题目契约：执行入口、工具/来源、答案要点、拒答预期
        ├─ 服务端确定性评分：工具选择、引用相关性、完整度、拒答正确率
        └─ 项目级会话聚合：当前版本每题最新结果、运行/覆盖、usage/成本
                              │
                              ▼
                 Hermes 页面治理状态卡片
```

H5 先提供静态问题集和只读治理汇总；H9.2 增加模型规划 usage、延迟、回退和显式价格成本；H9.3 将固定集扩展为十题并增加确定性评分。读取评测集不会调用模型，只有按题目声明入口实际提交问题才运行原有只读链路；不写业务数据，也不把会话正文返回治理卡片。普通引用覆盖仍要求 `llm_grounded` 的 `[S#]` 全部有效；H9.3 的引用相关性进一步要求实际引用编号指向期望来源类型且检索分数大于零。延迟输出平均值和 P95，人工反馈返回 helpful/not-helpful 计数；成本只来自 H9.2 显式价格配置，缺失 usage 或价格时保持不可用原因。

### H6 自然语言只读编排链路

```text
用户自然语言问题
        │
        ▼
确定性意图识别（不接受用户自定义工具名或参数）
        │
        ├─ 最多两个固定只读工具，逐个执行并保留状态/证据
        ├─ 缺少显式编号或任务类型 → 先追问，不猜测目标
        └─ 未命中工具 → 回到 H1 项目证据检索
```

H6 的编排器只从失败任务、运行详情、质量趋势、需求—用例追踪和知识详情五个 H3 工具中选择，最多执行两步；所有调用继续复用 viewer 权限、参数白名单、最长 5 秒、脱敏结果和审计链路。成功编排会把工具状态和稳定证据写入当前用户/项目会话，前端显示“自动读取链路”；不会触发重试、终止、创建、修改、删除或外部网络操作。

### H7 多轮参数补全链路

```text
H6 返回 needs_input
        │
        ▼
当前用户 / 项目会话保存脱敏追问与 allow-list pending_orchestration
        │
        ├─ 同一 project + user + conversation_id 的普通补充输入
        │      └─ 仅补齐原来的 run_detail / requirement_case_links / knowledge_detail
        │
        ├─ 新的明确匹配意图
        │      └─ 直接执行新计划并清除旧 pending 状态
        │
        └─ 新的 needs_input 意图
               └─ 替换为新的受控 pending 状态，不执行猜测调用
```

H7 只持久化三个不完整只读意图及其最小参数：运行详情的 `task_type`/`run_id`、需求—用例追踪的目标类型，或知识详情的空参数。页面恢复最近会话时会校验并恢复已保存的 `conversation_id`，因此刷新后仍可续接该状态；恢复请求也受加载序列和项目 ID 保护，切换项目时的旧会话不会覆盖新项目。下一轮输入只会填充当前挂起工具的编号或任务类型；没有已验证的同一会话状态时，单独的数字不会触发工具。追问消息标记为 `orchestration_clarification`，不计入 H5 回答质量分母，也不能提交 helpful/not-helpful 反馈。

### H8 挂起意图取消与恢复链路

```text
同一用户 / 项目 / 会话 / conversation_id 的 pending_orchestration
        │
        ├─ 精确取消词（如“取消当前查询”或“cancel current query”）
        │      │
        │      ├─ 不调用任何工具
        │      ├─ 删除 pending_orchestration
        │      └─ 返回 cancelled，并记录不可评价的控制消息
        │
        └─ 后续新问题 → 正常编排或 H1 项目证据检索
```

H8 只识别完整输入的明确取消控制，不把“取消查询后查看失败任务”等混合问题当作取消。参数追问会直接提示规范输入“取消当前查询”。服务端仍先验证当前用户、项目、会话和 `conversation_id`；跨会话、跨项目或没有合法 pending 状态的取消词不会清除任何状态，也不会被误路由为失败任务工具。取消消息标记为 `orchestration_cancellation`，与追问一样不计入 H5 回答质量，也不能提交 helpful/not-helpful 反馈。

### H9.1 模型辅助只读规划链路

```text
H6 确定性规则未命中的普通问题
        │
        ├─ 无项目模型 / 限额 / 超时 / 异常 → 原 H1 项目证据检索
        │
        ▼
项目模型生成候选 JSON 计划
        │
        ▼
固定工具白名单 → 外层结构 → 参数 Schema → 去重 → 最多两步
        │
        ├─ 任一校验失败 → 整体拒绝并回退
        └─ 校验通过 → 复用 H3 viewer 权限、超时、脱敏和审计执行
```

H9.1 不改变 H6～H8 的优先级：确定性规则命中、同会话挂起参数补全和精确取消均不调用模型。模型只看到脱敏且限长的用户问题及公开工具 Schema，不能直接指定项目、用户、权限或任意写操作。服务端不会信任模型给出的工具名和参数，必须再次通过固定 Literal 工具名、`extra=forbid` 参数模型、正整数目标和两步上限；前端展示规划来源、策略校验结果和每步理由。

## 4. API 契约

### 请求

```http
POST /api/v1/hermes/query
Content-Type: application/json
```

```json
{
  "project_id": 1,
  "query": "最近登录失败的主要原因是什么？",
  "limit": 8,
  "conversation_id": "hermes-1-5f9c2f8c",
  "history": [
    {"role": "user", "content": "上一轮先看认证服务"},
    {"role": "assistant", "content": "已找到认证相关来源 [S1]"}
  ],
  "source_types": ["knowledge", "requirement"],
  "updated_from": "2026-08-01",
  "updated_to": "2026-08-31",
  "context_budget": 6000
}
```

约束：

- `project_id` 必须为正整数。
- `query` 会去除首尾空格，长度为 1～2000。
- `limit` 范围为 1～20，默认 8。
- `conversation_id` 只允许有限字符，默认自动生成；它用于会话关联，不作为权限凭据。
- `history` 最多 12 条，每条最多 2000 字符；只接受 `user` / `assistant`。
- `source_types` 可选 `knowledge`、`requirement`、`case`，空数组代表全部来源。
- `updated_from` / `updated_to` 为包含边界的日期范围；日期筛选在来源 limit 之前执行。
- `context_budget` 范围为 1000～12000 字符，服务端仅保留最近的有界历史。

### 响应

```json
{
  "project_id": 1,
  "query": "最近登录失败的主要原因是什么？",
  "conversation_id": "hermes-1-5f9c2f8c",
  "history_used": 2,
  "history_omitted": 0,
  "context_chars": 48,
  "context_budget": 6000,
  "source_types": ["knowledge", "requirement"],
  "updated_from": "2026-08-01",
  "updated_to": "2026-08-31",
  "mode": "llm_grounded",
  "answer": "结论：…… [S1]",
  "sources": [
    {
      "source_type": "knowledge",
      "source_id": 2,
      "project_id": 1,
      "title": "登录排查手册",
      "excerpt": "已脱敏的来源摘要",
      "source_ref": "SOP-LOGIN",
      "path": "/knowledge?project_id=1&knowledge_id=2",
      "match_terms": ["登录"],
      "match_score": 25,
      "updated_at": "2026-09-01T06:00:00Z"
    }
  ],
  "generated_at": "2026-09-01T06:00:00Z"
}
```

`mode` 定义：

- `llm_grounded`：使用项目来源生成了证据约束回答。
- `project_retrieval`：未使用模型，返回规则检索摘要。
- `no_results`：当前项目没有匹配来源。
- `history_used` / `history_omitted` / `context_chars`：本次 prompt 实际带入的历史条数、被预算裁剪的条数和字符数。

### H2 会话接口

- `GET /api/v1/hermes/sessions?project_id={id}`：只返回当前用户在当前项目的最近 50 个会话。
- `POST /api/v1/hermes/sessions`：当前项目 `viewer` 可创建空会话，标题长度最多 80；用于首次保存草稿时建立持久会话。
- `POST /api/v1/hermes/sessions/{session_id}/drafts`：当前项目 `editor` 才能保存 H4 有界草稿。
- `POST /api/v1/hermes/sessions/{session_id}/drafts/confirm`：必须显式提交 `confirmation=CONFIRM`，只创建禁用的手工计划草稿。
- `POST /api/v1/hermes/sessions/{session_id}/feedback`：只接受当前会话仍保留的助手消息，提交 `message_index` 与服务端生成的 `message_id`；两者不一致返回 `409`。重复同一评价不重复计数，改评时调整旧、新计数。旧会话中没有消息 ID 的回复不再显示评价按钮。

### H5 / H9.3 评测与治理

- `GET /api/v1/hermes/governance/evaluation-set`：返回 `hermes-core-v2` 十道固定只读题，以及每题的 `execution`、`expected_tools`、`expected_source_types`、`requires_citation`、`required_answer_terms` 和 `expected_refusal`；读取元数据不触发模型调用。
- 评测题必须原样提交到声明的 `/hermes/query` 或 `/hermes/orchestrate` 入口。服务端只对当前版本精确题目评分；查询题先绕过模型工具规划，编排题仍执行原固定只读工具和权限链路。
- `GET /api/v1/hermes/governance/summary?project_id={id}`：在当前项目 viewer 权限下返回项目级聚合，包括四项评测准确率及各自样本数、运行次数、题目覆盖、prompt 版本、引用覆盖、拒答/无结果率、延迟、人工反馈和 H9.2 成本；不返回会话正文。
- 评测结果保存到 Session `metrics.evaluation_results`：累计 `run_count`，同一 Session 的同一道题只保留当前版本最新评分。正文裁剪不删除结果，重复题也不会重复增加质量指标分母；新版本与旧版本不混算。
- 当前固定集版本为 `2026-09-23.1`。`run-detail` 题显式指定 `case` 类型；正向题缺少可用项目来源或工具证据时不计入覆盖，规则检索回退不再获得模型引用相关性通过。旧版本结果不混入当前分母。

### H6/H7/H8 自然语言编排

- `POST /api/v1/hermes/orchestrate`：在当前项目 viewer 权限下，根据自然语言选择最多两个固定只读工具；返回计划、每步状态、脱敏数据、稳定证据和会话消息索引。
- 编排器未命中工具时返回 `no_match`，由前端继续调用 `/hermes/query`；缺少运行/需求/用例/知识显式目标时返回 `needs_input`，不执行猜测调用。
- H7 对 `needs_input` 持久化受控的 `pending_orchestration`，并返回 `session_id`；只有同一用户、项目、会话和 `conversation_id` 的后续输入可以补齐该固定工具。明确的新意图会取代旧状态；追问消息不能通过反馈接口评价。
- H8 对已验证 pending 状态的完整取消控制返回 `cancelled`；服务端清除状态但不执行工具，前端显示确认后不回退检索。取消控制不能通过反馈接口评价，也不计入治理口径。

### H3 工具目录与执行

```http
GET /api/v1/hermes/tools
```

目录只返回固定的只读工具、`viewer` 最低角色、最长 5000 ms 和每个工具的 JSON 参数模式。执行请求示例：

```http
POST /api/v1/hermes/tools/execute
Content-Type: application/json
```

```json
{
  "project_id": 1,
  "conversation_id": "hermes-1-session",
  "tool": "failed_tasks",
  "arguments": {"limit": 10, "task_type": "case"},
  "timeout_ms": 3000
}
```

响应统一包含 `status`、`duration_ms`、有界 `data`、`evidence` 和 `generated_at`。`status` 可能为 `ok`、`empty`、`not_found`、`timeout` 或 `error`；参数不符合工具专属白名单时返回 422，项目权限不足时返回 403。审计只记录工具名、项目、状态和耗时，不记录原始 arguments、会话正文或工具返回正文。

旧 `/hermes/sessions/{session_id}/tools/{tool_name}` 快捷接口已移除；页面中的快捷回答继续使用已加载的项目工作台数据。需要后端工具证据和审计时，调用本节固定的 H3 接口或自然语言编排入口。

## 5. AI 配置与安全边界

Hermes 使用项目的 `ai_llm_config_id`，复用系统已有的 provider、模型、Endpoint、加密 API Key、默认参数、系统提示词和每日配额配置。

安全规则：

1. 只有当前项目可见的 Knowledge、Requirement、Case 才能进入上下文；全局 Knowledge 仅允许已发布记录。
2. 来源标题、正文摘要、标签、用户问题和模型回答均执行限长或敏感信息脱敏；即使模型返回自然语言夹带 JSON，也会遮盖密码、Token、Key、Cookie 等字段。
3. 项目内容和用户问题都作为数据处理，不能覆盖 Hermes 系统规则或触发外部操作。
4. LLM 调用异常只记录配置 ID 和异常类型，不记录 API Key、请求正文或供应商响应正文。
5. 模型回答必须包含指向本次返回来源列表的有效 `[S#]` 引用；引用缺失、越界或格式无效时回退 `project_retrieval`。
6. Hermes H1 只读，不执行重试、终止、创建、修改或删除操作。
7. H2 的会话历史是客户端提供的不可信数据，只作为上下文参考，不获得系统指令权限，也不会成为来源证据；历史同样执行脱敏和长度预算。
8. H3 只允许固定的只读工具名和工具参数；执行前校验当前项目 viewer 权限，服务端强制最长 5 秒，并将成功、空结果、未找到、超时和异常写入脱敏审计摘要。
9. H4 草稿只能通过当前用户/项目会话保存；首次保存可先创建空会话，但草稿和业务计划仍要求当前项目 editor 权限。确认前不创建业务计划，二次确认后只创建禁用的手工 draft，或打开现有计划页供用户继续选择套件。两条路径都不自动执行，项目和编辑权限由服务端强制校验。
10. H6 只能从固定意图规则生成最多两个只读工具调用；用户自定义工具名、参数和目标不能直接透传，缺少显式编号时先追问，未命中则回退 H1 检索。
11. H7 只接受服务端 allow-list 反序列化后的挂起状态，并要求当前用户、项目、会话与 `conversation_id` 一致；下一轮只能补齐该单一只读工具。控制性追问不能计入 H5 回答质量或获得人工回答反馈。
12. H8 仅在 H7 已验证的同一会话 pending 状态下处理精确取消词；取消只移除该状态并写入脱敏控制消息，绝不执行工具、扩大意图或写入业务数据。取消控制同样不计入 H5 质量或人工反馈。
13. H9.1 模型计划只能作为候选输入；未知工具、额外参数、缺失目标、重复工具、超过两步或非法外层字段在执行前整体拒绝。取消和挂起补全不经过模型，模型不可用时保持 H6～H8 与 H1 回退可用。
14. H9.2 只读取供应商实际返回的 usage；成本只按项目 AI 配置中的显式价格估算，不内置供应商价格。指标写入不得改变 `conversation_id` 或 pending 控制状态，未知/损坏的历史指标按有界零值处理。
15. H9.3 评测结果只能由服务端对当前固定集的精确题目生成；普通问答、旧版本、未知题号和题目不适用的评分字段不得进入分母。引用相关性要求模型实际引用的 `[S#]` 指向期望来源类型且 `match_score > 0`，不能用“列表里另有相关来源”替代。
16. H9.4 套件建议只从当前项目失败 Case/Suite/Plan 与现有活动套件关系推导，最多 8 项并允许取消；计划页交接默认禁用，二次确认落库还必须由服务端复核当前项目和活动状态，禁止自动执行。
17. H9.5 会话状态更新必须携带数据库版本条件；陈旧副本不得覆盖较新消息、挂起意图、取消、草稿或治理指标。冲突必须回滚整个事务并返回 `409`，前端不得自动改走其他查询、重复写入或把草稿标记为已确认。

## 6. 后续开发计划

| 阶段 | 开发内容 | 验收出口 |
| --- | --- | --- |
| H1 | 项目检索、脱敏、LLM 总结、引用、规则回退 | 本地测试通过；真实模型完成成功与失败回退 |
| H2 | 用户/项目隔离会话、历史摘要、项目/时间/来源筛选、上下文预算 | 本地测试通过；切换项目/新会话不串话；历史脱敏并可观察裁剪统计 |
| H3 | 失败任务、运行详情、质量趋势、需求/用例关联、知识详情只读工具 | 本地工具 API 具备权限、超时、审计、脱敏和可复现实例；自然语言自动编排另行验收 |
| H4 | 测试计划、用例和回归范围结构化草稿 | 编辑前后 diff、来源和影响范围可见；确认后交给现有计划页，用户仍需选择套件并点击保存 |
| H5 | 问题集、引用准确率、拒答率、延迟、成本、提示词版本和反馈 | 真实模型、角色矩阵、审计和目标部署证据齐全 |
| H6 | 自然语言自动选择和编排固定只读工具 | 最多两步、目标明确、权限/超时/脱敏/审计保持有效；未知问题回退证据检索 |
| H7 | 多轮参数补全 | 仅恢复同一用户/项目/会话/`conversation_id` 的受控只读意图；单独数字不越权触发工具，明确新意图可替代旧状态 |
| H8 | 挂起意图取消与恢复 | 仅在同一受控 pending 状态下精确取消；不执行工具，清除状态后能继续处理新问题，控制消息不污染治理或反馈 |
| H9.1 | 模型辅助只读规划 | 只在规则未命中的普通问题上生成候选计划；服务端白名单、Schema、权限和两步上限保持强制，失败时确定性回退，界面展示规划来源和理由 |
| H9.2 | 模型规划 usage、调用、延迟、成本和回退治理 | 常见供应商 usage 可归一；价格必须显式配置；不可用原因、回退明细和分币种成本可观察 |
| H9.3 | 固定集扩展与确定性质量评分 | 工具选择、引用相关性、答案完整度和拒答正确率可重复；版本、分母和覆盖率清晰 |
| H9.4 | 失败任务回归与套件映射建议 | 建议有来源、可编辑且有界；确认后只产生禁用草稿，不自动执行 |
| H9.5 | 多副本一致性 | 数据库版本冲突不静默覆盖且整个事务回滚；前端安全提示，治理窗口稳定；目标环境多副本冒烟独立验收 |

推荐顺序：H2 → H3 → H4 → H5 → H6 → H7 → H8 → H9.1 → H9.2～H9.5。H9 不开放未经人工确认的写工具。

## 7. 本地开发与联调

当前开发拓扑：

```text
Windows 前端 http://127.0.0.1:4173
        │
        └─ SSH 本地转发 127.0.0.1:39083
              │
              └─ Linux 后端 192.168.3.196:29080
```

启动前端：

```powershell
cd E:\csh\MyProject\ATP\frontend
$env:VITE_BACKEND_ORIGIN = 'http://127.0.0.1:39083'
npm run dev
```

访问：

```text
http://127.0.0.1:4173/hermes?project_id=1
```

若要观察 `llm_grounded`，需要在配置中心为项目绑定一个已启用的 AI 配置，并确保当前查询能命中项目来源；否则预期结果是 `project_retrieval` 或 `no_results`。

H9.2 不内置模型价格。需要成本估算时，在项目绑定模型的 `default_params` 中显式配置：

```json
{
  "usage_pricing": {
    "hermes_tool_planning": {
      "input_per_million": 0.5,
      "output_per_million": 1.5,
      "currency": "USD"
    }
  }
}
```

单价单位为“每百万 Token”，币种使用三位字母。供应商未返回 usage 时显示 `usage_unavailable`；有 usage 但没有价格时显示 `pricing_not_configured`；部分调用未计价时显示 `partially_unpriced`。这些状态不会伪造为零成本。

运行当前十题评测前，先在受控隔离项目核实：项目绑定已启用模型；同一项目可访问 `case` 运行编号 1、需求编号 1 和知识编号 1；并有匹配“登录”的知识或需求来源。编号是当前固定题目的精确输入，不应在已有业务项目中强行改写主键来凑齐。缺少任一资产时，记录该题未覆盖，不把 `not_found`、追问或空数据算作真实模型通过。若需在任意项目使用其他编号，应另行设计项目绑定的评测题模板和服务端评分契约。

十题中六道编排题先命中确定性路由，两道无证据拒答题不会请求回答模型；只有两道有项目来源的查询题可能调用回答模型。固定集的工具选择率因此只验证规则路由与工具链，不能代表模型规划准确率；模型规划需另用未命中确定性规则的挑战题验收，并核对 `planner.source=model`、`planner.validation=accepted`、`model_calls=1`、实际工具步骤和证据。回答模型也要核对 `mode=llm_grounded` 和有效来源引用，规则回退不能记成模型成功。治理摘要聚合项目最近 500 个会话，同题在不同会话可重复进入分母；正式验收应保存单次执行的逐题状态、响应模式和样本数，不单凭治理面板四个比率下结论。已发布的全局知识可进入项目检索，隔离项目还需要检查语料边界。

2026-09-23 对发布环境的只读核对显示：启用模型配置 1 个，绑定模型的项目 0 个，固定题所需的运行/需求/知识编号 1 均不存在。因此该环境目前不具备十题真实模型验收前置条件；未调用模型或改动项目配置。脱敏记录见 [`evidence/hermes-evaluation-readiness-2026-09-23.json`](evidence/hermes-evaluation-readiness-2026-09-23.json)。

显式项目预检与逐题执行方式见 [`hermes-evaluation-acceptance.md`](hermes-evaluation-acceptance.md)。执行器的默认模式只读；实际提问必须显式传入 `--execute`。

同日复核单节点 K3s 的六个 ATP Pod 均处于 Ready；Backend 镜像仍为 `registry.local/atp/backend:bdb84286`，早于本轮已推送代码。当前真实环境结果不能当作新评分契约的验证证据，部署后需重新核对镜像提交与 API 题集版本。

生成测试计划时，Hermes 先在当前页编辑结构化草稿；“确认并打开计划页”会打开 `plans?project_id=<id>` 的预填保存页，刷新或关闭页面不会恢复该路径的未保存草稿；“确认后保存草稿”则在二次确认后创建禁用手工计划，不会自动执行。

## 8. 验证命令

Windows 没有 `make` 时，使用等价命令：

```powershell
# Hermes 后端定向测试
.venv\Scripts\python.exe -m pytest backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py backend/tests/services/test_hermes.py -q

# Hermes H3 工具定向测试
.venv\Scripts\python.exe -m pytest backend/tests/api/test_hermes_tools.py backend/tests/services/test_hermes_read_tools.py -q

# 后端非集成全量测试
.venv\Scripts\python.exe -m pytest backend/tests -q --ignore=backend/tests/integration

# Python 质量门禁
.venv\Scripts\python.exe -m ruff check backend/app/api/v1/hermes.py backend/app/services/ai_governance.py backend/app/services/hermes.py backend/app/services/hermes_orchestration.py backend/app/schemas/hermes.py backend/app/services/hermes_tools.py backend/app/schemas/hermes_tools.py backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py backend/tests/services/test_hermes.py backend/tests/api/test_hermes_tools.py backend/tests/services/test_hermes_read_tools.py
.venv\Scripts\python.exe -m ruff format --check backend/app/api/v1/hermes.py backend/app/services/ai_governance.py backend/app/services/hermes.py backend/app/services/hermes_orchestration.py backend/app/schemas/hermes.py backend/app/services/hermes_tools.py backend/app/schemas/hermes_tools.py backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py backend/tests/services/test_hermes.py backend/tests/api/test_hermes_tools.py backend/tests/services/test_hermes_read_tools.py
.venv\Scripts\python.exe -m compileall -q backend/app backend/tests

# 前端测试与构建
cd frontend
npm run test
npm run build
```

H4 定向回归：

```powershell
cd frontend
npm run test -- --run src/views/intelligence/HermesAssistantView.spec.ts src/views/plan/PlanList.spec.ts
npm run type-check
```

H3 当前验证记录：H3 工具 API/服务定向 `11 passed`，H1～H3 Hermes 组合回归 `27 passed`，后端非集成全量 `2411 passed`，前端全量 `69 files / 325 tests passed`；Ruff、格式检查、mypy、Python 编译、TypeScript 检查、生产构建和 `git diff --check` 通过。后端全量退出码为 0，Windows pytest 临时目录清理在进程退出时产生非致命 `WinError 5`，不影响测试结果。

H4 当前验证记录：Hermes 与计划页定向回归 `20 passed`，后端非集成全量 `2429 passed`，前端全量 `69 files / 327 tests passed`；TypeScript 检查、生产构建和 `git diff --check` 通过。本地结果只证明结构化草稿、路由交接、首次会话创建和人工确认边界，未替代目标环境角色、模型和发布门禁。

H5 当前验证记录：治理与评测集定向后端 `18 passed`，Hermes 前端定向 `12 passed`；后端非集成全量 `2432 passed`，前端全量 `69 files / 327 tests passed`，TypeScript、mypy、生产构建、Python 编译、Ruff、格式检查、密钥扫描和提交钩子均通过。H5 只证明固定评测输入、项目级指标聚合、有效引用口径、成本不可用声明和异步项目隔离；真实模型效果阈值、token usage/成本、角色矩阵、审计和目标部署仍待环境验收。

H6 当前验证记录：后端 Hermes 编排/服务定向 `22 passed`，前端 Hermes 定向 `14 passed`；后端非集成全量 `2436 passed`，前端全量 `69 files / 329 tests passed`，mypy、Ruff、TypeScript、生产构建、Python 编译、差异检查、密钥扫描和提交钩子均通过。后端全量退出码为 0，Windows pytest 临时目录清理在进程退出时产生非致命 `WinError 5`。H6 只证明固定规则下的最多两步只读编排、显式目标保护、会话证据记录和前端链路展示；自然语言覆盖率、真实模型工具选择、完整角色矩阵和目标部署仍待环境验收。

H7 当前验证记录：Hermes 编排/服务定向 `25 passed`（受影响文件独立 `18 passed`、`7 passed`），前端 Hermes 定向 `17 passed`；后端非集成全量 `2439 passed`，前端全量 `69 files / 332 tests passed`，TypeScript、mypy、生产构建、Python 编译、Ruff、格式/差异检查、密钥扫描及提交钩子均通过。后端全量退出码为 0，Windows pytest 临时目录清理在进程退出时产生非致命 `WinError 5`。H7 只证明受控会话内的参数补全、跨 `conversation_id` 隔离、明确意图替代、项目切换的迟到会话隔离和治理口径保护；真实模型工具选择、角色矩阵、审计完整性和目标部署仍待环境验收。

H8 当前验证记录：Hermes 编排/服务定向 `27 passed`，前端 Hermes 定向 `19 passed`；后端非集成全量 `2441 passed`，前端全量 `69 files / 334 tests passed`，TypeScript、mypy、生产构建、Python 编译、Ruff、格式/差异检查、密钥扫描及提交钩子均通过。H8 只证明确定性精确取消、跨 `conversation_id` 不清除状态、取消不执行工具、会话恢复和治理/反馈隔离；真实模型工具选择、角色矩阵、审计完整性和目标部署仍待环境验收。

H9.1 当前验证记录：模型规划与 Hermes 路由定向后端 `31 passed`，Hermes 前端定向 `24 passed`；后端非集成全量 `2592 passed / 1 skipped`，前端全量 `76 files / 363 tests passed`，TypeScript、mypy 和生产构建通过。覆盖提示词脱敏、模型语义计划、参数默认值规范化、额外字段/无效编号/重复及超步数拒绝、确定性优先、失败回退、会话持久化和前端解释展示；真实模型质量阈值、usage/成本、角色矩阵和目标部署仍待后续切片及环境验收。

H9.2 当前验证记录：模型规划与治理定向后端 `32 passed`，Hermes 前端定向 `26 passed`，受影响后端文件独立 `21 passed` 与 `11 passed`；后端非集成全量 `2593 passed / 1 skipped`，前端全量 `76 files / 363 tests passed`，TypeScript、生产构建、Ruff、格式和 mypy 通过。覆盖三类 usage 结构、非法 usage 拒绝、显式价格估算、无 usage/无价格原因码、分币种聚合、回退明细，以及 no-match 复用 Session 且不破坏 H7 pending 状态。真实供应商返回结构、账单单价准确性、角色矩阵、审计和目标部署仍待环境验收。

H9.3 当前验证记录：评测、治理与路由定向后端 `36 passed`，Hermes 前端定向 `26 passed`，受影响后端文件独立 `13 passed` 与 `23 passed`；后端非集成全量 `2597 passed / 1 skipped`，前端全量 `76 files / 363 tests passed`，TypeScript、mypy 和生产构建通过。覆盖固定题精确匹配、查询/编排入口、模型规划旁路、工具集合评分、实际 `[S#]` 相关来源绑定、答案要点、正反拒答、当前版本过滤、正文裁剪独立持久化、重复题最新值和页面自动刷新。该结果证明评测机制可复现，不证明任一真实项目或模型已达到阈值；运行检索题前需确保项目具备相应登录知识/需求，运行目标详情题前需准备可访问的运行、需求和知识编号 1，或在后续版本固定专用 fixture。

## 9. 发布前检查清单

- [ ] 目标环境配置启用的 AI 模型，并完成一次真实问答。
- [ ] 在隔离项目核实当前十题所需资产归属，运行 `2026-09-23.1` 版本评测及独立模型规划挑战题，并记录真实模型质量阈值、样本数与失败题。
- [ ] 真实模型异常、超时、限额及无有效 `[S#]` 引用场景仍能回退规则结果。
- [ ] 管理员和 viewer 完成跨项目读写隔离验证。
- [ ] 供应商请求、回答、审计日志中没有 API Key、Token、Cookie 或敏感正文。
- [x] H2 会话隔离、历史脱敏和筛选预算已完成本地切片。
- [x] H3 五个只读工具已完成项目权限、参数白名单、最长超时、脱敏结果、稳定证据和审计本地切片；H6 已补齐受控自然语言自动编排。
- [x] H4 本地草稿保存链路经过人工确认：确认前不能进入计划页；确认后可预填现有计划页，或在二次确认后创建禁用手工 draft；两条路径均不自动执行。
- [x] H5 本地评测与治理切片：固定 5 题评测集、有效引用覆盖率、拒答/无结果率、平均/P95 延迟、prompt 版本、反馈和成本不可用状态已具备后端 API 与 Hermes 页面展示。
- [x] H6 本地自然语言只读编排切片：最多两步固定工具选择、显式编号/任务类型保护、未命中回退 H1 检索、会话链路记录和前端状态展示已完成。
- [x] H7 本地多轮参数补全切片：受控 pending 状态仅限同一用户/项目/会话/`conversation_id`；明确新意图可覆盖旧状态，追问不计入回答质量且不可评价。
- [x] H8 本地挂起意图取消切片：精确取消词仅清除同一受控会话的 pending 状态，不执行工具；取消后可继续新问题，取消消息不计入回答质量且不可评价。
- [x] H9.1 本地模型辅助规划切片：规则未命中的普通问题才调用模型；候选计划必须通过固定工具白名单、严格参数 Schema、去重和两步上限，失败回退且界面展示规划来源与理由。
- [x] H9.2 本地 usage/成本治理切片：模型规划调用、延迟、Token、回退原因和显式配置的分币种估算成本已进入会话指标、治理 API 与页面；缺失数据保持不可用状态。
- [x] H9.3 本地质量评测切片：十道固定题、四项确定性指标、当前版本分母、每题最新结果和治理面板展示已完成。
- [x] H9.4 失败任务回归建议：Case/Suite/Plan 到活动套件的有界映射、可编辑 diff、禁用计划交接与服务端项目复核已完成。
- [x] H9.5 一致性验收：本地双 Session 与目标 K3s 同节点双 Backend 均验证会话乐观版本、陈旧写入事务回滚、稳定 `409`、前端冲突恢复和治理稳定排序；多节点故障域仍属于 P4/P9 独立门禁。
- [ ] P4 性能环境门禁和 P9 发布收口仍需单独完成，Hermes 本地通过不等价于整体发布通过。

## 10. 变更记录

### 2026-09-23 / 评测验收准备

- 评测集版本升为 `2026-09-23.1`：正向检索题缺少相关来源、正向编排题的工具未返回 `ok` 或缺少证据时不产生评分；规则检索回退不能拿到模型引用相关性通过。两道正向检索题的预期模式明确为 `llm_grounded`。
- 新增显式项目的脱敏验收执行器。默认只读预检，显式 `--execute` 才提交固定十题与一道不会命中确定性规则的模型规划挑战题；固定题和模型规划分别报告，`blocked` 不冒充通过。脚本不建立夹具或更改业务资产，执行模式留下 Hermes 会话和审计供人工复核。
- 发布机六个 ATP Pod 均 Ready，但 Backend 仍使用旧镜像 `bdb84286`。当前生产式数据缺少项目模型绑定与编号 1 资产，因此未运行真实模型验收，也未改变目标环境。

### 2026-09-23 / H9 加固

- 对可评价回复增加服务端生成的稳定 `message_id`。反馈请求同时验证 ID 与当前位置，避免最近 40 条历史裁剪后旧下标误评另一条消息；同评分重复提交保持幂等，改评按差量更新计数。旧无 ID 消息不再展示反馈按钮，失效下标返回 `409` 并提示刷新。既往已累计的重复反馈因历史消息可能已裁剪，无法可靠重建，本次不回写历史统计。
- 移除仍被页面调用的旧快捷工具接口和宽泛参数会话写入；后端受控工具入口统一为 H3 `/hermes/tools/execute`，快捷回答继续读取工作台已加载的数据。
- `run-detail` 固定题补 `case` 任务类型，评测集版本升至 `2026-09-23`，旧版本结果不混入新版本分母。增加所有编排题命中声明工具的回归契约。
- 独立审查发现并修复旧下标落到用户或控制消息时错误返回 `422` 的边界；所有目标错位统一返回 `409`。Hermes 后端定向 `57 passed`、后端非集成全量 `2629 passed / 2 skipped`，前端全量 `76 files / 369 tests passed`，TypeScript、生产构建、Ruff、格式和 mypy 通过。发布环境只读核对发现项目模型绑定和固定资产均缺失，真实模型、管理员/Viewer 角色矩阵及供应商审计仍待单独验收。

### 2026-09-14 / H9.5

- 为 `hermes_sessions` 增加 `state_version` 迁移和 ORM 乐观版本检查；两个独立数据库 Session 并发更新时，后提交的陈旧状态抛出冲突并回滚，避免消息、pending、取消、草稿和指标静默丢失。
- 会话状态写接口统一把陈旧版本转换为稳定 `409`；草稿确认与计划创建处于同一事务，冲突时不会留下重复计划。会话列表和治理最近 500 会话窗口增加 ID 次级排序。
- 前端查询、编排、评价和草稿确认均识别冲突；编排不回退为另一条 H1 查询，草稿不自动重试或误标已确认。
- 定向后端 `52 passed`、前端 `2 files / 26 tests passed`；后端非集成全量 `2602 passed / 1 skipped`、前端全量 `76 files / 367 tests passed`，TypeScript、mypy、Ruff、格式和生产构建通过。该结果是本地双 Session 并发模拟，不代替目标环境真实多副本验收。
- 目标 K3s 实测发现并修复原 `0068` 时间戳默认值缺失导致的 Session 创建 500，迁移 `0074` 已增加回归；revision 46 的两个 Backend 进程完成 40 次并发反馈，8 次成功、32 次 `409`、版本 2→10、丢失更新 0。临时资源归零后 6/6 正式 Pod Ready、零重启，证据见 [`evidence/hermes-multi-replica-2026-09-14.json`](evidence/hermes-multi-replica-2026-09-14.json)。

### 2026-09-14 / H9.4

- 失败 Case 反查包含该用例的活动套件，失败 Suite 直接映射自身，失败 Plan 展开其套件；候选按命中失败数排序、去重并限制 8 项。
- 草稿展示套件理由、来源、影响数和编辑前后 diff，失败用例优先进入用例草稿；确认交接只预填计划页并默认关闭启用开关。
- 会话草稿二次确认时，后端重新校验所选套件属于当前项目且为活动状态，只创建 `manual + draft + disabled` 计划并保留有界回归元数据，不触发运行。
- 定向后端 `25 passed`、前端 `3 files / 33 tests passed`；后端非集成全量使用项目内临时目录重跑为 `2599 passed / 1 skipped`，前端全量 `76 files / 363 tests passed`，TypeScript、mypy、Ruff、格式和生产构建通过。

### 2026-09-14 / H9.3

- 将评测集升级为 `hermes-core-v2` 十题，覆盖五个只读工具、双工具计划、项目证据、无依据拒答和提示注入拒答，并公开每题的确定性评分条件。
- 仅对当前版本精确题目评分；工具集合、实际相关引用编号、答案要点和拒答模式分别形成四项指标，普通会话和不适用字段不进入分母。
- 评测运行次数与每题最新结果持久化到 Session 指标，不受最近 40 条消息裁剪影响；治理 API/页面显示准确率、样本数及题目覆盖并在评测后刷新。

### 2026-09-14 / H9.2

- 归一 OpenAI、Claude 和 Ollama 常见 Token usage，记录模型规划次数与耗时；无 usage 时保留明确不可用原因。
- 仅按项目模型 `usage_pricing.hermes_tool_planning` 显式单价估算成本，按币种聚合并区分无调用、无 usage、无价格和部分未计价。
- 治理 API 与 Hermes 面板展示调用、Token、平均延迟、回退次数/原因和估算成本；no-match 指标复用同一 Session，但不修改会话控制状态。

### 2026-09-14 / H9.1

- 新增版本化模型工具规划提示词，只向项目模型提供脱敏问题和五个公开只读工具 Schema；确定性规则、挂起补全和取消继续优先且不额外调用模型。
- 服务端整体校验候选 JSON 的固定工具名、外层字段、参数 Schema、正整数目标、重复工具和两步上限；任何模型异常或策略拒绝都返回通用回退原因并继续原链路。
- API 与会话记录规划来源、校验状态、模型名和提示词版本；前端自动读取链路展示模型/规则来源、校验结果和每步选择理由。

### 2026-09-04 / H8

- 对同一用户、项目、会话和 `conversation_id` 的受控 pending 状态增加精确取消控制，返回 `cancelled` 并清除状态；取消不执行任何工具。
- 防止未绑定 pending 的取消词误触发失败任务读取；跨会话取消保留原状态，普通新问题在取消后恢复原有编排/H1 检索路径。
- 将取消控制排除在会话恢复的评价入口、H5 治理统计和后端反馈接口之外；补齐服务、路由和前端回归。

### 2026-09-01 / H4

- 将测试计划草稿扩展为模块、用例和失败任务回归范围的结构化编辑器，增加影响数量、证据来源和基线/当前 diff。
- 增加确认状态和同步路由交接：确认前不能打开计划保存页，确认后预填现有计划表单，明确套件映射和最终保存仍由用户完成；保留远端会话草稿的二次确认创建禁用手工 draft 能力。
- 计划页校验路由状态的项目 ID，只导入有界文本；保存页路径不调用创建 API，首次保存由会话接口建立空会话，二次确认后创建禁用计划；补充 Hermes/计划页交接回归和中英文提示。
- 修复 Windows 下脚本依赖 Python 路径回归测试写死 POSIX 路径的问题，改为按平台路径断言。

### 2026-09-01 / H5

- 增加版本化的 `hermes-core-v1` 五题静态评测集和只读元数据接口；评测题覆盖证据追溯、失败任务分诊、质量风险、无证据拒答和提示注入边界，不自动触发模型调用。
- 将治理汇总抽成可测试的聚合服务，严格区分 `llm_grounded` 有效 `[S#]` 引用、规则检索来源和 `no_results`，增加拒答率、平均/P95 延迟、prompt 版本、反馈计数及成本不可用状态。
- Hermes 页面新增紧凑治理状态卡片，展示评测集版本、引用覆盖、拒答/无结果、延迟、人工反馈和活动量；项目切换时丢弃过期治理响应，避免跨项目污染。

### 2026-09-03 / H7

- 在 `needs_input` 时持久化最小 allow-list 挂起只读意图，前端保留返回的会话 ID，用户可在下一轮直接补充运行、需求/用例或知识编号。
- 恢复路径强制当前用户、项目、会话和 `conversation_id` 一致；明确的新意图会替代旧状态，单独数字在不存在受控 pending 状态时不执行工具。
- 独立审查补充治理口径保护：参数追问不计入 H5 回答统计，也不会显示或接受人工 helpful/not-helpful 反馈；补齐会话恢复、跨会话隔离和新意图替代回归。

### 2026-09-03 / H6

- 增加 `/hermes/orchestrate` 自然语言只读编排入口，使用确定性规则从五个 H3 工具中选择最多两个工具，并复用项目 viewer 权限、参数校验、5 秒超时、脱敏和审计。
- 对运行详情、需求/用例追踪和知识详情要求显式编号；缺少目标或任务类型时返回 `needs_input`，未知问题返回 `no_match` 并由前端回退 H1 项目证据检索。
- Hermes 对话展示自动读取链路、每步工具状态和证据来源，刷新会话时恢复链路标记；补充组合问题、目标缺失、会话持久化和前端竞态回归。

### 2026-09-01 / H3

- 增加 Hermes 只读工具目录和执行接口，固定提供失败任务、运行详情、质量趋势、需求—用例关联和知识详情五个工具。
- 所有工具要求当前项目 viewer 权限，参数按工具专属模型校验，最长执行 5 秒，异常和超时返回通用状态。
- 工具结果统一脱敏并携带稳定项目路径和 `HERMES-*` 证据编号；执行审计只保留工具名、项目、状态和耗时。
- 增加工具目录、参数白名单、跨项目隔离、错误脱敏、证据和超时回归；补齐前端 API 类型契约。

### 2026-09-01 / H2

- 增加项目/用户绑定的持久会话；刷新恢复最近会话，切换项目或点击“新会话”会清空旧 Session ID，首次保存草稿可按需创建空会话。
- `POST /hermes/query` 支持有界历史、来源类型、来源更新时间范围和上下文字符预算；后端先做 SQL 时间筛选，再执行来源数量限制。
- 历史按最近消息优先裁剪，统一执行脱敏，并在 prompt 中明确标记为不具备指令权限的数据；响应返回使用量和裁剪量。
- 增加后端筛选/预算/提示词回归及前端筛选、会话重置、异步旧响应丢弃回归。

### 2026-09-01 / H1

- 新增项目证据约束的 LLM 问答链路和 `llm_grounded` 响应模式。
- 增加模型异常、未配置、超限时的规则检索回退。
- 增加共享 LLM 输出脱敏和有效来源引用门禁，避免混合文本中的敏感字段泄露或无依据回答进入 `llm_grounded`。
- 增加前端生成模式标签，修复中英文欢迎语。
- 增加后端成功/回退回归测试并同步验收文档。
