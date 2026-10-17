# T4.2 覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器服务验收 (2026-10-18)

## 概述与交付物

T4.2（覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.9.0 Phase 4 核心合规存证与防篡改证据链交付**：
1. **密码学存证证书签名服务 (`backend/app/services/coverage_evidence_signer.py`)**：
   - **确定性规范化序列化 (`canonicalize_payload`)**：对产物字典进行递归 key 排序并采用紧凑分隔符（`,` 与 `:`），消除键顺序差异带来的哈希雪崩；
   - **64 字符十六进制 SHA-256 存证指纹 (`compute_evidence_sha256`)**：为统一覆盖率、Diff 增量染色、高危分支分析和发布门禁裁决结果生成不可篡改的密码学指纹；
   - **平台权威防伪签名 (`compute_hmac_signature`)**：基于 HMAC-SHA256 生成防伪数字签名；
   - **四大覆盖率全生命周期产物证书化支持 (`CoverageArtifactType`)**：
     - `UNIFIED_COVERAGE_REPORT`（多源统一覆盖率报告）；
     - `DIFF_STAINING_REPORT`（Git Diff 增量逐行染色报告）；
     - `UNCOVERED_BRANCH_RISK`（未覆盖高危分支漏洞分析）；
     - `COVERAGE_GATE_VERDICT`（准入卡点与发布阻断裁决）；
   - **在线实时防篡改验签探针 (`verify_coverage_certificate`)**：
     - 双重比对 payload 重新哈希计算与原始指纹，以及 HMAC 签名真实性，精准拦截篡改（`TAMPERED_INVALID`）。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_coverage_evidence_signer.py`：8 passed（确定性序列化与 64 位 SHA-256 计算、统一覆盖率报告签发与验签、Diff 增量染色报告证书签发、门禁裁决证书签发、payload 篡改精准拦截、伪造签名拦截、不存在证书防呆校验、证书列表查询与项目 ID 过滤）；
   - **通过率**：**8 passed in 0.34s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
