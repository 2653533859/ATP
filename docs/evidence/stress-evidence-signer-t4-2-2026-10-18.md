# T4.2 容量基线推演结论与压测验收 64 位 SHA-256 存证证书器服务验收 (2026-10-18)

## 概述与交付物

T4.2（容量基线推演结论与压测验收 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**正式达成 ATP v6.2.0 Phase 4 核心存证中枢交付**：
1. **密码学不可篡改存证证书设计 (`StressEvidenceCertificate`)**：
   - 确定性 Canonical JSON 规范化序列化（按键严格字典排序，消除空格冗余）；
   - 64 字符十六进制标准 SHA-256 数据防伪哈希摘要计算（`compute_evidence_sha256`）；
   - 权威平台 HMAC-SHA256 签名（`compute_hmac_signature`）；
2. **覆盖生产影子压测全生命周期 4 大核心关键产物签发**：
   - `CAPACITY_KNEE_POINT_DEDUCTION`：USL 容量拐点与系统饱和天花板推演报告（`sign_capacity_knee_point_report`）；
   - `STRESS_OVERLOAD_CIRCUIT_BREAK`：生产击穿毫秒级熔断断路看门狗裁决（`sign_stress_overload_guard_verdict`）；
   - `SHADOW_DATA_CLEAN_AUDIT`：影子数据防污染巡检与存储清理审计报告（`sign_shadow_data_clean_report`）；
   - `STRESS_SAFETY_ADMISSION_VERDICT`：生产全链路压测三要素强准入放行结论（`sign_stress_safety_admission_verdict`）；
3. **在线合规防篡改验签探针 (`verify_stress_certificate`)**：
   - 重算规范化 JSON、比对 SHA-256 指纹与 HMAC-SHA256 签名（利用恒定时间 `hmac.compare_digest` 严防时序攻击）；
   - 灵敏识别三态验签结论：`VALID`（合规未篡改）、`TAMPERED_INVALID`（指纹或签名被篡改）、`CERTIFICATE_NOT_FOUND`（证书未找到）。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_stress_evidence_signer.py`：7 passed（Canonical JSON 与 64 位 SHA-256 生成、USL 容量报告存证签发与验签、熔断看门狗证书签发、影子数据清理证书签发、生产强准入证书签发、Payload 与签名被篡改时的秒级检出防御、证书查询过滤与字典序列化）；
   - **通过率**：**7 passed in 0.38s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
