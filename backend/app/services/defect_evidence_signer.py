"""缺陷归因结论与 SLA 履约 64 位 SHA-256 存证证书器服务 (T4.2)

为缺陷治理全流程产物（聚类去重、根因归因、双向同步审计、SLA 履约报告）提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证防伪指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (DefectEvidenceCertificate: VALID | TAMPERED_INVALID)。
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

from app.services.defect_bidirectional_sync_gateway import SyncExecutionResult
from app.services.defect_root_cause_router import AttributedResponsibility
from app.services.defect_similarity_deduplicator import ClusteredDefectGroup
from app.services.defect_sla_escalation_watchdog import DefectSLAEvaluationResult


class DefectArtifactType(str, enum.Enum):
    DEFECT_CLUSTER_GROUP = "DEFECT_CLUSTER_GROUP"  # 缺陷智能聚类去重结果
    ROOT_CAUSE_ATTRIBUTION = "ROOT_CAUSE_ATTRIBUTION"  # 故障责任微服务与团队归因
    SYNC_EXECUTION_AUDIT = "SYNC_EXECUTION_AUDIT"  # 跨平台工单双向状态同步审计
    SLA_COMPLIANCE_EVALUATION = "SLA_COMPLIANCE_EVALUATION"  # 缺陷解决 SLA 履约与升级结论


class DefectVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class DefectEvidenceCertificate:
    certificate_id: str
    artifact_type: DefectArtifactType
    artifact_id: str
    target_service: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_DEFECT_CERT_STORE: Dict[str, DefectEvidenceCertificate] = {}
_DEFAULT_DEFECT_SECRET = b"atp-v6-0-0-defect-intelligence-evidence-secret-2026"


def clear_defect_certificates() -> None:
    """清空存证证书内存库（测试隔离使用）"""
    _DEFECT_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算规范化 JSON 数据的 64 位 SHA-256 哈希指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(evidence_sha256: str, secret_key: bytes = _DEFAULT_DEFECT_SECRET) -> str:
    """对 SHA-256 哈希指纹生成平台权威防伪 HMAC 签名"""
    return hmac.new(secret_key, evidence_sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_defect_artifact(
    artifact_type: DefectArtifactType,
    artifact_id: str,
    target_service: str,
    payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP-DEFECT-INTELLIGENCE-AUTHORITY-v6.0.0",
    secret_key: bytes = _DEFAULT_DEFECT_SECRET,
) -> DefectEvidenceCertificate:
    """通用缺陷治理产物存证证书签发"""
    cert_id = f"cert_def_{uuid.uuid4().hex[:12]}"
    canonical_json = canonicalize_payload(payload)
    sha256_hash = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(sha256_hash, secret_key=secret_key)

    cert = DefectEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        target_service=target_service,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=signature,
        canonical_payload=payload,
        summary=summary,
    )
    _DEFECT_CERT_STORE[cert_id] = cert
    return cert


def sign_defect_cluster_group(cluster: ClusteredDefectGroup) -> DefectEvidenceCertificate:
    """为智能聚类主缺陷产物签发存证证书"""
    payload = cluster.to_dict()
    summary = {
        "cluster_id": cluster.cluster_id,
        "master_title": cluster.master_title,
        "total_failures_count": cluster.total_failures_count,
        "primary_fingerprint": cluster.primary_fingerprint,
        "target_service": cluster.target_service,
        "action": cluster.action.value,
    }
    return sign_defect_artifact(
        artifact_type=DefectArtifactType.DEFECT_CLUSTER_GROUP,
        artifact_id=cluster.cluster_id,
        target_service=cluster.target_service,
        payload=payload,
        summary=summary,
    )


def sign_root_cause_attribution(attribution: AttributedResponsibility) -> DefectEvidenceCertificate:
    """为微服务责任归因结论签发存证证书"""
    payload = attribution.to_dict()
    summary = {
        "attribution_id": attribution.attribution_id,
        "responsible_service": attribution.responsible_service,
        "responsible_team": attribution.responsible_team,
        "suggested_assignee": attribution.suggested_assignee,
        "root_cause_type": attribution.root_cause_type.value,
        "attribution_confidence_pct": attribution.attribution_confidence_pct,
    }
    return sign_defect_artifact(
        artifact_type=DefectArtifactType.ROOT_CAUSE_ATTRIBUTION,
        artifact_id=attribution.attribution_id,
        target_service=attribution.responsible_service,
        payload=payload,
        summary=summary,
    )


def sign_sync_execution_audit(sync_result: SyncExecutionResult) -> DefectEvidenceCertificate:
    """为跨平台工单双向同步流水签发存证证书"""
    payload = sync_result.to_dict()
    summary = {
        "sync_id": sync_result.sync_id,
        "defect_id": sync_result.defect_id,
        "platform": sync_result.platform.value,
        "action_taken": sync_result.action_taken.value,
        "external_ticket_key": sync_result.external_ticket_key,
    }
    return sign_defect_artifact(
        artifact_type=DefectArtifactType.SYNC_EXECUTION_AUDIT,
        artifact_id=sync_result.sync_id,
        target_service=sync_result.platform.value,
        payload=payload,
        summary=summary,
    )


def sign_sla_compliance_evaluation(evaluation: DefectSLAEvaluationResult) -> DefectEvidenceCertificate:
    """为缺陷解决 SLA 履约与升级结论签发存证证书"""
    payload = evaluation.to_dict()
    summary = {
        "tracking_id": evaluation.tracking_id,
        "defect_id": evaluation.defect_id,
        "severity": evaluation.severity.value,
        "compliance_status": evaluation.compliance_status.value,
        "escalation_action": evaluation.escalation_action.value,
        "is_release_blocked": evaluation.is_release_blocked,
    }
    return sign_defect_artifact(
        artifact_type=DefectArtifactType.SLA_COMPLIANCE_EVALUATION,
        artifact_id=evaluation.tracking_id,
        target_service=evaluation.defect_id,
        payload=payload,
        summary=summary,
    )


def verify_defect_certificate(
    certificate_id: str,
    secret_key: bytes = _DEFAULT_DEFECT_SECRET,
) -> Tuple[DefectVerificationVerdict, str]:
    """验证缺陷存证证书的 64 位 SHA-256 指纹完整性与 HMAC 数字签名真实性"""
    cert = _DEFECT_CERT_STORE.get(certificate_id)
    if not cert:
        return (
            DefectVerificationVerdict.CERTIFICATE_NOT_FOUND,
            f"存证证书库中未检索到证书 ID [{certificate_id}]",
        )

    # 1. 重新计算当前 payload 的确定性 SHA-256 指纹
    current_canonical = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(current_canonical)

    if recalculated_sha256 != cert.evidence_sha256:
        return (
            DefectVerificationVerdict.TAMPERED_INVALID,
            f"存证数据指纹不匹配: 原始 [{cert.evidence_sha256}] vs 当前计算 [{recalculated_sha256}]，数据已被篡改！",
        )

    # 2. 重新验证平台 HMAC-SHA256 签名真实性
    expected_sig = compute_hmac_signature(cert.evidence_sha256, secret_key=secret_key)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            DefectVerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 数字签名无效或由非可信私钥伪造，判定为非法证书！",
        )

    return (
        DefectVerificationVerdict.VALID,
        f"证书 [{certificate_id}] 验签成功：64 位 SHA-256 指纹与 HMAC 权威签名双重校验通过，缺陷治理数据真实未被篡改。",
    )


def get_defect_certificate(certificate_id: str) -> Optional[DefectEvidenceCertificate]:
    """获取指定存证证书"""
    return _DEFECT_CERT_STORE.get(certificate_id)


def list_defect_certificates(target_service: Optional[str] = None) -> List[DefectEvidenceCertificate]:
    """列出存证证书列表，支持按服务/目标过滤"""
    certs = list(_DEFECT_CERT_STORE.values())
    if target_service:
        return [c for c in certs if c.target_service == target_service]
    return sorted(certs, key=lambda c: c.issued_at, reverse=True)
