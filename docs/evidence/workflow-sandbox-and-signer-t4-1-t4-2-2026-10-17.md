# T4.1 ~ T4.2 工作流容灾沙箱看门狗与 64 位 SHA-256 签名存证验收 (2026-10-17)

## 概述与结论

T4.1（工作流执行死循环与超时熔断看门狗 `workflow_execution_sandbox_guard.py`）与 T4.2（工作流执行证据链 64 位 SHA-256 签名存证器 `workflow_evidence_fingerprint_signer.py`）已全量交付并完成验证，**为 ATP 混合工作流多端协同执行提供了工业级运行安全熔断与金融合规防篡改保障**：
1. **工作流沙箱与熔断看门狗 (`backend/app/services/workflow_execution_sandbox_guard.py`)**：
   - **死循环侦测与阻断 (`InfiniteLoopDetectedError`)**：实时统计单节点被访问与执行频次，当因业务条件配置错误形成死循环、访问频次超过上限（默认 50 次）时，毫秒级阻断并触发熔断；
   - **全链路超时看门狗 (`WorkflowTimeoutCircuitBreakError`)**：监控工作流自启动以来的累计耗时，超出阈值（默认 300 秒）强制熔断终止；
   - **连续失败快速熔断 (`ExcessiveFailuresCircuitBreakError`)**：连续多个节点报错时快速失败，防止无效重试耗尽 Worker 线程与真机资源；
   - **与拓扑引擎原生集成 (`hybrid_workflow_dag_engine.py`)**：节点调度前主动核验配额，节点执行后更新耗时与成功状态；
   - 告警审计日志留存 (`list_guard_violations`)。
2. **证据链 64 位 SHA-256 签名存证器 (`backend/app/services/workflow_evidence_fingerprint_signer.py`)**：
   - 严格遵循确定性 Canonical JSON 序列化，去除多端时钟漂移与字段顺序随机性；
   - 生成 64 字符十六进制 `evidence_sha256` 存证摘要与 HMAC-SHA256 防伪造签名证书 (`WorkflowEvidenceCertificate`)；
   - 在线验签核验：哪怕测试报告中某一个节点的执行耗时被篡改 1ms、状态由 FAILED 伪造为 SUCCESS，验签即时拦截并报警 `TAMPERED_HASH_MISMATCH`。
3. **REST API 扩展 (`backend/app/api/v1/hybrid_workflow_api.py`)**：
   - `POST /api/v1/workflow/evidence/sign`：为工作流运行生成 64 位 SHA-256 存证证书；
   - `POST /api/v1/workflow/evidence/verify`：验签工作流报告是否被篡改；
   - `GET /api/v1/workflow/evidence/{run_id}` / `GET /api/v1/workflow/evidences`：查询证书详情与全量列表；
   - `GET /api/v1/workflow/guard/violations`：查询看门狗沙箱熔断告警记录。

## 质量与测试门禁验证

1. **服务与 API 单元测试**：
   - `backend/tests/services/test_workflow_execution_sandbox_guard.py`：3 passed；
   - `backend/tests/services/test_workflow_evidence_fingerprint_signer.py`：1 passed；
   - `backend/tests/api/test_hybrid_workflow_api.py`：2 passed；
   - 总体通过率：**13 passed across all Phase 4 & workflow tests (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：8/8 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed!**；
   - `ruff format --check`：**All files already formatted.**；
   - `mypy`：**Success: no issues found in 6 source files.**。
