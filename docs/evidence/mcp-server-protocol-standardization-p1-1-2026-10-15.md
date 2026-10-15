# P1.1 ATP 核心工具 MCP Server 标准化暴露验收（2026-10-15）

## 概述与结论

P1.1（ATP 核心工具 MCP Server 标准化暴露）已完成标准实现与全链路实机验证：
1. **标准化 MCP JSON-RPC 2.0 引擎 (`backend/app/mcp/`)**：
   - 遵循 Model Context Protocol (MCP v1 / 2024-11-05) 协议标准；
   - 完整支持 `initialize` 协议协商（返回协议版本、capabilities 及 serverInfo `atp-mcp-server:2.5.0`）；
   - 支持 `ping` 心跳探针与 `notifications/initialized` 通知机制；
   - 支持 `tools/list` 标准工具清单发现与严格 JSON Schema 定义；
   - 支持 `tools/call` 工具执行与结果格式封装（`content: [{"type": "text", "text": "..."}]` 与 `isError` 状态标识）。
2. **开放 7 项 ATP 核心标准工具 (`app.mcp.tools`)**：
   - `atp_list_cases`：按项目、关键词、类型、状态灵活过滤用例；
   - `atp_get_case_detail`：获取包含请求头、参数、断言与提取规则的完整用例定义；
   - `atp_run_case`：异步下发用例执行，返回关联 `run_id` 与排队状态；
   - `atp_get_run_status`：实时查询运行耗时、状态、报错详情与分步执行结果；
   - `atp_diagnose_failure`：调用 AI 智能自愈诊断失败原因，输出分析建议与修复建议；
   - `atp_create_defect`：在项目中登记内部缺陷工单，支持关联失败执行记录；
   - `atp_get_project_summary`：聚合查询项目模块架构与各类型用例统计。
3. **双重运行模式支持**：
   - **FastAPI HTTP 端点** (`/api/v1/mcp/rpc`, `/api/v1/mcp/tools`, `/api/v1/mcp/status`)：供 Web 端 Agent、多会话助手或外部服务通过鉴权 HTTP 直接调用；
   - **Stdio 模式** (`python -m app.mcp`)：供 Cursor、Claude Desktop、Antigravity 等开发工具通过标准输入输出作为本地进程集成使用。
4. **实机运行与端到端测试全量通过**：
   - 8 项单测全量独立通过（`test_mcp_server.py`）；
   - 在真实 Windows 后端（`http://127.0.0.1:8001/api/v1/mcp`）实测通过认证、`initialize`、`tools/list`（7 项）与 `atp_get_project_summary` / `atp_list_cases` 真实调用。

---

## 质量门禁与验证

1. **后端单测扫描**：
   - `pytest backend/tests/api/test_mcp_server.py`：**8 passed in 0.80s**；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **代码规范与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 188 source files**。
3. **实机 HTTP 探针验证**：
   - `GET /api/v1/mcp/status`：返回 `{"server":"atp-mcp-server","version":"2.5.0","protocol_version":"2024-11-05","tools_count":7}`；
   - `POST /api/v1/mcp/rpc`：测试 `initialize`、`tools/list` 及 `atp_get_project_summary`，全部返回 200 OK 且 `isError: false`。
