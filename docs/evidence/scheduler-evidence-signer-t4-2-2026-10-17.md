# T4.2 调度决策 64 位 SHA-256 存证证书器服务验收 (2026-10-17)

## 概述与交付物

T4.2（调度决策 64 位 SHA-256 存证证书器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v5.4.0 Phase 4 核心合规存证里程碑**：
1. **密码学存证签名引擎 (`backend/app/services/scheduler_evidence_signer.py`)**：
   - **确定性 Canonical JSON 规范化**：提供严格字典键排序、剔除冗余空格与无损编码的标准序列化算法；
   - **64 字符 SHA-256 指纹**：提取任务调度决策记录（`RoutingDecisionResult`，包含任务规格、候选打分矩阵、命中真机 ID 与决策依据）或集群全局容量快照（`CapacitySummary`），计算 64 位十六进制 SHA-256 摘要；
   - **HMAC-SHA256 平台防伪数字签名**：使用平台内置私钥对 64 位 SHA-256 摘要加签；
   - **双产物存证签发**：
     - `sign_routing_decision_evidence()`：为真机调度派发决策签发证书 (`cert_route_...`)；
     - `sign_capacity_snapshot_evidence()`：为集群容量与算力水位快照签发证书 (`cert_capsnap_...`)；
   - **在线验签与防篡改探针 (`verify_scheduler_certificate`)**：
     - 重算 SHA-256 指纹与 HMAC 签名；
     - 任何对业务字段（如选中的设备 ID、适应度得分）或签名本身的篡改，均毫秒级返回 `TAMPERED_INVALID` 探针拦截；
     - 未被篡改则返回 `VALID`。
2. **REST API 端点集成 (`backend/app/api/v1/fleet_scheduler_api.py`)**：
   - `POST /api/v1/scheduler/evidence/sign`：为调度决策或容量快照在线签发存证证书；
   - `POST /api/v1/scheduler/evidence/verify`：在线核验证书真实性与未篡改性；
   - `GET /api/v1/scheduler/evidence/{certificate_id}`：单张证书详情查询；
   - `GET /api/v1/scheduler/evidence/list`：证书历史列表查询。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_scheduler_evidence_signer.py`：5 passed（调度决策存证合规、容量快照存证合规、载荷篡改阻断、签名篡改阻断、证书未找到）；
   - `backend/tests/api/test_fleet_scheduler_api.py`：7 passed；
   - 总体通过率：**34 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：8/8 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
