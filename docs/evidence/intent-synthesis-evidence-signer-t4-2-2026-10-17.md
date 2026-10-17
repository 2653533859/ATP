# T4.2 AI 生成与探索证据 64 位 SHA-256 存证签名服务验收 (2026-10-17)

## 概述与交付物

T4.2（AI 生成与探索证据 64 位 SHA-256 存证签名服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.2.0 Phase 4 核心合规存证里程碑**：
1. **密码学存证签名引擎 (`backend/app/services/intent_synthesis_evidence_signer.py`)**：
   - **确定性 Canonical JSON 规范化**：提供字典键严格排序、剔除冗余空格的确定性序列化算法，确保跨语言、跨端序列化输出的哈希严格一致；
   - **64 字符 SHA-256 指纹**：提取意图工作流核心结构（节点序列、有向边连接、变量绑定总线）或多模态探索轨迹（页面状态指纹、手势流、执行步数），计算 64 位十六进制 SHA-256 摘要；
   - **HMAC-SHA256 平台防伪数字签名**：使用平台内置私钥对 64 位 SHA-256 摘要加签；
   - **双产物存证签发**：
     - `sign_intent_workflow_evidence()`：为自然语言意图驱动生成的工作流签发证书 (`cert_aiwf_...`)；
     - `sign_exploration_trajectory_evidence()`：为多模态 VLM 自主探索交互轨迹签发证书 (`cert_exptr_...`)；
   - **在线验签与防篡改探针 (`verify_evidence_certificate`)**：
     - 重算 SHA-256 指纹与 HMAC 签名；
     - 任何对业务字段（如工作流名称、节点参数）或签名本身的篡改，均毫秒级返回 `TAMPERED_INVALID` 探针拦截；
     - 未被篡改则返回 `VALID`。
2. **REST API 端点集成 (`backend/app/api/v1/intent_workflow_api.py`)**：
   - `POST /api/v1/workflow/intent/evidence/sign`：为工作流或探索轨迹在线签发存证证书；
   - `POST /api/v1/workflow/intent/evidence/verify`：在线核验证书真实性与未篡改性；
   - `GET /api/v1/workflow/intent/evidence/{certificate_id}`：单张证书详情查询；
   - `GET /api/v1/workflow/intent/evidence/list`：证书历史列表查询。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_intent_synthesis_evidence_signer.py`：5 passed（意图工作流存证合规、探索轨迹存证合规、载荷篡改阻断、签名篡改阻断、证书未找到）；
   - `backend/tests/api/test_intent_workflow_api.py`：2 passed；
   - 总体通过率：**19 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：8/8 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
