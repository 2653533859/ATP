# Hermes 助手开发文档

> 版本：H1 / 2026-09-01
> 状态：本地实现完成，真实模型、目标部署和生产角色矩阵待复核
> 关联计划：[`development-plan-2026-08-25.md`](development-plan-2026-08-25.md) 2.4.24

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
| 多轮对话 | H2 计划中 | 当前对话仅保存在前端内存，不跨请求传递历史 |
| 工具调用 | H3 计划中 | 下一阶段先做权限保护的只读工具 |
| 结构化草稿保存 | H4 计划中 | 必须先展示 diff、来源和影响范围，再由用户确认 |

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
- 前端接口类型：`frontend/src/api/index.ts`

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
  "limit": 8
}
```

约束：

- `project_id` 必须为正整数。
- `query` 会去除首尾空格，长度为 1～2000。
- `limit` 范围为 1～20，默认 8。

### 响应

```json
{
  "project_id": 1,
  "query": "最近登录失败的主要原因是什么？",
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

## 5. AI 配置与安全边界

Hermes 使用项目的 `ai_llm_config_id`，复用系统已有的 provider、模型、Endpoint、加密 API Key、默认参数、系统提示词和每日配额配置。

安全规则：

1. 只有当前项目可见的 Knowledge、Requirement、Case 才能进入上下文；全局 Knowledge 仅允许已发布记录。
2. 来源标题、正文摘要、标签、用户问题和模型回答均执行限长或敏感信息脱敏；即使模型返回自然语言夹带 JSON，也会遮盖密码、Token、Key、Cookie 等字段。
3. 项目内容和用户问题都作为数据处理，不能覆盖 Hermes 系统规则或触发外部操作。
4. LLM 调用异常只记录配置 ID 和异常类型，不记录 API Key、请求正文或供应商响应正文。
5. 模型回答必须包含指向本次返回来源列表的有效 `[S#]` 引用；引用缺失、越界或格式无效时回退 `project_retrieval`。
6. Hermes H1 只读，不执行重试、终止、创建、修改或删除操作。

## 6. 后续开发计划

| 阶段 | 开发内容 | 验收出口 |
| --- | --- | --- |
| H1 | 项目检索、脱敏、LLM 总结、引用、规则回退 | 本地测试通过；真实模型完成成功与失败回退 |
| H2 | 会话 ID、历史摘要、项目/时间/来源筛选、上下文预算 | 切换项目不串话；历史数据脱敏；刷新后状态可解释 |
| H3 | 失败任务、运行详情、质量趋势、需求/用例关联、知识详情只读工具 | 每个工具具备权限、超时、审计和可复现实例 |
| H4 | 测试计划、用例和回归范围结构化草稿 | 编辑前后 diff 可见；用户确认后才允许保存 |
| H5 | 问题集、引用准确率、拒答率、延迟、成本、提示词版本和反馈 | 真实模型、角色矩阵、审计和目标部署证据齐全 |

推荐顺序：H2 → H3 → H4 → H5。H3 在 H2 的项目隔离和会话上下文契约完成后开始；H4 在人工确认和差异展示完成后开始。

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

## 8. 验证命令

Windows 没有 `make` 时，使用等价命令：

```powershell
# Hermes 后端定向测试
.venv\Scripts\python.exe -m pytest backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py -q

# 后端非集成全量测试
.venv\Scripts\python.exe -m pytest backend/tests -q --ignore=backend/tests/integration

# Python 质量门禁
.venv\Scripts\python.exe -m ruff check backend/app/api/v1/hermes.py backend/app/services/ai_governance.py backend/app/services/hermes.py backend/app/schemas/hermes.py backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py
.venv\Scripts\python.exe -m ruff format --check backend/app/api/v1/hermes.py backend/app/services/ai_governance.py backend/app/services/hermes.py backend/app/schemas/hermes.py backend/tests/api/test_hermes_routes.py backend/tests/services/test_ai_governance.py

# 前端测试与构建
cd frontend
npm run test
npm run build
```

H1 当前验证记录：Hermes 后端定向 `8 passed`、LLM 脱敏定向 `4 passed`，后端非集成测试 `2396 passed`，前端全量测试 `69 files / 321 tests passed`，Ruff、Python 编译、TypeScript 检查、生产构建和差异检查通过。

## 9. 发布前检查清单

- [ ] 目标环境配置启用的 AI 模型，并完成一次真实问答。
- [ ] 真实模型异常、超时、限额及无有效 `[S#]` 引用场景仍能回退规则结果。
- [ ] 管理员和 viewer 完成跨项目读写隔离验证。
- [ ] 供应商请求、回答、审计日志中没有 API Key、Token、Cookie 或敏感正文。
- [ ] H2 会话隔离完成后，再开放 H3 工具调用。
- [ ] H4 草稿保存必须经过人工确认，不允许后台静默落库。
- [ ] P4 性能环境门禁和 P9 发布收口仍需单独完成，Hermes 本地通过不等价于整体发布通过。

## 10. 变更记录

### 2026-09-01 / H1

- 新增项目证据约束的 LLM 问答链路和 `llm_grounded` 响应模式。
- 增加模型异常、未配置、超限时的规则检索回退。
- 增加共享 LLM 输出脱敏和有效来源引用门禁，避免混合文本中的敏感字段泄露或无依据回答进入 `llm_grounded`。
- 增加前端生成模式标签，修复中英文欢迎语。
- 增加后端成功/回退回归测试并同步验收文档。
