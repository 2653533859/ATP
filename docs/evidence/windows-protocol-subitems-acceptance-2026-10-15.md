# N2.5 分项收口协议、场景编排、AI 配置与单机性能验收（2026-10-15）

## 概述与结论

N2.5 涉及四项核心业务能力的收口验收：
1. **分项收口协议执行器（GraphQL / WebSocket / gRPC）**：
   - `graphql_executor.py`：支持 GraphQL Query 与 Mutation 执行、变量模板渲染、JSONPath 提取、GraphQL Error 处理与断言；
   - `websocket_executor.py`：支持 WebSocket 握手、帧发送与接收、文本/JSON 断言、超时防护与安全连接清理；
   - `grpc_executor.py`：基于 `grpc_tools.protoc` 动态编译 Proto 描述符，支持 Unary、Client Streaming、Server Streaming 及 Bidi Streaming 四类调用，元数据注入与响应断言；
   - `multiprotocol_executor.py`：支持在同一用例内编排 HTTP -> WebSocket -> gRPC 混合调用链，上下文变量（`{{var}}`）跨步骤无缝传递；
   - `case_dispatch.py`：通过 `_reject_empty_protocol_case` 在派发前拦截无执行步骤的协议用例并写入错误终态。
2. **多步场景编排（ApiScenarioOrchestrator）**：
   - 已于 2026-10-15 完成单步调试、响应提取、步骤依赖链（`depends_on`）以及就地增量合并保存，详见对应证据。
3. **AI 用例生成与大模型配置（AI Case Generation & LLM Configs）**：
   - `ai_case_generation.py`：支持基于 OpenAPI/PRD 需求文本智能生成正向、反向与边界用例，支持 SSE 流式推流与超时取消；
   - `ai_llm_configs.py`：支持配置主流大模型（OpenAI, Claude, Ollama, DeepSeek, Qwen），具备模型自动发现、连接健康检查、密钥加密存储。
4. **单机性能执行器（Single-machine Performance Executors）**：
   - 支持 k6、Locust、JMeter 执行器，通过 `shutil.which` 进行可执行程序探测；
   - 依赖缺失时给出明确可操作的提示，支持取消信号、进程安全回收与指标采样。

---

## 质量门禁与验证

1. **协议分项派发与拦截回归**：
   - `backend/tests/worker/test_n2_5_protocol_subitems.py`：**7 passed in 0.64s**（覆盖空用例拦截、GraphQL/WS/gRPC 派发及多协议流水线）。
2. **协议执行器单元缝测试**：
   - `backend/tests/worker/test_http_family_executors.py`：**74 passed**；
   - `backend/tests/worker/test_multiprotocol_executor.py`：**8 passed**。
3. **AI 生成与配置回归**：
   - `backend/tests/api/test_ai_case_generation_api.py`：**18 passed**；
   - `backend/tests/api/test_ai_llm_configs_api.py`：**15 passed**。
4. **单机性能引擎回归**：
   - `backend/tests/services/test_performance_executor.py`：**3 passed**；
   - `backend/tests/services/test_performance_grpc.py`：**14 passed**；
   - `backend/tests/services/test_performance_report.py`：**3 passed**。
5. **代码静态检查**：
   - `ruff check backend/tests/worker/test_n2_5_protocol_subitems.py`：**All checks passed**。
