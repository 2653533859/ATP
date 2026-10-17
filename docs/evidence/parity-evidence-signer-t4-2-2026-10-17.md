# T4.2 双端一致性 64 位 SHA-256 存证证书器服务验收 (2026-10-17)

## 概述与交付物

T4.2（双端一致性 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.3.0 Phase 4 核心合规存证里程碑**：
1. **密码学存证签名引擎 (`backend/app/services/parity_evidence_signer.py`)**：
   - **确定性 Canonical JSON 规范化**：提供字典键严格排序、剔除冗余空格的确定性序列化算法，确保跨语言、跨端序列化输出的哈希严格一致；
   - **64 字符 SHA-256 指纹**：提取跨端用例转译映射结果（源端/目标端平台、步骤序列、映射置信度）或双端功能一致性审计报告（综合评分、合规评级、发布门禁准入状态、差异缺陷统计），计算 64 位十六进制 SHA-256 摘要；
   - **HMAC-SHA256 平台防伪数字签名**：使用平台内置私钥对 64 位 SHA-256 摘要加签；
   - **双产物存证签发**：
     - `sign_case_migration_evidence()`：为跨端用例转译成果签发证书 (`cert_mig_...`)；
     - `sign_parity_report_evidence()`：为双端功能一致性审计报告签发证书 (`cert_parrep_...`)；
   - **在线验签与防篡改探针 (`verify_parity_certificate`)**：
     - 重算 SHA-256 指纹与 HMAC 签名；
     - 任何对业务字段（如综合得分、步骤映射参数）或签名本身的篡改，均毫秒级返回 `TAMPERED_INVALID` 探针拦截；
     - 未被篡改则返回 `VALID`。
2. **REST API 端点集成 (`backend/app/api/v1/cross_platform_migration_api.py`)**：
   - `POST /api/v1/migration/evidence/sign`：为跨端用例转译成果或双端一致性报告在线签发存证证书；
   - `POST /api/v1/migration/evidence/verify`：在线核验证书真实性与未篡改性；
   - `GET /api/v1/migration/evidence/{certificate_id}`：单张证书详情查询；
   - `GET /api/v1/migration/evidence/list`：证书历史列表查询。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_parity_evidence_signer.py`：5 passed（用例迁移存证合规、一致性报告存证合规、载荷篡改阻断、签名篡改阻断、证书未找到）；
   - `backend/tests/api/test_cross_platform_migration_api.py`：8 passed；
   - 总体通过率：**36 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：8/8 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
