# T4.2 增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器服务验收 (2026-10-17)

## 概述与交付物

T4.2（增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.7.0 Phase 4 第二个核心密码学防伪合规存证里程碑**：
1. **密码学存证证书签名引擎 (`backend/app/services/precision_evidence_signer.py`)**：
   - **确定性规范化 JSON 序列化 (`canonicalize_payload`)**：对产物键名严格字典排序并剥离无序空格；
   - **64 位 SHA-256 证据指纹生成 (`compute_evidence_sha256`)**：为增量筛选决策、拓扑图谱与波次执行计划生成不可篡改哈希摘要；
   - **平台权威 HMAC-SHA256 数字签名 (`sign_payload_hmac`)**：使用平台根密钥签发防伪签名，防范离线篡改；
   - **三类产物证书签发**：
     - `sign_precision_recommendation_certificate`：增量精准用例推荐结果（`PRECISION_RECOMMENDATION`）；
     - `sign_dag_topology_certificate`：用例依赖 DAG 拓扑图谱（`DAG_TOPOLOGY`）；
     - `sign_wave_plan_certificate`：并发执行波次调度计划（`WAVE_EXECUTION_PLAN`）；
   - **在线探针验签与防篡改裁决 (`verify_precision_certificate`)**：重算哈希并比对 HMAC，输出 `VALID`（通过）、`TAMPERED_INVALID`（篡改告警）或 `CERTIFICATE_NOT_FOUND`。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_precision_evidence_signer.py`：7 passed（确定性 Canonical JSON 序列化、精准推荐证书签发与验签、DAG 拓扑证书签发与验签、波次调度计划证书签发与验签、篡改载荷哈希失配阻断、未找到证书判定、证书按类型分类检索流水）；
   - **通过率**：**7 passed in 0.33s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
