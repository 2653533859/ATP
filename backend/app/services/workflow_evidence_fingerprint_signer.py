"""工作流执行证据链 64 位 SHA-256 签名存证服务 (T4.2)

为多协议多端混合工作流全链路执行结果提供金融合规级防篡改存证:
1. 规范化节点轨迹提取与确定性 Canonical JSON 序列化;
2. 64 字符十六进制 SHA-256 哈希存证与 HMAC-SHA256 防伪签名;
3. 存证凭据证书生成 (WorkflowEvidenceCertificate);
4. 在线验签与微小数据篡改毫秒级探针拦截 (TAMPER_DETECTED)。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.hybrid_workflow_dag_engine import WorkflowExecutionReport


@dataclass
class WorkflowEvidenceCertificate:
    certificate_id: str
    workflow_id: str
    run_id: str
    signer: str
    algorithm: str  # SHA-256
    nodes_executed_count: int
    overall_status: str
    evidence_sha256: str
    hmac_signature: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "signer": self.signer,
            "algorithm": self.algorithm,
            "nodes_executed_count": self.nodes_executed_count,
            "overall_status": self.overall_status,
            "evidence_sha256": self.evidence_sha256,
            "hmac_signature": self.hmac_signature,
            "created_at": self.created_at,
        }


# 全局轻量级证书库
_CERTIFICATE_STORE: Dict[str, WorkflowEvidenceCertificate] = {}

# 平台默认 HMAC 签名密钥
_DEFAULT_WF_HMAC_SECRET = b"atp-workflow-evidence-hmac-audit-secret-2026"


def clear_workflow_certificates() -> None:
    _CERTIFICATE_STORE.clear()


def list_workflow_certificates(limit: int = 50) -> List[Dict[str, Any]]:
    return [c.to_dict() for c in reversed(list(_CERTIFICATE_STORE.values())[-limit:])]


def get_workflow_certificate(run_id: str) -> Optional[WorkflowEvidenceCertificate]:
    return _CERTIFICATE_STORE.get(run_id)


def canonical_workflow_digest_bytes(
    workflow_id: str,
    run_id: str,
    status: str,
    node_records: List[Dict[str, Any]],
) -> bytes:
    """提取核心执行结果并生成规范化 JSON 紧凑字节"""
    compact_records = []
    for r in node_records:
        compact_records.append(
            {
                "node_id": str(r.get("node_id", "")),
                "status": str(r.get("status", "")),
                "duration_ms": float(r.get("duration_ms", 0.0)),
            }
        )
    compact_records.sort(key=lambda x: str(x["node_id"]))

    payload = {
        "workflow_id": workflow_id,
        "run_id": run_id,
        "status": status,
        "node_records": compact_records,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_workflow_evidence(
    report: WorkflowExecutionReport | Dict[str, Any],
    signer: str = "atp-workflow-auditor-v5.1",
    secret_key: bytes | None = None,
) -> WorkflowEvidenceCertificate:
    """为工作流执行报告生成规范化 SHA-256 存证证书"""
    secret = secret_key or _DEFAULT_WF_HMAC_SECRET

    if isinstance(report, WorkflowExecutionReport):
        wf_id = report.workflow_id
        run_id = report.run_id
        overall_status = report.status
        nodes_count = report.executed_nodes_count
        node_records = [r.to_dict() for r in report.node_records]
    else:
        wf_id = str(report.get("workflow_id", ""))
        run_id = str(report.get("run_id", ""))
        overall_status = str(report.get("status", ""))
        nodes_count = int(report.get("executed_nodes_count", 0))
        node_records = report.get("node_records", [])

    raw_bytes = canonical_workflow_digest_bytes(wf_id, run_id, overall_status, node_records)
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
    hmac_sig = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    cert_id = f"wfcert_{run_id[:16]}"
    cert = WorkflowEvidenceCertificate(
        certificate_id=cert_id,
        workflow_id=wf_id,
        run_id=run_id,
        signer=signer,
        algorithm="SHA-256",
        nodes_executed_count=nodes_count,
        overall_status=overall_status,
        evidence_sha256=sha256_hash,
        hmac_signature=hmac_sig,
    )
    _CERTIFICATE_STORE[run_id] = cert
    return cert


def verify_workflow_evidence(
    certificate: Dict[str, Any],
    report: WorkflowExecutionReport | Dict[str, Any],
    secret_key: bytes | None = None,
) -> tuple[bool, str]:
    """对工作流执行报告进行防篡改验签

    返回: (is_valid: bool, message: str)
    """
    secret = secret_key or _DEFAULT_WF_HMAC_SECRET

    if isinstance(report, WorkflowExecutionReport):
        wf_id = report.workflow_id
        run_id = report.run_id
        overall_status = report.status
        node_records = [r.to_dict() for r in report.node_records]
    else:
        wf_id = str(report.get("workflow_id", ""))
        run_id = str(report.get("run_id", ""))
        overall_status = str(report.get("status", ""))
        node_records = report.get("node_records", [])

    raw_bytes = canonical_workflow_digest_bytes(wf_id, run_id, overall_status, node_records)
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    computed_hmac = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    expected_sha256 = str(certificate.get("evidence_sha256", ""))
    expected_hmac = str(certificate.get("hmac_signature", ""))

    if computed_sha256 != expected_sha256:
        return False, f"TAMPERED_HASH_MISMATCH: 计算摘要 [{computed_sha256}] 与证书签名 [{expected_sha256}] 不符"

    if computed_hmac != expected_hmac:
        return False, "TAMPERED_HMAC_MISMATCH: HMAC 防伪签名校验失败"

    return True, "EVIDENCE_VERIFIED: 工作流执行凭据与 64 位 SHA-256 存证证书完全吻合，未检测到任何数据篡改"
