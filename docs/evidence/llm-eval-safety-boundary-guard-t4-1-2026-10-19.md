# T4.1 大模型线上接入合规审批与安全强准入看门狗验收 (2026-10-19)

## 概述与交付物

T4.1（大模型线上接入合规审批与安全强准入看门狗服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v6.3.0 Phase 4（生产防穿透安全沙箱、合规存证与全量发布）**：
1. **服务落地实现 (`backend/app/services/llm_eval_safety_boundary_guard.py`)**：
   - **生产准入三要素铁律审查**：
     - `要素 1: 安全评测审批单 (Evaluation Ticket)`：必须提供处于 `APPROVED` 状态的审批工单，且评测综合分 >= 80.0、红蓝越狱防御率 >= 85.0%，否则阻断（`BLOCKED_NO_TICKET` / `BLOCKED_TICKET_NOT_APPROVED`）；
     - `要素 2: 准入模型白名单 (Model Whitelist)`：白名单严密涵盖 Qwen 2.5 72B、DeepSeek V3、DeepSeek R1、Llama 3.3 70B、GPT-4o 等已备案模型，未知未审核野模生产调用直接阻断（`BLOCKED_UNAUTHORIZED_MODEL`）；
     - `要素 3: 访问鉴权令牌 (Security Token)`：生产模型调用必须携带以 `LLM_SEC_TOKEN_` 开头的合法安全令牌，缺失或伪造直接阻断（`BLOCKED_INVALID_TOKEN`）；
   - **环境自适应快速旁路机制**：
     - 在非生产环境（`staging`、`test`、`dev`）下自动触发免审旁路放行（`BYPASS_NON_PRODUCTION`）；
   - **前置强断言与异常阻断**：
     - 提供 `enforce_llm_safety_admission` 看门狗方法，不符合准入条件时立即抛出 `LlmSafetyAdmissionError` 阻断一切生产调用。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_llm_eval_safety_boundary_guard.py`：**8 passed in 1.44s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
