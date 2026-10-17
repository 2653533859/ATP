"""AI 生成与自主探索证据 64 位 SHA-256 存证签名服务 (T4.2)

为 AI 意图驱动生成的工作流拓扑与多模态 VLM 自主探索交互轨迹提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, stripped spaces);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防篡改数字签名 (HMAC-SHA256 Signer);
4. 存证证书签发与在线合规验签 (EvidenceCertificate & Tamper Detection: VALID | TAMPERED_INVALID)。
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.intent_workflow_synthesizer import SynthesizedWorkflowDAG
from app.services.vlm_autonomous_explorer import ExplorationSession


class ArtifactType(str, enum.Enum):
    INTENT_WORKFLOW = "INTENT_WORKFLOW"  # 自然语言意图驱动生成的工作流
    EXPLORATION_TRAJECTORY = "EXPLORATION_TRAJECTORY"  # 多模态自主探索轨迹


class VerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签通过，数据完整未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class EvidenceCertificate:
    certificate_id: str
    artifact_type: ArtifactType
    artifact_id: str
    signer_identity: str
    algorithm: str  # SHA-256 + HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_CERTIFICATE_STORE: Dict[str, EvidenceCertificate] = {}
_DEFAULT_EVIDENCE_SECRET = b"atp-v5-2-0-ai-intent-evidence-hmac-secret-2026"


def clear_evidence_certificates() -> None:
    """清空存证证书内存库（测试使用）"""
    _CERTIFICATE_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（排序键、无多余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算 64 字符标准十六进制 SHA-256 存证指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def sign_sha256_hash(sha256_hash: str, secret: bytes = _DEFAULT_EVIDENCE_SECRET) -> str:
    """对 64 位 SHA-256 哈希计算 HMAC-SHA256 防伪数字签名"""
    return hmac.new(secret, sha256_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_intent_workflow_evidence(
    workflow_dag: SynthesizedWorkflowDAG,
    signer_identity: str = "ATP_AI_INTENT_AUTHORITY_V5_2",
) -> EvidenceCertificate:
    """为自然语言意图驱动生成的工作流拓扑生成不可篡改存证证书"""
    cid = f"cert_aiwf_{uuid.uuid4().hex[:12]}"

    # 构建确定性规范载荷
    nodes_summary = [
        {
            "node_id": n.node_id,
            "node_type": n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type),
            "node_name": n.node_name,
        }
        for n in sorted(workflow_dag.nodes, key=lambda x: x.node_id)
    ]
    edges_summary = [
        {"edge_id": e.edge_id, "source": e.source_node_id, "target": e.target_node_id}
        for e in sorted(workflow_dag.edges, key=lambda x: x.edge_id)
    ]

    canonical_data = {
        "artifact_id": workflow_dag.synthesis_id,
        "artifact_type": ArtifactType.INTENT_WORKFLOW.value,
        "raw_prompt": workflow_dag.slots.raw_prompt,
        "business_domain": workflow_dag.slots.business_domain,
        "nodes": nodes_summary,
        "edges": edges_summary,
        "variable_bindings": dict(sorted(workflow_dag.variable_bindings.items())),
        "workflow_name": workflow_dag.workflow_name,
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = EvidenceCertificate(
        certificate_id=cid,
        artifact_type=ArtifactType.INTENT_WORKFLOW,
        artifact_id=workflow_dag.synthesis_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "workflow_name": workflow_dag.workflow_name,
            "nodes_count": len(workflow_dag.nodes),
            "edges_count": len(workflow_dag.edges),
            "domain": workflow_dag.slots.business_domain,
            "raw_prompt": workflow_dag.slots.raw_prompt,
        },
    )

    _CERTIFICATE_STORE[cid] = cert
    return cert


def sign_exploration_trajectory_evidence(
    session: ExplorationSession,
    signer_identity: str = "ATP_VLM_EXPLORER_AUTHORITY_V5_2",
) -> EvidenceCertificate:
    """为多模态 VLM 自主探索交互轨迹生成不可篡改存证证书"""
    cid = f"cert_exptr_{uuid.uuid4().hex[:12]}"

    transitions_summary = [
        {
            "transition_id": t.transition_id,
            "from_state": t.from_state_id,
            "to_state": t.to_state_id,
            "action": t.action_type.value,
            "target": t.target_element_label,
        }
        for t in sorted(session.transitions, key=lambda x: x.transition_id)
    ]

    states_summary = [
        {"state_id": s.state_id, "screen_name": s.screen_name, "signature": s.ui_signature}
        for s in sorted(session.states.values(), key=lambda x: x.state_id)
    ]

    canonical_data = {
        "artifact_id": session.session_id,
        "artifact_type": ArtifactType.EXPLORATION_TRAJECTORY.value,
        "goal": session.goal,
        "platform": session.platform,
        "device_id": session.device_id,
        "status": session.status,
        "step_count": session.step_count,
        "states": states_summary,
        "transitions": transitions_summary,
    }

    canon_str = canonicalize_payload(canonical_data)
    evidence_sha256 = compute_evidence_sha256(canon_str)
    signature = sign_sha256_hash(evidence_sha256)

    cert = EvidenceCertificate(
        certificate_id=cid,
        artifact_type=ArtifactType.EXPLORATION_TRAJECTORY,
        artifact_id=session.session_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=evidence_sha256,
        hmac_signature=signature,
        canonical_payload=canonical_data,
        summary={
            "session_id": session.session_id,
            "platform": session.platform,
            "goal": session.goal,
            "states_count": len(session.states),
            "transitions_count": len(session.transitions),
            "status": session.status,
        },
    )

    _CERTIFICATE_STORE[cid] = cert
    return cert


def verify_evidence_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_EVIDENCE_SECRET,
) -> Tuple[VerificationVerdict, str]:
    """在线核验证书数字签名与 64 位 SHA-256 指纹有效性

    Returns:
        (VerificationVerdict, reason_message)
    """
    cert = _CERTIFICATE_STORE.get(certificate_id)
    if not cert:
        return VerificationVerdict.CERTIFICATE_NOT_FOUND, f"存证证书 [{certificate_id}] 不存在"

    # 1. 重新从规范载荷计算 SHA-256
    recomputed_canon = canonicalize_payload(cert.canonical_payload)
    recomputed_sha256 = compute_evidence_sha256(recomputed_canon)

    if recomputed_sha256 != cert.evidence_sha256:
        return (
            VerificationVerdict.TAMPERED_INVALID,
            f"存证指纹不匹配: 记录值={cert.evidence_sha256}, 重算值={recomputed_sha256}",
        )

    # 2. 重新验证 HMAC-SHA256 签名
    expected_sig = sign_sha256_hash(recomputed_sha256, secret=secret)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            VerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 防伪签名校验失败，可能被外部伪造或私钥不匹配",
        )

    return VerificationVerdict.VALID, "存证证书签名完全合规，64 位 SHA-256 指纹未被任何篡改"


def get_evidence_certificate(certificate_id: str) -> Optional[EvidenceCertificate]:
    """查询单条存证证书"""
    return _CERTIFICATE_STORE.get(certificate_id)


def list_evidence_certificates(limit: int = 50) -> List[Dict[str, Any]]:
    """获取近期颁发的存证证书列表"""
    certs = list(_CERTIFICATE_STORE.values())
    certs.sort(key=lambda x: x.issued_at, reverse=True)
    return [c.to_dict() for c in certs[:limit]]
