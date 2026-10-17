# T4.2 流量回放与 Diff 报告 64 位 SHA-256 存证证书器服务验收 (2026-10-17)

## 概述与交付物

T4.2（流量回放与 Diff 报告 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.6.0 Phase 4 第二个核心密码学防伪合规存证里程碑**：
1. **密码学存证证书签名引擎 (`backend/app/services/replay_evidence_signer.py`)**：
   - **确定性规范化 JSON 序列化 (`canonicalize_payload`)**：对流量记录与 Diff 报告产物键名严格字典排序并剥离空格；
   - **64 位 SHA-256 证据指纹生成 (`compute_evidence_sha256`)**：为回放产物生成不可伪造的哈希摘要；
   - **平台权威 HMAC-SHA256 数字签名 (`sign_payload_hmac`)**：使用平台根密钥签发防伪签名，防范离线篡改；
   - **三类产物证书签发**：
     - `sign_traffic_record_certificate`：生产镜像流量录制记录（`TRAFFIC_RECORD`）；
     - `sign_diff_report_certificate`：双端响应结构比对报告（`DIFF_REPORT`）；
     - `sign_replay_evaluation_certificate`：回放一致性综合裁决结果（`REPLAY_EVALUATION`）；
   - **在线探针验签与防篡改裁决 (`verify_replay_certificate`)**：重算哈希并比对 HMAC，输出 `VALID`（通过）、`TAMPERED_INVALID`（篡改告警）或 `CERTIFICATE_NOT_FOUND`。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_replay_evidence_signer.py`：7 passed（确定性 Canonical JSON 序列化、流量记录证书签发与验签、Diff 报告证书签发与验签、一致性裁决证书签发与验签、篡改状态码哈希失配阻断、未找到证书判定、证书按类型分类检索流水）；
   - **通过率**：**7 passed in 0.31s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
